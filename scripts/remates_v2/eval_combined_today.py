# -*- coding: utf-8 -*-
"""Eval COMBINADA hoy 13-sep: base (110) + ampliación (7) = 117 partidos OOS."""
import os, sys, json, pickle, joblib, logging
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django; django.setup()
import numpy as np
from collections import defaultdict
from datetime import datetime
from football_api.models import ApiTeam, ApiLeague
from football_data.models import League as FL
from ai_predictions.shots_prediction_model import shots_prediction_model
from ai_predictions.xg_shots_model import xg_shots_model
from difflib import SequenceMatcher
logging.disable(logging.INFO)

R = '/var/www/predicta.com.co/scripts/remates_v2'
base = json.load(open(R + '/today_ft_stats.json'))
extra = json.load(open(R + '/newft_stats_20260913.json'))
ftc = json.load(open(R + '/ft_covered.json'))
fxmeta = {f['fixture']['id']: f for f in ftc}
base_usable = [r for r in base.values() if r.get('total_shots') is not None and r.get('teams') and len(r['teams']) == 2]
extra_usable = [r for r in extra.values() if r.get('total_shots') is not None and r.get('teams') and len(r['teams']) == 2]

md = joblib.load(R + '/gbm_v23.pkl')
model, feat_cols, calib = md['model'], md['feat_cols'], md['calib']
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
def g(r, k):
    v = r.get(k)
    try: return float(v) if v not in (None,'','None') else np.nan
    except: return np.nan
def eng(r):
    out = {}
    for k in feat_cols: out[k] = g(r, k)
    out['lamH_a'] = 0.5*(g(r,'h_f_ts') + g(r,'a_a_ts'))
    out['lamA_a'] = 0.5*(g(r,'a_f_ts') + g(r,'h_a_ts'))
    out['lamT_a'] = out.get('lamH_a', np.nan) + out.get('lamA_a', np.nan)
    out['lamT_g'] = np.sqrt(np.maximum(0, g(r,'h_f_ts')*g(r,'a_a_ts'))) + np.sqrt(np.maximum(0, g(r,'a_f_ts')*g(r,'h_a_ts')))
    out['sotT_a'] = 0.5*(g(r,'h_f_sot') + g(r,'a_a_sot')) + 0.5*(g(r,'a_f_sot') + g(r,'h_a_sot'))
    out['iboxT_a'] = 0.5*(g(r,'h_f_ibox') + g(r,'a_a_ts')) + 0.5*(g(r,'a_f_ibox') + g(r,'h_a_ts'))
    out['cornT_a'] = 0.5*(g(r,'h_f_corn') + g(r,'a_a_ts')) + 0.5*(g(r,'a_f_corn') + g(r,'h_a_ts'))
    out['ratio_h'] = g(r,'h_f_ts') / (g(r,'a_a_ts') + 1e-6)
    out['ratio_a'] = g(r,'a_f_ts') / (g(r,'h_a_ts') + 1e-6)
    out['l5_ratio_h'] = g(r,'h_l5_mean') / (g(r,'h_f_ts') + 1e-6)
    out['l5_ratio_a'] = g(r,'a_l5_mean') / (g(r,'a_f_ts') + 1e-6)
    return out

api2db = dict(ApiTeam.objects.values_list('api_id','id'))
lapi2db = dict(ApiLeague.objects.values_list('api_id','id'))
TODAY_ORD = datetime(2026,9,13).date().toordinal()

def build(r, h_api, a_api, lg_api):
    htid = api2db.get(h_api); atid = api2db.get(a_api)
    if htid is None or atid is None: return None
    lg = lapi2db.get(lg_api)
    hf = team_features(htid, TODAY_ORD, 'h'); af = team_features(atid, TODAY_ORD, 'a')
    if not (hf and af): return None
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
    return row

