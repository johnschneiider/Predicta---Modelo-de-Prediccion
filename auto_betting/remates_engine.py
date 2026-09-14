# -*- coding: utf-8 -*-
"""
MOTOR DE REMATES TOTALES v2.3 — integración a producción (auto_betting).

Predice el λ (total de remates del partido) con el modelo v2.3:
HistGradientBoosting + calibración lineal, entrenado leak-free sobre
37.946 partidos (API-Football, ventana exponencial half-life 120d).

Diseño (2026-09-14):
- Features inferidas EN VIVO desde la BD (football_api.TeamFixtureStat),
  replicando exactamente las definiciones del entrenamiento
  (scripts/remates_v2/build_features.py):
    * medias exponenciales por venue (for/against) — half-life 120d, ventana 400d
    * forma últimos 5 (todas las sedes), descanso, media de liga
    * n >= 3 partidos por equipo en ventana (igual que el entrenamiento)
- El λ resultante se pasa por el MISMO embudo de edge/calibración que los
  demás mercados (auto_betting.strategy.select_bets): devig, edge vs cuota
  justa, tiers por cuota, EV mínimo, distancia línea-λ, filtros por usuario.
- Distribución para las probabilidades: Negative Binomial phi=42.36
  (sobredispersión real de remates, auditada 2026-09-13).

No usa el pipeline web (modelos por nombre); ancla por IDs de API-Football
para evitar swaps de equipos (fix Vicenza→Venezia).
"""

import logging
import math
import re
import unicodedata
from collections import defaultdict
from datetime import timedelta

import numpy as np

logger = logging.getLogger('auto_betting')

# ── Parámetros del modelo (deben coincidir con el entrenamiento) ──
HALF_LIFE = 120.0
WINDOW_DAYS = 400
MIN_MATCHES = 3          # build_features: n < 3 → fila excluida del entrenamiento
PHI_TOTAL_SHOTS = 42.36  # sobredispersión de remates (auditoría 13-sep)

_clf_cache = None
_team_recs_cache = {}
_league_recs_cache = {}


def _load_model():
    global _clf_cache
    if _clf_cache is None:
        import joblib
        from django.conf import settings
        path = settings.BASE_DIR / 'auto_betting' / 'ml' / 'remates_v2_gbm_v23.pkl'
        md = joblib.load(str(path))
        _clf_cache = (md['model'], md['feat_cols'], md['calib'])
    return _clf_cache


def _w_of(age_days):
    return 0.5 ** (age_days / HALF_LIFE)


def _team_records(team):
    """Todos los partidos del equipo (con stats), en orden cronológico.

    Estructura idéntica a build_features/remates_v2:
      {'fid', 'date', 'ord', 'for': {venue: {...}}, 'ag': {venue: {...}}}
    """
    from football_api.models import TeamFixtureStat

    recs = _team_recs_cache.get(team.id)
    if recs is not None:
        return recs

    recs = []
    base = (TeamFixtureStat.objects
            .filter(team_id=team.id, total_shots__isnull=False)
            .select_related('fixture')
            .order_by('fixture__date'))
    rows = list(base)
    fids = [st.fixture.api_id for st in rows]
    opp = {}
    if fids:
        for fapi, ts, sot, blk in (TeamFixtureStat.objects
                                   .filter(fixture__api_id__in=fids)
                                   .exclude(team_id=team.id)
                                   .values_list('fixture__api_id', 'total_shots',
                                                'shots_on_goal', 'blocked_shots')):
            opp[fapi] = {'ts': ts, 'sot': sot, 'blk': blk}
    for st in rows:
        f = st.fixture
        o = opp.get(f.api_id)
        # Consistencia con el entrenamiento (build_features): solo entran
        # partidos con remates registrados en AMBOS lados (fx_list completo).
        if not o or o['ts'] is None or st.total_shots is None:
            continue
        venue = 'h' if f.home_team_id == team.id else 'a'
        recs.append({
            'fid': f.api_id,
            'date': f.date,
            'ord': f.date.date().toordinal(),
            'for': {venue: {'ts': st.total_shots, 'sot': st.shots_on_goal,
                            'ibox': st.shots_insidebox, 'corn': st.corner_kicks}},
            'ag': {venue: {'ts': o['ts'], 'sot': o['sot'], 'blk': o['blk']}},
        })
    _team_recs_cache[team.id] = recs
    return recs


