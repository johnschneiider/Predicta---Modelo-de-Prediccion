# -*- coding: utf-8 -*-
"""MOTOR BTTS v2 — PASO 2: GBM + calibración isotónica + eval OOS (1-13 sep)."""
import os, sys, json, pickle
import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score, brier_score_loss, accuracy_score

OUT = '/var/www/predicta.com.co/scripts/btts_v2'
FEATS = ['h_n','a_n','gf_h','gf_a','ga_h','ga_a','bts_h','bts_a','scored_h','scored_a','cs_h','cs_a','tot_h','tot_a',
         'form_pts_h','form_gf_h','form_ga_h','form_pts_a','form_gf_a','form_ga_a','rest_h','rest_a',
         'lg_n','lg_gf','lg_ga','lg_bts','lg_tot','lg_n90','lg_bts90','lg_tot90',
         'h2h_n','h2h_bts','h2h_gfh','h2h_gfa']

df = pd.read_csv(OUT + '/features_btts.csv', parse_dates=['date'])
df = df.dropna(subset=['gf_h','gf_a','bts_h','bts_a','lg_bts'])  # filas sin historia usable
print('filas:', len(df), '| base rate:', df['target'].mean().round(4))

tr = df[df.date < '2026-08-01']
cal = df[(df.date >= '2026-08-01') & (df.date < '2026-09-01')]
te = df[(df.date >= '2026-09-01') & (df.date < '2026-09-14')]
print('split: train', len(tr), '| cal', len(cal), '| test(1-13sep)', len(te))

Xtr, ytr = tr[FEATS].astype(float), tr['target'].values
Xcal, ycal = cal[FEATS].astype(float), cal['target'].values
Xte, yte = te[FEATS].astype(float), te['target'].values

model = HistGradientBoostingClassifier(max_iter=400, learning_rate=0.06, max_leaf_nodes=31,
                                       l2_regularization=1.0, random_state=42)
model.fit(Xtr, ytr)
p_raw_cal = model.predict_proba(Xcal)[:, 1]
iso = IsotonicRegression(out_of_bounds='clip', y_min=0.02, y_max=0.98)
iso.fit(p_raw_cal, ycal)
p_cal = iso.predict(p_raw_cal)

# eval test
p_raw = model.predict_proba(Xte)[:, 1]
p = iso.predict(p_raw)
auc = roc_auc_score(yte, p)
brier = brier_score_loss(yte, p)
acc = accuracy_score(yte, (p >= 0.5).astype(int))
print(f'\nTEST OOS 1-13 sep (n={len(te)}): AUC={auc:.4f} | Brier={brier:.4f} | WR@0.5={acc*100:.1f}%')
print(f'  base rate real: {yte.mean():.4f}')

# por lado
for th in [0.45, 0.5, 0.55]:
    sel = p >= th
    if sel.sum() >= 10:
        wr = yte[sel].mean()
        print(f'  Sí (P>={th}): n={sel.sum():4d} WR={wr*100:.1f}%')
    sel2 = p < 1 - th
    if sel2.sum() >= 10:
        wr2 = 1 - yte[sel2].mean()
        print(f'  No (P<{1-th:.2f}): n={sel2.sum():4d} WR={wr2*100:.1f}%')

# buckets calibración
print('\nCalibración test (buckets P):')
for lo in [0.35, 0.45, 0.55, 0.65, 0.75]:
    m = (p >= lo) & (p < lo + 0.10)
    if m.sum() >= 10:
        print(f'  P [{lo:.2f},{lo+0.10:.2f}): n={m.sum():4d} media={p[m].mean():.3f} real={yte[m].mean():.3f}')

with open(OUT + '/gbm_btts.pkl', 'wb') as f:
    pickle.dump({'model': model, 'iso': iso, 'feats': FEATS}, f)
print('\nModelo guardado: gbm_btts.pkl')

# importancia
imp = pd.Series(model.feature_importances_, index=FEATS).sort_values(ascending=False)
print('\nTop-12 features:'); print(imp.head(12).round(4))
