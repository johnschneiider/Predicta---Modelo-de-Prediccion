# -*- coding: utf-8 -*-
"""v2.2 — features extra: días de descanso, forma últimos 5, volatilidad; retrain + eval hoy."""
import os, sys, csv, json, pickle
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()
import numpy as np
from collections import defaultdict

R = '/var/www/predicta.com.co/scripts/remates_v2'
OUT = open(R + '/eval_v22.txt', 'w')
def w(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')

from datetime import datetime, timezone as dtz
w('MOTOR v2.2 — rest/form features', datetime.now(dtz.utc).isoformat())

fx_list = pickle.load(open(R + '/fx_list.pkl','rb'))

# histories for rest days (in fixture date order)
last_played = {}
rest_feats = {}
for d in fx_list:
    dt_ord = d['date'].date().toordinal()
    for tid in (d['htid'], d['atid']):
        prev = last_played.get(tid)
        rest_feats.setdefault(d['fid'], {})[tid] = (dt_ord - prev) if prev else None
        last_played[tid] = dt_ord

# last-5 raw / last-5 vs-expected (simple form)
recent = defaultdict(list)  # tid -> [(ord, ts)]
form = {}
for d in fx_list:
    dt_ord = d['date'].date().toordinal()
    f = {}
    for tid, venue in ((d['htid'],'h'), (d['atid'],'a')):
        rec = recent.get(tid, [])
        l5 = [ts for o, ts in rec[-5:]]
        f[tid] = (np.mean(l5) if l5 else None, np.std(l5) if len(l5)>=3 else None, len(l5))
        # vs conceded l5
    form[d['fid']] = f
    # update after
    recent[d['htid']].append((dt_ord, d['h']['ts']))
    recent[d['atid']].append((dt_ord, d['a']['ts']))

# load base features and append
rows = []
with open(R + '/features_all.csv') as fp:
    for r in csv.DictReader(fp): rows.append(r)

added = 0
for r in rows:
    fid = int(r['fid'])
    rf = rest_feats.get(fid, {})
    fm = form.get(fid, {})
    ht, at = int(r['htid']), int(r['atid'])
    r['h_rest'] = rf.get(ht); r['a_rest'] = rf.get(at)
    hf = fm.get(ht) or (None, None, 0); af = fm.get(at) or (None, None, 0)
    r['h_l5_mean'] = hf[0]; r['h_l5_std'] = hf[1]; r['h_l5_n'] = hf[2]
    r['a_l5_mean'] = af[0]; r['a_l5_std'] = af[1]; r['a_l5_n'] = af[2]
    added += 1
print('rows updated:', added)
keys = list(rows[0].keys())
with open(R + '/features_v22.csv','w',newline='') as fp:
    wr = csv.DictWriter(fp, fieldnames=keys); wr.writeheader()
    for r in rows: wr.writerow(r)
w('saved features_v22.csv')

# quick train/eval on val split
rows.sort(key=lambda r: r['date'])
n = len(rows); split = int(n*0.85)
base_cols = [k for k in rows[0].keys() if k not in ('fid','date','lg','htid','atid','y')]
def vecn(r):
    out = []
    for k in base_cols:
        v = r.get(k)
        try: out.append(float(v) if v not in (None,'','None') else np.nan)
        except: out.append(np.nan)
    return out
X = np.array([vecn(r) for r in rows], dtype=np.float32)
y = np.array([float(r['y']) for r in rows], dtype=np.float32)
from sklearn.ensemble import HistGradientBoostingRegressor
m = HistGradientBoostingRegressor(max_iter=600, learning_rate=0.05, max_depth=6, min_samples_leaf=40,
    l2_regularization=1.0, early_stopping=True, validation_fraction=0.1, random_state=7)
m.fit(X[:split], y[:split])
pv = m.predict(X[split:]); yv = y[split:]
w(f'v2.2 GBM val: MAE={np.mean(np.abs(pv-yv)):.3f} RMSE={np.sqrt(np.mean((pv-yv)**2)):.3f} bias={np.mean(pv-yv):+.3f}')
A = np.vstack([np.ones_like(pv), pv]).T
coef, *_ = np.linalg.lstsq(A, yv, rcond=None)
rec = coef[0] + coef[1]*pv
w(f'v2.2 recalculated: y={coef[0]:.3f}+{coef[1]:.3f}p  MAE={np.mean(np.abs(rec-yv)):.3f} bias={np.mean(rec-yv):+.3f}')

# save model + cols + calibration
import joblib
joblib.dump({'model': m, 'feat_cols': base_cols, 'calib': (float(coef[0]), float(coef[1])), 'version': 'v2.2'}, R + '/gbm_v22.pkl')
w('saved gbm_v22.pkl')
OUT.close()
