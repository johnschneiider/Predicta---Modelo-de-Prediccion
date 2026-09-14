"""
Cliente de la API de BetPlay (Kambi) para el auto-betting.
Login por ticket, obtención de cuotas, validación y colocación de apuestas.
"""

import json
import logging
import urllib.request
import urllib.error
import uuid

logger = logging.getLogger('auto_betting')

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/151.0.0.0 Safari/537.36"
OFFERING_BASE = "https://us.offering-api.kambicdn.com/offering/v2018/betplay"
AUTH_BASE = "https://cf-mt-auth-api.kambicdn.com/player/api/v2019/betplay"
COMMON_PARAMS = "lang=es_CO&market=CO&client_id=200&channel_id=1"


def _req(url, method="GET", body=None, extra_headers=None):
    """Hace una petición HTTP y devuelve (status_code, json_response)."""
    h = {
        "User-Agent": UA,
        "Origin": "https://betplay.com.co",
        "Referer": "https://betplay.com.co/",
    }
    if extra_headers:
        h.update(extra_headers)
    if body is not None:
        h["Content-Type"] = "application/json"

    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode())
        except Exception:
            return e.code, {"error": e.read().decode()[:200]}
    except Exception as e:
        return 0, {"error": str(e)}


# ════════════════════════════════════════════
#  AUTENTICACIÓN
# ════════════════════════════════════════════

# ════════════════════════════════════════════
#  CACHE DE TOKEN (evita logins excesivos)
# ════════════════════════════════════════════

_cached_token = None
_cached_routing_key = None
_cached_ticket = None
_cached_punter_id = None
_token_expires_at = 0  # epoch seconds


def login(ticket, punter_id="2585240"):
    """Login por ticket → devuelve (token, routing_key) o None.
    Usa cache: si hay un token válido (>5 min restantes) para el mismo ticket+punter_id,
    lo reutiliza sin llamar al API."""
    import time
    global _cached_token, _cached_routing_key, _cached_ticket, _cached_punter_id, _token_expires_at

    # Reutilizar token cacheado si es para la misma cuenta y no expira pronto
    if (_cached_token
            and _cached_ticket == ticket
            and _cached_punter_id == punter_id
            and time.time() < _token_expires_at - 300):  # >5 min de validez
        logger.info(f"Login BetPlay OK (cached) | token={_cached_token[:8]}...")
        return _cached_token, _cached_routing_key

    body = {
        "punterId": punter_id,
        "ticket": ticket,
        "customerSiteIdentifier": "",
        "channel": "WEB",
        "market": "CO",
        "requestStreaming": True,
    }
    status, data = _req(f"{AUTH_BASE}/punter/login?lang=es_CO&market=CO", "POST", body)
    if status == 200 and "token" in data:
        logger.info(f"Login BetPlay OK | token={data['token'][:8]}... | currency={data.get('currency')}")
        # Cache por 55 min (token dura 60 min, dejamos 5 min de margen)
        _cached_token = data["token"]
        _cached_routing_key = data.get("routingKey", "")
        _cached_ticket = ticket
        _cached_punter_id = punter_id
        _token_expires_at = time.time() + 3300  # 55 minutos
        return data["token"], data.get("routingKey", "")
    logger.error(f"Login BetPlay falló: {status} {data}")
    # Limpiar cache si el login falla
    _cached_token = None
    _cached_ticket = None
    _token_expires_at = 0
    return None, None


# ════════════════════════════════════════════
#  CUOTAS (OFFERING API — sin auth)
# ════════════════════════════════════════════

