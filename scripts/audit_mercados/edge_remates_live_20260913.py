# -*- coding: utf-8 -*-
"""
TEST DIRECTO DE EDGE — Remates totales y SOT: λ_modelo vs λ_mercado (live). READ-ONLY.
Kambi: cada línea es un betoffer separado (2 outcomes). Recolectamos por evento
todas las líneas de cada mercado, ajustamos λ de mercado (NegBin, phi conocidos),
comparamos con λ del modelo (pipeline shots: shots_prediction + xg_shots promediados).
"""
import os, sys, django, json, math
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
django.setup()

import requests
from collections import defaultdict
from datetime import datetime, timezone as dtz
from difflib import SequenceMatcher
from scipy.stats import nbinom

OFFERING = "https://us.offering-api.kambicdn.com/offering/v2018/betplay"
HDR = {"Accept": "application/json", "Origin": "https://betplay.com.co", "Referer": "https://betplay.com.co/"}
PARAMS = {"channel_id": 1, "client_id": 200, "lang": "es_CO", "market": "CO", "useCombined": "true", "useCombinedLive": "true"}

LABEL_TOT = "Total de Tiros (Resuelta usando Opta Data)"
LABEL_SOT = "Total de tiros a puerta (Resuelta usando Opta Data)"
PHI_TOT, PHI_SOT = 42.36, 35.81

OUT = open('/var/www/predicta.com.co/scripts/audit_mercados/edge_remates_live_out.txt', 'w')
def w(*a):
    s = ' '.join(str(x) for x in a); print(s); OUT.write(s + '\n')

w('EDGE TEST · remates totales + SOT · λ_modelo vs λ_mercado ·', datetime.now(dtz.utc).isoformat())
w('='*110)

def fetch_json(url, params):
    r = requests.get(url, params=params, headers=HDR, timeout=20)
    r.raise_for_status()
    return r.json()

# ── 1. listView: eventos NOT_STARTED ──
data = fetch_json(f"{OFFERING}/listView/football.json", {"channel_id":1,"client_id":200,"lang":"es_CO","market":"CO"})
events = []
for e in data.get('events', []):
    ev = e.get('event', e)
    if ev.get('state') != 'NOT_STARTED': continue
    events.append(ev)
w(f'Eventos NOT_STARTED: {len(events)}')

# ── 2. scan betoffer por evento; acumular líneas por mercado ──
market_lines = defaultdict(lambda: defaultdict(dict))  # (ev_id, label) -> {line: {over,under}}
ev_idx = {}
n_scanned = 0
for ev in events[:170]:
    n_scanned += 1
    try:
        j = fetch_json(f"{OFFERING}/betoffer/event/{ev['id']}.json", PARAMS)
    except Exception:
        continue
    for bo in j.get('betOffers', []):
        lab = (bo.get('criterion') or {}).get('label', '')
        if lab not in (LABEL_TOT, LABEL_SOT): continue
        for o in bo.get('outcomes', []):
            if o.get('status') != 'OPEN' or o.get('odds', 0) <= 0 or not o.get('line'): continue
            line = o['line']/1000.0
            key = (ev['id'], lab)
            ev_idx[ev['id']] = ev
            t = o.get('type','')
            if t.endswith('OVER'): market_lines[key][line]['over'] = o['odds']/1000.0
            elif t.endswith('UNDER'): market_lines[key][line]['under'] = o['odds']/1000.0
w(f'Eventos escaneados: {n_scanned} | eventos con mercado: {len(set(k[0] for k in market_lines))}')

def fit_lambda(pairs, phi, lo=5.0, hi=45.0, steps=2000):
    """pairs: {line: {'over':o,'under':u}} -> λ NegBin fit (mínimos cuadrados, p neto de vig)"""
    pts = []
    for line, d in sorted(pairs.items()):
        if 'over' in d and 'under' in d:
            po, pu = 1/d['over'], 1/d['under']
            s = po + pu
            pts.append((line, po/s, s))   # p_neto, overround
    if len(pts) < 2: return None, None, pts
    best = None
    for i in range(steps+1):
        lam = lo + (hi-lo)*i/steps
        n_ = phi/(phi+lam)
        se = sum((1 - nbinom.cdf(int(line), phi, n_) - pm)**2 for line, pm, _ in pts)
        if best is None or se < best[0]: best = (se, lam)
    return best[1], (best[0]/len(pts))**0.5, pts

