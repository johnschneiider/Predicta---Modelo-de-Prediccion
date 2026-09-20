# -*- coding: utf-8 -*-
"""
Inspector de apuestas — lógica de verificación independiente.

Verifica si una apuesta liquidada como PERDIDA (o GANADA) por BetPlay/Kambi
realmente no cumplió (o cumplió) las condiciones para ganar, usando la base
de datos local alimentada por API-Football (football_api.ApiFixture +
TeamFixtureStat), que es la misma fuente de los motores de Predicta.

Reglas de seguridad (anti falso positivo):
- Solo se marca REVISAR cuando los datos locales INDICAN claramente lo
  contrario al estado BetPlay, con fixture resuelto de forma no ambigua.
- Cualquier duda (fixture no encontrado, mercado no soportado, cupón con
  datos inconsistentes, prórroga/penales, stats ausentes) => NO_VERIFICABLE,
  nunca se alerta.

Nota sobre fuentes: BetPlay liquida algunos mercados con datos Opta, cuya
contabilidad de remates puede diferir ±1-2 de API-Football (evidencia:
scripts/audit_mercados/inv_out_20260913.txt ~1% de discrepancia). Por eso el
mensaje de alerta solicita SIEMPRE revisión manual.
"""

import difflib
import logging
import re
import unicodedata
from datetime import timedelta

from football_api.models import ApiFixture

logger = logging.getLogger('inspector')

# ── Normalización y similitud de nombres ──────────────────────────────────

_STOP = {
    'fc', 'cf', 'sc', 'ac', 'afc', 'cd', 'cs', 'ca', 'fk', 'sk', 'if', 'ff',
    'bk', 'us', 'sv', 'ss', 'as', 'club', 'calcio', 'de', 'do', 'da', 'del',
    'la', 'el', 'the', '1995', '1913', '1899', '1900', 'ii', 'iii',
}