def _team_features(recs, dt_ord, venue):
    """Medias exponenciales por venue (for/against). Réplica exacta del entrenamiento."""
    if not recs:
        return None
    lo = dt_ord - WINDOW_DAYS
    keys_for = ['ts', 'sot', 'ibox', 'corn']
    keys_ag = ['ts', 'sot', 'blk']
    sums = defaultdict(float)
    wsum = defaultdict(float)
    n = 0
    for rec in reversed(recs):
        if rec['ord'] < lo:
            break
        wt = _w_of(dt_ord - rec['ord'])
        n += 1
        fv = rec['for'].get(venue)
        av = rec['ag'].get(venue)
        if fv:
            for k in keys_for:
                sums['f_' + k] += wt * (fv.get(k) or 0)
                wsum['f_' + k] += wt
            sums['f_ts_v'] += wt * (fv.get('ts') or 0)
            wsum['f_ts_v'] += wt
        if av:
            for k in keys_ag:
                sums['a_' + k] += wt * (av.get(k) or 0)
                wsum['a_' + k] += wt
    if n < MIN_MATCHES or wsum['f_ts'] == 0:
        return None
    out = {k: (sums[k] / wsum[k] if wsum[k] > 0 else None) for k in sums}
    out['n'] = n
    return out


def _league_records(league):
    from football_api.models import TeamFixtureStat
    from django.db.models import Sum, Count

    recs = _league_recs_cache.get(league.id)
    if recs is not None:
        return recs
    qs = (TeamFixtureStat.objects
          .filter(fixture__league_id=league.id, total_shots__isnull=False)
          .values('fixture__api_id', 'fixture__date')
          .annotate(tot=Sum('total_shots'), cnt=Count('id'))
          .order_by('fixture__date'))
    recs = [(r['fixture__date'], r['fixture__date'].date().toordinal(), r['tot'])
            for r in qs if r['cnt'] == 2]
    _league_recs_cache[league.id] = recs
    return recs


def _league_mean(recs, dt_ord, before_dt):
    """Media exponencial de remates totales de la liga (ventana 400d)."""
    if not recs:
        return None
    lo = dt_ord - WINDOW_DAYS
    s = 0.0
    wsum = 0.0
    for d, o, tot in reversed(recs):
        if o < lo:
            break
        if d >= before_dt:
            continue
        wt = _w_of(dt_ord - o)
        s += wt * tot
        wsum += wt
    return (s / wsum) if wsum > 0 else None


def _eng(row):
    """Features derivadas — réplica exacta de remates_v2 (v2.3)."""
    model, feat_cols, calib = _load_model()

    def g(k):
        v = row.get(k)
        try:
            return float(v) if v not in (None, '', 'None') else np.nan
        except (TypeError, ValueError):
            return np.nan

    out = {}
    for k in feat_cols:
        out[k] = g(k)
    out['lamH_a'] = 0.5 * (g('h_f_ts') + g('a_a_ts'))
    out['lamA_a'] = 0.5 * (g('a_f_ts') + g('h_a_ts'))
    out['lamT_a'] = out.get('lamH_a', np.nan) + out.get('lamA_a', np.nan)
    out['lamT_g'] = (np.sqrt(np.maximum(0, g('h_f_ts') * g('a_a_ts')))
                     + np.sqrt(np.maximum(0, g('a_f_ts') * g('h_a_ts'))))
    out['sotT_a'] = 0.5 * (g('h_f_sot') + g('a_a_sot')) + 0.5 * (g('a_f_sot') + g('h_a_sot'))
    out['iboxT_a'] = 0.5 * (g('h_f_ibox') + g('a_a_ts')) + 0.5 * (g('a_f_ibox') + g('h_a_ts'))
    out['cornT_a'] = 0.5 * (g('h_f_corn') + g('a_a_ts')) + 0.5 * (g('a_f_corn') + g('h_a_ts'))
    out['ratio_h'] = g('h_f_ts') / (g('a_a_ts') + 1e-6)
    out['ratio_a'] = g('a_f_ts') / (g('h_a_ts') + 1e-6)
    out['l5_ratio_h'] = g('h_l5_mean') / (g('h_f_ts') + 1e-6)
    out['l5_ratio_a'] = g('a_l5_mean') / (g('a_f_ts') + 1e-6)
    return out


