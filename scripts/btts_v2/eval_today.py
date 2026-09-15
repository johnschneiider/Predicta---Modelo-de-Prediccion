# -*- coding: utf-8 -*-
"""
MOTOR BTTS v2 — PASO 3: TEST DE HOY (14-sep). Partidos FT de API que NO están en BD (sin sesgo).
Compara: motor nuevo (GBM btts_v2) vs motor producción (enhanced_both_teams_score).
Score: P>=0.5 → Sí, else No. W/L contra resultado real. Winrate.
"""
import os, sys, json, pickle, difflib, unicodedata
import numpy as np
import pandas as pd
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django; django.setup()
from datetime import date as ddate, timedelta
from football_data.models import Match, League

OUT = '/var/www/predicta.com.co/scripts/btts_v2'
HALF = 120.0
def w_of(days): return 0.5 ** (days / HALF)

state = pickle.load(open(OUT + '/btts_state.pkl', 'rb'))
TEAM_KEYS = {k: v for k, v in state['TEAM_KEYS'].items()}
hists = state['hists']; LSTATE = state['LSTATE']
PAIR = state['PAIR']
LAST_ORD = state['last_date_ord']

def norm(s):
    s = unicodedata.normalize('NFKD', s)
    return ''.join(c for c in s.lower() if c.isalnum())

# ---- replicar funciones de features ----
def team_feats(t, ord_):
    h = hists[t]
    out = {}
    for v, vn in ((0, 'h'), (1, 'a')):
        d = h['s'][v]
        sw = d['sw']
        if sw >= 1e-6:
            out[f'{vn}_n'] = sw
            out[f'gf_{vn}'] = d['gf'] / sw; out[f'ga_{vn}'] = d['ga'] / sw
            out[f'bts_{vn}'] = d['bts'] / sw; out[f'scored_{vn}'] = d['scored'] / sw
            out[f'cs_{vn}'] = d['cs'] / sw; out[f'tot_{vn}'] = d['tot'] / sw
        else:
            for kk in ('n','gf','ga','bts','scored','cs','tot'):
                out[f'{kk}_{vn}'] = None
    last = list(h['last'])
    if last:
        pts = 0; gf = 0; ga = 0
        for o, g, c, b, vv in last[-6:]:
            gf += g; ga += c; pts += 3 if g > c else (1 if g == c else 0)
        out['form_pts'] = pts / max(1, len(last[-6:]))
        out['form_gf'] = gf / max(1, len(last[-6:]))
        out['form_ga'] = ga / max(1, len(last[-6:]))
        out['rest'] = ord_ - last[-1][0]
    else:
        out['form_pts'] = out['form_gf'] = out['form_ga'] = None; out['rest'] = None
    return out

def league_feats(lid, ord_):
    st = LSTATE.get(lid)
    out = {}
    if st is None:
        return {k: None for k in ('lg_n','lg_gf','lg_ga','lg_bts','lg_tot','lg_n90','lg_bts90','lg_tot90')}
    f = 0.5 ** ((ord_ - st['last']) / HALF)
    out['lg_n'] = st['sw'] * f
    if out['lg_n'] >= 1e-6:
        out['lg_gf'] = st['gf'] * f / out['lg_n']; out['lg_ga'] = st['ga'] * f / out['lg_n']
        out['lg_bts'] = st['bts'] * f / out['lg_n']; out['lg_tot'] = st['tot'] * f / out['lg_n']
    else:
        out['lg_gf'] = out['lg_ga'] = out['lg_bts'] = out['lg_tot'] = None
    w90 = [o for o in st['last90'] if o > ord_ - 90]
    out['lg_n90'] = len(w90)
    out['lg_bts90'] = st['bts90_sum'] / len(w90) if w90 else None
    out['lg_tot90'] = st['tot90_sum'] / len(w90) if w90 else None
    return out

