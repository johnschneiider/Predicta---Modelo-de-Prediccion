# -*- coding: utf-8 -*-
"""
SHADOW SCORER — puntúa el ledger de remates totales cuando los partidos terminan.
Lee shadow_ledger.jsonl, busca resultados reales (BD o API), calcula:
  - error de λ_modelo vs real, vs λ_mercado (si hay)
  - rendimiento hipotético: si apostáramos el EV positivo mayor por línea con stake 1u,
    a las cuotas registradas. Comparar contra apostar siempre OVER/UNDER de referencia.
Esto mide si el modelo bate al mercado en prospectivo, no en backtest.

Uso: python scripts/remates_v2/shadow_score.py [--fetch-missing]
"""
import os, sys, django, json, argparse
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
django.setup()

import numpy as np
from datetime import datetime, timezone as dtz
from collections import defaultdict

R = '/var/www/predicta.com.co/scripts/remates_v2'
LEDGER = R + '/shadow_ledger.jsonl'
SCORED = R + '/shadow_scored.jsonl'

ap = argparse.ArgumentParser()
ap.add_argument('--fetch-missing', action='store_true')
args = ap.parse_args()

from football_api.models import ApiFixture, TeamFixtureStat

def get_actual(fixture_api_id):
    """Devuelve (total_shots, fuente) o None."""
    f = ApiFixture.objects.filter(api_id=fixture_api_id).first()
    if not f: return None, 'no_fixture'
    if f.status not in ('FT', 'AET', 'PEN'):
        if not args.fetch_missing: return None, f'status:{f.status}'
        # La BD aún no sincronizó el estado; consultar la API directamente
        try:
            from football_api.client import ApiFootballClient
            _c = ApiFootballClient()
            _d = _c.fixtures(id=fixture_api_id)
            _resp = _d.get('response', [])
            _st = _resp[0]['fixture']['status']['short'] if _resp else None
            if _st not in ('FT', 'AET', 'PEN'): return None, f'api_status:{_st}'
        except Exception as _e:
            return None, f'api_err:{str(_e)[:40]}'
    stats = list(TeamFixtureStat.objects.filter(fixture=f, total_shots__isnull=False))
    if len(stats) == 2:
        # confirm one is home, other away
        tot = sum(s.total_shots for s in stats)
        return tot, 'db'
    # try API fetch
    if args.fetch_missing:
        from football_api.client import ApiFootballClient
        c = ApiFootballClient()
        try:
            d = c.fixtures_statistics(fixture_api_id)
            tot = 0; found = 0
            for t in d.get('response', []):
                for s in (t.get('statistics') or []):
                    if s['type'] == 'Total Shots' and s['value'] is not None:
                        tot += int(s['value']); found += 1
            if found == 2:
                return tot, 'api'
        except Exception as e:
            return None, f'api_err:{str(e)[:60]}'
    return None, 'no_stats'

def parse_ledger():
    entries = []
    if not os.path.exists(LEDGER): return entries
    with open(LEDGER) as fp:
        for line in fp:
            line = line.strip()
            if not line: continue
            try: entries.append(json.loads(line))
            except: pass
    return entries

def parse_scored_keys():
    keys = set()
    if os.path.exists(SCORED):
        with open(SCORED) as fp:
            for line in fp:
                try:
                    e = json.loads(line)
                    keys.add((str(e.get('fixture_api_id')), str(e.get('start'))))
                except: pass
    return keys

entries = parse_ledger()
scored = parse_scored_keys()
now = datetime.now(dtz.utc)
print(f'ledger entries: {len(entries)} | ya puntuados: {len(scored)}')

new_scored = []
seen = set()
for e in entries:
    if 'fixture_api_id' not in e: continue  # old format, no fixture anchor
    key = (str(e.get('fixture_api_id')), str(e.get('start')))
    if key in scored or key in seen: continue
    seen.add(key)
    start = e.get('start', '')
    try:
        st = datetime.fromisoformat(start)
        if st.tzinfo is None: st = st.replace(tzinfo=dtz.utc)
    except Exception:
        continue
    if st > now: continue  # not finished window yet
    actual, src = get_actual(e['fixture_api_id'])
    if actual is None:
        continue
    lam_m = e['lambda_model']; lam_k = e.get('lambda_market')
    rec = dict(e)
    rec['actual_total_shots'] = actual
    rec['source'] = src
    rec['scored_at'] = now.isoformat()
    rec['err_model'] = round(lam_m - actual, 2)
    if lam_k: rec['err_market'] = round(lam_k - actual, 2)
    # hypothetical P&L: pick best-EV side per line with small edge threshold (2pp), 1u stake
    pnl = 0.0; bets = 0; wins = 0
    for L, d in (e.get('lines') or {}).items():
        Lf = float(L)
        ev_o = d.get('ev_over'); ev_u = d.get('ev_under')
        if ev_o is None or ev_u is None: continue
        if ev_o >= 0.02 and ev_o >= (ev_u or -1):
            # bet OVER
            won = actual > Lf
            pnl += (d['over'] - 1) if won else -1.0
            bets += 1; wins += 1 if won else 0
        elif ev_u is not None and ev_u >= 0.02:
            won = actual < Lf
            pnl += (d['under'] - 1) if won else -1.0
            bets += 1; wins += 1 if won else 0
    rec['shadow_bets'] = bets
    rec['shadow_wins'] = wins
    rec['shadow_pnl'] = round(pnl, 3)
    new_scored.append(rec)

if new_scored:
    with open(SCORED, 'a') as fp:
        for r in new_scored:
            fp.write(json.dumps(r, ensure_ascii=False) + '\n')
    print(f'nuevos puntuados: {len(new_scored)}')
    for r in new_scored[:10]:
        print(f"  {r['name'][:40]:40s} real={r['actual_total_shots']} λ_m={r['lambda_model']} err={r['err_model']} | bets={r['shadow_bets']} pnl={r['shadow_pnl']}")
else:
    print('nada nuevo que puntuar (partidos sin terminar o sin stats)')

# ── summary of all scored ──
all_scored = []
if os.path.exists(SCORED):
    with open(SCORED) as fp:
        for line in fp:
            try: all_scored.append(json.loads(line))
            except: pass
if all_scored:
    errs = [r['err_model'] for r in all_scored]
    mkt = [r['err_market'] for r in all_scored if r.get('err_market') is not None]
    pnl = sum(r.get('shadow_pnl', 0) for r in all_scored)
    bets = sum(r.get('shadow_bets', 0) for r in all_scored)
    print()
    print(f'=== RESUMEN SHADOW ({len(all_scored)} partidos) ===')
    print(f'Error absoluto medio modelo: {np.mean(np.abs(errs)):.2f}')
    if mkt: print(f'Error absoluto medio mercado: {np.mean(np.abs(mkt)):.2f}')
    print(f'P&L hipotético (bets EV+>=2pp, stake 1u): {pnl:+.2f}u en {bets} apuestas')