def predict_total_shots_lambda(home_team, away_team, league, kickoff_dt):
    """λ de remates totales para home_team vs away_team.

    Returns: dict {'lambda', 'raw', 'n_home', 'n_away'} o None si faltan datos.
    """
    md = _load_model()
    model, feat_cols, calib = md

    hrecs = [r for r in _team_records(home_team) if r['date'] < kickoff_dt]
    arecs = [r for r in _team_records(away_team) if r['date'] < kickoff_dt]
    dt_ord = kickoff_dt.date().toordinal()

    hf = _team_features(hrecs, dt_ord, 'h')
    af = _team_features(arecs, dt_ord, 'a')
    if not (hf and af):
        logger.info(f'remates_v2: sin features para {home_team.name} vs {away_team.name} '
                    f'(n_home={hf["n"] if hf else 0}, n_away={af["n"] if af else 0})')
        return None

    row = {}
    for k, v in hf.items():
        row['h_' + k] = v
    for k, v in af.items():
        row['a_' + k] = v
    row['lgm'] = _league_mean(_league_records(league), dt_ord, kickoff_dt) if league else None

    last_h = hrecs[-1]['ord'] if hrecs else None
    last_a = arecs[-1]['ord'] if arecs else None
    row['h_rest'] = (dt_ord - last_h) if last_h else None
    row['a_rest'] = (dt_ord - last_a) if last_a else None

    def _l5_any_venue(recs):
        vals = []
        for rec in reversed(recs):
            v = (rec['for'].get('h', {}).get('ts') if 'h' in rec['for']
                 else rec['for'].get('a', {}).get('ts'))
            if v is not None:
                vals.append(v)
            if len(vals) >= 5:
                break
        return vals

    l5h = _l5_any_venue(hrecs)
    l5a = _l5_any_venue(arecs)
    row['h_l5_mean'] = np.mean(l5h) if l5h else None
    row['h_l5_std'] = np.std(l5h) if len(l5h) >= 3 else None
    row['h_l5_n'] = len(l5h)
    row['a_l5_mean'] = np.mean(l5a) if l5a else None
    row['a_l5_std'] = np.std(l5a) if len(l5a) >= 3 else None
    row['a_l5_n'] = len(l5a)

    e = _eng(row)
    X = np.array([[e.get(k, np.nan) for k in feat_cols]], dtype=np.float32)
    raw = float(model.predict(X)[0])
    lam = float(calib[0] + calib[1] * raw)
    lam = min(45.0, max(5.0, lam))
    return {
        'lambda': round(lam, 3),
        'raw': round(raw, 3),
        'n_home': hf['n'],
        'n_away': af['n'],
    }


# ── Resolución Kambi → ApiFixture (anclaje por IDs, sin fuzzy de clubes) ──

def _toks(s):
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^a-z0-9]+', ' ', s.lower())
    return set(s.split())


def _sim(name_a, name_b):
    ta, tb = _toks(name_a), _toks(name_b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / max(len(ta), len(tb))


def resolve_kambi_fixture(match):
    """Encuentra el ApiFixture que corresponde a un partido de Kambi.

    match: dict de fetch_upcoming_matches con 'league_path', 'home', 'away', 'start_time'.
    Criterio: liga por kambi_path exacto + ambos lados similares (>=0.5) +
    diferencia horaria < 18h. Devuelve ApiFixture o None.
    """
    from football_api.models import ApiFixture, ApiLeague

    lp = match.get('league_path') or ''
    start = match.get('start_time')
    if not start:
        return None
    lg = ApiLeague.objects.filter(kambi_path=lp).first() if lp else None

    qs = (ApiFixture.objects
          .filter(date__gte=start - timedelta(hours=18),
                  date__lte=start + timedelta(hours=18))
          .exclude(status__in=['FT', 'AET', 'PEN'])
          .select_related('home_team', 'away_team'))
    if lg:
        qs = qs.filter(league_id=lg.id)

    best = None
    for f in qs:
        sh = _sim(f.home_team.name, match.get('home', ''))
        sa = _sim(f.away_team.name, match.get('away', ''))
        if sh >= 0.5 and sa >= 0.5:
            dt_h = abs((f.date - start).total_seconds()) / 3600.0
            cand = (round(sh + sa, 3), -dt_h, f)
            if best is None or cand[:2] > best[:2]:
                best = cand
    return best[2] if best else None


def predict_remates_for_kambi(match):
    """Predicción para un partido del feed Kambi. Devuelve dict o None."""
    from football_api.models import ApiFixture

    f = resolve_kambi_fixture(match)
    if not f:
        return None
    kickoff = f.date
    # predict_total_shots_lambda filtra por fecha (< kickoff), lo que excluye
    # el propio fixture; el guard fid!=api_id cubre stats ya cargadas del mismo.
    pred = predict_total_shots_lambda(f.home_team, f.away_team, f.league, kickoff)
    if not pred:
        return None
    pred['fixture_api_id'] = f.api_id
    pred['confidence'] = 0.5
    pred['home_team_id'] = f.home_team_id
    pred['away_team_id'] = f.away_team_id
    pred['league_id'] = f.league_id
    return pred
