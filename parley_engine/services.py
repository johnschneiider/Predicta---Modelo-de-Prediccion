# -*- coding: utf-8 -*-
"""Servicios del motor independiente de parleys reales.

Reglas:
- Pool: picks AutoBet OPEN del admin cuyos partidos se juegan en las
  próximas 24 h (por ``start_time``), solo lectura.
- Todas las combinaciones de 2..max_legs patas, una pata por evento.
- Filtro: EV = prod(p_rec * cuota_actual) >= ev_gate.
- Stake fijo COP; ledger interno propio; nada toca el motor real.
- Rate limit conservador con backoff y sin reintentos ciegos de colocación.
"""
import bisect
import fcntl
import json
import logging
import math
import os
import re
import time
import unicodedata
import uuid
from datetime import date, datetime, time as dtime, timedelta, timezone as dt_tz
from zoneinfo import ZoneInfo

import requests
from django.conf import settings
from django.db import connection, transaction
from django.db.models import Q, Sum
from django.utils import timezone

from auto_betting.models import AutoBet, AutoBetConfig
from auto_betting.services import AUTH_BASE, COMMON_PARAMS, OFFERING_BASE, UA, login

from .models import (
    ParleyCoupon, ParleyCouponLeg, ParleyEngineConfig, ParleyLedger, ParleyRun,
)

logger = logging.getLogger('parley_engine')
BOG = ZoneInfo('America/Bogota')

SQL_FIT = """
  SELECT predicta_prob, estado
  FROM auto_betting_autobet
  WHERE usuario_id = %s AND predicta_prob IS NOT NULL
    AND estado IN ('WIN','LOSE')
    AND creado < %s
  ORDER BY id
"""

SQL_POOL = """
  SELECT id, evento_id, mercado, seleccion, cuota, predicta_prob, liga,
         estado, home_team, away_team, start_time, edge, linea
  FROM auto_betting_autobet
  WHERE usuario_id = %s
    AND start_time > %s AND start_time <= %s
    AND estado = 'OPEN'
    AND cuota IS NOT NULL AND predicta_prob IS NOT NULL AND cuota > 0
  ORDER BY start_time, id
"""


# ─────────────────────────────────────────────────────────────────────────────
# Rate limit / HTTP
# ─────────────────────────────────────────────────────────────────────────────

class RateLimitError(Exception):
    """Se agotaron los reintentos por 429/5xx."""


class AmbiguousPlacement(Exception):
    """No sabemos si la colocación se ejecutó (timeout/5xx). No reintentar a ciegas.

    Lleva el ``requestId`` real usado en la colocación para dejar rastro y
    poder conciliar a mano desde el historial de BetPlay.
    """

    def __init__(self, message, request_id=''):
        super().__init__(message)
        self.request_id = request_id


def _retry_after_seconds(value):
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        pass
    try:
        from email.utils import parsedate_to_datetime
        dt = parsedate_to_datetime(value)
        if dt is None:
            return None
        return max(0.0, (dt - datetime.now(dt_tz.utc)).total_seconds())
    except Exception:
        return None


class RateLimitedClient:
    """Cliente HTTP secuencial con rate limit y backoff.

    - 429/503: respeta Retry-After o usa backoff exponencial.
    - GET/validate: reintenta 5xx/timeout.
    - POST de colocación: no reintenta a ciegas; lanza AmbiguousPlacement.
    """

    def __init__(self, requests_per_minute=30, max_backoff=300, timeout=20,
                 sleep_fn=time.sleep):
        self.min_interval = 60.0 / max(1, int(requests_per_minute))
        self.max_backoff = max(1, int(max_backoff))
        self.timeout = max(5, int(timeout))
        self.sleep_fn = sleep_fn
        self._last = 0.0
        self.events = []

    def _wait(self):
        elapsed = time.monotonic() - self._last
        wait = self.min_interval - elapsed
        if wait > 0:
            self.sleep_fn(wait)
        self._last = time.monotonic()

    def _backoff(self, attempt, retry_after=None):
        base = min(self.max_backoff, 2 ** max(1, attempt))
        delay = retry_after if retry_after is not None else base
        delay = min(max(delay, 1.0), self.max_backoff)
        self.events.append({'attempt': attempt, 'sleep': delay})
        logger.warning('Rate limit/backoff: esperando %.1fs (intento %s)', delay, attempt)
        self.sleep_fn(delay)

    def request(self, method, url, body=None, headers=None, params=None,
                idempotent=True, max_retries=5):
        h = {
            'User-Agent': UA,
            'Origin': 'https://betplay.com.co',
            'Referer': 'https://betplay.com.co/',
            'Accept': 'application/json',
        }
        if headers:
            h.update(headers)
        if body is not None:
            h['Content-Type'] = 'application/json'

        last_error = None
        for attempt in range(1, max_retries + 1):
            self._wait()
            try:
                r = requests.request(method, url, json=body, headers=h,
                                     params=params, timeout=self.timeout)
            except (requests.Timeout, requests.ConnectionError) as exc:
                last_error = exc
                if not idempotent:
                    raise AmbiguousPlacement(str(exc)) from exc
                if attempt >= max_retries:
                    break
                self._backoff(attempt)
                continue

            status = r.status_code
            try:
                data = r.json()
            except ValueError:
                data = {'_text': r.text[:500]}

            if status in (429, 503):
                retry_after = _retry_after_seconds(r.headers.get('Retry-After'))
                if attempt >= max_retries:
                    raise RateLimitError(f'HTTP {status} tras {max_retries} intentos')
                self._backoff(attempt, retry_after)
                continue

            if status >= 500:
                if not idempotent:
                    raise AmbiguousPlacement(f'HTTP {status}: {data}')
                if attempt >= max_retries:
                    break
                self._backoff(attempt)
                continue

            return status, data, r.headers

        raise RateLimitError(f'No se pudo completar {method} {url}: {last_error}')