def find_league(path_names):
    from football_data.models import League
    # kambi path: ['Fútbol', 'Argentina', 'Liga Profesional Argentina']
    country = path_names[1] if len(path_names) > 1 else ''
    comp = path_names[2] if len(path_names) > 2 else ''
    best = None
    for lg in League.objects.all():
        s = SequenceMatcher(None, (lg.name or '').lower(), comp.lower()).ratio()
        if (lg.country or '').lower() == country.lower(): s += 0.15
        if best is None or s > best[0]: best = (s, lg)
    return best[1] if best and best[0] > 0.5 else None

from ai_predictions.shots_prediction_model import shots_prediction_model
from ai_predictions.xg_shots_model import xg_shots_model

def model_lambda(kind, home, away, lg):
    try:
        m = {'tot': 'predict_shots_total', 'sot': 'predict_shots_on_target_total'}[kind]
        p1 = getattr(shots_prediction_model, m)(home, away, lg)
        p2 = getattr(xg_shots_model, m)(home, away, lg)
        vals = [p['prediction'] for p in (p1, p2) if p and p.get('prediction')]
        return sum(vals)/len(vals) if vals else None
    except Exception as e:
        return None

w()
w(f'{"evento":46s} {"mer":5s} {"liga":24s} {"λ_mkt":7s} {"λ_mod":7s} {"Δ":7s} {"rmse":7s} {"vig%":6s} lineas')
w('-'*130)
results = []
for (ev_id, lab), pairs in sorted(market_lines.items()):
    ev = ev_idx[ev_id]
    phi = PHI_TOT if lab == LABEL_TOT else PHI_SOT
    lam_mkt, rmse, pts = fit_lambda(pairs, phi)
    if lam_mkt is None: continue
    name = ev.get('name') or ''
    parts = [p.strip() for p in name.split(' - ')]
    if len(parts) != 2: continue
    home, away = parts
    path_names = [p['name'] for p in ev.get('path', [])]
    lg = find_league(path_names)
    if not lg: continue
    kind = 'tot' if lab == LABEL_TOT else 'sot'
    lam_mod = model_lambda(kind, home, away, lg)
    tag = 'REM' if kind=='tot' else 'SOT'
    lns = ','.join(str(int(l)) for l in sorted(pairs))
    vig = sum((1/d['over'] + 1/d['under'] - 1)/2 for d in pairs.values() if 'over' in d and 'under' in d)/max(1,len(pts))*100
    if lam_mod is None:
        w(f'{name[:46]:46s} {tag:5s} {lg.name[:24]:24s} {lam_mkt:7.2f} {"—":7s} {"—":7s} {rmse:7.4f} {vig:6.1f} {lns}')
    else:
        w(f'{name[:46]:46s} {tag:5s} {lg.name[:24]:24s} {lam_mkt:7.2f} {lam_mod:7.2f} {lam_mod-lam_mkt:+7.2f} {rmse:7.4f} {vig:6.1f} {lns}')
        results.append(dict(name=name, lab=tag, liga=lg.name, lam_mkt=lam_mkt, lam_mod=lam_mod, pts=pts, phi=phi, vig=vig))
w()
w(f'Comparables con modelo: {len(results)}')

# ── 3. Δp por línea ──
w()
w('Δp (modelo - mercado) por línea, en puntos porcentuales:')
for rd in sorted(results, key=lambda r: -abs(r['lam_mod']-r['lam_mkt'])):
    lam_m, lam_k, phi = rd['lam_mod'], rd['lam_mkt'], rd['phi']
    n_m = phi/(phi+lam_m); n_k = phi/(phi+lam_k)
    row = []
    for line, pm, _ in sorted(rd['pts']):
        p_mod = 1 - nbinom.cdf(int(line), phi, n_m)
        row.append(f'{line:.0f}:{100*(p_mod-pm):+.1f}')
    w(f"  {rd['name'][:42]:42s} [{rd['lab']}] {rd['liga'][:18]:18s} λ{lam_k:.2f}→{lam_m:.2f} | " + '  '.join(row))
OUT.close()
print('DONE')
