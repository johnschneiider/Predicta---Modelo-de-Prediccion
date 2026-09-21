# -*- coding: utf-8 -*-
"""v2.3 — features derivadas (estimadores A/D explícitos) + retrain + eval hoy."""
import os, sys, csv, json, pickle
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()
import numpy as np
from collections import defaultdict
from datetime import datetime, timezone as dtz

R = '/var/www/predicta.com.co/scripts/remates_v2'
OUT = open(R + '/eval_v23.txt', 'w')
def w(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')

def g(r, k):
    v = r.get(k)
    try: return float(v) if v not in (None,'','None') else np.nan
    except: return np.nan

BASE_COLS = None
def eng(r):
    """Derived features."""
    out = {}
    for k, v in r.items():
        if k in ('fid','date','lg','htid','atid','y'): continue
        out[k] = g(r, k)
    # explicit A/D estimators (geometric and arithmetic)
    out['lamH_a'] = 0.5*(g(r,'h_f_ts') + g(r,'a_a_ts'))
    out['lamA_a'] = 0.5*(g(r,'a_f_ts') + g(r,'h_a_ts'))
    out['lamT_a'] = out['lamH_a'] + out['lamA_a']
    out['lamT_g'] = np.sqrt(np.maximum(0, g(r,'h_f_ts')*g(r,'a_a_ts'))) + np.sqrt(np.maximum(0, g(r,'a_f_ts')*g(r,'h_a_ts')))
    out['sotT_a'] = 0.5*(g(r,'h_f_sot') + g(r,'a_a_sot')) + 0.5*(g(r,'a_f_sot') + g(r,'h_a_sot'))
    out['iboxT_a'] = 0.5*(g(r,'h_f_ibox') + g(r,'a_a_ts')) + 0.5*(g(r,'a_f_ibox') + g(r,'h_a_ts'))
    out['cornT_a'] = 0.5*(g(r,'h_f_corn') + g(r,'a_a_ts')) + 0.5*(g(r,'a_f_corn') + g(r,'h_a_ts'))
    out['ratio_h'] = g(r,'h_f_ts') / (g(r,'a_a_ts') + 1e-6)
    out['ratio_a'] = g(r,'a_f_ts') / (g(r,'h_a_ts') + 1e-6)
    out['l5_ratio_h'] = g(r,'h_l5_mean') / (g(r,'h_f_ts') + 1e-6)
    out['l5_ratio_a'] = g(r,'a_l5_mean') / (g(r,'a_f_ts') + 1e-6)
    return out

rows = []
with open(R + '/features_v22.csv') as fp:
    for r in csv.DictReader(fp): rows.append(r)
rows.sort(key=lambda r: r['date'])
n = len(rows); split = int(n*0.85)
eng_rows = [eng(r) for r in rows]
feat_cols = list(eng_rows[0].keys())
X = np.array([[e[k] for k in feat_cols] for e in eng_rows], dtype=np.float32)
y = np.array([float(r['y']) for r in rows], dtype=np.float32)

from sklearn.ensemble import HistGradientBoostingRegressor
m = HistGradientBoostingRegressor(max_iter=700, learning_rate=0.05, max_depth=6, min_samples_leaf=40,
    l2_regularization=1.0, early_stopping=True, validation_fraction=0.1, random_state=11)
m.fit(X[:split], y[:split])
pv = m.predict(X[split:]); yv = y[split:]
w(f'v2.3 GBM val: MAE={np.mean(np.abs(pv-yv)):.3f} RMSE={np.sqrt(np.mean((pv-yv)**2)):.3f} bias={np.mean(pv-yv):+.3f}')
A = np.vstack([np.ones_like(pv), pv]).T
coef, *_ = np.linalg.lstsq(A, yv, rcond=None)
rec = coef[0] + coef[1]*pv
w(f'v2.3 calib: y={coef[0]:.3f}+{coef[1]:.3f}p MAE={np.mean(np.abs(rec-yv)):.3f} bias={np.mean(rec-yv):+.3f}')

# train final on ALL data (v2.2 did this implicitly for today eval? No — today eval used model trained on 85%. For final save retrain on all.)
m_full = HistGradientBoostingRegressor(max_iter=700, learning_rate=0.05, max_depth=6, min_samples_leaf=40,
    l2_regularization=1.0, early_stopping=True, validation_fraction=0.1, random_state=11)
m_full.fit(X, y)
import joblib
joblib.dump({'model': m_full, 'feat_cols': feat_cols, 'calib': (float(coef[0]), float(coef[1])), 'version': 'v2.3'}, R + '/gbm_v23.pkl')
w('saved gbm_v23.pkl (trained on all data)')

# ── evaluate on today ──
# load histories and build today rows exactly like final_eval, then apply eng + predict
pj = pickle.load(open(R + '/histories.pkl','rb'))
hist, hist_lg = pj['hist'], pj['hist_lg']

def w_of(age): return 0.5 ** (age / 120.0)
def team_features(tid, dt_ord, venue):
    h = hist.get(tid)
    if not h: return None
    lo = dt_ord - 400
    keys_for = ['ts','sot','ibox','corn']; keys_ag = ['ts','sot','blk']
    sums = defaultdict(float); wsum = defaultdict(float); nn = 0
    for rec in reversed(h):
        if rec['ord'] < lo: break
        wt = w_of(dt_ord - rec['ord']); nn += 1
        fv = rec['for'].get(venue); av = rec['ag'].get(venue)
        if fv:
            for k in keys_for:
                sums['f_'+k] += wt*(fv.get(k) or 0); wsum['f_'+k] += wt
        if av:
            for k in keys_ag:
                sums['a_'+k] += wt*(av.get(k) or 0); wsum['a_'+k] += wt
    if nn < 2 or wsum['f_ts'] == 0: return None
    out = {k: (sums[k]/wsum[k] if wsum[k] > 0 else None) for k in sums}
    out['n'] = nn
    return out
def league_mean(lg, dt_ord):
    h = hist_lg.get(lg)
    if not h: return None
    lo = dt_ord - 400
    s = 0.0; wsum = 0.0
    for rec in reversed(h):
        if rec[0] < lo: break
        wt = w_of(dt_ord - rec[0]); s += wt*rec[1]; wsum += wt
    return s/wsum if wsum > 0 else None

gt = json.load(open(R + '/today_ft_stats.json'))
usable = [r for r in gt.values() if r.get('total_shots') is not None and r.get('teams') and len(r['teams']) == 2]
FT = json.load(open('/tmp/ft_covered.json'))
fxmeta = {f['fixture']['id']: f for f in FT}
byid_lg = {f['fixture']['id']: f['league']['id'] for f in FT}
from football_api.models import ApiTeam, ApiLeague
api2db = dict(ApiTeam.objects.filter(api_id__in=[i for mm in [fxmeta.get(r['fixture_id']) for r in usable] if mm for i in (mm['teams']['home']['id'], mm['teams']['away']['id'])]).values_list('api_id','id'))
lapi2db = dict(ApiLeague.objects.values_list('api_id','id'))
TODAY_ORD = datetime(2026,9,13).date().toordinal()

today_rows = []
for r in usable:
    fid = r['fixture_id']; meta = fxmeta.get(fid)
    if not meta: continue
    htid = api2db.get(meta['teams']['home']['id']); atid = api2db.get(meta['teams']['away']['id'])
    if htid is None or atid is None: continue
    lg = lapi2db.get(byid_lg.get(fid))
    hf = team_features(htid, TODAY_ORD, 'h'); af = team_features(atid, TODAY_ORD, 'a')
    lgm = league_mean(lg, TODAY_ORD) if lg else None
    if not (hf and af): continue
    row = {'fid': fid, 'lg': lg, 'htid': htid, 'atid': atid, 'y': r['total_shots'], 'league_name': r['league'],
           'home_name': meta['teams']['home']['name'], 'away_name': meta['teams']['away']['name']}
    for k, v in hf.items(): row['h_'+k] = v
    for k, v in af.items(): row['a_'+k] = v
    row['lgm'] = lgm
    lh = hist.get(htid) or []; la = hist.get(atid) or []
    last_h = lh[-1]['ord'] if lh else None; last_a = la[-1]['ord'] if la else None
    row['h_rest'] = (TODAY_ORD - last_h) if last_h else None
    row['a_rest'] = (TODAY_ORD - last_a) if last_a else None
    l5h = [rec['for'].get('h', {}).get('ts') for rec in reversed(lh) if rec['for'].get('h')][:5]
    l5a = [rec['for'].get('a', {}).get('ts') for rec in reversed(la) if rec['for'].get('a')][:5]
    l5h = [x for x in l5h if x is not None]; l5a = [x for x in l5a if x is not None]
    row['h_l5_mean'] = np.mean(l5h) if l5h else None
    row['h_l5_std'] = np.std(l5h) if len(l5h) >= 3 else None
    row['h_l5_n'] = len(l5h)
    row['a_l5_mean'] = np.mean(l5a) if l5a else None
    row['a_l5_std'] = np.std(l5a) if len(l5a) >= 3 else None
    row['a_l5_n'] = len(l5a)
    today_rows.append(row)

te = [eng(r) for r in today_rows]
Xt = np.array([[e.get(k, np.nan) for k in feat_cols] for e in te], dtype=np.float32)
yt = np.array([float(r['y']) for r in today_rows], dtype=np.float32)
pt_raw = m.predict(Xt)  # use split-trained model for honest eval
pt_cal = coef[0] + coef[1]*pt_raw
err = np.abs(pt_cal - yt)
w()
w(f'### v2.3 OUT-OF-SAMPLE HOY ({len(today_rows)} partidos)')
w(f'raw MAE={np.mean(np.abs(pt_raw-yt)):.3f} | calibrado MAE={err.mean():.3f} RMSE={np.sqrt((err**2).mean()):.3f} bias={np.mean(pt_cal-yt):+.3f}')
w(f'baseline global 25.25: {np.mean(np.abs(25.25-yt)):.3f} | liga: {np.mean([abs(float(r["lgm"])-float(r["y"])) for r in today_rows if r.get("lgm")]):.3f}')
w(f'±3: {(err<3).mean()*100:.0f}% | ±5: {(err<5).mean()*100:.0f}%')
idx = np.argsort(-err)
w('Top-10 errores:')
for i in idx[:10]:
    r = today_rows[i]
    w(f"  {r['league_name'][:20]:20s} {r['home_name'][:16]:16s} vs {r['away_name'][:16]:16s} | pred={pt_cal[i]:5.1f} real={yt[i]:5.1f} err={pt_cal[i]-yt[i]:+5.1f}")
OUT.close()
print('DONE')