def _es_partido_no_valido(ev, path):
    """
    Devuelve True si el partido NO es fútbol real de primera división:
    eSports/virtual, ligas de reservas/juveniles, o femeniles.
    """
    import re
    group = (ev.get("group") or "").lower()
    home = (ev.get("homeName") or "").lower()
    away = (ev.get("awayName") or "").lower()
    league_name = (path[2].get("localizedName") or path[2].get("englishName") or "").lower() if len(path) > 2 else ""
    sport = (path[1].get("termKey") or "").lower() if len(path) > 1 else ""

    # 1) eSports / fútbol virtual
    if "esports" in (sport + group + league_name):
        return True
    if any(t in group for t in ("cyber", "battle", "arena", "virtual")):
        return True

    # 2) Reservas / juveniles (liga)
    if any(t in league_name for t in (
            "reserve", "reservas", "reserves",
            "u21", "u23", "u20", "u19", "u18", "u17", "u16",
            "sub-")):
        return True

    # 3) Femenil / femenino (liga)
    if any(t in league_name for t in ("femen", "women", "(w)", "(f)")):
        return True

    # 4) Equipos filiales / reservas en el nombre (sufijo B, II, 2, Sub-x, U2x)
    for nombre in (home, away):
        if re.search(r'\b(reservas|reserves)\b', nombre):
            return True
        if re.search(r'\s(b|ii|2)$', nombre.strip()):
            return True
        if re.search(r'\b(sub-?[0-9]+|u1[6-9]|u2[0-9])\b', nombre):
            return True

    return False


