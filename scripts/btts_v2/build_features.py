# -*- coding: utf-8 -*-
"""
MOTOR BTTS v2 — PASO 1: FEATURES LEAK-FREE (solo info anterior al partido).
Fuente: football_data.Match (fthg/ftag 100% cobertura, both_teams_score como target).
Historia por equipo/liga con medias exp-weight (half-life 120d) + forma last6 + H2H + liga.
Al final vuelca el estado (hist) a btts_state.pkl para predecir partidos de HOY sin sesgo.
"""
import os, sys, json, math, pickle, csv
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django; django.setup()
from datetime import date as ddate
from collections import defaultdict, deque
from football_data.models import Match, League

OUT = '/var/www/predicta.com.co/scripts/btts_v2'
HALF = 120.0
def w_of(days): return 0.5 ** (days / HALF)

# ---------- estado por equipo ----------
# hist[tkey] = {'sums': {k: (sum_w, sum_wv)}, 'last': deque[(date, gf, ga, bts, venue)]}
TEAM_KEYS = {}   # (league_id, name) -> tkey
def tkey(lid, name):
    k = (lid, name)
    if k not in TEAM_KEYS:
        t = len(TEAM_KEYS)
        TEAM_KEYS[k] = t
    return TEAM_KEYS[k]

hists = []      # per tkey
for _ in range(20000):  # prealloc hint
    pass
def get_hist(t):
    while len(hists) <= t: hists.append(None)
    if hists[t] is None:
        hists[t] = {
            # exp-weighted sums por venue (0=home,1=away) para gf, ga, bts, f_scored, cs
            's': {v: {'sw': 0.0, 'gf': 0.0, 'ga': 0.0, 'bts': 0.0, 'scored': 0.0, 'cs': 0.0, 'tot': 0.0}
                  for v in (0, 1)},
            'last': deque(maxlen=10),
            'last_date': None,
        }
    return hists[t]

LSTATE = {}  # lid -> {'sw':..,'gf':..,'ga':..,'bts':..,'tot':..,'n':..} exp sums global liga + n_last90
PAIR = defaultdict(list)  # (lid, hk, ak) -> list of (date_ord, bts, gfh, gfa)

def decay(sums, days):
    if days > 0:
        f = 0.5 ** (days / HALF)
        for v in (0, 1):
            d = sums[v]
            d['sw'] *= f; d['gf'] *= f; d['ga'] *= f; d['bts'] *= f; d['scored'] *= f; d['cs'] *= f; d['tot'] *= f

def add_match(t, ord_, venue, gf, ga, bts):
    h = get_hist(t)
    if h['last_date'] is not None:
        decay(h['s'], ord_ - h['last_date'])
    h['last_date'] = ord_
    d = h['s'][venue]
    d['sw'] += 1.0; d['gf'] += gf; d['ga'] += ga
    d['bts'] += (1.0 if bts else 0.0)
    d['scored'] += (1.0 if gf > 0 else 0.0)
    d['cs'] += (1.0 if ga == 0 else 0.0)
    d['tot'] += (gf + ga)
    h['last'].append((ord_, gf, ga, bts, venue))

def team_feats(t, ord_, venue):
    h = get_hist(t)
    out = {}
    for v, vn in ((0, 'h'), (1, 'a')):
        d = h['s'][v]
        sw = d['sw']
        out[f'{vn}_n'] = sw
        if sw >= 1e-6:
            out[f'gf_{vn}'] = d['gf'] / sw
            out[f'ga_{vn}'] = d['ga'] / sw
            out[f'bts_{vn}'] = d['bts'] / sw
            out[f'scored_{vn}'] = d['scored'] / sw
            out[f'cs_{vn}'] = d['cs'] / sw
            out[f'tot_{vn}'] = d['tot'] / sw
        else:
            for kk in ('gf', 'ga', 'bts', 'scored', 'cs', 'tot'):
                out[f'{kk}_{vn}'] = None
    # forma last6 (pts + goles)
    last = list(h['last'])
    if last:
        pts = 0; gf = 0; ga = 0
        for o, g, c, b, vv in last[-6:]:
            gf += g; ga += c
            pts += 3 if g > c else (1 if g == c else 0)
        out['form_pts'] = pts / max(1, len(last[-6:]))
        out['form_gf'] = gf / max(1, len(last[-6:]))
        out['form_ga'] = ga / max(1, len(last[-6:]))
        out['rest'] = ord_ - last[-1][0]
    else:
        out['form_pts'] = out['form_gf'] = out['form_ga'] = None
        out['rest'] = None
    return out

