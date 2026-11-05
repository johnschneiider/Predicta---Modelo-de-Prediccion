# -*- coding: utf-8 -*-
"""Recolector (solo datos) de totales de Pinnacle (The Odds API) para el
paperbet de baloncesto NBA — pregame y descanso 2Q→3Q.

No toma decisiones de apuesta: únicamente guarda snapshots en PinnacleSnapshot
para compararlos después (columnas "P. PRE" / "P. 2Q→3Q" en la página
/auto-betting/paperbet/baloncesto/). Todo en try/except: jamás interrumpe el
flujo de apuestas y no toca ningún otro motor/paperbet.

- Pregame: 1 llamada liga-wide (1 crédito) guarda el total de TODOS los
  partidos de la jornada próxima, para basketball_nba y basketball_nba_preseason.
- 2Q→3Q: cuando la pasada del bot (cada 2 min) detecta partidos en ventana,
  1 llamada liga-wide extrae el total live de Pinnacle de esos partidos.

Guardas:
  * BASKET_PINNACLE_DISABLED=1 desactiva la recolección.
  * BASKET_PINNACLE_MIN_CREDITOS (default 30): si los créditos restantes de la
    última llamada quedan por debajo, no se vuelve a llamar.
  * Topes: pregame max 6 llamadas/día/liga y throttle de 60 min; break con
    backoff de 10 min tras una llamada fallida.
"""
import logging
import os
import re
import unicodedata
from datetime import timedelta

import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .models import PinnacleCallLog, PinnacleSnapshot

logger = logging.getLogger(__name__)

SPORT_KEYS = ('basketball_nba', 'basketball_nba_preseason')
API_BASE = 'https://api.the-odds-api.com/v4'
TIMEOUT = 20
HORAS_JORNADA = 14          # "hoy" = jornada próxima dentro de 14 h
PREGAME_ANTES_MIN = 90      # recolectar cuando el 1er partido está a <= 90 min
PREGAME_REFRESCO_H = 6      # refrescar eventos cuyo dato supera 6 h
PREGAME_THROTTLE_MIN = 60   # máximo 1 llamada pregame/hora por liga
PREGAME_MAX_DIA = 6         # tope de llamadas pregame por día y liga
BREAK_BACKOFF_MIN = 10      # tras una llamada fallida, esperar antes de repetir

# Variantes frecuentes Kambi/BetPlay -> nombre habitual en The Odds API.
_ALIAS = {
    'la clippers': 'los angeles clippers',
    'ny knicks': 'new york knicks',
    'no pelicans': 'new orleans pelicans',
    'gs warriors': 'golden state warriors',
    'sa spurs': 'san antonio spurs',
}


def habilitado():
    return os.environ.get('BASKET_PINNACLE_DISABLED', '').lower() not in ('1', 'true', 'yes')


def min_creditos():
    try:
        return int(os.environ.get('BASKET_PINNACLE_MIN_CREDITOS', '30'))
    except (TypeError, ValueError):
        return 30


def _api_key():
    return getattr(settings, 'ODDS_API_KEY', '') or ''


# --------------------------------------------------------------------------- #
#  Nombres entre ecosistemas (Kambi/BetPlay ↔ The Odds API)                    #
# --------------------------------------------------------------------------- #
def _norm(nombre):
    s = unicodedata.normalize('NFKD', nombre or '').encode('ascii', 'ignore').decode().lower()
    s = re.sub(r'[^a-z0-9 ]', ' ', s)
    s = ' '.join(s.split())
    s = _ALIAS.get(s, s)
    return {t for t in s.split() if t not in {'fc', 'bc', 'club', 'the', 'de'}}


def _sim(a, b):
    """Similitud por tokens (intersección / menor longitud). 1.0 = contención."""
    A, B = _norm(a), _norm(b)
    if not A or not B:
        return 0.0
    return len(A & B) / min(len(A), len(B))


def _parse_dt(txt):
    return parse_datetime((txt or '').replace('Z', '+00:00'))


def _match_kambi(ev_api, partidos):
    """Empareja un evento The Odds API con un PartidoLive de Kambi por nombres
    + hora (±4 h). Ambos ecosistemas usan nombres en inglés; se toleran
    variantes (p. ej. 'LA Clippers' ↔ 'Los Angeles Clippers')."""
    mejor, score = None, 0.0
    t_api = _parse_dt(ev_api.get('commence_time'))
    for p in partidos:
        s = min(_sim(ev_api.get('home_team', ''), p.local),
                _sim(ev_api.get('away_team', ''), p.visitante))
        if s < 0.5:
            continue
        t_p = _parse_dt(p.inicio)
        if t_api and t_p and abs((t_api - t_p).total_seconds()) > 4 * 3600:
            continue
        if s > score:
            mejor, score = p, s
    return mejor


