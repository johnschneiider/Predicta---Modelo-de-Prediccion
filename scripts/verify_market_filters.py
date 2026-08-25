import os, django
os.environ['DJANGO_SETTINGS_MODULE'] = 'betting_bot.settings'
django.setup()

from auto_betting.strategy import get_official_predictions, select_bets, MARKET_FILTERS
from auto_betting.services import fetch_upcoming_matches
from auto_betting.management.commands.run_auto_bets import _build_market_data, find_predicta_league, map_teams

print('MARKET_FILTERS:', MARKET_FILTERS)
print()

matches = fetch_upcoming_matches(24)
tot, tot_new = {}, {}
n_proc = 0
for m in matches:
    league = find_predicta_league(m)
    if not league:
        continue
    home, away = map_teams(m, league)
    if not home or not away:
        continue
    try:
        markets = _build_market_data(m, home, away, league)
    except Exception:
        continue
    n_proc += 1
    old = select_bets(markets, 2.0, min_p=0.50, min_confidence=0.35)
    for c in old:
        tot[c['market']] = tot.get(c['market'], 0) + 1
    new = select_bets(markets, 2.0, min_p=0.50, min_confidence=0.35, market_filters=MARKET_FILTERS)
    for c in new:
        tot_new[c['market']] = tot_new.get(c['market'], 0) + 1
    if n_proc >= 80:
        break

print(f'Partidos procesados: {n_proc}')
print()
print('ANTES (global P>=0.50):')
for k, v in sorted(tot.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')
print()
print('DESPUES (filtros por mercado):')
for k, v in sorted(tot_new.items(), key=lambda x: -x[1]):
    print(f'  {k}: {v}')
print()
print('RESUMEN:')
for k in tot:
    a, b = tot.get(k, 0), tot_new.get(k, 0)
    red = (1 - b / a) * 100 if a else 0
    print(f'  {k}: {a} -> {b} (reduce {red:.0f}%)')