def _norm(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower()
    s = re.sub(r'[^a-z0-9]+', ' ', s)
    s = re.sub(r'\s+[a-z]{2}\s*$', '', s)  # sufijos tipo 'RJ', 'SP' (Vasco da Gama-RJ)
    return re.sub(r'\s+', ' ', s).strip()


def _tokens(s):
    return {t for t in _norm(s).split() if t not in _STOP and len(t) > 1}


def _sim(a, b):
    """Similitud 0-1 entre dos nombres (tokens + caracteres)."""
    ta, tb = _tokens(a), _tokens(b)
    base = 0.0
    if ta and tb:
        inter = ta & tb
        if inter:
            base = max(len(inter) / min(len(ta), len(tb)), len(inter) / len(ta | tb))
    ra = _norm(a).replace(' ', '')
    rb = _norm(b).replace(' ', '')
    ch = difflib.SequenceMatcher(None, ra, rb).ratio() if ra and rb else 0.0
    return max(base, ch * 0.85)


def _team_side(fixture, name):
    """Devuelve 'home'/'away' si `name` corresponde a un equipo del fixture."""
    sh = _sim(fixture.home_team.name, name)
    sa = _sim(fixture.away_team.name, name)
    if max(sh, sa) < 0.55:
        return None
    return 'home' if sh >= sa else 'away'


# ── Resolución apuesta → fixture (anclaje por nombres + fecha + liga) ─────

def resolve_fixture(bet):
    """Encuentra el ApiFixture correspondiente a la apuesta.

    Devuelve (fixture | None, confianza 'alta'/'media' | '', motivo).
    Criterio conservador: ambos equipos deben parecerse (>= 0.55 mínimo,
    >= 0.62 en general) y no puede haber un segundo candidato casi-empate
    (salvo que la liga lo desambigüe).
    """
    start = bet.event_start_date
    if not start:
        return None, '', 'sin fecha de partido'
    window = timedelta(hours=14)
    qs = (ApiFixture.objects
          .filter(date__gte=start - window, date__lte=start + window)
          .select_related('home_team', 'away_team', 'league'))

    cands = []
    for f in qs:
        sh = _sim(f.home_team.name, bet.home_team or '')
        sa = _sim(f.away_team.name, bet.away_team or '')
        if min(sh, sa) < 0.55:
            continue
        score = sh + sa
        liga_bonus = 0.0
        if bet.liga:
            ls = max(_sim(bet.liga, f.league.name),
                     _sim(bet.liga, f.league.predicta_name or ''))
            if ls >= 0.75:
                liga_bonus = 0.35
                score += liga_bonus
        cands.append({'score': score, 'sh': sh, 'sa': sa, 'f': f, 'liga_ok': liga_bonus > 0})

    if not cands:
        return None, '', 'sin candidatos en ±14h'
    cands.sort(key=lambda c: -c['score'])
    top = cands[0]

    min_sim = min(top['sh'], top['sa'])
    if min_sim < 0.62 and not (top['liga_ok'] and min_sim >= 0.55):
        return None, '', f'similitud baja {top["sh"]:.2f}/{top["sa"]:.2f}'

    if len(cands) > 1:
        second = cands[1]
        if second['f'].api_id != top['f'].api_id and (top['score'] - second['score']) < 0.06:
            l_top = max(_sim(bet.liga or '', top['f'].league.name),
                        _sim(bet.liga or '', top['f'].league.predicta_name or ''))
            l_sec = max(_sim(bet.liga or '', second['f'].league.name),
                        _sim(bet.liga or '', second['f'].league.predicta_name or ''))
            if not (l_top >= 0.75 and l_sec < 0.5):
                return None, '', (f'ambiguo: {top["f"].api_id} vs {second["f"].api_id} '
                                  f'({top["score"]:.2f}/{second["score"]:.2f})')

    conf = 'alta' if min(top['sh'], top['sa']) >= 0.80 else 'media'
    f = top['f']
    return f, conf, (f'score {top["score"]:.2f} '
                     f'(h={top["sh"]:.2f} a={top["sa"]:.2f}, liga={f.league.name})')


# ── Stats faltantes: fetch puntual (presupuesto acotado) ──────────────────

def ensure_stats(fixture, client, tried_ids):
    """Garantiza que el fixture tenga sus 2 filas de TeamFixtureStat.

    Devuelve True si hay stats; False si no. Máximo UNA llamada a
    API-Football por fixture por corrida (tried_ids).
    """
    rows = list(fixture.stats.all())
    if len(rows) == 2:
        return True
    if fixture.api_id in tried_ids:
        return len(fixture.stats.all()) == 2
    tried_ids.add(fixture.api_id)
    try:
        from football_api.services import save_statistics
        save_statistics(fixture, client)
    except Exception as e:  # noqa: BLE001 — cuota/red: reintentará otra corrida
        logger.warning('ensure_stats: error fixture %s: %s', fixture.api_id, e)
        return False
    return len(fixture.stats.all()) == 2


# ── Evaluación del mercado ────────────────────────────────────────────────

def _sel_line(sel, line):
    """Número de línea desde la selección ('Más de 2.5') validándolo vs `linea`."""
    m = re.search(r'(\d+(?:[.,]\d+)?)', sel or '')
    n = float(m.group(1).replace(',', '.')) if m else None
    lb = line if line is not None else None
    if n is not None and lb is not None and abs(n - lb) > 0.01:
        return None, 'selección y línea no coinciden (cupón inconsistente)'
    return (n if n is not None else lb), None


def _over(sel):
    s = (sel or '').lower()
    if 'más' in s or 'mas ' in s:
        return True
    if 'menos' in s:
        return False
    return None


def evaluate_bet(bet, fixture):
    """Evalúa la apuesta contra el fixture.

    Devuelve (estado_esperado | None, detalle, margen | None, motivo_skip).
    estado_esperado en {'WON','LOST','VOID'} — None = no verificable.
    margen = |valor − línea| cuando el mercado tiene línea (None si no).
    """
    mkt = bet.mercado or ''
    sel = bet.seleccion or ''
    ml = mkt.lower()
    st = fixture.status or ''

    if st in ('PST', 'CANC', 'ABD', 'AWD', 'WO', 'SUSP', 'INT'):
        return None, '', None, f'partido {st} (no jugado/cancelado)'
    if st in ('NS', 'TBD'):
        return None, '', None, 'aún no iniciado'
    if st in ('1H', '2H', 'HT', 'ET', 'BT', 'LIVE'):
        return None, '', None, f'en juego ({st})'
    if st in ('AET', 'PEN'):
        if ml != 'descanso':
            return None, '', None, 'prórroga/penales (no comparable)'

    eh, ea = fixture.ft_home, fixture.ft_away
    hh, ha = fixture.ht_home, fixture.ht_away

    line_n = None
    if any(k in ml for k in ('total de', 'más de', 'menos de', 'número total', 'a favor de')):
        line_n, err = _sel_line(sel, bet.linea)
        if err:
            return None, '', None, err
        if line_n is None:
            return None, '', None, 'sin línea'
    over = _over(sel)

    # ── Ambos Equipos Marcarán ──
    if 'ambos equipos marcar' in ml:
        s = _norm(sel)
        if s not in ('si', 'no'):
            return None, '', None, f'selección BTTS inesperada: {sel!r}'
        if eh is None or ea is None:
            return None, '', None, 'sin marcador'
        bts = eh > 0 and ea > 0
        won = bts if s == 'si' else not bts
        return ('WON' if won else 'LOST'), f'BTTS={bts} ({eh}-{ea})', None, ''

    # ── Mercados con línea ──
    if line_n is not None:
        if over is None:
            return None, '', None, f'dirección desconocida: {sel!r}'
        val = None
        name = ''
        if 'esquina' in ml or 'corner' in ml:
            if 'a favor de' in ml:
                tm = mkt.split('a favor de')[-1].strip()
                side = _team_side(fixture, tm)
                if side is None:
                    return None, '', None, f'equipo no reconocido: {tm!r}'
                row = next((r for r in fixture.stats.all()
                            if r.team_id == (fixture.home_team_id if side == 'home'
                                             else fixture.away_team_id)), None)
                if row is None or row.corner_kicks is None:
                    return None, '', None, 'sin stats (corners equipo)'
                val = int(row.corner_kicks)
                name = f'corners {tm}'
            else:
                rows = list(fixture.stats.all())
                if len(rows) != 2 or any(r.corner_kicks is None for r in rows):
                    return None, '', None, 'sin stats (corners)'
                val = sum(int(r.corner_kicks) for r in rows)
                name = 'corners'
        elif 'por parte de' in ml:
            mm = re.search(r'por parte de (.+?)(?:\s*\(|$)', mkt)
            tm = mm.group(1).strip() if mm else ''
            side = _team_side(fixture, tm)
            if side is None:
                return None, '', None, f'equipo no reconocido: {tm!r}'
            row = next((r for r in fixture.stats.all()
                        if r.team_id == (fixture.home_team_id if side == 'home'
                                         else fixture.away_team_id)), None)
            if row is None or row.total_shots is None:
                return None, '', None, 'sin stats (tiros equipo)'
            val = int(row.total_shots)
            name = f'tiros {tm}'
        elif 'tiros a puerta' in ml or 'tiros al arco' in ml:
            rows = list(fixture.stats.all())
            if len(rows) != 2 or any(r.shots_on_goal is None for r in rows):
                return None, '', None, 'sin stats (tiros a puerta)'
            val = sum(int(r.shots_on_goal) for r in rows)
            name = 'sot'
        elif 'tiros' in ml or 'disparos' in ml:
            rows = list(fixture.stats.all())
            if len(rows) != 2 or any(r.total_shots is None for r in rows):
                return None, '', None, 'sin stats (tiros totales)'
            val = sum(int(r.total_shots) for r in rows)
            name = 'tiros'
        elif 'goles' in ml:
            if eh is None or ea is None:
                return None, '', None, 'sin marcador'
            val = eh + ea
            name = 'goles'
        if val is None:
            return None, '', None, f'mercado no soportado: {mkt!r}'
        margen = abs(val - line_n)
        if val == line_n:
            return 'VOID', f'{name}={val} (= línea {line_n:g})', 0.0, ''
        won = val > line_n if over else val < line_n
        return ('WON' if won else 'LOST'), f'{name}={val} vs {line_n:g}', margen, ''

    # ── Resultado Final ──
    if ml == 'resultado final':
        if eh is None or ea is None:
            return None, '', None, 'sin marcador'
        r = '1' if eh > ea else ('X' if eh == ea else '2')
        s = sel.strip().lower()
        if s in ('1', 'home', 'ot_1'):
            won = r == '1'
        elif s in ('2', 'away', 'ot_2'):
            won = r == '2'
        elif s in ('x', 'draw', 'ot_x'):
            won = r == 'X'
        else:
            side = _team_side(fixture, sel)
            if side is None:
                return None, '', None, f'selección no reconocida: {sel!r}'
            won = (r == '1') if side == 'home' else (r == '2')
        return ('WON' if won else 'LOST'), f'1X2={r} ({eh}-{ea})', None, ''

    # ── Descanso ──
    if ml == 'descanso':
        if hh is None or ha is None:
            return None, '', None, 'sin marcador HT'
        r = '1' if hh > ha else ('X' if hh == ha else '2')
        s = sel.strip().lower()
        if s in ('1', 'x', '2'):
            won = (s == r.lower())
        else:
            side = _team_side(fixture, sel)
            if side is None:
                return None, '', None, f'selección no reconocida: {sel!r}'
            won = (r == '1') if side == 'home' else (r == '2')
        return ('WON' if won else 'LOST'), f'HT={r} ({hh}-{ha})', None, ''

    # ── Doble Oportunidad ──
    if 'doble oportunidad' in ml:
        if eh is None or ea is None:
            return None, '', None, 'sin marcador'
        s = re.sub(r'[^12xX]', '', sel.replace(' ', '')).upper()
        if len(s) == 2 and s in ('1X', 'X2', '12'):
            won = (eh >= ea) if s == '1X' else ((eh <= ea) if s == 'X2' else (eh != ea))
        else:
            side = _team_side(fixture, sel)
            if side is None:
                return None, '', None, f'selección no reconocida: {sel!r}'
            won = (eh >= ea) if side == 'home' else (ea >= eh)
        return ('WON' if won else 'LOST'), f'DO {s} ({eh}-{ea})', None, ''

    return None, '', None, f'mercado no soportado: {mkt!r}'

# ── Flujo completo de inspección de una apuesta ───────────────────────────

# ── Flujo completo de inspección de una apuesta ───────────────────────────

def inspect_bet(bet, client=None, tried_ids=None):
    """Inspecciona una apuesta y devuelve un dict con el resultado."""
    fixture, conf, why = resolve_fixture(bet)
    if fixture is None:
        return {'veredicto': 'NO_VERIFICABLE', 'direccion': '', 'estado_esperado': '',
                'confianza': '', 'detalle': f'fixture no resuelto: {why}',
                'fixture_api_id': None, 'margen': None}

    if client is not None and tried_ids is not None:
        ml = (bet.mercado or '').lower()
        needs_stats = any(k in ml for k in ('esquina', 'corner', 'tiros', 'disparos'))
        if needs_stats and fixture.status in ('FT', 'AET', 'PEN'):
            if not ensure_stats(fixture, client, tried_ids):
                return {'veredicto': 'NO_VERIFICABLE', 'direccion': '', 'estado_esperado': '',
                        'confianza': conf, 'detalle': 'sin cobertura de estadísticas',
                        'fixture_api_id': fixture.api_id, 'margen': None}

    esperado, detalle, margen, skip = evaluate_bet(bet, fixture)
    if esperado is None:
        return {'veredicto': 'NO_VERIFICABLE', 'direccion': '', 'estado_esperado': '',
                'confianza': conf, 'detalle': skip, 'fixture_api_id': fixture.api_id,
                'margen': None}

    kambi = bet.bet_status
    if kambi == esperado:
        return {'veredicto': 'OK', 'direccion': '', 'estado_esperado': esperado,
                'confianza': conf, 'detalle': detalle, 'fixture_api_id': fixture.api_id,
                'margen': margen}

    direccion = 'perdida_dudosa' if kambi == 'LOST' else 'victoria_dudosa'
    return {'veredicto': 'REVISAR', 'direccion': direccion, 'estado_esperado': esperado,
            'confianza': conf, 'detalle': detalle, 'fixture_api_id': fixture.api_id,
            'margen': margen}