# --------------------------------------------------------------------------- #
#  HTTP                                                                        #
# --------------------------------------------------------------------------- #
def _get(path, params):
    params = dict(params)
    params['api_key'] = _api_key()
    r = requests.get(f'{API_BASE}/{path}', params=params, timeout=TIMEOUT)
    remaining = r.headers.get('x-requests-remaining')
    cost = r.headers.get('x-requests-last')
    r.raise_for_status()
    return (r.json(),
            int(remaining) if remaining is not None else None,
            int(cost) if cost is not None else None)


def _fetch_events(sport_key):
    """Eventos de la liga (endpoint gratuito: no consume créditos)."""
    return _get(f'sports/{sport_key}/events', {})[0]


def _fetch_totals(sport_key):
    """1 crédito: totales de Pinnacle de TODA la liga (próximos + en vivo)."""
    return _get(f'sports/{sport_key}/odds',
                {'bookmakers': 'pinnacle', 'markets': 'totals',
                 'oddsFormat': 'decimal'})


def _totales_de(ev):
    """(línea, cuota_over, cuota_under, last_update) del mercado totals de
    Pinnacle en un evento, o None si no está disponible."""
    for b in ev.get('bookmakers') or []:
        if b.get('key') != 'pinnacle':
            continue
        for m in b.get('markets') or []:
            if m.get('key') != 'totals':
                continue
            over = next((o for o in m.get('outcomes', []) if o.get('name') == 'Over'), None)
            under = next((o for o in m.get('outcomes', []) if o.get('name') == 'Under'), None)
            if over and under:
                return (over.get('point'), over.get('price'), under.get('price'),
                        b.get('last_update') or m.get('last_update'))
    return None


# --------------------------------------------------------------------------- #
#  Guardas de créditos / registro                                              #
# --------------------------------------------------------------------------- #
def _creditos_ok():
    ult = PinnacleCallLog.objects.order_by('-capturado_en').first()
    if ult and ult.creditos_restantes is not None and ult.creditos_restantes < min_creditos():
        return False
    return True


def _log(sport_key, tipo, ok, eventos, remaining, detalle=''):
    try:
        PinnacleCallLog.objects.create(
            capturado_en=timezone.now(),
            sport_key=sport_key, tipo=tipo, ok=ok, eventos=eventos,
            creditos_restantes=remaining, detalle=(detalle or '')[:200])
    except Exception:  # noqa: BLE001
        logger.exception('basket_pinnacle: no se pudo registrar la llamada')


def _guardar(tipo, sport_key, evs, partidos, ahora):
    """Guarda/actualiza una fila por evento (una por tipo). Devuelve cuántas."""
    n = 0
    for ev in evs:
        tot = _totales_de(ev)
        if not tot:
            continue
        punto, over, under, last = tot
        p = _match_kambi(ev, partidos)
        defaults = dict(
            sport_key=sport_key,
            kambi_event_id=str(p.evento_id) if p else '',
            home_team=ev.get('home_team', ''),
            away_team=ev.get('away_team', ''),
            liga=(p.liga_nombre if p and p.liga_nombre else ev.get('sport_title', '')),
            commence_time=_parse_dt(ev.get('commence_time')),
            capturado_en=ahora,
            linea=punto,
            cuota_over=over,
            cuota_under=under,
            market_last_update=_parse_dt(last),
        )
        PinnacleSnapshot.objects.update_or_create(
            api_event_id=ev.get('id', ''), tipo=tipo, defaults=defaults)
        n += 1
    return n


def _en_jornada(ev, ahora):
    t = _parse_dt(ev.get('commence_time'))
    return t is not None and ahora <= t <= ahora + timedelta(hours=HORAS_JORNADA)


