# -*- coding: utf-8 -*-
"""Eval el motor remates v2.3 en partidos de HOY terminados que la BD aún no tiene (ground truth API)."""
import os, sys, json, pickle, joblib
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django; django.setup()
import numpy as np
from collections import defaultdict
from datetime import datetime, timezone as dtz, timedelta
from football_api.client import ApiFootballClient
from football_api.models import ApiTeam, ApiLeague

R = '/var/www/predicta.com.co/scripts/remates_v2'
OUT = open(R + '/eval_newft_20260913.txt', 'w')
def w(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')
def g(r, k):
    v = r.get(k)
    try: return float(v) if v not in (None,'','None') else np.nan
    except: return np.nan
def eng(r):
    out = {}
    for k, v in r.items():
        if k in ('fid','date','lg','htid','atid','y'): continue
        out[k] = g(r, k)
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

prev = json.load(open(R + '/today_ft_stats.json'))
prev_ids = {int(k) for k in prev}
ftc = json.load(open(R + '/ft_covered.json'))
cov = {f['league']['id'] for f in ftc}

c = ApiFootballClient()
d = c.fixtures(date='2026-09-13')
resp = d.get('response', [])
w(f'fetch hoy: {len(resp)} fixtures | quota remaining={c.daily_remaining}')
FT = [f for f in resp if f['fixture']['status']['short'] in ('FT','AET','PEN')]
newFT = [f for f in FT if f['fixture']['id'] not in prev_ids and f['league']['id'] in cov]
w(f'FT hoy: {len(FT)} | nuevos (no en cache previa, ligas cubiertas): {len(newFT)}')

stats = {}
for f in newFT:
    fid = f['fixture']['id']
    try:
        sd = c.fixtures_statistics(fid)
    except Exception as e:
        print(fid, 'ERR', str(e)[:80]); continue
    teams = []
    for t in sd.get('response', []):
        st = {}
        for s_ in (t.get('statistics') or []):
            if s_['type'] in ('Total Shots','Shots on Goal'):
                st[s_['type']] = s_['value']
        teams.append({'team': t['team']['name'], 'home': t['team']['id']==f['teams']['home']['id'], 'stats': st})
    tot = None
    if len(teams)==2 and all(t['stats'].get('Total Shots') is not None for t in teams):
        tot = sum(int(t['stats']['Total Shots']) for t in teams)
    stats[fid] = {'fixture_id': fid, 'league': f['league']['name'], 'league_id': f['league']['id'],
                  'home': f['teams']['home']['name'], 'away': f['teams']['away']['name'],
                  'kickoff': f['fixture']['date'], 'teams': teams, 'total_shots': tot}
json.dump(stats, open(R + '/newft_stats_20260913.json','w'), ensure_ascii=False)
usable = {fid: r for fid, r in stats.items() if r.get('total_shots') is not None}
w(f'stats descargadas: {len(stats)} | con total_shots: {len(usable)} | sin stats: {len(stats)-len(usable)}')

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

api_ids = []
for f in newFT:
    api_ids += [f['teams']['home']['id'], f['teams']['away']['id']]
tmap = dict(ApiTeam.objects.filter(api_id__in=api_ids).values_list('api_id','id'))
lapi2db = dict(ApiLeague.objects.values_list('api_id','id'))

rows = []
skipped = []
for fid, r in usable.items():
    meta = next((ff for ff in newFT if ff['fixture']['id']==fid), None)
    if meta is None: skipped.append((fid,'no meta')); continue
    htid = tmap.get(meta['teams']['home']['id']); atid = tmap.get(meta['teams']['away']['id'])
    if htid is None or atid is None: skipped.append((fid,'team no mapeado')); continue
    lg = lapi2db.get(r['league_id'])
    try:
        kdt = datetime.fromisoformat(r['kickoff'].replace('Z','+00:00'))
    except Exception:
        kdt = datetime(2026,9,13, tzinfo=dtz.utc)
    ord_ = kdt.date().toordinal()
    hf = team_features(htid, ord_, 'h'); af = team_features(atid, ord_, 'a')
    if not (hf and af): skipped.append((fid,'sin historia')); continue
    lgm = league_mean(lg, ord_) if lg else None
    row = {'fid': fid, 'lg': lg, 'htid': htid, 'atid': atid, 'y': r['total_shots'],
           'league_name': r['league'], 'home_name': r['home'], 'away_name': r['away']}
    for k, v in hf.items(): row['h_'+k] = v
    for k, v in af.items(): row['a_'+k] = v
    row['lgm'] = lgm
    lh = hist.get(htid) or []; la = hist.get(atid) or []
    last_h = lh[-1]['ord'] if lh else None; last_a = la[-1]['ord'] if la else None
    row['h_rest'] = (ord_ - last_h) if last_h else None
    row['a_rest'] = (ord_ - last_a) if last_a else None
    l5h = [rec['for'].get('h', {}).get('ts') for rec in reversed(lh) if rec['for'].get('h')][:5]
    l5a = [rec['for'].get('a', {}).get('ts') for rec in reversed(la) if rec['for'].get('a')][:5]
    l5h = [x for x in l5h if x is not None]; l5a = [x for x in l5a if x is not None]
    row['h_l5_mean'] = np.mean(l5h) if l5h else None
    row['h_l5_std'] = np.std(l5h) if len(l5h) >= 3 else None
    row['h_l5_n'] = len(l5h)
    row['a_l5_mean'] = np.mean(l5a) if l5a else None
    row['a_l5_std'] = np.std(l5a) if len(l5a) >= 3 else None
    row['a_l5_n'] = len(l5a)
    rows.append(row)

w(f'evaluables: {len(rows)} | skipped: {len(skipped)} {skipped[:6]}')
if rows:
    te = [eng(r) for r in rows]
    X = np.array([[e.get(k, np.nan) for k in feat_cols] for e in te], dtype=np.float32)
    yt = np.array([float(r['y']) for r in rows])
    pt_raw = model.predict(X)
    pt = calib[0] + calib[1]*pt_raw
    err = pt - yt
    w()
    w('=== MOTOR v2.3 en partidos NUEVOS terminados hoy (no en BD; modelo no los vio) ===')
    w(f'n={len(rows)} | MAE={np.mean(np.abs(err)):.2f} | RMSE={np.sqrt(np.mean(err**2)):.2f} | bias={np.mean(err):+.2f}')
    w(f'±3: {(np.abs(err)<3).mean()*100:.0f}% | ±5: {(np.abs(err)<5).mean()*100:.0f}%')
    lg_err = [abs(float(r['lgm'])-float(r['y'])) for r in rows if r.get('lgm')]
    if lg_err: w(f'baseline liga-media: MAE={np.mean(lg_err):.2f} | baseline global 25.25: {np.mean(np.abs(25.25-yt)):.2f}')
    w()
    w('Partido | pred v2.3 | real | err')
    for i in np.argsort(-np.abs(err)):
        r = rows[i]
        w(f"  {r['league_name'][:22]:22s} {r['home_name'][:18]:18s} vs {r['away_name'][:18]:18s} | {pt[i]:5.1f} | {yt[i]:5.0f} | {err[i]:+5.1f}")
OUT.close()
print('DONE')
