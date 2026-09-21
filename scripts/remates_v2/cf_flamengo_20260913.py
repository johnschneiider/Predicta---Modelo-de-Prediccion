# -*- coding: utf-8 -*-
"""CONTRAFACTUAL: si se hubiera apostado al mercado 'Total de Tiros' de Flamengo-Corinthians (13-sep, ya jugado)
con las cuotas reales capturadas a las 18:32 UTC (snapshot Kambi), ¿cómo habría ido con el motor v2.3?
Resultado real: 35 remates (Flamengo 32 + Corinthians 3, API)."""
import os, sys, json, pickle, joblib
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django; django.setup()
import numpy as np
from collections import defaultdict
from scipy.stats import nbinom
from football_api.models import ApiFixture

R = '/var/www/predicta.com.co/scripts/remates_v2'
PHI = 42.36
REAL = 35

f = ApiFixture.objects.select_related('home_team','away_team','league').filter(api_id=1492375).first()
print('fixture:', f.api_id, f.date, f.status, '|', f.home_team.name, '-', f.away_team.name)

md = joblib.load(R + '/gbm_v23.pkl'); model, feat_cols, calib = md['model'], md['feat_cols'], md['calib']
pj = pickle.load(open(R + '/histories.pkl','rb')); hist, hist_lg = pj['hist'], pj['hist_lg']

def w_of(age): return 0.5 ** (age/120.0)
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

dt_ord = f.date.date().toordinal()
htid, atid = f.home_team_id, f.away_team_id
hf = team_features(htid, dt_ord, 'h'); af = team_features(atid, dt_ord, 'a')
print('features ok:', bool(hf and af), '| hist sizes:', len(hist.get(htid) or []), len(hist.get(atid) or []))
row = {}
for k, v in hf.items(): row['h_'+k] = v
for k, v in af.items(): row['a_'+k] = v
row['lgm'] = league_mean(f.league_id, dt_ord) if f.league_id else None
lh = hist.get(htid) or []; la = hist.get(atid) or []
last_h = lh[-1]['ord'] if lh else None; last_a = la[-1]['ord'] if la else None
row['h_rest'] = (dt_ord - last_h) if last_h else None
row['a_rest'] = (dt_ord - last_a) if last_a else None
l5h = [rec['for'].get('h', {}).get('ts') for rec in reversed(lh) if rec['for'].get('h')][:5]
l5a = [rec['for'].get('a', {}).get('ts') for rec in reversed(la) if rec['for'].get('a')][:5]
l5h = [x for x in l5h if x is not None]; l5a = [x for x in l5a if x is not None]
row['h_l5_mean'] = np.mean(l5h) if l5h else None; row['h_l5_std'] = np.std(l5h) if len(l5h) >= 3 else None; row['h_l5_n'] = len(l5h)
row['a_l5_mean'] = np.mean(l5a) if l5a else None; row['a_l5_std'] = np.std(l5a) if len(l5a) >= 3 else None; row['a_l5_n'] = len(l5a)
e = eng(row)
X = np.array([[e.get(k, np.nan) for k in feat_cols]], dtype=np.float32)
lam = calib[0] + calib[1]*float(model.predict(X)[0])
print(f'\nλ_modelo v2.3 = {lam:.2f}')

# market lines (real odds captured 18:32 UTC)
d = json.load(open('/tmp/ev_big_1025985641.json'))
pairs = {}
for bo in d.get('betOffers', []):
    if (bo.get('criterion') or {}).get('label') != 'Total de Tiros (Resuelta usando Opta Data)': continue
    for o in bo.get('outcomes', []):
        if o.get('status') != 'OPEN' or o.get('odds',0) <= 0 or not o.get('line'): continue
        L = o['line']/1000.0
        pairs.setdefault(L, {})
        if o['type'].endswith('OVER'): pairs[L]['over'] = o['odds']/1000.0
        elif o['type'].endswith('UNDER'): pairs[L]['under'] = o['odds']/1000.0
pts = []
for L, dd in sorted(pairs.items()):
    if 'over' in dd and 'under' in dd:
        po, pu = 1/dd['over'], 1/dd['under']; s0 = po+pu
        pts.append((L, po/s0))
print('líneas capturadas:', sorted(pairs.keys()))
# fit λ mercado
best = None
for i in range(1501):
    lm = 8 + 40*i/1501
    n_ = PHI/(PHI+lm)
    se = sum((1 - nbinom.cdf(int(L), PHI, n_) - pm)**2 for L, pm in pts)
    if best is None or se < best[0]: best = (se, lm)
lam_k = best[1]
print(f'λ_mercado (fit NegBin de cuotas) = {lam_k:.2f} | Δ = {lam-lam_k:+.2f}')

print(f'\n{"Línea":>6} | {"O":>5} {"U":>5} | {"p_mod":>6} {"p_mkt":>6} | {"EV_O":>7} {"EV_U":>7} | {"pick":>10} | resultado')
n_m = PHI/(PHI+lam)
pnl = 0.0; bets = 0; wins = 0; picks = []
for L, dd in sorted(pairs.items()):
    if 'over' not in dd or 'under' not in dd: continue
    p_mod_o = float(1 - nbinom.cdf(int(L), PHI, n_m))
    p_mkt_o = None
    for LL, pm in pts:
        if LL == L: p_mkt_o = pm
    ev_o = p_mod_o*dd['over'] - 1.0
    ev_u = (1-p_mod_o)*dd['under'] - 1.0
    pick = None
    if ev_o >= 0.02 and ev_o >= ev_u: pick = ('OVER', dd['over'], ev_o, p_mod_o)
    elif ev_u >= 0.02: pick = ('UNDER', dd['under'], ev_u, 1-p_mod_o)
    res = ''
    if pick:
        side, odds, ev, p = pick
        won = (REAL > L) if side == 'OVER' else (REAL < L)
        pnl += (odds - 1) if won else -1.0
        bets += 1; wins += 1 if won else 0
        res = f'{side} -> {"WON" if won else "LOST"} ({odds:+.2f}u)' if won else f'{side} -> LOST (-1u)'
        picks.append((L, side, odds, ev))
    print(f'{L:6.1f} | {dd["over"]:5.2f} {dd["under"]:5.2f} | {p_mod_o:6.3f} {p_mkt_o:6.3f} | {ev_o:+7.3f} {ev_u:+7.3f} | {pick[0] if pick else "-":>10} | {res}')

print(f'\n=== RESUMEN CONTRAFACTUAL Flamengo-Corinthians (real={REAL}) ===')
print(f'picks EV≥+2pp: {bets} | ganadas: {wins} | winrate: {wins/max(bets,1)*100:.0f}% | P&L (stake 1u): {pnl:+.2f}u')
print(f'Si se hubiera apostado solo al mercado (todas las líneas OVER por el modelo): el real {REAL} habría ganado OVER en todas las líneas ≤ {max(pairs.keys())}')