# --------------------------------------------------------------------------- #
#  Recolección                                                                 #
# --------------------------------------------------------------------------- #
def recolectar_pregame(partidos, log=None, ahora=None):
    """Antes de la jornada: guarda el total pregame de TODOS los partidos de
    hoy (hasta 14 h vista). Devuelve el número de llamadas hechas."""
    if not habilitado() or not _api_key() or not _creditos_ok():
        return 0
    ahora = ahora or timezone.now()
    llamadas = 0
    for key in SPORT_KEYS:
        try:
            evs = _fetch_events(key)
        except Exception as exc:  # noqa: BLE001
            _log(key, 'pregame', False, 0, None, f'events: {exc}')
            continue
        jornada = [e for e in evs if _en_jornada(e, ahora)]
        if not jornada:
            continue
        primera = min(_parse_dt(e['commence_time']) for e in jornada)
        if ahora < primera - timedelta(minutes=PREGAME_ANTES_MIN):
            continue
        ult = (PinnacleCallLog.objects
               .filter(sport_key=key, tipo='pregame')
               .order_by('-capturado_en').first())
        if ult and (ahora - ult.capturado_en) < timedelta(minutes=PREGAME_THROTTLE_MIN):
            continue
        hoy_n = PinnacleCallLog.objects.filter(
            sport_key=key, tipo='pregame',
            capturado_en__date=ahora.date()).count()
        if hoy_n >= PREGAME_MAX_DIA:
            continue
        ids = [e['id'] for e in jornada]
        frescos = set(PinnacleSnapshot.objects.filter(
            tipo='pregame', api_event_id__in=ids,
            capturado_en__gte=ahora - timedelta(hours=PREGAME_REFRESCO_H),
        ).values_list('api_event_id', flat=True))
        if len(frescos) >= len(ids):
            continue
        try:
            data, remaining, cost = _fetch_totals(key)
        except Exception as exc:  # noqa: BLE001
            _log(key, 'pregame', False, 0, None, f'odds: {exc}')
            continue
        n = _guardar('pregame', key, [e for e in data if _en_jornada(e, ahora)],
                     partidos, ahora)
        _log(key, 'pregame', True, n, remaining, f'cost={cost}')
        if log:
            log.write(f'  · Pinnacle pregame {key}: {n} partidos '
                      f'(créditos restantes {remaining})')
        llamadas += 1
    return llamadas


def recolectar_break(en_ventana, partidos, log=None, ahora=None):
    """En el descanso 2Q→3Q: extrae el total live de Pinnacle de los partidos
    en ventana (universo completo: tenga o no modelo/apuesta)."""
    if not habilitado() or not _api_key() or not _creditos_ok() or not en_ventana:
        return 0
    ahora = ahora or timezone.now()
    llamadas = 0
    for key in SPORT_KEYS:
        try:
            evs = _fetch_events(key)
        except Exception as exc:  # noqa: BLE001
            _log(key, 'break', False, 0, None, f'events: {exc}')
            continue
        pares = []
        for e in evs:
            p = _match_kambi(e, en_ventana)
            if p:
                pares.append((e, p))
        if not pares:
            continue
        faltan = [p for e, p in pares if not PinnacleSnapshot.objects.filter(
            tipo='break', kambi_event_id=str(p.evento_id)).exists()]
        if not faltan:
            continue
        ult = (PinnacleCallLog.objects
               .filter(sport_key=key, tipo='break')
               .order_by('-capturado_en').first())
        if ult and not ult.ok and (ahora - ult.capturado_en) < timedelta(minutes=BREAK_BACKOFF_MIN):
            continue
        try:
            data, remaining, cost = _fetch_totals(key)
        except Exception as exc:  # noqa: BLE001
            _log(key, 'break', False, 0, None, f'odds: {exc}')
            continue
        ids = {e['id'] for e, p in pares}
        n = _guardar('break', key, [e for e in data if e.get('id') in ids],
                     partidos, ahora)
        # n=0 con partidos en ventana = Pinnacle aún sin dato → backoff de 10 min.
        _log(key, 'break', n > 0, n, remaining, f'cost={cost}')
        if log:
            log.write(f'  · Pinnacle 2Q→3Q {key}: {n} partidos en ventana '
                      f'(créditos restantes {remaining})')
        llamadas += 1
    return llamadas


def recolectar(partidos, en_ventana, log=None, dry=False):
    """Punto de entrada del bot: pregame + break. En dry-run no llama a la API.
    Nunca propaga errores al flujo de apuestas."""
    if dry:
        return 0, 0
    try:
        return (recolectar_pregame(partidos, log),
                recolectar_break(en_ventana, partidos, log))
    except Exception:  # noqa: BLE001
        logger.exception('basket_pinnacle: error en la recolección (se ignora)')
        return 0, 0


def rellenar_pinnacle(bet):
    """Copia a la apuesta (solo datos) el total pregame y el del descanso de
    Pinnacle, si existen. No altera ninguna decisión."""
    try:
        pre = (PinnacleSnapshot.objects
               .filter(tipo='pregame', kambi_event_id=bet.evento_id)
               .order_by('-capturado_en').first())
        brk = (PinnacleSnapshot.objects
               .filter(tipo='break', kambi_event_id=bet.evento_id)
               .order_by('-capturado_en').first())
        campos = []
        if pre and pre.linea is not None:
            bet.pin_pregame_linea = pre.linea
            campos.append('pin_pregame_linea')
        if brk and brk.linea is not None:
            bet.pin_break_linea = brk.linea
            bet.pin_break_at = brk.capturado_en
            campos += ['pin_break_linea', 'pin_break_at']
        if campos:
            bet.save(update_fields=campos)
    except Exception:  # noqa: BLE001
        logger.exception('basket_pinnacle: no se pudieron copiar los datos a la apuesta')