FEATS = ['h_n','a_n','gf_h','gf_a','ga_h','ga_a','bts_h','bts_a','scored_h','scored_a','cs_h','cs_a','tot_h','tot_a',
         'form_pts_h','form_gf_h','form_ga_h','form_pts_a','form_gf_a','form_ga_a','rest_h','rest_a',
         'lg_n','lg_gf','lg_ga','lg_bts','lg_tot','lg_n90','lg_bts90','lg_tot90',
         'h2h_n','h2h_bts','h2h_gfh','h2h_gfa']

art = pickle.load(open(OUT + '/gbm_btts.pkl', 'rb'))
model, iso, FEATS = art['model'], art['iso'], art['feats']

# ---- mapeo nombres: API → BD (por liga) ----
# candidatos por liga
from collections import defaultdict
cands = defaultdict(set)
for lid, home, away in Match.objects.filter(date__gte=ddate(2024, 6, 1)).values_list('league_id', 'home_team', 'away_team'):
    cands[lid].add(home); cands[lid].add(away)
norm_cands = {lid: [(norm(c), c) for c in cs] for lid, cs in cands.items()}

from football_api.models import ApiLeague
API2LID = {a.api_id: a.predicta_league_id for a in ApiLeague.objects.filter(active=True, predicta_league_id__isnull=False)}
LEAGUE_OBJ = {l.id: l for l in League.objects.all()}

def find_league(m):
    lid = API2LID.get(m['league_id'])
    return LEAGUE_OBJ.get(lid)

def map_team(api_name, lid):
    n = norm(api_name)
    cs = norm_cands.get(lid, [])
    if not cs: return None
    # exacto
    for nc, c in cs:
        if nc == n: return c
    scored = sorted(((difflib.SequenceMatcher(None, n, nc).ratio(), c) for nc, c in cs), reverse=True)
    if not scored: return None
    s1, c1 = scored[0]
    s2 = scored[1][0] if len(scored) > 1 else 0.0
    if s1 >= 0.68 and s1 - s2 >= 0.03:
        return c1
    return None

# ---- hoy ----
today = json.load(open('/tmp/today_ft_20260914.json'))
ORD = ddate(2026, 9, 14).toordinal()

from ai_predictions.enhanced_both_teams_score import enhanced_both_teams_score_model as PROD

rows = []
skip_league = skip_name = 0
for m in today:
    api_lg = m['league']
    lobj = find_league(m)
    if lobj is None:
        skip_league += 1; continue
    lid = lobj.id
    hdb = map_team(m['home'], lid)
    adb = map_team(m['away'], lid)
    if hdb is None or adb is None or hdb == adb:
        skip_name += 1; continue
    bts_real = 1 if (m['h'] is not None and m['a'] is not None and m['h'] > 0 and m['a'] > 0) else 0
    # nuevo motor
    hk = TEAM_KEYS.get(f'{lid}|{hdb}'); ak = TEAM_KEYS.get(f'{lid}|{adb}')
    if hk is None or ak is None:
        skip_name += 1; continue
    fh = team_feats(hk, ORD); fa = team_feats(ak, ORD); lf = league_feats(lid, ORD)
    pkey = f'{lid}|{hk}|{ak}'
    pl = PAIR.get(pkey, [])
    h2h = [x for x in pl if x[0] > ORD - 1095][-10:]
    if h2h:
        h2h_n = len(h2h); h2h_bts = sum(x[1] for x in h2h)/h2h_n
        h2h_gfh = sum(x[2] for x in h2h)/h2h_n; h2h_gfa = sum(x[3] for x in h2h)/h2h_n
    else:
        h2h_n = 0; h2h_bts = h2h_gfh = h2h_gfa = None
    row = {'h_n': fh['h_n'], 'a_n': fa['a_n'], 'gf_h': fh['gf_h'], 'gf_a': fa['gf_a'],
           'ga_h': fh['ga_h'], 'ga_a': fa['ga_a'], 'bts_h': fh['bts_h'], 'bts_a': fa['bts_a'],
           'scored_h': fh['scored_h'], 'scored_a': fa['scored_a'], 'cs_h': fh['cs_h'], 'cs_a': fa['cs_a'],
           'tot_h': fh['tot_h'], 'tot_a': fa['tot_a'], 'form_pts_h': fh['form_pts'], 'form_gf_h': fh['form_gf'],
           'form_ga_h': fh['form_ga'], 'form_pts_a': fa['form_pts'], 'form_gf_a': fa['form_gf'],
           'form_ga_a': fa['form_ga'], 'rest_h': fh['rest'], 'rest_a': fa['rest'],
           'lg_n': lf['lg_n'], 'lg_gf': lf['lg_gf'], 'lg_ga': lf['lg_ga'], 'lg_bts': lf['lg_bts'],
           'lg_tot': lf['lg_tot'], 'lg_n90': lf['lg_n90'], 'lg_bts90': lf['lg_bts90'], 'lg_tot90': lf['lg_tot90'],
           'h2h_n': h2h_n, 'h2h_bts': h2h_bts, 'h2h_gfh': h2h_gfh, 'h2h_gfa': h2h_gfa}
    X = pd.DataFrame([row])[FEATS].astype(float)
    p_new = float(iso.predict(model.predict_proba(X)[:, 1])[0])
    # producción
    try:
        p_prod = PROD.predict(hdb, adb, lobj)
    except Exception:
        p_prod = None
    rows.append({'league': api_lg, 'home': m['home'], 'away': m['away'], 'hdb': hdb, 'adb': adb,
                 'gh': m['h'], 'ga': m['a'], 'bts': bts_real, 'p_new': p_new, 'p_prod': p_prod})