# ─────────────────────────────────────────────────────────────────────────────
# Fit / pool / combinaciones
# ─────────────────────────────────────────────────────────────────────────────

def build_lookup(fit_rows, min_fit=50):
    """Bordes de deciles + winrate por decil -> p_rec(prob)."""
    n = len(fit_rows)
    if n < min_fit:
        return None, {'n_fit': n}
    data = sorted((p, 1 if e == 'WIN' else 0) for p, e in fit_rows)
    probs = [p for p, _ in data]
    edges = [probs[min(int(math.ceil(k * n / 10.0)), n) - 1] for k in range(1, 10)]
    buckets = [[0, 0] for _ in range(10)]
    for p, w in data:
        idx = min(bisect.bisect_left(edges, p), 9)
        buckets[idx][0] += 1
        buckets[idx][1] += w
    rates = [None if tot < 20 else (w / tot) for tot, w in buckets]
    gwr = sum(w for _, w in data) / n

    def p_rec(pr):
        idx = min(bisect.bisect_left(edges, pr), 9)
        r = rates[idx]
        return r if r is not None else gwr

    return p_rec, {'n_fit': n, 'edges': edges, 'rates': rates, 'gwr': gwr}


def fit_rows(usuario_id, cutoff_start):
    """Picks ya liquidados y creados antes del inicio de la ventana (sin lookahead)."""
    with connection.cursor() as c:
        c.execute(SQL_FIT, [usuario_id, cutoff_start])
        return c.fetchall()


def junk_phrases(config):
    return [ln.strip().lower() for ln in (config.junk_mercados or '').splitlines()
            if ln.strip()]


def pool_autobet(usuario_id, cutoff_start, cutoff_end, frases):
    """Picks OPEN cuyos partidos empiezan dentro de la ventana (próximas 24 h).

    Se filtra por ``start_time``, no por fecha de creación del pick: la ventana
    es de partidos que se juegan desde ahora hasta dentro de 24 h.

    Dedup por (evento, mercado, selección). Solo lectura de AutoBet (apuestas
    reales ya colocadas por Predicta).
    """
    with connection.cursor() as c:
        c.execute(SQL_POOL, [usuario_id, cutoff_start, cutoff_end])
        rows = c.fetchall()
    dedup = {}
    eventos = {}
    n_skip = 0
    for (bid, ev_id, mkt, sel, cuota, prob, liga, estado, home, away,
         start_time, edge, linea) in rows:
        mm = (mkt or '').lower()
        if any(f in mm for f in frases):
            n_skip += 1
            continue
        key = (ev_id, mkt, sel)
        if key in dedup:
            n_skip += 1
            continue
        dedup[key] = dict(
            id=bid, evento=ev_id, mercado=mkt, seleccion=sel,
            cuota=float(cuota), prob=float(prob), liga=liga or '',
            estado=estado, home=home, away=away, start_time=start_time,
            edge=edge, linea=linea)
        eventos.setdefault(ev_id or f'ev{bid}', []).append(key)
    return dedup, eventos, n_skip


def enum_parlays(groups, ev_gate, max_legs, min_legs=2):
    """Todas las combinaciones (una pata por evento) con EV >= gate.

    `groups` es lista de listas [(leg, q)]. Implementación exacta con cota
    superior de producto de las mejores q restantes.
    """
    n = len(groups)
    if n < min_legs:
        return
    top = [[1.0] * (max_legs + 1) for _ in range(n + 1)]
    for i in range(n - 1, -1, -1):
        for k in range(1, max_legs + 1):
            best = top[i + 1][k]
            for _, q in groups[i]:
                v = q * top[i + 1][k - 1]
                if v > best:
                    best = v
            top[i][k] = best

    def rec(i, count, prod, legs):
        # Emitir exactamente una vez por combinación: al final, al tope de
        # patas, o cuando ya no puede crecer y la combinación actual es válida.
        if i >= n or count >= max_legs:
            if count >= min_legs and prod >= ev_gate:
                yield list(legs)
            return
        rem = max_legs - count
        if prod * top[i][rem] < ev_gate:
            if count >= min_legs and prod >= ev_gate:
                yield list(legs)
            return
        # no elegir este evento
        yield from rec(i + 1, count, prod, legs)
        # elegir una pata de este evento
        for leg, q in groups[i]:
            nq = prod * q
            if nq >= ev_gate or nq * top[i + 1][rem - 1] >= ev_gate:
                legs.append(leg)
                yield from rec(i + 1, count + 1, nq, legs)
                legs.pop()

    yield from rec(0, 0, 1.0, [])


