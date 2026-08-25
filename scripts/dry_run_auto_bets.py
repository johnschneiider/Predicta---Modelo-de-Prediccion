"""
DRY-RUN del auto-betting: replica el embudo completo de selección SIN colocar apuestas.
No llama a validate_coupon ni place_bet. Solo lectura (login + fetch + predict).
"""
import os
import sys
import django

sys.path.insert(0, '/var/www/predicta.com.co')

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
django.setup()

from auto_betting.models import AutoBetConfig
from auto_betting.services import login, fetch_upcoming_matches
from auto_betting.strategy import select_bets
from auto_betting.management.commands.run_auto_bets import (
    find_predicta_league, map_teams, _build_market_data, MARKET_LABELS,
)
from ai_predictions.simple_models import analyze_team_statistics

MIN_TEAM_MATCHES = 10

# Permitir elegir usuario por email: python scripts/dry_run_auto_bets.py [email]
email = sys.argv[1] if len(sys.argv) > 1 else None
qs = AutoBetConfig.objects.filter(activo=True)
if email:
    qs = qs.filter(usuario__email=email)
cfg = qs.first()
if not cfg:
    print('Sistema inactivo o sin config.')
    raise SystemExit(1)
print(f'👤 Usuario: {cfg.usuario.email}')

token, rk = login(cfg.ticket, cfg.punter_id)
print('Login:', 'OK' if token else 'FAIL')
if not token:
    raise SystemExit(1)

matches = fetch_upcoming_matches(cfg.horas_adelante)
print(f'Partidos próximas {cfg.horas_adelante}h: {len(matches)}\n')

n_league_fail = 0
n_team_fail = 0
n_data_fail = 0
n_no_value = 0
seleccionados = []

for m in matches:
    league = find_predicta_league(m)
    if not league:
        n_league_fail += 1
        continue

    home_team, away_team = map_teams(m, league)
    if not home_team:
        n_team_fail += 1
        continue

    home_stats = analyze_team_statistics(home_team, league, 'goals')
    away_stats = analyze_team_statistics(away_team, league, 'goals')
    total_home = home_stats['home_matches'] + home_stats['away_matches']
    total_away = away_stats['home_matches'] + away_stats['away_matches']
    if total_home < MIN_TEAM_MATCHES or total_away < MIN_TEAM_MATCHES:
        n_data_fail += 1
        continue

    markets = _build_market_data(m, home_team, away_team, league)
    if not markets:
        continue

    candidates = select_bets(markets, cfg.cuota_minima, min_p=0.50, min_confidence=0.35)
    if not candidates:
        n_no_value += 1
        continue

    best = candidates[0]
    market_label = MARKET_LABELS.get(best['market'], best['market'])
    side = best['side']
    sel = f"{'Over' if side == 'over' else ('Under' if side == 'under' else side)}"
    if best.get('line') is not None:
        sel += f" {best['line']}"
    seleccionados.append({
        'match': f"{home_team} vs {away_team}",
        'liga': league.name,
        'mercado': market_label,
        'sel': sel,
        'cuota': best['cuota'],
        'p': best['p'],
        'ev': best['ev'],
    })

print('=== EMBUDO ===')
print(f'  Total partidos:            {len(matches)}')
print(f'  Sin liga mapeada:          {n_league_fail}')
print(f'  Sin mapeo de equipos:      {n_team_fail}')
print(f'  Datos insuficientes (<10): {n_data_fail}')
print(f'  Sin value (EV/P/conf):     {n_no_value}')
print(f'  => SELECCIONADOS:          {len(seleccionados)}')
print()

print('=== CANDIDATOS (orden EV desc) ===')
for s in sorted(seleccionados, key=lambda x: -x['ev']):
    print(f"  {s['match']} | {s['mercado']} {s['sel']} @{s['cuota']} | P={s['p']*100:.1f}% EV={s['ev']*100:+.1f}% | {s['liga']}")
