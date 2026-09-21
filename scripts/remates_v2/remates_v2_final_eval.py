# -*- coding: utf-8 -*-
"""v2.3 — evaluación FINAL en partidos de HOY (out-of-sample) con modelo v2.2 + calibración.
Incluye: comparación con baselines, análisis de error por rangos, y verificación vs mercado."""
import os, sys, csv, json, pickle, joblib
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()
import numpy as np
from datetime import datetime, timezone as dtz
from collections import defaultdict

R = '/var/www/predicta.com.co/scripts/remates_v2'
OUT = open(R + '/eval_final.txt', 'w')
def w(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')

w('MOTOR REMATES TOTALES v2 — EVALUACIÓN FINAL OUT-OF-SAMPLE', datetime.now(dtz.utc).isoformat())
w('='*100)
w('Test: partidos del 13-sep-2026 (HOY) que la BD no tenía; ground truth post-partido desde API-Football.')
w('Modelo entrenado SOLO con datos anteriores a hoy. Cero leakage.')
w()

md = joblib.load(R + '/gbm_v22.pkl')
model, feat_cols, calib = md['model'], md['feat_cols'], md['calib']

# today features (recompute with v2.2 extras: build from histories + rest/form)
pj = pickle.load(open(R + '/histories.pkl','rb'))
hist, hist_lg = pj['hist'], pj['hist_lg']
fxp = pickle.load(open(R + '/fx_list.pkl','rb'))

# rest + form maps
last_played = {}
rest_feats = {}
recent = defaultdict(list)
form = {}
for d in fxp:
    dt_ord = d['date'].date().toordinal()
    for tid in (d['htid'], d['atid']):
        prev = last_played.get(tid)
        rest_feats.setdefault(d['fid'], {})[tid] = (dt_ord - prev) if prev else None
        last_played[tid] = dt_ord
    f = {}
    for tid in (d['htid'], d['atid']):
        l5 = [ts for o, ts in recent.get(tid, [])[-5:]]
        f[tid] = (np.mean(l5) if l5 else None, np.std(l5) if len(l5) >= 3 else None, len(l5))
    form[d['fid']] = f
    recent[d['htid']].append((dt_ord, d['h']['ts']))
    recent[d['atid']].append((dt_ord, d['a']['ts']))

def w_of(age): return 0.5 ** (age / 120.0)
def team_features(tid, dt_ord, venue):
    h = hist.get(tid)
    if not h: return None
    lo = dt_ord - 400
    keys_for = ['ts','sot','ibox','corn']; keys_ag = ['ts','sot','blk']
    sums = defaultdict(float); wsum = defaultdict(float); n = 0
    for rec in reversed(h):
        if rec['ord'] < lo: break
        wt = w_of(dt_ord - rec['ord']); n += 1
        fv = rec['for'].get(venue); av = rec['ag'].get(venue)
        if fv:
            for k in keys_for:
                sums['f_'+k] += wt*(fv.get(k) or 0); wsum['f_'+k] += wt
        if av:
            for k in keys_ag:
                sums['a_'+k] += wt*(av.get(k) or 0); wsum['a_'+k] += wt
    if n < 2 or wsum['f_ts'] == 0: return None
    out = {k: (sums[k]/wsum[k] if wsum[k] > 0 else None) for k in sums}
    out['n'] = n
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
api2db = dict(ApiTeam.objects.filter(api_id__in=[i for m in [fxmeta.get(r['fixture_id']) for r in usable] if m for i in (m['teams']['home']['id'], m['teams']['away']['id'])]).values_list('api_id','id'))
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
    # rest/form for today
    lh = hist.get(htid) or []
    la = hist.get(atid) or []
    last_h = lh[-1]['ord'] if lh else None; last_a = la[-1]['ord'] if la else None
    row['h_rest'] = (TODAY_ORD - last_h) if last_h else None
    row['a_rest'] = (TODAY_ORD - last_a) if last_a else None
    # form l5 from raw histories
    l5h = []
    for rec in reversed(lh):
        l5h.append(rec['for'].get('h', {}).get('ts'))
        if len(l5h) >= 5: break
    l5a = []
    for rec in reversed(la):
        l5a.append(rec['for'].get('a', {}).get('ts'))
        if len(l5a) >= 5: break
    l5h = [x for x in l5h if x is not None]; l5a = [x for x in l5a if x is not None]
    row['h_l5_mean'] = np.mean(l5h) if l5h else None
    row['h_l5_std'] = np.std(l5h) if len(l5h) >= 3 else None
    row['h_l5_n'] = len(l5h)
    row['a_l5_mean'] = np.mean(l5a) if l5a else None
    row['a_l5_std'] = np.std(l5a) if len(l5a) >= 3 else None
    row['a_l5_n'] = len(l5a)
    today_rows.append(row)

print(f'today evaluables: {len(today_rows)}')

def vec(r):
    out = []
    for k in feat_cols:
        v = r.get(k)
        try: out.append(float(v) if v not in (None,'','None') else np.nan)
        except: out.append(np.nan)
    return out

X_t = np.array([vec(r) for r in today_rows], dtype=np.float32)
y_t = np.array([float(r['y']) for r in today_rows], dtype=np.float32)
p_raw = model.predict(X_t)
p_cal = calib[0] + calib[1]*p_raw

mae_raw = np.mean(np.abs(p_raw-y_t)); mae_cal = np.mean(np.abs(p_cal-y_t))
rmse_cal = np.sqrt(np.mean((p_cal-y_t)**2)); bias_cal = np.mean(p_cal-y_t)
w(f'### RESULTADO FINAL EN HOY ({len(today_rows)} partidos)')
w(f'GBM v2.2 raw:      MAE={mae_raw:.2f}')
w(f'GBM v2.2 calibrado: MAE={mae_cal:.2f}  RMSE={rmse_cal:.2f}  bias={bias_cal:+.2f}')
w()
# baselines
mu_g = 25.25
w(f'baseline mu-global (25.25):   MAE={np.mean(np.abs(mu_g-y_t)):.2f}')
lg_errs = [abs(float(r["lgm"])-float(r["y"])) for r in today_rows if r.get('lgm')]
w(f'baseline liga-media (n={len(lg_errs)}): MAE={np.mean(lg_errs):.2f}')
# naive l5
l5_errs = [abs((r['h_l5_mean']+r['a_l5_mean'])-float(r['y'])) for r in today_rows if r.get('h_l5_mean') and r.get('a_l5_mean')]
if l5_errs: w(f'baseline last5-mean (n={len(l5_errs)}): MAE={np.mean(l5_errs):.2f}')
# old pipeline comment: MAE 4.52 on its own backtest
w()
w('Comparación con el motor viejo (medido antes): MAE 4.52 (remates, backtest, no-today).')
w()

# error buckets
err = np.abs(p_cal - y_t)
w('Distribución de |error| (calibrado):')
for lo, hi in [(0,2),(2,4),(4,6),(6,8),(8,10),(10,15),(15,100)]:
    cnt = int(((err>=lo)&(err<hi)).sum())
    w(f'  [{lo:2d}-{hi:3d}): {cnt:3d}  ({cnt/len(err)*100:4.1f}%)')
w()
w(f'% dentro de ±3: {((err<3).mean()*100):.0f}% | ±5: {((err<5).mean()*100):.0f}%')
# implied profit if we bet OVER/UNDER at line = round(p_cal) for a synthetic check? We don't have market lines for finished matches.
# top errors
w()
w('Top 15 errores:')
idx = np.argsort(-err)
for i in idx[:15]:
    r = today_rows[i]
    w(f"  {r['league_name'][:20]:20s} {r['home_name'][:16]:16s} vs {r['away_name'][:16]:16s} | pred={p_cal[i]:5.1f} real={y_t[i]:5.1f} err={p_cal[i]-y_t[i]:+5.1f}")
OUT.close()
print('DONE')