def make_key(legs):
    """Key idempotente por combinación de picks.

    No incluye el día: la misma combinación de apuestas AutoBet no puede
    volver a apostarse nunca, ni siquiera si el escaneo de 24 h la vuelve a
    ver en la corrida siguiente.
    """
    ids = sorted(int(l['id']) for l in legs)
    return '-'.join(str(i) for i in ids)


# ─────────────────────────────────────────────────────────────────────────────
# Guard de duplicados (motor vs. cualquier cupón ya existente del día)
# ─────────────────────────────────────────────────────────────────────────────

def _round_line(value):
    if value is None:
        return None
    try:
        return round(float(value), 3)
    except (TypeError, ValueError):
        return None


def _leg_label_sig(event_id, mercado, seleccion, linea):
    return (event_id, _norm(mercado), _norm(seleccion), _round_line(linea))


def coupon_signatures(usuario, since=None):
    """Firmas de los cupones de la cuenta (todas, o desde ``since``).

    Se escanean todas por defecto: con la ventana por ``start_time`` un pick
    pudo crearse hace días y su cupón manual también, así que un filtro por
    fecha dejaría pasar duplicados. Devuelve ``(outcome_sets, label_sets)``:
    - outcome_sets: frozenset de outcome IDs (firma fiable de BetPlay).
    - label_sets: fallback (evento, mercado, selección, línea) normalizado.

    Sirve para no volver a apostar una combinación que ya existe en la cuenta,
    la haya colocado el motor, Predicta o el propio usuario a mano.
    """
    qs = ParleyCouponLeg.objects.filter(coupon__usuario=usuario)
    if since is not None:
        since_date = since.astimezone(BOG).date()
        qs = qs.filter(Q(coupon__creado__gte=since)
                       | Q(coupon__placed_date__gte=since)
                       | Q(coupon__dia__gte=since_date))
    rows = qs.values_list('coupon_id', 'event_id', 'mercado', 'seleccion',
                          'linea', 'outcome_id')
    by_coupon = {}
    for cid, event_id, mercado, seleccion, linea, outcome_id in rows:
        by_coupon.setdefault(cid, []).append(
            (event_id, mercado, seleccion, linea, outcome_id))
    outcome_sets = set()
    label_sets = set()
    for legs in by_coupon.values():
        oids = frozenset(l[4] for l in legs if l[4])
        if oids and len(oids) == len(legs):
            outcome_sets.add(oids)
        if all(l[0] is not None for l in legs):
            label_sets.add(frozenset(
                _leg_label_sig(l[0], l[1], l[2], l[3]) for l in legs))
    return outcome_sets, label_sets


def _candidate_signatures(legs):
    oids = []
    labels = []
    for l in legs:
        o = l.get('current_offer') or {}
        oid = o.get('outcome_id')
        if oid:
            oids.append(oid)
        labels.append(_leg_label_sig(
            l.get('evento'),
            o.get('market_label') or l.get('mercado') or '',
            o.get('label') or l.get('seleccion') or '',
            o.get('line') if o.get('line') is not None else l.get('linea')))
    outcome_sig = frozenset(oids) if len(oids) == len(legs) else None
    return outcome_sig, frozenset(labels)


def is_duplicate_candidate(legs, signatures):
    """True si la combinación ya existe como cupón del día (cualquier origen)."""
    outcome_sets, label_sets = signatures
    outcome_sig, label_sig = _candidate_signatures(legs)
    if outcome_sig is not None and outcome_sig in outcome_sets:
        return True
    return label_sig in label_sets


# ─────────────────────────────────────────────────────────────────────────────
# Cuotas actuales y matching
# ─────────────────────────────────────────────────────────────────────────────

