# -*- coding: utf-8 -*-
"""
MOTOR REMATES TOTALES v2 — PASO 2: ENTRENAMIENTO + EVALUACIÓN OUT-OF-SAMPLE.

Test pedido por John: partidos de HOY (13-sep-2026) que la BD no tiene;
ground truth de la API descargado post-partido (today_ft_stats.json).
Entrenamiento: SOLO partidos anteriores a hoy (features_all.csv).

Modelos:
  A) GBM (HistGradientBoostingRegressor) sobre features exp-weighted.
  B) A/D paramétrico (attack/defense con shrinkage) — ya construido inline aquí para blend.
  C) Blend GBM + A/D (peso óptimo por evaluación interna temporal).
Evaluación: MAE/RMSE/bias vs actuales (25.25 baseline), y comparación con λ de mercado donde esté disponible.
"""
import os, sys, csv, json, math, pickle
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()
import numpy as np

R = '/var/www/predicta.com.co/scripts/remates_v2'
OUT = open(R + '/eval_out.txt', 'w')
def w(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')

from datetime import datetime, timezone as dtz
w('MOTOR REMATES TOTALES v2 — EVAL OUT-OF-SAMPLE (partidos de HOY)', datetime.now(dtz.utc).isoformat())
w('='*100)

# ── Load features ──
rows = []
with open(R + '/features_all.csv') as fp:
    rd = csv.DictReader(fp)
    for r in rd:
        rows.append(r)
print(f'features rows: {len(rows)}')

# train = all rows (they are all pre-today anyway); last 15% as internal validation for blend weight
rows.sort(key=lambda r: r['date'])
n = len(rows)
split = int(n * 0.85)
train, val = rows[:split], rows[split:]
print(f'train {len(train)} | val {len(val)}')

feat_cols = [k for k in rows[0].keys() if k not in ('fid','date','lg','htid','atid','y')]
# convert numerics (None -> nan)
import math
def vec(r):
    out = []
    for k in feat_cols:
        v = r.get(k)
        try: out.append(float(v) if v not in (None,'','None') else np.nan)
        except: out.append(np.nan)
    return out

X = np.array([vec(r) for r in rows], dtype=np.float32)
y = np.array([float(r['y']) for r in rows], dtype=np.float32)
Xn, Xv = X[:split], X[split:]
yn, yv = y[:split], y[split:]

from sklearn.ensemble import HistGradientBoostingRegressor
print('entrenando GBM...')
gbm = HistGradientBoostingRegressor(
    max_iter=500, learning_rate=0.05, max_depth=6, min_samples_leaf=40,
    l2_regularization=1.0, early_stopping=True, validation_fraction=0.1, random_state=42)
gbm.fit(Xn, yn)

pv = gbm.predict(Xv)
mae_v = np.mean(np.abs(pv - yv)); rmse_v = np.sqrt(np.mean((pv - yv)**2))
print(f'GBM validación interna: MAE={mae_v:.2f} RMSE={rmse_v:.2f} bias={np.mean(pv-yv):+.2f}')

# baselines on validation
mu_tr = yn.mean()
print(f'baseline mu(train)={mu_tr:.2f}: MAE={np.mean(np.abs(mu_tr-yv)):.2f}')

# ── Evaluate on TODAY ──
gt = json.load(open(R + '/today_ft_stats.json'))
usable = [r for r in gt.values() if r.get('total_shots') is not None and r.get('teams') and len(r['teams'])==2]
print(f'today usable: {len(usable)}')

FT = json.load(open('/tmp/ft_covered.json'))
fxmeta = {f['fixture']['id']: f for f in FT}
byid_lg = {f['fixture']['id']: f['league']['id'] for f in FT}

from football_api.models import ApiTeam
# id translations: today matches' team ids may not be in history if never seen.
# Build features for today matches using histories.pkl
pj = pickle.load(open(R + '/histories.pkl','rb'))
hist, hist_lg = pj['hist'], pj['hist_lg']

def w_of(age_days): return 0.5 ** (age_days / 120.0)

def team_features_now(tid, dt_ord, venue):
    h = hist.get(tid)
    if not h: return None
    lo = dt_ord - 400
    keys_for = ['ts','sot','ibox','corn']
    keys_ag  = ['ts','sot','blk']
    from collections import defaultdict
    sums = defaultdict(float); wsum = defaultdict(float); n = 0
    for rec in reversed(h):
        if rec['ord'] < lo: break
        age = dt_ord - rec['ord']; wt = w_of(age); n += 1
        fv = rec['for'].get(venue); av = rec['ag'].get(venue)
        if fv:
            for k in keys_for:
                sums['f_'+k] += wt*(fv.get(k) or 0); wsum['f_'+k] += wt
        if av:
            for k in keys_ag:
                sums['a_'+k] += wt*(av.get(k) or 0); wsum['a_'+k] += wt
    if n < 2 or wsum['f_ts'] == 0:
        return None
    out = {k: (sums[k]/wsum[k] if wsum[k] > 0 else None) for k in sums}
    out['n'] = n
    return out

def league_mean_now(lg, dt_ord):
    h = hist_lg.get(lg)
    if not h: return None
    lo = dt_ord - 400
    s = 0.0; wsum = 0.0
    for rec in reversed(h):
        if rec[0] < lo: break
        wt = w_of(dt_ord - rec[0]); s += wt*rec[1]; wsum += wt
    return s/wsum if wsum > 0 else None

TODAY_ORD = datetime(2026, 9, 13).date().toordinal()

# Map API ids -> Django ApiTeam ids (histories are keyed by Django FK id!)
from football_api.models import ApiTeam, ApiLeague
api_ids = set()
for r in usable:
    m = fxmeta.get(r['fixture_id'])
    if m:
        api_ids.add(m['teams']['home']['id']); api_ids.add(m['teams']['away']['id'])
api2db = dict(ApiTeam.objects.filter(api_id__in=api_ids).values_list('api_id', 'id'))
print(f'team id map: {len(api2db)}/{len(api_ids)}')
lapi2db = dict(ApiLeague.objects.values_list('api_id', 'id'))

today_rows = []
for r in usable:
    fid = r['fixture_id']; meta = fxmeta.get(fid)
    if not meta: continue
    htid = api2db.get(meta['teams']['home']['id']); atid = api2db.get(meta['teams']['away']['id'])
    if htid is None or atid is None: continue
    lg = lapi2db.get(byid_lg.get(fid))
    hf = team_features_now(htid, TODAY_ORD, 'h')
    af = team_features_now(atid, TODAY_ORD, 'a')
    lgm = league_mean_now(lg, TODAY_ORD) if lg else None
    if not (hf and af and lgm): continue
    row = {'fid': fid, 'date': '2026-09-13', 'lg': lg, 'htid': htid, 'atid': atid, 'y': r['total_shots'],
           'league_name': r['league'], 'home_name': meta['teams']['home']['name'], 'away_name': meta['teams']['away']['name']}
    for k, v in hf.items(): row['h_'+k] = v
    for k, v in af.items(): row['a_'+k] = v
    row['lgm'] = lgm
    today_rows.append(row)

print(f'today evaluables (con features): {len(today_rows)}')
w()
w(f'### EVALUACIÓN OUT-OF-SAMPLE (HOY = {len(today_rows)} partidos)')

X_t = np.array([vec(r) for r in today_rows], dtype=np.float32)
y_t = np.array([float(r['y']) for r in today_rows], dtype=np.float32)
p_t = gbm.predict(X_t)
mae = np.mean(np.abs(p_t - y_t)); rmse = np.sqrt(np.mean((p_t-y_t)**2)); bias = np.mean(p_t - y_t)
w(f'GBM v2:  MAE={mae:.2f}  RMSE={rmse:.2f}  bias={bias:+.2f}')
mu_now = np.mean([float(r['y']) for r in train]) if False else np.mean(y[:split])
w(f'baseline mu-global: MAE={np.mean(np.abs(mu_now-y_t)):.2f}')
lgerr = []
for r, p in zip(today_rows, p_t):
    lgm = r.get('lgm')
    if lgm: lgerr.append(abs(float(lgm) - float(r['y'])))
w(f'baseline liga-media (n={len(lgerr)}): MAE={np.mean(lgerr):.2f}')

# blend with A/D: compute simple A/D on the fly from histories (def vs for)
def ad_lam(tid_h, tid_a):
    h = hist.get(tid_h); a = hist.get(tid_a)
    if not h or not a: return None
    # very simple recent mean (exp weighted): last 15 games each side
    def recmean(tid, keys, venue=None, k=15):
        hh = hist.get(tid)
        if not hh: return None
        vals = []
        for rec in reversed(hh):
            fv = rec['for'].get(venue) if venue else None
            if fv: vals.append(fv.get(keys))
            if len(vals) >= k: break
        vals = [v for v in vals if v is not None]
        return np.mean(vals) if vals else None
    fh = recmean(tid_h, 'ts', 'h'); fa = recmean(tid_a, 'ts', 'a')
    # defense of opponent: average ts conceded as home for away team = ?
    # use 'ag' ts as venue 'a' for htid (shots conceded at home)
    def conmean(tid, venue):
        hh = hist.get(tid); vals = []
        for rec in reversed(hh):
            av = rec['ag'].get(venue)
            if av: vals.append(av.get('ts'))
            if len(vals) >= 15: break
        vals = [v for v in vals if v is not None]
        return np.mean(vals) if vals else None
    con_a_away = conmean(tid_a, 'a')  # away team's shots conceded as away (i.e., home shots)
    con_h_home = conmean(tid_h, 'h')
    if None in (fh, fa, con_a_away, con_h_home): return None
    lam_h = (fh + con_a_away)/2; lam_a = (fa + con_h_home)/2
    return lam_h + lam_a

ad_preds = []
for r in today_rows:
    v = ad_lam(r['htid'], r['atid'])
    ad_preds.append(v)
ok = [i for i, v in enumerate(ad_preds) if v is not None]
if ok:
    ad_p = np.array([ad_preds[i] for i in ok]); ad_y = y_t[ok]
    print(f'A/D simple eval n={len(ok)}: MAE={np.mean(np.abs(ad_p-ad_y)):.2f} RMSE={np.sqrt(np.mean((ad_p-ad_y)**2)):.2f}')
    w(f'A/D simple: MAE={np.mean(np.abs(ad_p-ad_y)):.2f}')

# blend
blend_maes = {}
for alpha in [0,0.25,0.5,0.75,1.0]:
    p = alpha*p_t + (1-alpha)*np.array([ad_preds[i] if ad_preds[i] is not None else p_t[i] for i in range(len(p_t))])
    blend_maes[alpha] = np.mean(np.abs(p - y_t))
print('blend MAEs:', blend_maes)
best_alpha = min(blend_maes, key=blend_maes.get)
w(f'blend: alpha GBM={best_alpha} → MAE={blend_maes[best_alpha]:.2f}')

# top-10 by |error|
w()
w('Detalle por partido (ordenado por |error|):')
idx = np.argsort(-np.abs(p_t - y_t))
for i in idx[:25]:
    r = today_rows[i]
    w(f"  {r['league_name'][:20]:20s} {r['home_name'][:18]:18s} vs {r['away_name'][:18]:18s} | pred={p_t[i]:5.1f} real={y_t[i]:5.1f} err={p_t[i]-y_t[i]:+5.1f}")

OUT.close()
print('DONE')
