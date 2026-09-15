# -*- coding: utf-8 -*-
"""Paperbet CÓRNERS v2 — features leak-free (target: córners total del partido).
Fuente: fx_list.pkl (remates_v2). Exp-weighted half-life 120d por equipo (venue-split):
córners for/against, sot, ibox, xg, posesión. Estado final en corners_state.pkl (por team id).
"""
import os, sys, pickle, csv
import numpy as np
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django; django.setup()
from collections import defaultdict

OUT = '/var/www/predicta.com.co/scripts/paperbet'
HALF = 120.0
fx = pickle.load(open('/var/www/predicta.com.co/scripts/remates_v2/fx_list.pkl', 'rb'))
print('fixtures:', len(fx))

hist = defaultdict(dict)
LSTATE = {}

def _num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def decay(d, days):
    if days > 0:
        f = 0.5 ** (days / HALF)
        for k in list(d):
            if isinstance(d[k], dict):
                for kk in d[k]: d[k][kk] *= f
            elif isinstance(d[k], float):
                d[k] *= f

def ensure(tid):
    h = hist[tid]
    for v in (0, 1):
        h.setdefault(v, {'sw': 0.0, 'corn_f': 0.0, 'corn_a': 0.0, 'sot_f': 0.0, 'ibox_f': 0.0, 'xg_f': 0.0, 'poss_f': 0.0})
    return h

def tf(tid):
    h = hist[tid]
    out = {}
    for v, vn in ((0, 'h'), (1, 'a')):
        dd = h[v]
        sw = dd['sw']
        out[f'{vn}_n'] = sw
        for k in ('corn_f', 'corn_a', 'sot_f', 'ibox_f', 'xg_f', 'poss_f'):
            out[f'{k}_{vn}'] = dd[k] / sw if sw > 1e-6 else None
    return out

rows = []
for d in fx:
    dt = d['date']; ord_ = dt.toordinal(); lid = d['lg']
    for tid in (d['htid'], d['atid']):
        h = ensure(tid)
        if 'last' in h and h['last'] is not None:
            decay(h, ord_ - h['last'])
        h['last'] = ord_
    fh = tf(d['htid']); fa = tf(d['atid'])
    st = LSTATE.get(lid)
    if st:
        f = 0.5 ** ((ord_ - st['last']) / HALF)
        lg_n = st['sw'] * f
        lg_corn = st['corn'] * f / lg_n if lg_n > 1e-6 else None
        lg_xg = st['xg'] * f / lg_n if lg_n > 1e-6 else None
    else:
        lg_n = lg_corn = lg_xg = None
    ch, ca = _num(d['h'].get('corn')), _num(d['a'].get('corn'))
    if ch is None or ca is None:
        continue
    row = {'date': dt.isoformat(), 'lid': lid, 'htid': d['htid'], 'atid': d['atid'],
           'corn_h': ch, 'corn_a': ca}
    row.update(fh); row.update(fa)
    row['lg_n'] = lg_n; row['lg_corn'] = lg_corn; row['lg_xg'] = lg_xg
    rows.append(row)
    # post-update
    for tid, side, own, opp in ((d['htid'], 0, d['h'], d['a']), (d['atid'], 1, d['a'], d['h'])):
        h = ensure(tid)
        dd = h[side]
        dd['sw'] += 1.0
        for k, v in (('corn_f', own.get('corn')), ('corn_a', opp.get('corn')), ('sot_f', own.get('sot')),
                     ('ibox_f', own.get('ibox')), ('xg_f', own.get('xg')), ('poss_f', own.get('poss'))):
            vv = _num(v)
            if vv is not None: dd[k] += vv
    if st is None:
        st = {'sw': 0.0, 'corn': 0.0, 'xg': 0.0, 'last': ord_}
        LSTATE[lid] = st
    f = 0.5 ** ((ord_ - st['last']) / HALF)
    st['sw'] *= f; st['corn'] *= f; st['xg'] *= f
    st['last'] = ord_
    st['sw'] += 1; st['corn'] += (ch + ca)
    xg_h, xg_a = _num(d['h'].get('xg')), _num(d['a'].get('xg'))
    if xg_h is not None and xg_a is not None: st['xg'] += (xg_h + xg_a)

print('filas corners:', len(rows))
with open(OUT + '/features_corners.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
with open(OUT + '/corners_state.pkl', 'wb') as f:
    pickle.dump({'hist': hist, 'LSTATE': LSTATE, 'last_ord': fx[-1]['date'].toordinal()}, f)
print('guardado features_corners.csv + corners_state.pkl')
