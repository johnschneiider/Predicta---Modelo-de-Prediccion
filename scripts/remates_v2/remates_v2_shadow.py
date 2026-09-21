# -*- coding: utf-8 -*-
"""
MOTOR REMATES TOTALES v2 — SHADOW LEDGER (modo prospectivo).

Idea ("hasta tener edge"): registrar AHORA (pre-partido) las predicciones del modelo y las líneas
reales de BetPlay para partidos próximos. Cuando los partidos terminen, la evaluación se hace contra
resultados reales (shadow scoring) SIN haber apostado nada.

Esto permite acumular evidencia prospectiva (no backtest) y medir si el modelo bate al mercado
consistentemente antes de decidir activarlo.

Ledger: scripts/remates_v2/shadow_ledger.jsonl  (una línea JSON por evento+snapshot)
Enrichment posterior: scripts/remates_v2/shadow_score.py

Uso: python scripts/remates_v2/remates_v2_shadow.py [--window-hours 48]
"""
import os, sys, django, json, pickle, joblib
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
WINDOW_H = 48

OFFERING = "https://us.offering-api.kambicdn.com/offering/v2018/betplay"
HDR = {"Accept": "application/json", "Origin": "https://betplay.com.co", "Referer": "https://betplay.com.co/"}
PARAMS = {"channel_id": 1, "client_id": 200, "lang": "es_CO", "market": "CO", "useCombined": "true", "useCombinedLive": "true"}
LABEL_TOT = 'Total de Tiros (Resuelta usando Opta Data)'
PHI = 42.36

md = joblib.load(R + '/gbm_v22.pkl')
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

def predict(home_tid, away_tid, lg, dt_ord):
    hf = team_features(home_tid, dt_ord, 'h')
    af = team_features(away_tid, dt_ord, 'a')
    if not (hf and af): return None
    lgm = league_mean(lg, dt_ord) if lg else None
    row = {}
    for k, v in hf.items(): row['h_'+k] = v
    for k, v in af.items(): row['a_'+k] = v
    row['lgm'] = lgm
    # rest/l5
    lh = hist.get(home_tid) or []; la = hist.get(away_tid) or []
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
    X = np.array([[float(row.get(k)) if row.get(k) not in (None, '', 'None') else np.nan for k in feat_cols]], dtype=np.float32)
    try:
        p_raw = float(model.predict(X)[0])
    except Exception:
        return None
    return calib[0] + calib[1]*p_raw

# ── Kambi scan ──
def fetch(url, params):
    r = requests.get(url, params=params, headers=HDR, timeout=20)
    r.raise_for_status()
    return r.json()

data = fetch(f"{OFFERING}/listView/football.json", {"channel_id":1,"client_id":200,"lang":"es_CO","market":"CO"})
events = [e['event'] for e in data.get('events', []) if e.get('event', {}).get('state') == 'NOT_STARTED']
now = datetime.now(dtz.utc)
horizon = now + timedelta(hours=WINDOW_H)
events = [e for e in events if e.get('start') and now <= datetime.fromisoformat(e['start'].replace('Z','+00:00')) <= horizon]
print(f'events next {WINDOW_H}h: {len(events)}')

from football_api.models import ApiTeam, ApiLeague
lapi2db = dict(ApiLeague.objects.values_list('api_id','id'))

batch = {}
entries = 0
for ev in events:
    try:
        j = fetch(f"{OFFERING}/betoffer/event/{ev['id']}.json", PARAMS)
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
    if not pairs: continue
    name = ev.get('name') or ''
    parts = [p.strip() for p in name.split(' - ')]
    if len(parts) != 2: continue
    # team match: try normalize via ApiTeam (kambi-name unknown; use token match)
    def find_team(nm):
        n0 = nm.lower()
        cands = ApiTeam.objects.filter(normalized_name=n0)
        if cands.exists(): return cands.first()
        toks = set(n0.split())
        best = None
        for t in ApiTeam.objects.filter(normalized_name__icontains=n0.split()[0][:6])[:50]:
            score = len(toks & set((t.normalized_name or '').split()))
            if score and (best is None or score > best[0]): best = (score, t)
        return best[1] if best else None
    ht = find_team(parts[0]); at = find_team(parts[1])
    if not ht or not at: 
        continue
    start = datetime.fromisoformat(ev['start'].replace('Z','+00:00'))
    dt_ord = start.date().toordinal()
    lam = predict(ht.id, at.id, None, dt_ord)
    if lam is None:
        continue
    # market lambda fit
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
    snap = {
        'ts_utc': now.isoformat(),
        'event_id': ev['id'],
        'name': name,
        'start': ev['start'],
        'league_path': '/'.join(p.get('name','') for p in ev.get('path', [])),
        'lam_model': round(lam, 3),
        'lam_market': round(lam_mkt, 3),
        'delta': round(lam - lam_mkt, 3),
        'lines': {str(L): {'over': d.get('over'), 'under': d.get('under'),
                           'p_model_over': round(float(1-nbinom.cdf(int(L), PHI, n_m)), 4),
                           'p_market_over': round(float(pm), 4)} for L, pm in pts for d in [pairs[L]]},
    }
    batch[str(ev['id'])] = snap
    entries += 1

with open(LEDGER, 'a') as fp:
    for snap in batch.values():
        fp.write(json.dumps(snap) + '\n')
print(f'shadow ledger: {entries} eventos registrados ({WINDOW_H}h window)')
for sname, s in list(batch.items())[:20]:
    d = s['delta']
    flag = ''
    if abs(d) >= 1.5: flag = '  <== diferencia notable'
    print(f"  {s['name'][:48]:48s} λ_m={s['lam_model']:5.2f} λ_k={s['lam_market']:5.2f} Δ={d:+5.2f}{flag}")
