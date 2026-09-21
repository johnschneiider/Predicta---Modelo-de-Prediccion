# -*- coding: utf-8 -*-
"""
MOTOR REMATES TOTALES v2 — LIVE PREDICT: partidos PRÓXIMOS (no empezados) con líneas de mercado.

Predice λ, convierte a p_over/under por línea, y compara contra las cuotas reales de BetPlay
(quitando vig). Esto mide "edge potencial" EN VIVO. No apuesta — read-only.

Uso: DJANGO_SETTINGS_MODULE=betting_bot.settings python scripts/remates_v2/remates_v2_live.py
"""
import os, sys, django, json, pickle
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
django.setup()

import numpy as np
from datetime import datetime, timezone as dtz, timedelta
from collections import defaultdict
from scipy.stats import nbinom
import requests
from sklearn.exceptions import NotFittedError

R = '/var/www/predicta.com.co/scripts/remates_v2'
OUT = open(R + '/live_out.txt', 'a')
def w(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')

w('')
w('='*100)
w('LIVE PREDICT — REMATES TOTALES — partidos NO empezados', datetime.now(dtz.utc).isoformat())

# ── Load model ──
import joblib
model_path = R + '/gbm_model.pkl'
if not os.path.exists(model_path):
    # train quickly and save
    import csv as _csv
    rows = []
    with open(R + '/features_all.csv') as fp:
        for r in _csv.DictReader(fp): rows.append(r)
    rows.sort(key=lambda r: r['date'])
    feat_cols = [k for k in rows[0].keys() if k not in ('fid','date','lg','htid','atid','y')]
    def vec(r):
        out = []
        for k in feat_cols:
            v = r.get(k)
            try: out.append(float(v) if v not in (None,'','None') else np.nan)
            except: out.append(np.nan)
        return out
    X = np.array([vec(r) for r in rows], dtype=np.float32)
    y = np.array([float(r['y']) for r in rows], dtype=np.float32)
    from sklearn.ensemble import HistGradientBoostingRegressor
    m = HistGradientBoostingRegressor(max_iter=500, learning_rate=0.05, max_depth=6, min_samples_leaf=40,
        l2_regularization=1.0, early_stopping=True, validation_fraction=0.1, random_state=42)
    m.fit(X, y)
    joblib.dump({'model': m, 'feat_cols': feat_cols}, model_path)
    print('model trained & saved')
md = joblib.load(model_path)
gbm, feat_cols = md['model'], md['feat_cols']

pj = pickle.load(open(R + '/histories.pkl','rb'))
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

def vec(r):
    out = []
    for k in feat_cols:
        v = r.get(k)
        try: out.append(float(v) if v not in (None,'','None') else np.nan)
        except: out.append(np.nan)
    return out

# ── Kambi events ──
OFFERING = "https://us.offering-api.kambicdn.com/offering/v2018/betplay"
HDR = {"Accept": "application/json", "Origin": "https://betplay.com.co", "Referer": "https://betplay.com.co/"}
PARAMS = {"channel_id":1,"client_id":200,"lang":"es_CO","market":"CO","useCombined":"true","useCombinedLive":"true"}
data = requests.get(f"{OFFERING}/listView/football.json", params={"channel_id":1,"client_id":200,"lang":"es_CO","market":"CO"}, headers=HDR, timeout=20).json()
events = [e['event'] for e in data.get('events', []) if e.get('event', {}).get('state') == 'NOT_STARTED']
print(f'NOT_STARTED events: {len(events)}')

PHI = 42.36  # remates totales
found_any = False
for ev in events[:200]:
    try:
        j = requests.get(f"{OFFERING}/betoffer/event/{ev['id']}.json", params=PARAMS, headers=HDR, timeout=12).json()
    except Exception:
        continue
    pairs = defaultdict(dict)
    for bo in j.get('betOffers', []):
        lab = (bo.get('criterion') or {}).get('label','')
        if lab != 'Total de Tiros (Resuelta usando Opta Data)': continue
        for o in bo.get('outcomes', []):
            if o.get('status') != 'OPEN' or o.get('odds',0)<=0 or not o.get('line'): continue
            L = o['line']/1000.0
            side = 'over' if o.get('type','').endswith('OVER') else 'under'
            pairs[L][side] = o['odds']/1000.0
    if not pairs: continue
    # find our teams: match vs ApiTeam names via fuzzy (simple contains on normalized)
    from football_api.models import ApiTeam, ApiLeague
    name = ev.get('name') or ''
    parts = [p.strip() for p in name.split(' - ')]
    if len(parts) != 2: continue
    def find_team(nm):
        n0 = nm.lower()
        # try exact normalized, then token overlap
        cands = ApiTeam.objects.filter(normalized_name=n0)
        if cands.exists(): return cands.first()
        # token match
        toks = set(n0.split())
        best = None
        for t in ApiTeam.objects.filter(normalized_name__icontains=n0.split()[0][:6])[:40]:
            score = len(toks & set((t.normalized_name or '').split()))
            if score and (best is None or score > best[0]):
                best = (score, t)
        return best[1] if best else None
    ht = find_team(parts[0]); at = find_team(parts[1])
    if not ht or not at: continue
    TODAY_ORD = datetime(2026,9,13).date().toordinal()
    hf = team_features(ht.id, TODAY_ORD, 'h')
    af = team_features(at.id, TODAY_ORD, 'a')
    if not (hf and af): continue
    row = {}; 
    for k, v in hf.items(): row['h_'+k] = v
    for k, v in af.items(): row['a_'+k] = v
    # league mean by name-based lookup: find league id from event path group (kambi group id -> our leagues?) skip: use None
    # try find via ApiLeague names
    lgname = None
    for p in ev.get('path', []):
        if p.get('name') not in ('Fútbol','Football'): lgname = p.get('name')
    # league fallback: average of all leagues (rare cases); use overall hist via summing? use mean of league of home team last games in hist? simplest: skip lgm -> model handles nan
    row['lgm'] = None
    X = np.array([vec(row)], dtype=np.float32)
    lam = float(gbm.predict(X)[0])
    # market fit
    pts = []
    for L, d in sorted(pairs.items()):
        if 'over' in d and 'under' in d:
            po, pu = 1/d['over'], 1/d['under']; s0 = po+pu
            pts.append((L, po/s0, d['over'], d['under'], s0-1))
    if len(pts) < 2: continue
    # fit market lambda too
    best = None
    for i in range(1501):
        lm = 8 + 40*i/1501
        n_ = PHI/(PHI+lm)
        se = sum((1 - nbinom.cdf(int(L), PHI, n_) - pm)**2 for L, pm, *_ in pts)
        if best is None or se < best[0]: best = (se, lm)
    lam_mkt = best[1]
    found_any = True
    w('')
    w(f"### {name}  [{lgname}]  event={ev['id']}  start={ev.get('start')}")
    w(f"  λ_modelo={lam:.2f} | λ_mercado≈{lam_mkt:.2f} | Δ={lam-lam_mkt:+.2f}")
    n_m = PHI/(PHI+lam); n_k = PHI/(PHI+lam_mkt)
    for L, pm, o_ov, o_un, vig in pts:
        p_mod = 1 - nbinom.cdf(int(L), PHI, n_m)
        p_mkt_net = pm
        edge = p_mod - p_mkt_net
        # EV per side if model right:
        ev_over = p_mod*o_ov - 1
        ev_under = (1-p_mod)*o_un - 1
        flag = ''
        if ev_over > 0.02: flag = ' <== OVER +EV'
        if ev_under > 0.02: flag = ' <== UNDER +EV'
        w(f"   L{L:4.1f}: O={o_ov:.2f} U={o_un:.2f} | p_mod={p_mod:.3f} p_mkt={p_mkt_net:.3f} Δ={edge*100:+.1f}pp | EV_O={ev_over*100:+.1f}% EV_U={ev_under*100:+.1f}%{flag}")
        if len(pts) > 0 and pts.index((L, pm, o_ov, o_un, vig)) > 6: break

if not found_any:
    w('No se encontraron eventos con mercado de remates totales ahora mismo.')

OUT.close()
print('DONE')