def league_feats(lid, ord_):
    st = LSTATE.get(lid)
    out = {}
    if st is None:
        return {k: None for k in ('lg_n','lg_gf','lg_ga','lg_bts','lg_tot','lg_n90','lg_bts90','lg_tot90')}
    # decay para el partido objetivo
    f = 0.5 ** ((ord_ - st['last']) / HALF) if st['last'] is not None else 0.0
    out['lg_n'] = st['sw'] * f
    if out['lg_n'] >= 1e-6:
        out['lg_gf'] = st['gf'] * f / out['lg_n']
        out['lg_ga'] = st['ga'] * f / out['lg_n']
        out['lg_bts'] = st['bts'] * f / out['lg_n']
        out['lg_tot'] = st['tot'] * f / out['lg_n']
    else:
        out['lg_gf'] = out['lg_ga'] = out['lg_bts'] = out['lg_tot'] = None
    # ventana 90 días
    w90 = [o for o in st['last90'] if o > ord_ - 90]
    out['lg_n90'] = len(w90)
    out['lg_bts90'] = st['bts90_sum'] / len(w90) if w90 else None
    out['lg_tot90'] = st['tot90_sum'] / len(w90) if w90 else None
    return out

def add_league(lid, ord_, gf, ga, bts):
    st = LSTATE.get(lid)
    if st is None:
        st = {'sw': 0.0, 'gf': 0.0, 'ga': 0.0, 'bts': 0.0, 'tot': 0.0, 'last': None, 'last90': deque(maxlen=2000), 'bts90_sum': 0.0, 'tot90_sum': 0.0}
        LSTATE[lid] = st
    if st['last'] is not None:
        f = 0.5 ** ((ord_ - st['last']) / HALF)
        st['sw'] *= f; st['gf'] *= f; st['ga'] *= f; st['bts'] *= f; st['tot'] *= f
    st['last'] = ord_
    st['sw'] += 1; st['gf'] += gf; st['ga'] += ga; st['bts'] += (1 if bts else 0); st['tot'] += (gf + ga)
    st['last90'].append(ord_); st['bts90_sum'] += (1 if bts else 0); st['tot90_sum'] += (gf + ga)

FEATS = ['h_n','a_n','gf_h','gf_a','ga_h','ga_a','bts_h','bts_a','scored_h','scored_a','cs_h','cs_a','tot_h','tot_a',
         'form_pts_h','form_gf_h','form_ga_h','form_pts_a','form_gf_a','form_ga_a','rest_h','rest_a',
         'lg_n','lg_gf','lg_ga','lg_bts','lg_tot','lg_n90','lg_bts90','lg_tot90',
         'h2h_n','h2h_bts','h2h_gfh','h2h_gfa']

print('Cargando partidos...')
q = (Match.objects.filter(fthg__isnull=False, ftag__isnull=False)
     .select_related('league')
     .order_by('date')
     .values_list('id','date','league_id','home_team','away_team','fthg','ftag'))
