# -*- coding: utf-8 -*-
"""
MOTOR REMATES TOTALES v2 — PASO 1: FEATURES LEAK-FREE.

Construye features por partido usando SOLO información anterior a la fecha del partido.
Fuentes: football_api.TeamFixtureStat + ApiFixture (BD, pre-hoy).
Salida:
  scripts/remates_v2/features_all.csv   (todos los partidos, con fecha)
  (hoy se añade aparte en la evaluación)
"""
import os, sys, django, csv, math, pickle
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
django.setup()

import numpy as np
from collections import defaultdict
from bisect import bisect_left

print('Cargando fixtures/stats...')
from football_api.models import TeamFixtureStat

# fixture-level: gather both sides
# For memory efficiency, iterate ordered by date
q = (TeamFixtureStat.objects
     .filter(total_shots__isnull=False)
     .select_related('fixture')
     .order_by('fixture__date')
     .values_list('fixture__api_id','fixture__date','fixture__league_id','fixture__home_team_id','fixture__away_team_id',
                  'team_id','total_shots','shots_on_goal','shots_insidebox','blocked_shots','corner_kicks','expected_goals','ball_possession'))
print('iterando...')
fx = {}
for fid, date, lg, htid, atid, tid, ts, sot, ibox, blk, corn, xg, poss in q.iterator(chunk_size=5000):
    d = fx.get(fid)
    if d is None:
        d = {'fid': fid, 'date': date, 'lg': lg, 'htid': htid, 'atid': atid, 'h': {}, 'a': {}}
        fx[fid] = d
    side = 'h' if tid == htid else 'a'
    if side == 'a' and tid != atid:  # inconsistent guard
        continue
    d[side] = dict(ts=ts, sot=sot, ibox=ibox, blk=blk, corn=corn, xg=xg, poss=poss)
fx_list = [d for d in fx.values() if d['h'].get('ts') is not None and d['a'].get('ts') is not None]
fx_list.sort(key=lambda d: d['date'])
print(f'partidos completos: {len(fx_list)} | rango: {fx_list[0]["date"].date()} → {fx_list[-1]["date"].date()}')

with open('/var/www/predicta.com.co/scripts/remates_v2/fx_list.pkl','wb') as f:
    pickle.dump(fx_list, f)

# ── Historiales por equipo (para features exp-weighted) ──
# history[team] = list of (date_ordinal, dict for, against) — both venues kept
HALF_LIFE = 120.0   # días
def w_of(age_days): return 0.5 ** (age_days / HALF_LIFE)

hist = defaultdict(list)  # tid -> list of dicts {ord, for:{venue:vals}, ag:{venue:vals}}
feat_rows = []
LEAGUE_ACC = {}

def team_features(tid, dt_ord, venue, hist):
    """Exp-weighted averages for team, venue-split + overall."""
    h = hist.get(tid)
    if not h: return None
    acc = {}
    # only look back 400 days
    lo = dt_ord - 400
    # iterate from the end (most recent) until older than 400d
    keys_for = ['ts','sot','ibox','corn']
    keys_ag  = ['ts','sot','blk']
    sums = defaultdict(float); wsum = defaultdict(float); n = 0
    for rec in reversed(h):
        if rec['ord'] < lo: break
        age = dt_ord - rec['ord']
        wt = w_of(age)
        n += 1
        fv = rec['for'].get(venue)
        av = rec['ag'].get(venue)
        if fv:
            for k in keys_for: sums['f_'+k] += wt * (fv.get(k) or 0); wsum['f_'+k] += wt
            sums['f_ts_v'] += wt * (fv.get('ts') or 0); wsum['f_ts_v'] += wt
        if av:
            for k in keys_ag: sums['a_'+k] += wt * (av.get(k) or 0); wsum['a_'+k] += wt
    if n < 3 or wsum['f_ts'] == 0: return None
    out = {}
    for k in list(sums.keys()):
        out[k] = sums[k] / wsum[k] if wsum[k] > 0 else None
    out['n'] = n
    return out

def league_mean(lg, dt_ord, hist_lg):
    h = hist_lg.get(lg)
    if not h: return None
    lo = dt_ord - 400
    s = 0.0; wsum = 0.0
    for rec in reversed(h):
        if rec[0] < lo: break
        wt = w_of(dt_ord - rec[0])
        s += wt * rec[1]; wsum += wt
    return s / wsum if wsum > 0 else None

hist_lg = defaultdict(list)  # lg -> [(ord, tot_shots)]

print('Construyendo features (esto tarda un poco)...')
cnt = 0
for d in fx_list:
    dt = d['date']; dt_ord = dt.date().toordinal()
    hf = team_features(d['htid'], dt_ord, 'h', hist)
    af = team_features(d['atid'], dt_ord, 'a', hist)
    lgm = league_mean(d['lg'], dt_ord, hist_lg)
    hts = d['h']['ts']; ats = d['a']['ts']
    if hf and af and lgm:
        row = {'fid': d['fid'], 'date': dt.date().isoformat(), 'lg': d['lg'], 'htid': d['htid'], 'atid': d['atid'],
               'y': hts + ats}
        for k, v in hf.items(): row['h_'+k] = v
        for k, v in af.items(): row['a_'+k] = v
        row['lgm'] = lgm
        feat_rows.append(row)
        cnt += 1
    # append to histories AFTER feature computation (leak-free)
    hist[d['htid']].append({'ord': dt_ord, 'for': {'h': d['h']}, 'ag': {'h': {'ts': ats, 'sot': d['a'].get('sot'), 'blk': d['a'].get('blk')}}})
    hist[d['atid']].append({'ord': dt_ord, 'for': {'a': d['a']}, 'ag': {'a': {'ts': hts, 'sot': d['h'].get('sot'), 'blk': d['h'].get('blk')}}})
    hist_lg[d['lg']].append((dt_ord, hts + ats))

print(f'filas con features: {cnt}')
# save
keys = list(feat_rows[0].keys())
with open('/var/www/predicta.com.co/scripts/remates_v2/features_all.csv','w',newline='') as fp:
    wr = csv.DictWriter(fp, fieldnames=keys)
    wr.writeheader()
    for r in feat_rows: wr.writerow(r)
print('guardado features_all.csv')

# save histories for reuse (today features)
with open('/var/www/predicta.com.co/scripts/remates_v2/histories.pkl','wb') as f:
    pickle.dump({'hist': dict(hist), 'hist_lg': dict(hist_lg)}, f)
print('guardado histories.pkl')