def fetch_upcoming_matches(hours_ahead=24):
    """
    Trae partidos de fútbol NOT_STARTED de Kambi (BetPlay).
    Devuelve lista de dicts: {event_id, home, away, league, league_path, start_time}
    """
    import requests
    from datetime import datetime, timezone, timedelta

    url = f"{OFFERING_BASE}/listView/football.json"
    params = {"channel_id": 1, "client_id": 200, "lang": "es_CO", "market": "CO",
              "useCombined": "true", "useCombinedLive": "true"}
    headers = {"Accept": "application/json", "Origin": "https://betplay.com.co", "Referer": "https://betplay.com.co/"}

    try:
        r = requests.get(url, params=params, timeout=20, headers=headers)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Error fetching matches: {e}")
        return []

    events = r.json().get("events", [])
    now = datetime.now(timezone.utc)
    limite = now + timedelta(hours=hours_ahead)
    matches = []
    for e in events:
        ev = e.get("event", {})
        if ev.get("state") != "NOT_STARTED":
            continue
        path = ev.get("path", [])
        if len(path) < 3:
            continue
        if _es_partido_no_valido(ev, path):
            continue
        try:
            start = datetime.fromisoformat(ev["start"].replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        if start < now or start > limite:
            continue

        league_path = "/".join(p.get("termKey", "") for p in path[:3])
        matches.append({
            "event_id": int(ev["id"]),
            "home": ev.get("homeName", ""),
            "away": ev.get("awayName", ""),
            "league": path[2].get("localizedName", path[2].get("englishName", "")),
            "league_path": league_path,
            "start_time": start,
        })
    logger.info(f"Partidos próximos {hours_ahead}h: {len(matches)}")
    return matches


def fetch_market_odds(event_id, market_label):
    """
    Trae las cuotas over/under de un mercado específico (por label exacto) de un evento.
    `market_label` también acepta una lista/tupla de labels (una sola llamada HTTP).
    Devuelve lista de dicts: {betoffer_id, outcome_id, label, odds, odds_decimal, line, type, status, ...}
    """
    import requests
    url = f"{OFFERING_BASE}/betoffer/event/{event_id}.json"
    params = {"channel_id": 1, "client_id": 200, "lang": "es_CO", "market": "CO",
              "useCombined": "true", "useCombinedLive": "true"}
    headers = {"Accept": "application/json", "Origin": "https://betplay.com.co", "Referer": "https://betplay.com.co/"}

    labels = tuple(market_label) if isinstance(market_label, (list, tuple, set)) else (market_label,)

    try:
        r = requests.get(url, params=params, timeout=20, headers=headers)
        r.raise_for_status()
    except Exception as e:
        logger.error(f"Error fetching odds for event {event_id}: {e}")
        return []

    offers = []
    for bo in r.json().get("betOffers", []):
        crit = bo.get("criterion", {})
        if crit.get("label") not in labels:
            continue
        for o in bo.get("outcomes", []):
            if o.get("status") != "OPEN":
                continue
            odds_raw = o.get("odds", 0)
            if odds_raw == 0:
                continue
            line = o.get("line")
            if line:
                line = line / 1000.0
            offers.append({
                "betoffer_id": bo["id"],
                "outcome_id": o["id"],
                "label": o.get("label", ""),
                "odds": odds_raw,
                "odds_decimal": odds_raw / 1000.0,
                "line": line,
                "type": o.get("type", ""),
                "status": o.get("status", ""),
                "cashout_status": o.get("cashOutStatus", ""),
                "display_order": o.get("displayOrder", 0),
                "criterion": crit,
                "betoffer_tags": bo.get("tags", []),
                "event_id": event_id,
            })
    return offers


def fetch_corners_odds(event_id):
    """Cuotas over/under de 'Total de Tiros de Esquina' (córners)."""
    return fetch_market_odds(event_id, "Total de Tiros de Esquina")


def fetch_shots_on_target_odds(event_id):
    """Cuotas over/under de 'Total de tiros a puerta' (remates a puerta, resuelto con Opta)."""
    # La etiqueta exacta en BetPlay incluye el sufijo de Opta. Probamos ambas.
    for label in ["Total de tiros a puerta (Resuelta usando Opta Data)", "Total de tiros a puerta"]:
        odds = fetch_market_odds(event_id, label)
        if odds:
            return odds
    return []


def fetch_goals_odds(event_id):
    """Cuotas over/under de 'Total de goles' (partido completo)."""
    return fetch_market_odds(event_id, "Total de goles")


def fetch_total_shots_odds(event_id):
    """Cuotas over/under de 'remates totales' (total de disparos, Opta).

    Label REAL de BetPlay (auditoría 2026-09-13, BUG A): 'Total de Tiros
    (Resuelta usando Opta Data)'. Variantes legacy incluidas por
    compatibilidad. UNA sola llamada HTTP para todos los labels
    (motor remates v2.3 — el mercado existe en ~3% de eventos; evitar
    5 llamadas por evento sin mercado).
    """
    return fetch_market_odds(event_id, [
        "Total de Tiros (Resuelta usando Opta Data)",
        "Número total de disparos (Resuelta usando Opta Data)",
        "Total de disparos (Resuelta usando Opta Data)",
        "Número total de tiros (Resuelta usando Opta Data)",
        "Total de tiros (Resuelta usando Opta Data)",
    ])


def fetch_x12_odds(event_id):
    """Cuotas 1X2 de 'Resultado Final'."""
    return fetch_market_odds(event_id, "Resultado Final")


def fetch_btts_odds(event_id):
    """Cuotas de 'Ambos Equipos Marcarán' (Sí/No)."""
    return fetch_market_odds(event_id, "Ambos Equipos Marcarán")


# ════════════════════════════════════════════
#  APOSTAR (AUTH API — requiere token)
# ════════════════════════════════════════════

def _build_coupon(outcome, event_data, stake=500000):
    """Construye el body del cupón para validar/colocar."""
    return {
        "couponRows": [
            {"index": 0, "odds": outcome["odds"], "outcomeId": outcome["outcome_id"], "type": "SIMPLE"}
        ],
        "allowOddsChange": "NO",
        "allowOddsChangeLive": "NO",
        "allowOddsChangePreMatch": "NO",
        "bets": [
            {"couponRowIndexes": [0], "eachWay": False, "stake": stake}
        ],
        "channel": "WEB",
        "requestId": str(uuid.uuid4()),
        "trackingData": {
            "hasTeaser": False, "isBetBuilderCombination": False,
            "isMultiBuilder": False, "isPrePackCombination": False,
            "partnerSpecials": [], "reward": {}
        },
        "selectedOutcomes": [
            {
                "id": outcome["outcome_id"],
                "outcomeId": outcome["outcome_id"],
                "betofferId": outcome["betoffer_id"],
                "eventId": event_data["event_id"],
                "approvedOdds": outcome["odds"],
                "betOfferTags": outcome.get("betoffer_tags", []),
                "criterion": outcome.get("criterion", {}),
                "eachWayApproved": True, "fromBetBuilder": True, "fromPrePack": False,
                "isLiveBetoffer": True, "isPrematchBetoffer": True, "oddsApproved": True,
                "label": outcome["label"], "line": int(outcome["line"] * 1000) if outcome.get("line") else None,
                "type": outcome["type"], "status": outcome["status"],
                "odds": outcome["odds"], "displayOrder": outcome.get("display_order", 0),
                "cashOutStatus": outcome.get("cashout_status", ""),
                "path": event_data.get("path", []),
            }
        ]
    }


def _auth_headers(token):
    return {"Authorization": f"Bearer {token}"}


def validate_coupon(token, outcome, event_data, stake=500000):
    """Valida un cupón. Devuelve (success, response)."""
    body = _build_coupon(outcome, event_data, stake)
    status, data = _req(
        f"{AUTH_BASE}/coupon/validate.json?{COMMON_PARAMS}",
        "POST", body, _auth_headers(token)
    )
    success = status == 200 and data.get("status") == "SUCCESS" and data.get("validSession", False)
    return success, data


def place_bet(token, outcome, event_data, stake=500000):
    """Coloca una apuesta. Devuelve (success, response)."""
    body = _build_coupon(outcome, event_data, stake)
    status, data = _req(
        f"{AUTH_BASE}/coupon.json?{COMMON_PARAMS}",
        "POST", body, _auth_headers(token)
    )
    if status == 200 and data.get("status") == "SUCCESS":
        coupon = data.get("coupon", {})
        return True, {
            "coupon_ref": coupon.get("couponRef"),
            "bet_ref": coupon.get("bets", [{}])[0].get("betRef") if coupon.get("bets") else None,
            "potential_payout": coupon.get("bets", [{}])[0].get("potentialPayout") if coupon.get("bets") else None,
            "played_odds": coupon.get("bets", [{}])[0].get("playedOdds") if coupon.get("bets") else None,
        }
    return False, data


# ════════════════════════════════════════════
#  HISTORIAL DE APUESTAS (tracking de resultados)
# ════════════════════════════════════════════

def fetch_bet_history(token, range_size=200):
    """
    Trae el historial completo de apuestas (coupons) de la cuenta.
    Devuelve lista de dicts con la estructura de `coupon/history.json`.
    """
    from datetime import datetime, timezone, timedelta
    to_date = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S") + ".999Z"
    url = (
        f"{AUTH_BASE}/coupon/history.json?lang=es_CO&market=CO&client_id=200&channel_id=1"
        f"&range_size={range_size}&range_start=0&toDate={to_date}"
    )
    status, data = _req(url, "GET", None, _auth_headers(token))
    if status != 200:
        logger.error(f"Historial falló: {status} {data}")
        return []
    cups = data.get("historyCoupons", [])
    logger.info(f"Historial BetPlay: {len(cups)} cupones")
    return cups


def _parse_iso(s):
    if not s:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(s.replace('Z', '+00:00'))
    except (ValueError, TypeError):
        return None


def _parse_coupon(c):
    """Convierte un coupon del API a un dict plano para HistorialApuesta."""
    b = c.get('bets', [{}])[0] if c.get('bets') else {}
    o = c.get('outcomes', [{}])[0] if c.get('outcomes') else {}
    ev = c.get('events', [{}])[0] if c.get('events') else {}
    bo = c.get('betOffers', [{}])[0] if c.get('betOffers') else {}

    grupos = ev.get('eventGroups', [])
    liga = grupos[-1].get('name', '') if grupos else ''

    linea = bo.get('line')
    if linea:
        linea = linea / 1000.0

    return {
        'coupon_ref': c.get('couponRef'),
        'coupon_external_ref': c.get('couponExternalRef', ''),
        'placed_date': _parse_iso(c.get('placedDate')),
        'bet_ref': b.get('betRef'),
        'bet_odds': (b.get('betOdds') or 0) / 1000.0 if b.get('betOdds') else None,
        'played_odds': (b.get('playedOdds') or 0) / 1000.0 if b.get('playedOdds') else None,
        'bet_status': b.get('betStatus', 'OPEN'),
        'stake': b.get('stake') or 0,
        'payout': b.get('payout') or 0,
        'potential_payout': b.get('potentialPayout') or 0,
        'outcome_id': o.get('outcomeId'),
        'event_id': ev.get('eventId') or o.get('eventId'),
        'home_team': ev.get('homeName', ''),
        'away_team': ev.get('awayName', ''),
        'event_start_date': _parse_iso(ev.get('eventStartDate')),
        'seleccion': o.get('label', ''),
        'mercado': (bo.get('criterion') or {}).get('label', '') if isinstance(bo.get('criterion'), dict) else (bo.get('criterion') or ''),
        'linea': linea,
        'sport': ev.get('sport', ''),
        'liga': liga,
    }


def _capture_snapshot_for_apuesta(ap, now=None):
    """
    Captura un OddsSnapshot para una apuesta cuyo partido aún no ha empezado.
    Esto asegura que tengamos cuotas pre-partido para calcular CLV después.
    """
    from django.utils import timezone
    from auto_betting.models import OddsSnapshot

    if now is None:
        now = timezone.now()

    if not ap.event_start_date or ap.event_start_date <= now:
        return False  # Partido ya empezó o no tiene fecha
    if not ap.outcome_id or ap.outcome_id == 0:
        return False  # Sin outcome_id para buscar
    # Si ya hay snapshot para este outcome, no duplicar
    if OddsSnapshot.objects.filter(outcome_id=ap.outcome_id).exists():
        return False

    # Mapear el mercado del historial al label de Kambi
    mercado_label = None
    mercado_str = (ap.mercado or '').lower()
    for mp in [
        'Total de Tiros de Esquina',
        'Total de goles',
        'Total de tiros a puerta',
        'Total de Tiros (Resuelta usando Opta Data)',
        'Resultado Final',
        'Ambos Equipos Marcarán',
    ]:
        if mp.lower() in mercado_str or mercado_str in mp.lower():
            mercado_label = mp
            break
    if not mercado_label:
        mercado_label = 'Total de Tiros de Esquina'  # fallback

    # Para mercados de tiros a puerta, probar la variante Opta
    if mercado_label == 'Total de tiros a puerta':
        for label in [
            'Total de tiros a puerta (Resuelta usando Opta Data)',
            'Total de tiros a puerta',
        ]:
            try:
                offers = fetch_market_odds(ap.event_id, label)
            except Exception as e:
                logger.warning(f'Error fetching odds event={ap.event_id} market={label}: {e}')
                continue
            for offer in offers:
                if offer.get('outcome_id') == ap.outcome_id:
                    OddsSnapshot.objects.update_or_create(
                        outcome_id=offer['outcome_id'],
                        captured_at=now,
                        defaults={
                            'event_id': ap.event_id,
                            'market': label,
                            'seleccion': offer.get('label', ''),
                            'linea': offer.get('line'),
                            'side': '',
                            'odds_decimal': offer.get('odds_decimal', 0),
                        },
                    )
                    return True
        return False

    try:
        offers = fetch_market_odds(ap.event_id, mercado_label)
    except Exception as e:
        logger.warning(f'Error fetching odds event={ap.event_id} market={mercado_label}: {e}')
        return False

    for offer in offers:
        if offer.get('outcome_id') == ap.outcome_id:
            OddsSnapshot.objects.update_or_create(
                outcome_id=offer['outcome_id'],
                captured_at=now,
                defaults={
                    'event_id': ap.event_id,
                    'market': mercado_label,
                    'seleccion': offer.get('label', ''),
                    'linea': offer.get('line'),
                    'side': '',
                    'odds_decimal': offer.get('odds_decimal', 0),
                },
            )
            return True
    return False


def sync_historial(since_str='2026-08-01', usuario=None):
    """
    Sincroniza el historial de apuestas desde `since_str` (YYYY-MM-DD).
    - Borra registros previos al corte.
    - Importa/actualiza cupones desde el corte.
    - Marca is_system según si el coupon_ref existe en AutoBet.
    - Captura snapshots de cuotas para apuestas con partido no iniciado (CLV).
    Devuelve dict con conteos.
    """
    from datetime import datetime
    from django.utils import timezone
    from auto_betting.models import AutoBetConfig, AutoBet, HistorialApuesta

    since = timezone.make_aware(datetime.strptime(since_str, '%Y-%m-%d'))
    now = timezone.now()

    qs_cfg = AutoBetConfig.objects.all()
    if usuario is not None:
        qs_cfg = qs_cfg.filter(usuario=usuario)
    config = qs_cfg.first()
    if not config:
        return {'error': 'No hay AutoBetConfig'}
    owner = config.usuario

    borrados, _ = HistorialApuesta.objects.filter(usuario=owner, placed_date__lt=since).delete()

    token, _ = login(config.ticket, config.punter_id)
    if not token:
        return {'error': 'Ticket BetPlay inválido o expirado. Actualízalo en ⚙️ Config BetPlay del menú.'}

    # 2026-09-01: rango ampliado a 500 (antes 200) porque cuentas con más de
    # 200 cupones nunca sincronizaban los más antiguos desde el corte.
    cups = fetch_bet_history(token, range_size=500)
    # Set de coupon_refs del sistema (AutoBet) para marcar is_system
    system_refs = set(AutoBet.objects.filter(usuario=owner).exclude(coupon_ref__isnull=True)
                      .values_list('coupon_ref', flat=True))

    creados = actualizados = omitidos = snapshots = 0
    for c in cups:
        data = _parse_coupon(c)
        if not data.get('coupon_ref'):
            continue
        if data.get('placed_date') and data['placed_date'] < since:
            omitidos += 1
            continue
        # Marcar si es del sistema o manual
        data['is_system'] = data['coupon_ref'] in system_refs
        ap, created = HistorialApuesta.objects.update_or_create(
            usuario=owner,
            coupon_ref=data['coupon_ref'],
            defaults=data,
        )
        if created:
            creados += 1
        else:
            actualizados += 1

        # Capturar snapshot inmediato si el partido aún no ha empezado
        if ap.event_start_date and ap.event_start_date > now and ap.outcome_id and ap.outcome_id != 0:
            try:
                if _capture_snapshot_for_apuesta(ap, now):
                    snapshots += 1
            except Exception as e:
                logger.warning(f'Error capturando snapshot para {ap.coupon_ref}: {e}')

    # 2026-09-01: limpieza de registros fantasma. Si el ticket de la cuenta
    # cambió (o se pegó el ticket de OTRA cuenta), BetPlay deja de devolver
    # los cupones de la cuenta anterior y esos registros quedaban mezclados
    # para siempre. Ahora borramos los registros (desde el corte) que NO
    # aparecen en el historial real de la cuenta.
    # Guard: solo si el fetch cubre TODO el rango desde `since` (el cupón más
    # antiguo devuelto es anterior al corte). Si la cuenta tiene tantos cupones
    # que el fetch se trunca dentro del rango, no borramos nada (conservador).
    borrados_ghost = 0
    if cups:
        oldest_placed = min(
            (_parse_iso(c.get('placedDate')) for c in cups if c.get('placedDate')),
            default=None,
        )
        if oldest_placed is not None and oldest_placed < since:
            refs_betplay = {c.get('couponRef') for c in cups}
            ghost_qs = HistorialApuesta.objects.filter(
                usuario=owner, placed_date__gte=since
            ).exclude(coupon_ref__in=refs_betplay)
            borrados_ghost, _ = ghost_qs.delete()
            if borrados_ghost:
                logger.warning(
                    f'sync_historial {owner.email}: eliminados {borrados_ghost} registros '
                    'que no existen en BetPlay (cuenta/ticket distinto o cupón cancelado).'
                )

    return {
        'ok': True,
        'borrados': borrados,
        'creados': creados,
        'actualizados': actualizados,
        'omitidos': omitidos,
        'snapshots': snapshots,
        'borrados_ghost': borrados_ghost,
        'total': HistorialApuesta.objects.filter(usuario=owner).count(),
    }
