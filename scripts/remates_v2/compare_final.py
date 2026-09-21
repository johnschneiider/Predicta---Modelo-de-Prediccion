# -*- coding: utf-8 -*-
"""
PRUEBA COMPARATIVA FINAL — motor viejo vs v2.3 vs baselines, en los 110 partidos de HOY.
Además: sanity de edge vía simulación de apuestas a líneas de mercado plausibles
(no tenemos líneas reales de partidos terminados; usamos líneas típicas centradas en λ_mercado
estimado si estuviera; sin embargo SÍ podemos usar los partidos que tengan línea registrada en
shadow_ledger + los 3 captures).
"""
import os, sys, csv, json, pickle, joblib
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()
import numpy as np
from datetime import datetime, timezone as dtz
from collections import defaultdict

R = '/var/www/predicta.com.co/scripts/remates_v2'
OUT = open(R + '/compare_final.txt', 'w')
def w(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')

w('COMPARATIVA FINAL — HOY 13-sep (110 partidos con ground truth API)', datetime.now(dtz.utc).isoformat())
w('='*100)

# ── 1. OLD MOTOR on today's matches (using its own pipeline: shots_prediction + xg_shots) ──
from football_api.models import ApiFixture, ApiTeam, ApiLeague, TeamFixtureStat
gt = json.load(open(R + '/today_ft_stats.json'))
usable = [r for r in gt.values() if r.get('total_shots') is not None and r.get('teams') and len(r['teams']) == 2]
FT = json.load(open('/tmp/ft_covered.json'))
fxmeta = {f['fixture']['id']: f for f in FT}

# The old pipeline needs football_data.Match name lookup; ApiTeam names are what we have.
# old model used football_data.Match (legacy) names. For a fair test, call via name if possible:
from football_data.models import League as FL, Match as FM
from ai_predictions.shots_prediction_model import shots_prediction_model
from ai_predictions.xg_shots_model import xg_shots_model

# league matching: ApiLeague name -> football_data.League by name approx
from difflib import SequenceMatcher
fd_leagues = list(FL.objects.all())
def find_fl(name):
    best = None
    for lg in fd_leagues:
        s = SequenceMatcher(None, (lg.name or '').lower(), name.lower()).ratio()
        if best is None or s > best[0]: best = (s, lg)
    return best[1] if best and best[0] > 0.6 else None

def old_predict(home_name, away_name, lgn):
    lg = find_fl(lgn)
    if not lg: return None
    try:
        p1 = shots_prediction_model.predict_shots_total(home_name, away_name, lg)
        p2 = xg_shots_model.predict_shots_total(home_name, away_name, lg)
        vals = [p['prediction'] for p in (p1, p2) if p and p.get('prediction')]
        return sum(vals)/len(vals) if vals else None
    except Exception:
        return None

import logging
logging.disable(logging.INFO)
old_preds = []
for r in usable:
    meta = fxmeta.get(r['fixture_id'])
    if not meta: old_preds.append(None); continue
    ln = r['league']
    v = old_predict(meta['teams']['home']['name'], meta['teams']['away']['name'], ln)
    old_preds.append(v)
ok_old = [i for i, v in enumerate(old_preds) if v]
print(f'old motor evaluable en {len(ok_old)}/{len(usable)}')
if ok_old:
    errs = [abs(old_preds[i]-usable[i]['total_shots']) for i in ok_old]
    w(f'Motor VIEJO (shots+xg por nombre): n={len(ok_old)} MAE={np.mean(errs):.2f} RMSE={np.sqrt(np.mean(np.square(errs))):.2f} bias={np.mean([old_preds[i]-usable[i]["total_shots"] for i in ok_old]):+.2f}')

# ── 2. v2.3 on the same matches (reuse precomputed list) ──
# Load the saved eval rows via the same module logic — faster: recompute from saved text? Just re-run prediction inline (load eval rows from a pickled snapshot if exists)
# We'll recompute using the exact same functions as remates_v2_v23.py — abbreviated copy.
md = joblib.load(R + '/gbm_v23.pkl')
model, feat_cols, calib = md['model'], md['feat_cols'], md['calib']
pj = pickle.load(open(R + '/histories.pkl', 'rb'))
hist, hist_lg = pj['hist'], pj['hist_lg']
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

api2db = dict(ApiTeam.objects.filter(api_id__in=[i for mm in [fxmeta.get(r['fixture_id']) for r in usable] if mm for i in (mm['teams']['home']['id'], mm['teams']['away']['id'])]).values_list('api_id','id'))
lapi2db = dict(ApiLeague.objects.values_list('api_id','id'))
byid_lg = {f['fixture']['id']: f['league']['id'] for f in FT}
TODAY_ORD = datetime(2026,9,13).date().toordinal()

def eng2(r):
    out = {}
    def g(k):
        v = r.get(k)
        try: return float(v) if v not in (None,'','None') else np.nan
        except: return np.nan
    for k in feat_cols:
        out[k] = g(k)
    out['lamH_a'] = 0.5*(g('h_f_ts') + g('a_a_ts'))
    out['lamA_a'] = 0.5*(g('a_f_ts') + g('h_a_ts'))
    out['lamT_a'] = out.get('lamH_a', np.nan) + out.get('lamA_a', np.nan)
    out['lamT_g'] = np.sqrt(np.maximum(0, g('h_f_ts')*g('a_a_ts'))) + np.sqrt(np.maximum(0, g('a_f_ts')*g('h_a_ts')))
    out['sotT_a'] = 0.5*(g('h_f_sot') + g('a_a_sot')) + 0.5*(g('a_f_sot') + g('h_a_sot'))
    out['iboxT_a'] = 0.5*(g('h_f_ibox') + g('a_a_ts')) + 0.5*(g('a_f_ibox') + g('h_a_ts'))
    out['cornT_a'] = 0.5*(g('h_f_corn') + g('a_a_ts')) + 0.5*(g('a_f_corn') + g('h_a_ts'))
    out['ratio_h'] = g('h_f_ts') / (g('a_a_ts') + 1e-6)
    out['ratio_a'] = g('a_f_ts') / (g('h_a_ts') + 1e-6)
    out['l5_ratio_h'] = g('h_l5_mean') / (g('h_f_ts') + 1e-6)
    out['l5_ratio_a'] = g('a_l5_mean') / (g('a_f_ts') + 1e-6)
    return out

v23 = []
for r in usable:
    fid = r['fixture_id']; meta = fxmeta.get(fid)
    if not meta: v23.append(None); continue
    htid = api2db.get(meta['teams']['home']['id']); atid = api2db.get(meta['teams']['away']['id'])
    if htid is None or atid is None: v23.append(None); continue
    lg = lapi2db.get(byid_lg.get(fid))
    hf = team_features(htid, TODAY_ORD, 'h'); af = team_features(atid, TODAY_ORD, 'a')
    if not (hf and af): v23.append(None); continue
    row = {}
    for k, v in hf.items(): row['h_'+k] = v
    for k, v in af.items(): row['a_'+k] = v
    row['lgm'] = league_mean(lg, TODAY_ORD) if lg else None
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
    e = eng2(row)
    X = np.array([[e.get(k, np.nan) for k in feat_cols]], dtype=np.float32)
    pr = float(model.predict(X)[0])
    v23.append(calib[0] + calib[1]*pr)

ok23 = [i for i, v in enumerate(v23) if v is not None]
if ok23:
    errs23 = [abs(v23[i]-usable[i]['total_shots']) for i in ok23]
    w(f'v2.3 (este motor):                n={len(ok23)} MAE={np.mean(errs23):.2f} RMSE={np.sqrt(np.mean(np.square(errs23))):.2f} bias={np.mean([v23[i]-usable[i]["total_shots"] for i in ok23]):+.2f}')

# common subset comparison
both = [i for i in ok_old if v23[i] is not None]
if both:
    eo = [abs(old_preds[i]-usable[i]['total_shots']) for i in both]
    en = [abs(v23[i]-usable[i]['total_shots']) for i in both]
    w()
    w(f'En común (n={len(both)}): VIEJO MAE={np.mean(eo):.2f} | v2.3 MAE={np.mean(en):.2f} | mejora={(np.mean(eo)-np.mean(en))/np.mean(eo)*100:.1f}%')
    # per match
    wins = sum(1 for i in range(len(both)) if en[i] < eo[i])
    w(f'v2.3 gana en {wins}/{len(both)} partidos ({wins/len(both)*100:.0f}%)')

# ── 3. simple summary ──
w()
w('RESUMEN PARA TOMAR DECISIONES:')
w(f'- motor viejo MAE (n={len(ok_old)}): {np.mean([abs(old_preds[i]-usable[i]["total_shots"]) for i in ok_old]):.2f}' if ok_old else '- motor viejo: no evaluable')
w(f'- motor v2.3 MAE (n={len(ok23)}): {np.mean(errs23):.2f}' if ok23 else '- v2.3: no evaluable')
OUT.close()
print('DONE')