# old motor
fd_leagues = list(FL.objects.all())
def find_fl(name):
    best = None
    for lg in fd_leagues:
        s = SequenceMatcher(None, (lg.name or '').lower(), name.lower()).ratio()
        if best is None or s > best[0]: best = (s, lg)
    return best[1] if best and best[0] > 0.6 else None
def old_predict(hn, an, lgn):
    lg = find_fl(lgn)
    if not lg: return None
    try:
        p1 = shots_prediction_model.predict_shots_total(hn, an, lg)
        p2 = xg_shots_model.predict_shots_total(hn, an, lg)
        vals = [p['prediction'] for p in (p1, p2) if p and p.get('prediction')]
        return sum(vals)/len(vals) if vals else None
    except Exception:
        return None

rowsA = []  # (name, v23, old, real)
for r in base_usable:
    meta = fxmeta.get(r['fixture_id'])
    if not meta: continue
    row = build(r, meta['teams']['home']['id'], meta['teams']['away']['id'], meta['league']['id'])
    if row is None: continue
    e = eng(row); X = np.array([[e.get(k, np.nan) for k in feat_cols]], dtype=np.float32)
    pt = calib[0] + calib[1]*float(model.predict(X)[0])
    op = old_predict(meta['teams']['home']['name'], meta['teams']['away']['name'], r['league'])
    rowsA.append((meta['teams']['home']['name'], pt, op, float(r['total_shots'])))

rowsB = []
for r in extra_usable:
    row = build(r, r.get('home_api_id'), r.get('away_api_id'), r.get('league_id'))
    if row is None: continue
    e = eng(row); X = np.array([[e.get(k, np.nan) for k in feat_cols]], dtype=np.float32)
    pt = calib[0] + calib[1]*float(model.predict(X)[0])
    nm = r.get('home', '?')
    op = old_predict(r.get('home',''), r.get('away',''), r.get('league',''))
    rowsB.append((nm, pt, op, float(r['total_shots'])))

def stats(rows, label):
    v23 = [rr for rr in rows if rr[1] is not None]
    old = [rr for rr in rows if rr[2] is not None]
    both = [rr for rr in rows if rr[2] is not None]
    print(f'\n=== {label} ===')
    if v23:
        errs = [abs(rr[1]-rr[3]) for rr in v23]
        print(f'v2.3: n={len(v23)} MAE={np.mean(errs):.2f} RMSE={np.sqrt(np.mean(np.array(errs)**2)):.2f} bias={np.mean([rr[1]-rr[3] for rr in v23]):+.2f} ±3:{(np.array(errs)<3).mean()*100:.0f}% ±5:{(np.array(errs)<5).mean()*100:.0f}%')
    if old:
        errs = [abs(rr[2]-rr[3]) for rr in old]
        print(f'VIEJO: n={len(old)} MAE={np.mean(errs):.2f} RMSE={np.sqrt(np.mean(np.array(errs)**2)):.2f} bias={np.mean([rr[2]-rr[3] for rr in old]):+.2f}')
    if v23 and old:
        eo = {rr[0]: abs(rr[2]-rr[3]) for rr in old}; en = {rr[0]: abs(rr[1]-rr[3]) for rr in v23 if rr[0] in eo}
        wins = sum(1 for k in en if en[k] < eo[k]); n = len(en)
        mej = (np.mean([eo[k] for k in en]) - np.mean([en[k] for k in en])) / np.mean([eo[k] for k in en]) * 100
        print(f'en común n={n}: mejora={mej:.1f}% | v2.3 gana {wins}/{n} ({wins/n*100:.0f}%)')

print('COMBINADA — HOY 13-sep — base(110) + ampliación(7)')
stats(rowsA, 'Base (DB-stored, ground truth API 20:10 UTC)')
stats(rowsB, 'Ampliación (BD NO los tenía; ground truth 21:10 UTC)')
stats(rowsA + rowsB, 'UNIÓN (todos los partidos de hoy testeados)')
