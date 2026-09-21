# -*- coding: utf-8 -*-
"""
MOTOR REMATES TOTALES v2 — SHADOW LEDGER v2 (prospectivo, sin apostar).

Flujo:
 1. Toma fixtures próximos (ApiFixture, próximas N horas) → equipo htid/atid exactos (sin fuzzy).
 2. Para cada uno, busca el evento Kambi por nombre (match directo con normalized_name de ApiTeam).
 3. Registra: λ_modelo, λ_mercado (fit NegBin), líneas y EV por lado EN un ledger JSONL.
 4. (shadow_score.py puntúa cuando terminen, contra stats reales de la API.)

Esto ES la manera de "predecir hasta tener edge": evidencia prospectiva, no backtest.

Uso: python scripts/remates_v2/remates_v2_shadow2.py [--hours 48] [--dry]
"""
import os, sys, django, json, pickle, joblib, argparse
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
django.setup()

import numpy as np
from datetime import datetime, timezone as dtz, timedelta
from collections import defaultdict
from scipy.stats import nbinom
import requests

R = '/var/www/predicta.com.co/scripts/remates_v2'
LEDGER = R + '/shadow_ledger.jsonl'

ap = argparse.ArgumentParser()
ap.add_argument('--hours', type=int, default=48)
ap.add_argument('--dry', action='store_true')
args = ap.parse_args()

md = joblib.load(R + '/gbm_v23.pkl')
model, feat_cols, calib = md['model'], md['feat_cols'], md['calib']
pj = pickle.load(open(R + '/histories.pkl', 'rb'))
hist, hist_lg = pj['hist'], pj['hist_lg']

OFFERING = "https://us.offering-api.kambicdn.com/offering/v2018/betplay"
HDR = {"Accept": "application/json", "Origin": "https://betplay.com.co", "Referer": "https://betplay.com.co/"}
PARAMS = {"channel_id":1,"client_id":200,"lang":"es_CO","market":"CO","useCombined":"true","useCombinedLive":"true"}
LABEL_TOT = 'Total de Tiros (Resuelta usando Opta Data)'
PHI = 42.36

from football_api.models import ApiFixture, ApiTeam, ApiLeague

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

def build_row(htid, atid, lg, dt_ord):
    hf = team_features(htid, dt_ord, 'h')
    af = team_features(atid, dt_ord, 'a')
    if not (hf and af): return None
    lgm = league_mean(lg, dt_ord) if lg else None
    row = {}
    for k, v in hf.items(): row['h_'+k] = v
    for k, v in af.items(): row['a_'+k] = v
    row['lgm'] = lgm
    lh = hist.get(htid) or []; la = hist.get(atid) or []
    last_h = lh[-1]['ord'] if lh else None; last_a = la[-1]['ord'] if la else None
    row['h_rest'] = (dt_ord - last_h) if last_h else None
    row['a_rest'] = (dt_ord - last_a) if last_a else None
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

def eng(r):
    out = {}
    for k in feat_cols:
        v = r.get(k)
        try: out[k] = float(v) if v not in (None,'','None') else np.nan
        except: out[k] = np.nan
    # derived (only if base present)
    g = lambda k: out.get(k, np.nan)
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

# load model feat_cols — note: v2.3 model expects the derived cols; get row via eng on build_row output? 
# The v2.3 training rows were eng(features_v22.csv rows). So we must apply eng() to the raw v2.2 row.
# But build_row output uses same base keys (h_f_ts etc.) — good.

now = datetime.now(dtz.utc)
end = now + timedelta(hours=args.hours)
fx = ApiFixture.objects.filter(date__gte=now - timedelta(hours=2), date__lte=end).select_related('league', 'home_team', 'away_team')
print(f'fixtures in window: {fx.count()}')

# Kambi events
r = requests.get(f"{OFFERING}/listView/football.json", params={"channel_id":1,"client_id":200,"lang":"es_CO","market":"CO"}, headers=HDR, timeout=20)
events = [e['event'] for e in r.json().get('events', []) if e.get('event', {}).get('state') == 'NOT_STARTED']
print(f'kambi events: {len(events)}')