rows = []
n = 0
for mid, dt, lid, home, away, fthg, ftag in q.iterator(chunk_size=5000):
    ord_ = dt.toordinal()
    bts = 1 if (fthg > 0 and ftag > 0) else 0
    hk = tkey(lid, home); ak = tkey(lid, away)
    hh = get_hist(hk); ha = get_hist(ak)
    # decay hasta hoy
    for t, h in ((hk, hh), (ak, ha)):
        if h['last_date'] is not None:
            decay(h['s'], ord_ - h['last_date'])
            h['last_date'] = ord_ if h['last_date'] > ord_ else h['last_date']
    # league feats
    lf = league_feats(lid, ord_)
    # h2h
    pkey = (lid, hk, ak)
    plist = PAIR[pkey]
    h2h = [x for x in plist if x[0] > ord_ - 1095]  # 3 años
    h2h = h2h[-10:]
    if h2h:
        h2h_n = len(h2h); h2h_bts = sum(x[1] for x in h2h) / h2h_n
        h2h_gfh = sum(x[2] for x in h2h) / h2h_n; h2h_gfa = sum(x[3] for x in h2h) / h2h_n
    else:
        h2h_n = 0; h2h_bts = h2h_gfh = h2h_gfa = None
    # armar fila
    fh = team_feats(hk, ord_, 0); fa = team_feats(ak, ord_, 1)
    row = {'date': dt.isoformat(), 'lid': lid, 'home': home, 'away': away,
           'h_n': fh['h_n'], 'a_n': fa['a_n'],
           'gf_h': fh['gf_h'], 'gf_a': fa['gf_a'], 'ga_h': fh['ga_h'], 'ga_a': fa['ga_a'],
           'bts_h': fh['bts_h'], 'bts_a': fa['bts_a'], 'scored_h': fh['scored_h'], 'scored_a': fa['scored_a'],
           'cs_h': fh['cs_h'], 'cs_a': fa['cs_a'], 'tot_h': fh['tot_h'], 'tot_a': fa['tot_a'],
           'form_pts_h': fh['form_pts'], 'form_gf_h': fh['form_gf'], 'form_ga_h': fh['form_ga'],
           'form_pts_a': fa['form_pts'], 'form_gf_a': fa['form_gf'], 'form_ga_a': fa['form_ga'],
           'rest_h': fh['rest'], 'rest_a': fa['rest'],
           'lg_n': lf['lg_n'], 'lg_gf': lf['lg_gf'], 'lg_ga': lf['lg_ga'], 'lg_bts': lf['lg_bts'], 'lg_tot': lf['lg_tot'],
           'lg_n90': lf['lg_n90'], 'lg_bts90': lf['lg_bts90'], 'lg_tot90': lf['lg_tot90'],
           'h2h_n': h2h_n, 'h2h_bts': h2h_bts, 'h2h_gfh': h2h_gfh, 'h2h_gfa': h2h_gfa,
           'target': bts}
    rows.append(row)
    # actualizar estado (post-partido → no hay fuga)
    add_match(hk, ord_, 0, fthg, ftag, bts)
    add_match(ak, ord_, 1, ftag, fthg, bts)
    add_league(lid, ord_, fthg, ftag, bts)
    PAIR[pkey].append((ord_, bts, fthg, ftag))
    n += 1
    if n % 20000 == 0:
        print(f'{n} partidos... {dt}')

print(f'Total filas: {len(rows)}')
with open(OUT + '/features_btts.csv', 'w', newline='') as f:
    wcsv = csv.DictWriter(f, fieldnames=['date','lid','home','away'] + FEATS + ['target'])
    wcsv.writeheader()
    for r in rows:
        wcsv.writerow(r)

# dump estado para HOY
state = {'TEAM_KEYS': {f'{lid}|{name}': t for (lid, name), t in TEAM_KEYS.items()},
         'hists': hists, 'LSTATE': LSTATE,
         'PAIR': {f'{lid}|{hk}|{ak}': v for (lid, hk, ak), v in PAIR.items()},
         'last_date_ord': ddate(2026, 9, 13).toordinal()}
with open(OUT + '/btts_state.pkl', 'wb') as f:
    pickle.dump(state, f)
print('Estado guardado en btts_state.pkl')
print('last fechas:', sorted(LSTATE.items(), key=lambda x: -x[1]['last'])[:3])
