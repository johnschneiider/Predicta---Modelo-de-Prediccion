# -*- coding: utf-8 -*-
"""Paperbet — entrena los 3 motores independientes:
  goles_v2 (Poisson λ total goles) · sot_v2 (NegBin λ SOT) · x12_v2 (H/D/A)
Valida OOS 1-13 sep. Guarda pkls en scripts/paperbet/.
"""
import os, sys, json, pickle
import numpy as np
import pandas as pd
from scipy.stats import poisson, nbinom
from sklearn.ensemble import HistGradientBoostingRegressor, HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import roc_auc_score, brier_score_loss, accuracy_score

OUT = '/var/www/predicta.com.co/scripts/paperbet'
BTT = '/var/www/predicta.com.co/scripts/btts_v2'
FEATS = ['h_n','a_n','gf_h','gf_a','ga_h','ga_a','bts_h','bts_a','scored_h','scored_a','cs_h','cs_a','tot_h','tot_a',
         'form_pts_h','form_gf_h','form_ga_h','form_pts_a','form_gf_a','form_ga_a','rest_h','rest_a',
         'lg_n','lg_gf','lg_ga','lg_bts','lg_tot','lg_n90','lg_bts90','lg_tot90',
         'h2h_n','h2h_bts','h2h_gfh','h2h_gfa']

df = pd.read_csv(BTT + '/features_btts.csv', parse_dates=['date'])
df = df.dropna(subset=['gf_h','gf_a','bts_h','bts_a','lg_bts'])
# targets de Match (join por date+lid+home+away)
import sys as _s
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django; django.setup()
from football_data.models import Match
goals = {(m['date'].isoformat(), m['league_id'], m['home_team'], m['away_team']): (m['fthg'], m['ftag'])
         for m in Match.objects.exclude(fthg__isnull=True).values('date','league_id','home_team','away_team','fthg','ftag').iterator()}
df['fthg'] = [goals.get((r.date.strftime('%Y-%m-%d'), r.lid, r.home, r.away), (None, None))[0] for r in df.itertuples()]
df['ftag'] = [goals.get((r.date.strftime('%Y-%m-%d'), r.lid, r.home, r.away), (None, None))[1] for r in df.itertuples()]
df = df.dropna(subset=['fthg','ftag'])
df['tot'] = df['fthg'] + df['ftag']
df['res'] = np.where(df['fthg'] > df['ftag'], 0, np.where(df['fthg'] == df['ftag'], 1, 2))
print('filas match:', len(df))

tr = df[df.date < '2026-08-01']
cal = df[(df.date >= '2026-08-01') & (df.date < '2026-09-01')]
te = df[(df.date >= '2026-09-01') & (df.date < '2026-09-14')]
print(f'split: train {len(tr)} | cal {len(cal)} | test {len(te)}')

Xtr, ytr = tr[FEATS].astype(float), tr['tot'].values
Xcal = cal[FEATS].astype(float)
Xte, yte = te[FEATS].astype(float), te['tot'].values

# ── GOLES v2: λ Poisson ──
g_reg = HistGradientBoostingRegressor(loss='poisson', max_iter=300, learning_rate=0.06,
                                      max_leaf_nodes=31, l2_regularization=1.0, random_state=42)
g_reg.fit(Xtr, ytr)
lam_cal = g_reg.predict(Xcal)
lam_te = g_reg.predict(Xte)
mae = np.mean(np.abs(lam_te - yte))
print(f'\nGOLES v2: λ MAE OOS = {mae:.3f} | bias = {np.mean(lam_te - yte):+.3f} | media λ = {lam_te.mean():.3f} (real {yte.mean():.3f})')
for line in [1.5, 2.5, 3.5]:
    p_over = 1 - poisson.cdf(line, lam_te)  # P(total > line)
    pick_over = p_over >= 0.5
    wr = ((pick_over & (yte > line)) | (~pick_over & (yte <= line))).mean()
    n_over = pick_over.sum()
    print(f'  línea {line}: n_over={n_over:4d} n_under={len(te)-n_over:4d} | WR(mejor lado)={wr*100:.1f}% | media P_over={p_over.mean():.3f} real over={((yte>line).mean()):.3f}')

# ── X12 v2: multiclase ──
x_clf = HistGradientBoostingClassifier(max_iter=300, learning_rate=0.06, max_leaf_nodes=31,
                                       l2_regularization=1.0, random_state=42)
