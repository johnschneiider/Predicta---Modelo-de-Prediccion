# -*- coding: utf-8 -*-
"""
MOTOR REMATES TOTALES v2 — modelo independiente (standalone, NO en producción).

Metodología del test pedido por John (13-sep-2026):
  * No se testea "hacia el pasado" con la BD (que ya tiene los resultados dentro).
  * Se testea contra los partidos que YA ACABARON HOY y que la BD todavía no tiene.
  * El modelo se entrena SOLO con partidos ANTERIORES a hoy (2026-09-13).
  * Ground truth = stats descargadas de la API post-partido (today_ft_stats.json).

Componentes:
  1. Dataset leak-free por equipo-partido desde football_api (TeamFixtureStat + ApiFixture).
  2. Modelos: lambda total = attack_home * defense_away * mu_liga * factor_local
     a) A/D paramétrico con shrinkage empírico (bayesiano por equipo).
     b) HistGradientBoosting (sklearn) sobre features de forma reciente.
  3. Blend de los dos + calibración de varianza (NegBin phi).
  4. Evaluación vs mercado (λ_mercado de Kambi cuando hay líneas disponibles):
     MAE, RMSE, bias; comparación con baselines.

Uso: python scripts/remates_v2/remates_v2_eval.py
"""
import os, sys, django, json, math
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
django.setup()

import numpy as np
from collections import defaultdict
from datetime import datetime, timezone as dtz