def _norm(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = s.lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    return re.sub(r'\s+', ' ', s).strip()


def fetch_event_offers(client, event_id):
    url = f'{OFFERING_BASE}/betoffer/event/{event_id}.json'
    params = {'channel_id': 1, 'client_id': 200, 'lang': 'es_CO',
              'market': 'CO', 'useCombined': 'true',
              'useCombinedLive': 'true'}
    status, data, _ = client.request('GET', url, params=params, idempotent=True)
    if status != 200 or not isinstance(data, dict):
        return []
    offers = []
    for bo in data.get('betOffers', []):
        crit = bo.get('criterion') or {}
        for o in bo.get('outcomes', []):
            if o.get('status') != 'OPEN':
                continue
            odds = o.get('odds', 0)
            if not odds:
                continue
            line = o.get('line')
            if line is not None:
                line = line / 1000.0
            offers.append({
                'market_label': crit.get('label') or '',
                'betoffer_id': bo.get('id'),
                'outcome_id': o.get('id'),
                'label': o.get('label') or '',
                'line': line,
                'odds': odds,
                'odds_decimal': odds / 1000.0,
                'status': o.get('status') or '',
                'type': o.get('type') or '',
                'criterion': crit,
                'betoffer_tags': bo.get('tags') or [],
                'display_order': o.get('displayOrder', 0),
                'cashout_status': o.get('cashOutStatus', ''),
                'event_id': event_id,
            })
    return offers


_MARKET_EXCLUDE = (
    ' 1 parte', ' 2 parte', ' 1ª parte', ' 2ª parte', ' cuarto',
    ' 3 way', ' asiatico', ' tarjetas', ' esquina por parte',
    ' a favor de', ' intervalo',
)


def _market_score(bet_market, offer_market):
    bm, om = _norm(bet_market), _norm(offer_market)
    if not bm or not om:
        return 0
    # variantes NBA
    if bm == 'handicap':
        if om == 'handicap':
            return 100
        if om.startswith('handicap de puntos') and not any(x in om for x in _MARKET_EXCLUDE):
            return 90
        return 0
    if bm.startswith('total de puntos'):
        if not om.startswith('total de puntos'):
            return 0
        if any(x in om for x in (' 1 parte', ' 2 parte', ' cuarto', ' de ')):
            return 0
        return 100 if om == bm else 85
    if bm == 'total de goles':
        if om == bm:
            return 100
        if om.startswith(bm) and ' de ' not in om:
            return 80
        return 0
    if bm == 'total de tiros de esquina':
        if om == bm:
            return 100
        return 0
    if bm.startswith('total de tiros'):
        if om == bm:
            return 100
        if bm in om or om in bm:
            return 80
        return 0
    if bm == 'ambos equipos marcaran':
        return 100 if om == bm else 0
    if bm == 'resultado final':
        return 100 if om == bm else 0
    if bm == 'ganador':
        return 100 if om == bm else 0
    # genérico: exacto > contiene
    if om == bm:
        return 100
    if bm in om or om in bm:
        return 50
    return 0


def _parse_selection(sel, linea=None):
    raw = str(sel or '').strip().lower()
    raw = unicodedata.normalize('NFKD', raw)
    raw = ''.join(ch for ch in raw if not unicodedata.combining(ch))
    raw = re.sub(r'\s+', ' ', raw).strip()
    line = linea
    m = re.match(r'^(over|mas de|under|menos de)\s+(-?\d+(?:[.,]\d+)?)$', raw)
    if m:
        return {'kind': 'ou',
                'side': 'over' if m.group(1) in ('over', 'mas de') else 'under',
                'line': float(m.group(2).replace(',', '.'))}
    m = re.match(r'^(.+?)\s+([+-]\d+(?:[.,]\d+)?)$', raw)
    if m:
        return {'kind': 'team_line', 'team': _norm(m.group(1)),
                'line': float(m.group(2).replace(',', '.'))}
    n = _norm(raw)
    return {'kind': 'label', 'label': n, 'line': line}


def _selection_match(sel, offer):
    parsed = _parse_selection(sel, None)
    ol = _norm(offer.get('label'))
    line = offer.get('line')
    if parsed['kind'] == 'ou':
        want = ('mas de', 'over') if parsed['side'] == 'over' else ('menos de', 'under')
        if ol not in want:
            return False
        return line is not None and abs(line - parsed['line']) < 1e-6
    if parsed['kind'] == 'team_line':
        if parsed['team'] not in ol:
            return False
        return line is not None and abs(line - parsed['line']) < 1e-6
    want = parsed['label']
    if ol != want:
        return False
    if parsed.get('line') is not None and line is not None:
        return abs(line - parsed['line']) < 1e-6
    return True


def resolve_current_pick(bet, offers):
    """Encuentra la cuota actual del pick en las ofertas del evento.

    Devuelve el offer+market o None si no se puede identificar sin ambigüedad.
    """
    if not offers:
        return None
    mercado = bet.get('mercado') if isinstance(bet, dict) else getattr(bet, 'mercado', '')
    seleccion = bet.get('seleccion') if isinstance(bet, dict) else getattr(bet, 'seleccion', '')
    scored = []
    for o in offers:
        ms = _market_score(mercado, o.get('market_label'))
        if ms <= 0:
            continue
        if not _selection_match(seleccion, o):
            continue
        scored.append((ms, o))
    if not scored:
        return None
    # Duplicados del mismo outcome (varios betOffers): quedarse con la mejor cuota.
    dedup = {}
    for ms, o in scored:
        oid = o.get('outcome_id')
        prev = dedup.get(oid)
        if prev is None or o.get('odds_decimal', 0) > prev[1].get('odds_decimal', 0):
            dedup[oid] = (ms, o)
    scored = list(dedup.values())
    scored.sort(key=lambda x: -x[0])
    if len(scored) > 1 and scored[0][0] == scored[1][0]:
        # ambigüedad real entre outcomes distintos: no adivinar
        return None
    ms, offer = scored[0]
    return {'market_label': offer['market_label'], 'offer': offer, 'score': ms}


def enrich_pool(dedup, eventos, client, offers_cache):
    """Resuelve cuota actual para cada pick. Devuelve grupos enriquecidos."""
    groups = []
    skipped = 0
    now = timezone.now()
    for ev in sorted(eventos):
        opts = []
        for key in eventos[ev]:
            leg = dedup[key]
            # Nunca formar parleys con eventos ya iniciados.
            if leg.get('start_time') and leg['start_time'] <= now:
                skipped += 1
                continue
            eid = leg['evento']
            if eid not in offers_cache:
                offers_cache[eid] = fetch_event_offers(client, eid)
            cur = resolve_current_pick(leg, offers_cache[eid])
            if not cur:
                skipped += 1
                continue
            leg = dict(leg)
            leg['current_offer'] = cur['offer']
            leg['cuota_actual'] = cur['offer']['odds_decimal']
            leg['market_label_actual'] = cur['market_label']
            opts.append(leg)
        if opts:
            groups.append(opts)
    return groups, skipped


# ─────────────────────────────────────────────────────────────────────────────
# Cupón multi-pata
# ─────────────────────────────────────────────────────────────────────────────

def _selected_outcome(leg):
    o = leg['current_offer']
    is_live = o.get('is_live')
    return {
        'id': o['outcome_id'], 'outcomeId': o['outcome_id'],
        'betofferId': o['betoffer_id'], 'eventId': leg['evento'],
        'approvedOdds': o['odds'],
        'betOfferTags': o.get('betoffer_tags', []),
        'criterion': o.get('criterion', {}),
        'eachWayApproved': True, 'fromBetBuilder': True, 'fromPrePack': False,
        'isLiveBetoffer': True if is_live is None else bool(is_live),
        'isPrematchBetoffer': True if is_live is None else not bool(is_live),
        'oddsApproved': True,
        'label': o['label'],
        'line': int(o['line'] * 1000) if o.get('line') is not None else None,
        'type': o['type'], 'status': o['status'], 'odds': o['odds'],
        'displayOrder': o.get('display_order', 0),
        'cashOutStatus': o.get('cashout_status', ''),
        'path': [],
    }


def build_coupon_body(legs, stake_cop, request_id=None):
    rows = []
    selected = []
    for i, leg in enumerate(legs):
        o = leg['current_offer']
        rows.append({'index': i, 'odds': o['odds'],
                     'outcomeId': o['outcome_id'], 'type': 'SIMPLE'})
        selected.append(_selected_outcome(leg))
    return {
        'couponRows': rows,
        'allowOddsChange': 'NO',
        'allowOddsChangeLive': 'NO',
        'allowOddsChangePreMatch': 'NO',
        'bets': [{'couponRowIndexes': list(range(len(legs))),
                  'eachWay': False, 'stake': int(stake_cop) * 1000}],
        'channel': 'WEB',
        'requestId': request_id or str(uuid.uuid4()),
        'trackingData': {
            'hasTeaser': False, 'isBetBuilderCombination': False,
            'isMultiBuilder': False, 'isPrePackCombination': False,
            'partnerSpecials': [], 'reward': {},
        },
        'selectedOutcomes': selected,
    }


def stable_request_id(key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f'predicta-parley:{key}'))


