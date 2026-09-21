# -*- coding: utf-8 -*-
"""BET-SIM SIN CUOTAS — contrafactual del motor remates v2 sobre los partidos de HOY (13-sep).
Regla: sin odds; la apuesta se genera por convicción del modelo vs una LINEA NEUTRAL.
  ideas: L=25.5 (linea estandar global ~media 25.25) y L=media de la liga del partido.
  margen m: apuesta OVER si lambda >= L+m; UNDER si lambda <= L-m; si no, no hay apuesta.
  gana OVER si real > L; gana UNDER si real < L. (Sin cuotas, stake 1u c/u para contar W/L.)
"""
import os, sys, json, pickle, joblib
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django; django.setup()
import numpy as np
from collections import defaultdict
from datetime import datetime
from football_api.models import ApiTeam, ApiLeague, ApiFixture

R = '/var/www/predicta.com.co/scripts/remates_v2'
OUT = open(R + '/betsim_no_odds_20260913.txt', 'w')
def w(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')

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

api2db = dict(ApiTeam.objects.values_list('api_id','id'))
lapi2db = dict(ApiLeague.objects.values_list('api_id','id'))
TODAY_ORD = datetime(2026,9,13).date().toordinal()

def build_row(htid, atid, lg, dt_ord):
    hf = team_features(htid, dt_ord, 'h'); af = team_features(atid, dt_ord, 'a')
    if not (hf and af): return None
    row = {}
    for k, v in hf.items(): row['h_'+k] = v
    for k, v in af.items(): row['a_'+k] = v
    row['lgm'] = league_mean(lg, dt_ord) if lg else None
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

def predict(row):
    e = eng(row)
    X = np.array([[e.get(k, np.nan) for k in feat_cols]], dtype=np.float32)
    return calib[0] + calib[1]*float(model.predict(X)[0])

base = json.load(open(R + '/today_ft_stats.json'))
extra = json.load(open(R + '/newft_stats_20260913.json'))
ftc = json.load(open(R + '/ft_covered.json'))
fxmeta = {f['fixture']['id']: f for f in ftc}
base_usable = [r for r in base.values() if r.get('total_shots') is not None and r.get('teams') and len(r['teams']) == 2]
extra_usable = [r for r in extra.values() if r.get('total_shots') is not None and r.get('teams') and len(r['teams']) == 2]

rows = []
for r in base_usable:
    meta = fxmeta.get(r['fixture_id'])
    if not meta: continue
    br = build_row(api2db.get(meta['teams']['home']['id']), api2db.get(meta['teams']['away']['id']), lapi2db.get(meta['league']['id']), TODAY_ORD)
    if br is None: continue
    rows.append({'name': f"{meta['teams']['home']['name']} - {meta['teams']['away']['name']}", 'league': r['league'],
                 'pred': round(predict(br),2), 'actual': int(r['total_shots']), 'lgm': br.get('lgm')})
for r in extra_usable:
    br = build_row(api2db.get(r.get('home_api_id')), api2db.get(r.get('away_api_id')), lapi2db.get(r.get('league_id')), TODAY_ORD)
    if br is None: continue
    rows.append({'name': f"{r['home']} - {r['away']}", 'league': r['league'],
                 'pred': round(predict(br),2), 'actual': int(r['total_shots']), 'lgm': br.get('lgm')})
# Flamengo-Corinthians (jugado 20:30 UTC; resultado API = 35)
fa = ApiFixture.objects.filter(api_id=1492375).select_related('home_team','away_team','league').first()
if fa:
    br = build_row(fa.home_team_id, fa.away_team_id, fa.league_id, TODAY_ORD)
    if br:
        rows.append({'name': 'Flamengo - Corinthians', 'league': 'Serie A (BRA)',
                     'pred': round(predict(br),2), 'actual': 35, 'lgm': br.get('lgm'), 'flag': 'cuotas reales capturadas'})

json.dump(rows, open(R + '/betsim_rows_20260913.json','w'), ensure_ascii=False, indent=1)
w(f"BET-SIM SIN CUOTAS — motor remates v2 — partidos de HOY 13-sep")
w(f"n partidos con prediccion y resultado real: {len(rows)}")
w("="*95)

LINE_FIXED = 25.5
def sim(rows, Lmode, margin):
    bets=[]; pushes=0
    for r in rows:
        L = LINE_FIXED if Lmode=='fixed' else r.get('lgm')
        if L is None: continue
        lam = r['pred']; act = r['actual']
        if lam >= L + margin: side='over'
        elif lam <= L - margin: side='under'
        else: continue
        if side=='over':
            if act > L: res='W'
            elif act < L: res='L'
            else: pushes+=1; continue
        else:
            if act < L: res='W'
            elif act > L: res='L'
            else: pushes+=1; continue
        bets.append({'name': r['name'], 'league': r['league'], 'side': side, 'line': L, 'lam': lam, 'act': act, 'res': res})
    wins=sum(1 for b in bets if b['res']=='W'); losses=len(bets)-wins
    o=[b for b in bets if b['side']=='over']; u=[b for b in bets if b['side']=='under']
    return {'bets':bets,'n':len(bets),'w':wins,'l':losses,'wr':(wins/len(bets)*100 if bets else 0),'pushes':pushes,
            'no':len(o),'wo':sum(1 for b in o if b['res']=='W'),'nu':len(u),'wu':sum(1 for b in u if b['res']=='W')}

w()
w("VARIANTE A — linea fija estandar 25.5 (~media global del mercado)")
w(f"{'margen':>8} | {'apuestas':>9} {'ganadas':>8} {'perdidas':>9} {'winrate':>8} | over: W/N | under: W/N")
for m in (0.0, 0.5, 0.75, 1.0, 1.5):
    s=sim(rows,'fixed',m)
    w(f"{m:8.2f} | {s['n']:9d} {s['w']:8d} {s['l']:9d} {s['wr']:7.1f}% | {s['wo']}/{s['no']} | {s['wu']}/{s['nu']}")

w()
w("VARIANTE B — linea = media de la liga del partido (adaptativa)")
w(f"{'margen':>8} | {'apuestas':>9} {'ganadas':>8} {'perdidas':>9} {'winrate':>8} | over: W/N | under: W/N | pushes")
for m in (0.0, 0.5, 0.75, 1.0, 1.5):
    s=sim(rows,'league',m)
    w(f"{m:8.2f} | {s['n']:9d} {s['w']:8d} {s['l']:9d} {s['wr']:7.1f}% | {s['wo']}/{s['no']} | {s['wu']}/{s['nu']} | {s['pushes']}")

w()
w("DETALLE — Variante A margen 0.75 (principal):")
sA=sim(rows,'fixed',0.75)
w(f"apuestas={sA['n']} ganadas={sA['w']} perdidas={sA['l']} winrate={sA['wr']:.1f}%")
w("  PERDIDAS:")
for b in sA['bets']:
    if b['res']=='L':
        w(f"    {b['name'][:44]:44s} [{b['league'][:16]:16s}] {b['side']} {b['line']} | pred={b['lam']} real={b['act']}")
w()
w("DETALLE — Variante B margen 0.75 (principal):")
sB=sim(rows,'league',0.75)
w(f"apuestas={sB['n']} ganadas={sB['w']} perdidas={sB['l']} winrate={sB['wr']:.1f}%")
w("  PERDIDAS:")
for b in sB['bets']:
    if b['res']=='L':
        w(f"    {b['name'][:44]:44s} [{b['league'][:16]:16s}] {b['side']} {b['line']:.2f} | pred={b['lam']} real={b['act']}")

w()
w("EJEMPLO CON LINEAS REALES — Flamengo-Corinthians (sin cuotas; lineas capturadas 22.5-28.5):")
w("  lambda=29.43 -> el modelo va OVER en las 7 lineas (real=35) -> 7/7 ganadas (partido).")
OUT.close()
print("DONE")