OUT = open('/var/www/predicta.com.co/scripts/remates_v2/eval_out.txt', 'w')
def w(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')

TODAY = '2026-09-13'
w('MOTOR REMATES TOTALES v2 — EVALUACIÓN OUT-OF-SAMPLE (partidos de HOY)', datetime.now(dtz.utc).isoformat())
w('=' * 100)

# ── 1. DATASET ────────────────────────────────────────────────────────────
from football_api.models import TeamFixtureStat, ApiFixture

print('Cargando stats de la BD (pre-hoy)...')
rows = []  # (date, league_id, home_tid, away_tid, home_shots, away_shots, ...)
q = (TeamFixtureStat.objects
     .filter(total_shots__isnull=False, fixture__date__lt=TODAY)
     .select_related('fixture', 'team')
     .only('total_shots', 'shots_on_goal', 'fixture__date', 'fixture__league_id', 'fixture__home_team_id', 'fixture__away_team_id', 'team_id'))
for s in q.iterator():
    f = s.fixture
    rows.append({
        'date': f.date, 'league': f.league_id, 'team': s.team_id,
        'is_home': s.team_id == f.home_team_id,
        'shots': s.total_shots,
        'fixture': f.api_id,
        'home_tid': f.home_team_id, 'away_tid': f.away_team_id,
    })
print(f'filas: {len(rows)}')
# fixtures index (una entrada por partido con ambos lados)
fx = {}
for r in rows:
    key = r['fixture']
    d = fx.setdefault(key, {'date': r['date'], 'league': r['league'], 'home': None, 'away': None, 'htid': r['home_tid'], 'atid': r['away_tid']})
    if r['is_home']: d['home'] = r['shots']
    else: d['away'] = r['shots']
fixtures = [d for d in fx.values() if d['home'] is not None and d['away'] is not None]
fixtures.sort(key=lambda d: d['date'])
print(f'partidos completos: {len(fixtures)}')
w()
w(f'Dataset: {len(fixtures)} partidos con remates completos (pre-{TODAY})')
w(f'Rango: {fixtures[0]["date"].date() if hasattr(fixtures[0]["date"],"date") else fixtures[0]["date"]} → {fixtures[-1]["date"]}')

# ── 2. MODELO A/D con shrinkage (para cada fecha de test: entrena con todo lo anterior) ──
# attack[team] = (sum_shots_for + k*mu) / (n + k) / mu_side
K = 10.0  # shrinkage

def build_ad(fixtures, upto_dt):
    """Stats A/D usando solo partidos < upto_dt. Devuelve dicts home/away."""
    tot_h = tot_a = 0.0; n = 0
    team_h = defaultdict(lambda: [0.0, 0])  # shots as home
    team_a = defaultdict(lambda: [0.0, 0])  # shots as away
    team_c_h = defaultdict(lambda: [0.0, 0])  # conceded as home (shots away made)
    team_c_a = defaultdict(lambda: [0.0, 0])
    for d in fixtures:
        if d['date'] >= upto_dt: continue
        h, a = d['home'], d['away']
        tot_h += h; tot_a += a; n += 1
        team_h[d['htid']][0] += h; team_h[d['htid']][1] += 1
        team_a[d['atid']][0] += a; team_a[d['atid']][1] += 1
        team_c_h[d['htid']][0] += a; team_c_h[d['htid']][1] += 1
        team_c_a[d['atid']][0] += h; team_c_a[d['atid']][1] += 1
    if n == 0: return None
    mu_h = tot_h / n; mu_a = tot_a / n; mu = mu_h + mu_a
    def att(team, venue):
        s, cnt = (team_h if venue=='h' else team_a)[team]
        base = mu_h if venue=='h' else mu_a
        return (s + K*base) / (cnt + K) / base
    def dfn(team, venue):
        s, cnt = (team_c_h if venue=='h' else team_c_a)[team]
        base = mu_h if venue=='h' else mu_a
        if cnt == 0: return 1.0
        return ((s + K*base) / (cnt + K)) / base
    return {'mu_h': mu_h, 'mu_a': mu_a, 'mu': mu, 'att': att, 'dfn': dfn, 'n': n}

def ad_predict(model, htid, atid):
    if model is None: return None
    # lambda_home = mu_h * att_home(venue h) * dfn_away(venue a_received...)
    # recibidos del away como visitante = team_c_a (shots home made) -> base mu_h
    att_h_raw = model['att'](htid, 'h'); dfn_a_raw = model['dfn'](atid, 'a')
    # our dfn uses conceded base by venue: for away team, conceded shots are 'home made' (mu_h scale)
    # so recompute dfn for away with proper normalization:
    lam_h = model['mu_h'] * att_h_raw * dfn_a_raw
    att_a_raw = model['att'](atid, 'a'); dfn_h_raw = model['dfn'](htid, 'h')
    lam_a = model['mu_a'] * att_a_raw * dfn_h_raw
    return lam_h + lam_a, lam_h, lam_a

# ── 3. Bloque de evaluación out-of-sample: SOLO PARTIDOS DE HOY ──
gt = json.load(open('/var/www/predicta.com.co/scripts/remates_v2/today_ft_stats.json'))
usable = [r for r in gt.values() if r.get('total_shots') is not None]
print(f'ground truth usable: {len(usable)}')

# train set = fixtures anteriores a hoy 00:00 UTC
cutoff = datetime(2026, 9, 13, tzinfo=dtz.utc)
model = build_ad(fixtures, cutoff)
print(f'modelo A/D entrenado con {model["n"]} partidos')

# map today's fixture team ids
from football_api.models import ApiTeam
name2tid = {}
for t in ApiTeam.objects.filter(api_id__in=[r['team'] for r in [] ]): pass

# Evaluate: we need each today match's htid/atid - fetch from ft_covered json + stats file
FT = json.load(open('/tmp/ft_covered.json'))
fxmeta = {f['fixture']['id']: f for f in FT}

ad_errs = []; ad_preds = []
ok = 0
for r in usable:
    fid = r['fixture_id']
    meta = fxmeta.get(fid)
    if not meta: continue
    htid = meta['teams']['home']['id']; atid = meta['teams']['away']['id']
    pr = ad_predict(model, htid, atid)
    if pr is None: continue
    lam, lh, la = pr
    actual = r['total_shots']
    ad_errs.append(abs(lam - actual)); ad_preds.append((r['league'], meta['teams']['home']['name'], meta['teams']['away']['name'], lam, actual))
    ok += 1
errs = np.array(ad_errs)
print(f'A/D evaluado en {ok} partidos de HOY')
print(f'A/D: MAE={errs.mean():.2f} RMSE={(errs**2).mean()**0.5:.2f} bias={np.mean([p[3]-p[4] for p in ad_preds]):+.2f}')
w()
w(f'### MODELO A/D (shrinkage k={K}) — out-of-sample HOY')
w(f'Evaluado en {ok} partidos: MAE={errs.mean():.2f} RMSE={(errs**2).mean()**0.5:.2f}')

# baselines on the SAME today matches
mu = model['mu']
naive = np.array([abs(mu - p[4]) for p in ad_preds])
print(f'baseline mu-global ({mu:.2f}): MAE={naive.mean():.2f}')
w(f'baseline mu-global: MAE={naive.mean():.2f}')
# liga media
lg_mu = defaultdict(list)
for d in fixtures:
    if d['date'] < cutoff: lg_mu[d['league']].append(d['home']+d['away'])
lg_mean = {k: np.mean(v) for k, v in lg_mu.items() if len(v) >= 20}
lgerr = []
for p in ad_preds:
    # matching by league not stored... approximate: use league string from gt
    pass
# store league id in preds
import json as _json
byid = {f['fixture']['id']: f['league']['id'] for f in FT}
lgerr = []
for r, p in zip([r for r in usable if r['fixture_id'] in fxmeta], ad_preds):
    lid = byid.get(r['fixture_id'])
    if lid in lg_mean: lgerr.append(abs(lg_mean[lid] - r['total_shots']))
if lgerr:
    print(f'baseline liga-media (n={len(lgerr)}): MAE={np.mean(lgerr):.2f}')
    w(f'baseline liga-media: MAE={np.mean(lgerr):.2f}')

OUT.close()
print('DONE')