def validate_and_place(client, token, body):
    """Valida y coloca. Devuelve ``(ok, response, request_id)``.

    ``request_id`` es el requestId REAL de la colocación (no el de
    validación): se guarda en el cupón para poder conciliar si la respuesta
    se pierde. La colocación usa un requestId nuevo, igual que el flujo real
    probado.

    Si BetPlay responde SUCCESS pero sin ``coupon.couponRef`` no se puede
    confirmar el cupón: se lanza ``AmbiguousPlacement`` y NO se reintenta.
    """
    headers = {'Authorization': f'Bearer {token}'}
    status, val, _ = client.request(
        'POST', f'{AUTH_BASE}/coupon/validate.json?{COMMON_PARAMS}',
        body=body, headers=headers, idempotent=True)
    if status != 200 or not isinstance(val, dict) or val.get('status') != 'SUCCESS' \
            or not val.get('validSession'):
        return False, {'stage': 'validate', 'status': status, 'response': val}, ''
    place_body = dict(body)
    place_request_id = str(uuid.uuid4())
    place_body['requestId'] = place_request_id
    try:
        status, res, _ = client.request(
            'POST', f'{AUTH_BASE}/coupon.json?{COMMON_PARAMS}',
            body=place_body, headers=headers, idempotent=False)
    except AmbiguousPlacement as exc:
        exc.request_id = exc.request_id or place_request_id
        raise
    if status != 200 or not isinstance(res, dict) or res.get('status') != 'SUCCESS':
        return False, {'stage': 'place', 'status': status, 'response': res}, \
            place_request_id
    coupon = res.get('coupon')
    if not isinstance(coupon, dict) or not coupon.get('couponRef'):
        raise AmbiguousPlacement(
            f'Colocación SUCCESS sin couponRef: requestId={place_request_id}',
            request_id=place_request_id)
    return True, res, place_request_id