def norm(s):
    import re, unicodedata
    s = unicodedata.normalize('NFKD', s or '')
    s = ''.join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r'[^a-z0-9]+', ' ', s.lower())
    return ' '.join(s.split())

entries = []
matched = 0
for f in fx:
    hname = norm(f.home_team.name); aname = norm(f.away_team.name)
    if not hname or not aname: continue
    # find kambi event: fuzzy on both names
    cand = None
    for ev in events:
        nm = ev.get('name') or ''
        parts = [norm(p) for p in nm.split(' - ')]
        if len(parts) != 2: continue
        def sim(a, b):
            ta, tb = set(a.split()), set(b.split())
            if not ta or not tb: return 0.0
            return len(ta & tb) / max(len(ta), len(tb))
        s = sim(parts[0], hname) + sim(parts[1], aname)
        if s >= 1.0:
            cand = (s, ev); break
    if not cand: continue
    ev = cand[1]
    # fetch lines
    try:
        j = requests.get(f"{OFFERING}/betoffer/event/{ev['id']}.json", params=PARAMS, headers=HDR, timeout=12).json()
    except Exception:
        continue
    pairs = defaultdict(dict)
    for bo in j.get('betOffers', []):
        lab = (bo.get('criterion') or {}).get('label','')
        if lab != LABEL_TOT: continue
        for o in bo.get('outcomes', []):
            if o.get('status') != 'OPEN' or o.get('odds',0)<=0 or not o.get('line'): continue
            L = o['line']/1000.0
            side = 'over' if o.get('type','').endswith('OVER') else 'under'
            pairs[L][side] = o['odds']/1000.0
    if len(pairs) < 2: continue
    dt_ord = f.date.date().toordinal()
    row = build_row(f.home_team_id, f.away_team_id, f.league_id, dt_ord)
    if not row: continue
    e = eng(row)
    X = np.array([[e.get(k, np.nan) for k in feat_cols]], dtype=np.float32)
    p_raw = float(model.predict(X)[0])
    lam = calib[0] + calib[1]*p_raw
    # market lambda
    pts = []
    for L, d in sorted(pairs.items()):
        if 'over' in d and 'under' in d:
            po, pu = 1/d['over'], 1/d['under']; s0 = po+pu
            pts.append((L, po/s0))
    if len(pts) < 2: continue
    best = None
    for i in range(1501):
        lm = 8 + 40*i/1501
        n_ = PHI/(PHI+lm)
        se = sum((1 - nbinom.cdf(int(L), PHI, n_) - pm)**2 for L, pm in pts)
        if best is None or se < best[0]: best = (se, lm)
    lam_mkt = best[1]
    n_m = PHI/(PHI+lam); n_k = PHI/(PHI+lam_mkt)
    snaps = {}
    for L, pm in pts:
        d = pairs[L]
        p_mod = float(1 - nbinom.cdf(int(L), PHI, n_m))
        snaps[str(L)] = {
            'over': d.get('over'), 'under': d.get('under'),
            'p_model_over': round(p_mod, 4), 'p_market_over': round(pm, 4),
            'ev_over': round(p_mod*d['over']-1, 4) if d.get('over') else None,
            'ev_under': round((1-p_mod)*d['under']-1, 4) if d.get('under') else None,
        }
    entry = {
        'ts_utc': now.isoformat(), 'fixture_api_id': f.api_id, 'event_id': ev['id'],
        'name': f'{f.home_team.name} - {f.away_team.name}', 'start': f.date.isoformat(),
        'league': f.league.name, 'lambda_model': round(lam, 3), 'lambda_market': round(lam_mkt, 3),
        'delta': round(lam - lam_mkt, 3), 'lines': snaps,
    }
    entries.append(entry); matched += 1

print(f'matched fixtures with market: {matched}')
if not args.dry:
    with open(LEDGER, 'a') as fp:
        for e in entries:
            fp.write(json.dumps(e, ensure_ascii=False) + '\n')
    print(f'appended {len(entries)} ledger entries')
else:
    for e in entries[:25]:
        print(f"  {e['name'][:44]:44s} [{e['league'][:18]:18s}] λ_m={e['lambda_model']:5.2f} λ_k={e['lambda_market']:5.2f} Δ={e['delta']:+5.2f}")