x_clf.fit(Xtr, tr['res'].values)
p_cal = x_clf.predict_proba(Xcal)
p_te = x_clf.predict_proba(Xte)
acc = accuracy_score(te['res'].values, p_te.argmax(1))
print(f'\nX12 v2: accuracy OOS = {acc*100:.1f}% | baseline home={ (te["res"].values==0).mean()*100:.1f}% | baseline liga={100*te["res"].mode().iloc[0] if False else max((te["res"].values==i).mean() for i in range(3))*100:.1f}%')
for i, nm in enumerate(['home','draw','away']):
    m = p_te.argmax(1) == i
    if m.sum():
        print(f'  pick {nm}: n={m.sum():4d} WR={((te["res"].values[m]==i)).mean()*100:.1f}% | media P={p_te[m,i].mean():.3f}')
# calibración home win
iso_h = IsotonicRegression(out_of_bounds='clip', y_min=0.02, y_max=0.98)
iso_h.fit(p_cal[:,0], (cal['res'].values==0).astype(int))
p_h_cal = iso_h.predict(p_te[:,0])
print(f'  home calibrada: AUC={roc_auc_score((te["res"].values==0).astype(int), p_h_cal):.3f} Brier={brier_score_loss((te["res"].values==0).astype(int), p_h_cal):.4f}')

# ── SOT v2: NegBin λ ──
SFEATS = ['h_n','a_n','sot_f_h','sot_a_h','ibox_f_h','xg_f_h','corn_f_h','poss_f_h',
          'sot_f_a','sot_a_a','ibox_f_a','xg_f_a','corn_f_a','poss_f_a','lg_n','lg_sot','lg_xg']
sdf = pd.read_csv(OUT + '/features_sot.csv', parse_dates=['date'])
sdf = sdf.dropna(subset=['sot_f_h','sot_a_h'])
sdf['tot_sot'] = sdf['sot_h'] + sdf['sot_a']
str_ = sdf[sdf.date < '2026-08-01']; scal = sdf[(sdf.date >= '2026-08-01') & (sdf.date < '2026-09-01')]; ste = sdf[(sdf.date >= '2026-09-01') & (sdf.date < '2026-09-14')]
print(f'\nSOT split: train {len(str_)} | cal {len(scal)} | test {len(ste)}')
s_reg = HistGradientBoostingRegressor(loss='poisson', max_iter=300, learning_rate=0.06,
                                      max_leaf_nodes=31, l2_regularization=1.0, random_state=42)
s_reg.fit(str_[SFEATS].astype(float), str_['tot_sot'].values)
lam_s_cal = s_reg.predict(scal[SFEATS].astype(float))
lam_s_te = s_reg.predict(ste[SFEATS].astype(float))
yt_s = ste['tot_sot'].values
PHI = 36.0
mae_s = np.mean(np.abs(lam_s_te - yt_s))
print(f'SOT v2: λ MAE OOS = {mae_s:.3f} | bias = {np.mean(lam_s_te-yt_s):+.3f} | media λ = {lam_s_te.mean():.3f} (real {yt_s.mean():.3f})')
for line in [7.5, 8.5, 9.5]:
    # NegBin: nbinom.cdf(k, n, p) con media=lam, var=lam+lam^2/phi → n=lam^2/phi? Ajuste: r=phi*lam/(lam+phi)... usar param: n=phi, p=phi/(phi+lam)
    p_over = 1 - nbinom.cdf(line, PHI, PHI/(PHI + lam_s_te))
    pick_over = p_over >= 0.5
    wr = ((pick_over & (yt_s > line)) | (~pick_over & (yt_s <= line))).mean()
    print(f'  línea {line}: n_over={pick_over.sum():4d} | WR(mejor lado)={wr*100:.1f}% | media P_over={p_over.mean():.3f} real over={(yt_s>line).mean():.3f}')

with open(OUT + '/engines.pkl', 'wb') as f:
    pickle.dump({'goles': g_reg, 'x12': x_clf, 'x12_iso_h': iso_h, 'sot': s_reg,
                 'FEATS': FEATS, 'SFEATS': SFEATS, 'PHI_SOT': PHI}, f)
print('\nMotores guardados: scripts/paperbet/engines.pkl')
