# -*- coding: utf-8 -*-
"""Paperbet SOT v2 — features leak-free para tiros a puerta (target: sot total).
Reusa fx_list.pkl de remates_v2 (37.946 partidos con stats de ambos equipos).
Exp-weighted half-life 120d por equipo (venue-split): sot for/against, ibox, xg, córners, posesión.
"""
import os, sys, pickle, csv
import numpy as np
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django; django.setup()
from collections import defaultdict
from datetime import date as ddate

OUT = '/var/www/predicta.com.co/scripts/paperbet'
HALF = 120.0
fx = pickle.load(open('/var/www/predicta.com.co/scripts/remates_v2/fx_list.pkl', 'rb'))
print('fixtures con stats:', len(fx))

hist = defaultdict(dict)  # tid -> {venue: {sw, sot_f, sot_a, ibox_f, xg_f, corn_f, poss_f}, last}
LSTATE = {}  # lid -> {sw, sot, ...}
LEAGUE_ACC = {}

def decay(d, days):
    if days > 0:
        f = 0.5 ** (days / HALF)
        for k in list(d):
            if isinstance(d[k], dict):
                for kk in d[k]: d[k][kk] *= f
            elif isinstance(d[k], float):
                d[k] *= f

def ensure(tid, venue):
    h = hist[tid]
    for v in (0, 1):
        h.setdefault(v, {'sw': 0.0, 'sot_f': 0.0, 'sot_a': 0.0, 'ibox_f': 0.0, 'xg_f': 0.0, 'corn_f': 0.0, 'poss_f': 0.0})
    return h

rows = []
for d in fx:
    dt = d['date']; ord_ = dt.toordinal()
    lid = d['lg']
    for tid, side in ((d['htid'], 0), (d['atid'], 1)):
        h = ensure(tid, side)
        if 'last' in h and h['last'] is not None:
            decay(h, ord_ - h['last'])
        h['last'] = ord_
    # features para este partido (estado PRE-partido)
    def tf(tid, venue):
        h = hist[tid]
        out = {}
        for v, vn in ((0, 'h'), (1, 'a')):
            dd = h[v]
            sw = dd['sw']
            out[f'{vn}_n'] = sw
            for k in ('sot_f', 'sot_a', 'ibox_f', 'xg_f', 'corn_f', 'poss_f'):
                out[f'{k}_{vn}'] = dd[k] / sw if sw > 1e-6 else None
        return out
    fh = tf(d['htid'], 0); fa = tf(d['atid'], 1)
    # liga
    st = LSTATE.get(lid)
    lf = {}
    if st:
        f = 0.5 ** ((ord_ - st['last']) / HALF)
        lf['lg_n'] = st['sw'] * f
        lf['lg_sot'] = st['sot'] * f / lf['lg_n'] if lf['lg_n'] > 1e-6 else None
        lf['lg_xg'] = st['xg'] * f / lf['lg_n'] if lf['lg_n'] > 1e-6 else None
    else:
        lf = {'lg_n': None, 'lg_sot': None, 'lg_xg': None}
    def _num(x):
        try: return float(x)
        except (TypeError, ValueError): return None
    sot_h, sot_a = _num(d['h'].get('sot')), _num(d['a'].get('sot'))
    if sot_h is None or sot_a is None:
        continue
    row = {'date': dt.isoformat(), 'lid': lid, 'htid': d['htid'], 'atid': d['atid'],
           'sot_h': sot_h, 'sot_a': sot_a}
    for k in ('h_n','a_n','sot_f_h','sot_a_h','ibox_f_h','xg_f_h','corn_f_h','poss_f_h',
              'sot_f_a','sot_a_a','ibox_f_a','xg_f_a','corn_f_a','poss_f_a'):
        row[k] = fh[k] if k in fh else fa[k]
    row.update(lf)
    rows.append(row)
    # actualizar estado POST (sin fuga)
    for tid, side, own, opp in ((d['htid'], 0, d['h'], d['a']), (d['atid'], 1, d['a'], d['h'])):
        h = ensure(tid, side)
        dd = h[side]
        dd['sw'] += 1.0
        def _num(x):
            try: return float(x)
            except (TypeError, ValueError): return None
        for k, v in (('sot_f', own.get('sot')), ('sot_a', opp.get('sot')), ('ibox_f', own.get('ibox')),
                     ('xg_f', own.get('xg')), ('corn_f', own.get('corn')), ('poss_f', own.get('poss'))):
            vv = _num(v)
            if vv is not None: dd[k] += vv
    st = LSTATE.get(lid)
    tot_sot = (sot_h or 0) + (sot_a or 0)
    xg_h, xg_a = _num(d['h'].get('xg')), _num(d['a'].get('xg'))
    if st is None:
        st = {'sw': 0.0, 'sot': 0.0, 'xg': 0.0, 'last': ord_}
        LSTATE[lid] = st
    if st['last'] is not None:
        f = 0.5 ** ((ord_ - st['last']) / HALF)
        st['sw'] *= f; st['sot'] *= f; st['xg'] *= f
    st['last'] = ord_
    st['sw'] += 1; st['sot'] += tot_sot
    if xg_h is not None and xg_a is not None: st['xg'] += (xg_h + xg_a)

print('filas SOT:', len(rows))
with open(OUT + '/features_sot.csv', 'w', newline='') as f:
    w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
    w.writeheader(); w.writerows(rows)
print('guardado features_sot.csv')
with open(OUT + '/sot_state.pkl', 'wb') as f:
    pickle.dump({'hist': hist, 'LSTATE': LSTATE, 'last_ord': fx[-1]['date'].toordinal()}, f)
print('estado SOT guardado (sot_state.pkl)')