def _parse_iso(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(str(s).replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


# ─────────────────────────────────────────────────────────────────────────────
# Ledger
# ─────────────────────────────────────────────────────────────────────────────

def ledger_balance(usuario, config):
    total = (ParleyLedger.objects.filter(usuario=usuario)
             .aggregate(s=Sum('monto'))['s'] or 0.0)
    return float(config.capital_inicial) + float(total)


def record_ledger(usuario, tipo, monto, coupon=None, nota=''):
    with transaction.atomic():
        config = ParleyEngineConfig.objects.select_for_update().get(usuario=usuario)
        total = (ParleyLedger.objects.filter(usuario=usuario)
                 .aggregate(s=Sum('monto'))['s'] or 0.0)
        balance = float(config.capital_inicial) + float(total) + float(monto)
        return ParleyLedger.objects.create(
            usuario=usuario, coupon=coupon, tipo=tipo, monto=float(monto),
            balance_after=balance, nota=nota[:300])


def record_settlement_if_needed(coupon, payout):
    if coupon is None or not coupon.is_motor:
        return None
    if ParleyLedger.objects.filter(coupon=coupon, tipo='SETTLEMENT').exists():
        return None
    return record_ledger(coupon.usuario, 'SETTLEMENT', float(payout or 0.0),
                         coupon=coupon, nota=f'liquidación {coupon.status}')


# ─────────────────────────────────────────────────────────────────────────────
# Historial BetPlay (para panel y liquidación)
# ─────────────────────────────────────────────────────────────────────────────

def fetch_history(client, token, range_size=1000):
    to_date = (datetime.now(dt_tz.utc) + timedelta(days=1)).strftime(
        '%Y-%m-%dT%H:%M:%S') + '.999Z'
    url = (f'{AUTH_BASE}/coupon/history.json?lang=es_CO&market=CO'
           f'&client_id=200&channel_id=1&range_size={range_size}'
           f'&range_start=0&toDate={to_date}')
    status, data, _ = client.request(
        'GET', url, headers={'Authorization': f'Bearer {token}'}, idempotent=True)
    if status != 200 or not isinstance(data, dict):
        return []
    return data.get('historyCoupons', [])


def _coupon_legs(c):
    rows = c.get('couponRows') or []
    outs = c.get('outcomes') or []
    evs = c.get('events') or []
    n = max(len(rows), len(outs), len(evs), 1)
    outs_by_id = {o.get('outcomeId'): o for o in outs if o.get('outcomeId')}
    evs_by_id = {e.get('eventId'): e for e in evs if e.get('eventId')}
    bos_by_id = {}
    for b in (c.get('betOffers') or []):
        bid = b.get('betOfferId') or b.get('id')
        if bid:
            bos_by_id[bid] = b
    legs = []
    for i in range(n):
        row = rows[i] if i < len(rows) else {}
        out = outs_by_id.get(row.get('outcomeId'))
        if out is None and i < len(outs):
            out = outs[i]
        ev = evs_by_id.get((out or {}).get('eventId')) or (evs[i] if i < len(evs) else {})
        bo = bos_by_id.get((out or {}).get('betOfferId'))
        line = (out or {}).get('line')
        if line is not None:
            line = line / 1000.0
        odds = row.get('playedOdds') or (out or {}).get('odds') or 0
        groups = ev.get('eventGroups') or []
        league = groups[-1].get('name', '') if groups else ''
        crit = (bo or {}).get('criterion')
        market = crit.get('label', '') if isinstance(crit, dict) else (crit or '')
        legs.append({
            'position': i + 1,
            'event_id': (out or {}).get('eventId') or ev.get('eventId'),
            'home_team': ev.get('homeName', ''),
            'away_team': ev.get('awayName', ''),
            'liga': league,
            'sport': ev.get('sport', '') or '',
            'mercado': market,
            'seleccion': (out or {}).get('label', ''),
            'linea': line,
            'cuota_colocada': (odds / 1000.0) if odds else None,
            'outcome_id': (out or {}).get('outcomeId'),
            'betoffer_id': (out or {}).get('betOfferId'),
            'estado_final': row.get('status') or (out or {}).get('status') or '',
        })
    return legs


def _coupon_sport(legs):
    sports = {l.get('sport') for l in legs if l.get('sport')}
    if not sports:
        return ''
    if len(sports) == 1:
        return next(iter(sports))
    return 'MIXED'


def upsert_history_coupon(usuario, c):
    ref = c.get('couponRef')
    if not ref:
        return None
    legs = _coupon_legs(c)
    n_legs = len(legs)
    if n_legs <= 1:
        return None
    bet = (c.get('bets') or [{}])[0]
    status = bet.get('betStatus') or 'OPEN'
    stake = (bet.get('stake') or 0) / 1000.0
    payout = (bet.get('payout') or 0) / 1000.0
    potential = (bet.get('potentialPayout') or 0) / 1000.0
    played = (bet.get('playedOdds') or 0) / 1000.0
    placed = _parse_iso(c.get('placedDate'))
    existing = ParleyCoupon.objects.filter(coupon_ref=ref).first()
    if existing is not None and existing.usuario_id != usuario.id:
        # Un couponRef es global en Kambi. Si ya pertenece a otra cuenta, no
        # se reasigna (evita cruzar datos entre usuarios); se omite y alerta.
        logger.warning(
            'coupon_ref %s ya pertenece a %s; se omite para %s',
            ref, existing.usuario_id, usuario.id)
        return None
    is_motor = existing.is_motor if existing else False
    dia = existing.dia if existing and existing.dia else (
        placed.astimezone(BOG).date() if placed else None)
    defaults = {
        'usuario': usuario,
        'bet_ref': bet.get('betRef'),
        'dia': dia,
        'placed_date': placed,
        'stake': int(round(stake)),
        'payout': payout,
        'potential_payout': potential,
        'played_odds': played or None,
        'n_legs': n_legs,
        'status': status,
        'sport': _coupon_sport(legs),
        'legs': legs,
    }
    if existing is None:
        defaults.update({'is_motor': is_motor, 'key': None})
        coupon = ParleyCoupon.objects.create(coupon_ref=ref, **defaults)
    else:
        for k, v in defaults.items():
            setattr(existing, k, v)
        existing.save()
        coupon = existing
    # patas
    if existing is None or coupon.leg_rows.count() == 0:
        for l in legs:
            ParleyCouponLeg.objects.create(
                coupon=coupon, position=l['position'], event_id=l['event_id'],
                home_team=l['home_team'], away_team=l['away_team'],
                liga=l['liga'], sport=l['sport'], mercado=l['mercado'],
                seleccion=l['seleccion'], linea=l['linea'],
                cuota_colocada=l['cuota_colocada'], outcome_id=l['outcome_id'],
                betoffer_id=l['betoffer_id'], estado_final=l['estado_final'])
    else:
        for l in legs:
            updated = ParleyCouponLeg.objects.filter(
                coupon=coupon, position=l['position']).update(
                    cuota_colocada=l['cuota_colocada'],
                    estado_final=l['estado_final'],
                    linea=l['linea'], seleccion=l['seleccion'],
                    mercado=l['mercado'])
            if not updated:
                ParleyCouponLeg.objects.create(
                    coupon=coupon, position=l['position'],
                    event_id=l['event_id'], home_team=l['home_team'],
                    away_team=l['away_team'], liga=l['liga'],
                    sport=l['sport'], mercado=l['mercado'],
                    seleccion=l['seleccion'], linea=l['linea'],
                    cuota_colocada=l['cuota_colocada'],
                    outcome_id=l['outcome_id'],
                    betoffer_id=l['betoffer_id'],
                    estado_final=l['estado_final'])
        # Si el cupón perdió patas (cashout/void), no dejar filas viejas.
        coupon.leg_rows.filter(position__gt=n_legs).delete()
    if coupon.is_motor and coupon.status != 'OPEN':
        record_settlement_if_needed(coupon, coupon.payout)
    return coupon


def find_history_match(client, token, legs, stake, since):
    """Busca en el historial un cupón reciente con las mismas patas y stake.

    Solo considera cupones colocados desde ``since`` con el mismo número de
    patas, el mismo set de ``outcome_id`` y el mismo stake. Devuelve el cupón
    más reciente o ``None``. Es la base para reconciliar una colocación
    ambigua sin reintentar a ciegas.
    """
    want = frozenset(
        (l.get('current_offer') or {}).get('outcome_id') for l in legs)
    want.discard(None)
    if len(want) != len(legs):
        return None
    cups = fetch_history(client, token, range_size=200)
    matches = []
    for c in cups:
        placed = _parse_iso(c.get('placedDate'))
        if not placed or placed < since:
            continue
        cl = _coupon_legs(c)
        oids = frozenset(l['outcome_id'] for l in cl if l['outcome_id'])
        if len(cl) != len(legs) or oids != want:
            continue
        bet = (c.get('bets') or [{}])[0]
        if int(round((bet.get('stake') or 0) / 1000.0)) != int(stake):
            continue
        matches.append((placed, c))
    if not matches:
        return None
    matches.sort(key=lambda x: x[0])
    return matches[-1][1]


def reconcile_ambiguous_coupon(placeholder, history_coupon):
    """Enlaza un placeholder ambiguo con el cupón real del historial.

    Si el sync ya había creado una fila para ese ``couponRef``, se fusionan en
    una sola (la del motor). Registra PLACEMENT una única vez y liquida si el
    cupón ya viene resuelto. Devuelve el cupón final o ``None``.
    """
    ref = history_coupon.get('couponRef')
    if not ref:
        return None
    legs = _coupon_legs(history_coupon)
    if not legs:
        return None
    bet = (history_coupon.get('bets') or [{}])[0]
    status = bet.get('betStatus') or 'OPEN'
    stake = int(round((bet.get('stake') or 0) / 1000.0)) or placeholder.stake
    payout = (bet.get('payout') or 0) / 1000.0
    potential = (bet.get('potentialPayout') or 0) / 1000.0
    played = (bet.get('playedOdds') or 0) / 1000.0
    placed = _parse_iso(history_coupon.get('placedDate'))

    with transaction.atomic():
        other = (ParleyCoupon.objects.filter(coupon_ref=ref)
                 .exclude(pk=placeholder.pk).first())
        key = placeholder.key
        engine_run = placeholder.engine_run
        dia = placeholder.dia
        request_id = placeholder.request_id
        if other is not None:
            placeholder.delete()
            target = other
            target.key = key
        else:
            target = placeholder
        target.coupon_ref = ref
        target.bet_ref = bet.get('betRef')
        target.is_motor = True
        target.engine_run = engine_run
        target.dia = dia
        target.placed_date = placed
        target.stake = stake
        target.payout = payout
        target.potential_payout = potential
        target.played_odds = played or None
        target.n_legs = len(legs)
        target.status = status
        target.sport = _coupon_sport(legs)
        target.legs = legs
        target.request_id = request_id
        target.save()
        target.leg_rows.all().delete()
        for l in legs:
            ParleyCouponLeg.objects.create(
                coupon=target, position=l['position'],
                event_id=l['event_id'], home_team=l['home_team'],
                away_team=l['away_team'], liga=l['liga'], sport=l['sport'],
                mercado=l['mercado'], seleccion=l['seleccion'],
                linea=l['linea'], cuota_colocada=l['cuota_colocada'],
                outcome_id=l['outcome_id'], betoffer_id=l['betoffer_id'],
                estado_final=l['estado_final'])
        if not ParleyLedger.objects.filter(coupon=target,
                                           tipo='PLACEMENT').exists():
            record_ledger(target.usuario, 'PLACEMENT', -target.stake,
                          coupon=target, nota=f'reconciliado | {key}')
        if target.status != 'OPEN':
            record_settlement_if_needed(target, target.payout)
    return target


def sync_history(usuario, client, token, range_size=1000):
    cups = fetch_history(client, token, range_size=range_size)
    n = 0
    for c in cups:
        try:
            if upsert_history_coupon(usuario, c):
                n += 1
        except Exception as exc:
            logger.warning('sync parley %s falló: %s', c.get('couponRef'), exc)
    return n


LOCK_PATH = '/var/www/predicta.com.co/logs/real_parleys.lock'


def sync_user_history(usuario, range_size=1000):
    """Sincroniza y liquida el historial BetPlay de UN usuario.

    Devuelve {'ok': bool, 'updated': int, 'error': str}. No lanza excepciones:
    el panel necesita un mensaje claro. Usa el mismo lock que las corridas del
    motor para no pisar una colocación en curso.
    """
    config = ParleyEngineConfig.objects.filter(usuario=usuario).first()
    if config is None:
        return {'ok': False, 'updated': 0,
                'error': 'Tu usuario no tiene configuración de parleys.'}
    ac = AutoBetConfig.objects.filter(usuario=usuario).first()
    if not ac or not ac.ticket:
        return {'ok': False, 'updated': 0,
                'error': 'Sin credenciales de BetPlay configuradas.'}
    token, _ = login(ac.ticket, ac.punter_id)
    if not token:
        return {'ok': False, 'updated': 0,
                'error': 'Login BetPlay falló (ticket vencido o inválido).'}
    os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
    lock = open(LOCK_PATH, 'w')
    try:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        return {'ok': False, 'updated': 0,
                'error': 'Hay una corrida del motor en curso; intenta en un minuto.'}
    try:
        client = RateLimitedClient(
            requests_per_minute=(config.requests_per_minute if config else 30),
            max_backoff=(config.max_backoff_seconds if config else 300),
            timeout=(config.request_timeout if config else 20))
        n = sync_history(usuario, client, token, range_size=range_size)
    except Exception as exc:
        logger.exception('sync manual de parleys falló para %s', usuario)
        return {'ok': False, 'updated': 0,
                'error': f'{type(exc).__name__}: {exc}'}
    finally:
        lock.close()
    return {'ok': True, 'updated': n, 'error': ''}
