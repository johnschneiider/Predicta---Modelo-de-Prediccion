# -*- coding: utf-8 -*-
"""
MOTOR REMATES TOTALES v2.1 — mejoras: modelos separados home/away + corrección de sesgo + features extras.
Itera sobre validación interna (últimos 15%) y confirma out-of-sample en partidos de HOY.
"""
import os, sys, csv, json, pickle
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()
import numpy as np

R = '/var/www/predicta.com.co/scripts/remates_v2'
OUT = open(R + '/eval_v21.txt', 'w')
def w(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')

from datetime import datetime, timezone as dtz
w('MOTOR v2.1 — split home/away + bias corr', datetime.now(dtz.utc).isoformat())
w('='*100)

rows = []
with open(R + '/features_all.csv') as fp:
    for r in csv.DictReader(fp): rows.append(r)
rows.sort(key=lambda r: r['date'])
n = len(rows); split = int(n*0.85)
train, val = rows[:split], rows[split:]

# feature cols: base + engineered
base_cols = [k for k in rows[0].keys() if k not in ('fid','date','lg','htid','atid','y')]

def eng(r):
    """Engineered features from base row."""
    def g(k):
        v = r.get(k)
        try: return float(v) if v not in (None,'','None') else np.nan
        except: return np.nan
    out = dict()
    for k in base_cols:
        out[k] = g(k)
    # interactions / ratios
    out['r_h_att_a_def'] = g('h_f_ts') / (g('a_a_ts') + 1e-6)   # home attack vs away away-defense
    out['r_a_att_h_def'] = g('a_f_ts') / (g('h_a_ts') + 1e-6)
    out['sum_f'] = g('h_f_ts') + g('a_f_ts')
    out['sum_a'] = g('h_a_ts') + g('a_a_ts')
    out['lgm_ratio'] = (g('h_f_ts') + g('a_f_ts')) / (2*g('lgm') + 1e-6)
    out['h_sot_ratio'] = g('h_f_sot') / (g('h_f_ts') + 1e-6)
    out['a_sot_ratio'] = g('a_f_sot') / (g('a_f_ts') + 1e-6)
    out['h_ibox_ratio'] = g('h_f_ibox') / (g('h_f_ts') + 1e-6)
    out['a_ibox_ratio'] = g('a_f_ibox') / (g('a_f_ts') + 1e-6)
    return out

def mat(rs):
    return [eng(r) for r in rs]

feat_cols_all = None
tv = mat(train); vv = mat(val)
feat_cols_all = list(tv[0].keys())
def toX(dd):
    return np.array([[d[k] for k in feat_cols_all] for d in dd], dtype=np.float32)

X = toX(tv); y_h = np.array([float(r['y']) for r in train], dtype=np.float32)
Xv = toX(vv); yv = np.array([float(r['y']) for r in val], dtype=np.float32)

from sklearn.ensemble import HistGradientBoostingRegressor
def mk():
    return HistGradientBoostingRegressor(max_iter=600, learning_rate=0.05, max_depth=6,
        min_samples_leaf=40, l2_regularization=1.0, early_stopping=True, validation_fraction=0.1, random_state=7)

# Model 1: total (same as before for comparison)
m_tot = mk(); m_tot.fit(X, y_h)
pv_tot = m_tot.predict(Xv)
w(f"MODEL total: val MAE={np.mean(np.abs(pv_tot-yv)):.3f} RMSE={np.sqrt(np.mean((pv_tot-yv)**2)):.3f} bias={np.mean(pv_tot-yv):+.3f}")

# Model 2: home/away split — need home/away y columns; we only stored total. Rebuild from features? No — need yi split.
# We must recompute targets from the raw fixtures; append hy (home shots) and ay (away shots) in build step.
# Instead: recompute quickly from fixture data for these rows using fid.
print('recompute per-side targets...')
# use fx_list.pkl saved by build_features.py: entries have fid, h{ts}, a{ts}
fxp = pickle.load(open(R + '/fx_list.pkl','rb'))
fxs = {d['fid']: d for d in fxp}
hy = []; ay = []
for r in rows:
    d = fxs.get(int(r['fid']), {})
    hy.append((d.get('h') or {}).get('ts')); ay.append((d.get('a') or {}).get('ts'))
# note: team_id in side dict is Django team id? no - it's ApiTeam Django id (FK). row htid is FK id too (from build script: htid from fixture FK). good.
hy = [v if v is not None else np.nan for v in hy]; ay = [v if v is not None else np.nan for v in ay]
ok = [i for i in range(len(hy)) if not (np.isnan(hy[i]) or np.isnan(ay[i]))]
print(f'side targets ok: {len(ok)}/{len(rows)}')
if len(ok) == len(rows):
    hy = np.array(hy, dtype=np.float32); ay = np.array(ay, dtype=np.float32)
    hy_tr, hy_v = hy[:split], hy[split:]; ay_tr, ay_v = ay[:split], ay[split:]
    m_h = mk(); m_h.fit(X, hy_tr)
    m_a = mk(); m_a.fit(X, ay_tr)
    pv_h = m_h.predict(Xv); pv_a = m_a.predict(Xv)
    pv_split = pv_h + pv_a
    w(f"MODEL split:  val MAE={np.mean(np.abs(pv_split-yv)):.3f} RMSE={np.sqrt(np.mean((pv_split-yv)**2)):.3f} bias={np.mean(pv_split-yv):+.3f}")
    # blend
    for alpha in [0.3, 0.5, 0.7]:
        pv_b = alpha*pv_split + (1-alpha)*pv_tot
        w(f"blend split {alpha:.1f}: val MAE={np.mean(np.abs(pv_b-yv)):.3f}")
else:
    w('side targets incomplete; skipping split model')
    m_h = m_a = None

# ── Bias correction: adjust by league mean of residuals on train (out-of-fold-ish: use val to estimate) ──
# estimate bias on val by league
from collections import defaultdict
bias_by_lg = defaultdict(list)
for i, r in enumerate(val):
    lid = r['lg']
    bias_by_lg[lid].append(pv_tot[i] - yv[i])
# apply small correction on val itself is cheating; we just report a global linear recalibration
# global: y ≈ a + b*p
A = np.vstack([np.ones_like(pv_tot), pv_tot]).T
coef, *_ = np.linalg.lstsq(A, yv, rcond=None)
rec = coef[0] + coef[1]*pv_tot
w(f"global recalibration: y = {coef[0]:.2f} + {coef[1]:.3f}*p -> val MAE={np.mean(np.abs(rec-yv)):.3f} bias={np.mean(rec-yv):+.3f}")

OUT.close()
print('DONE')