print(f'Partidos FT hoy: {len(today)} | con liga BD: {len(today)-skip_league} | skip nombre: {skip_name} | evaluados: {len(rows)}\n')

def score(rows, key):
    ok = [r for r in rows if r[key] is not None]
    if not ok: return
    acc = sum(1 for r in ok if (r[key] >= 0.5) == bool(r['bts'])) / len(ok)
    brier = sum((r[key] - r['bts'])**2 for r in ok) / len(ok)
    si = [r for r in ok if r[key] >= 0.5]
    no = [r for r in ok if r[key] < 0.5]
    wr_si = sum(r['bts'] for r in si)/len(si) if si else 0
    wr_no = sum(1 - r['bts'] for r in no)/len(no) if no else 0
    print(f'{key.upper():7} | n={len(ok):3d} | WR={acc*100:5.1f}% | Brier={brier:.4f} | Sí: n={len(si)} WR={wr_si*100:.1f}% | No: n={len(no)} WR={wr_no*100:.1f}% | media P={np.mean([r[key] for r in ok]):.3f}')
    return ok

score(rows, 'p_new')
score(rows, 'p_prod')
base_real = np.mean([r['bts'] for r in rows])*100
print(f'\nBase real BTTS hoy: {base_real:.1f}%')

json.dump(rows, open(OUT + '/today_eval_20260914.json', 'w'), ensure_ascii=False, indent=1)
print('guardado today_eval_20260914.json')

# detalle: desacuerdos donde producción falló y nuevo acertó
dis = [r for r in rows if r['p_prod'] is not None and ((r['p_new']>=0.5) != (r['p_prod']>=0.5))]
print(f'\nDesacuerdos motor nuevo vs producción: {len(dis)}')
for r in dis[:25]:
    ok_new = (r['p_new']>=0.5) == bool(r['bts']); ok_prod = (r['p_prod']>=0.5) == bool(r['bts'])
    ok_n = '✓' if ok_new else '✗'
    ok_p = '✓' if ok_prod else '✗'
    print(f"  {r['league'][:18]:18} {r['home'][:16]:16} vs {r['away'][:16]:16} | {r['gh']}-{r['ga']} | nuevo P={r['p_new']:.2f} {ok_n} | prod P={r['p_prod']:.2f} {ok_p}")
