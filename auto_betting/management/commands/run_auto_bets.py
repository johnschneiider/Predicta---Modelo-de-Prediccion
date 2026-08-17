"""
Comando de management que ejecuta el auto-betting v4 multi-mercado:
1. Login BetPlay (ticket → token)
2. Escanea partidos de próximas 24h (filtrados: sin eSports/reservas/femenil)
3. Filtro de datos insuficientes: equipos con <10 partidos en ventana 730d
4. Predice 6 mercados: córners, tiros a puerta, goles, remates totales, 1X2, ambos marcan
5. Trae cuotas de BetPlay para cada mercado
6. Selecciona por EV > 0 Y P > 50% Y confidence >= 0.35 Y cuota >= mínima
7. Coloca hasta N apuestas de 500 COP
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone as django_timezone

from auto_betting.models import AutoBetConfig, AutoBet, DailyCounter
from auto_betting.services import (
    login, fetch_upcoming_matches,
    fetch_corners_odds, fetch_shots_on_target_odds,
    fetch_goals_odds, fetch_total_shots_odds, fetch_x12_odds, fetch_btts_odds,
    validate_coupon, place_bet,
)
from auto_betting.strategy import (
    predict_corners, predict_shots_on_target, predict_goals,
    predict_total_shots, predict_x12, predict_btts, select_bets,
)

logger = logging.getLogger('auto_betting')

MARKET_LABELS = {
    'corners': 'Total de Tiros de Esquina',
    'shots_on_target': 'Total de tiros a puerta',
    'goals': 'Total de goles',
    'total_shots': 'Número total de disparos',
    'x12': 'Resultado Final',
    'btts': 'Ambos Equipos Marcarán',
}


def find_predicta_league(match):
    """Encuentra la liga de Predicta para un partido de Kambi (solo mapeo exacto)."""
    from football_data.models import League
    from value_betting.mapping import map_league

    name = map_league(match['league_path'])
    if name:
        return League.objects.filter(name=name).first()
    return None


def map_teams(match, league):
    """Mapea los nombres de equipos de Kambi a los de Predicta (fuzzy)."""
    from football_data.models import Match
    from value_betting.mapping import fuzzy_match_team

    teams_qs = Match.objects.filter(league=league).order_by('-date')[:500]
    all_teams = set()
    for m in teams_qs:
        all_teams.add(m.home_team)
        all_teams.add(m.away_team)
    all_teams_list = list(all_teams)

    home_result = fuzzy_match_team(match['home'], all_teams_list, threshold=0.65)
    away_result = fuzzy_match_team(match['away'], all_teams_list, threshold=0.65)
    if not home_result or not away_result:
        return None, None
    return home_result[0], away_result[0]


def _build_market_data(match, home_team, away_team, league):
    """Construye la lista de datos de mercado (predicción + cuotas) para un partido."""
    markets = []

    corners = predict_corners(home_team, away_team, league)
    if corners:
        markets.append({
            'market': 'corners', 'type': 'over_under',
            'lambda': corners['lambda'],
            'confidence': corners.get('confidence', 0.35),
            'odds': fetch_corners_odds(match['event_id']),
        })

    shots = predict_shots_on_target(home_team, away_team, league)
    if shots:
        markets.append({
            'market': 'shots_on_target', 'type': 'over_under',
            'lambda': shots['lambda'],
            'confidence': shots.get('confidence', 0.5),
            'odds': fetch_shots_on_target_odds(match['event_id']),
        })

    goals = predict_goals(home_team, away_team, league)
    if goals:
        markets.append({
            'market': 'goals', 'type': 'over_under',
            'lambda': goals['lambda'],
            'confidence': goals.get('confidence', 0.5),
            'odds': fetch_goals_odds(match['event_id']),
        })

    tshots = predict_total_shots(home_team, away_team, league)
    if tshots:
        markets.append({
            'market': 'total_shots', 'type': 'over_under',
            'lambda': tshots['lambda'],
            'confidence': tshots.get('confidence', 0.5),
            'odds': fetch_total_shots_odds(match['event_id']),
        })

    x12 = predict_x12(home_team, away_team, league)
    if x12:
        markets.append({
            'market': 'x12', 'type': 'x12',
            'probs': x12,
            'confidence': 0.5,
            'odds': fetch_x12_odds(match['event_id']),
        })

    btts = predict_btts(home_team, away_team, league)
    if btts:
        markets.append({
            'market': 'btts', 'type': 'btts',
            'p_yes': btts['yes'],
            'confidence': 0.5,
            'odds': fetch_btts_odds(match['event_id']),
        })

    return markets


def _seleccion_label(best):
    side = best['side']
    if side in ('over', 'under'):
        return f"{'Over' if side == 'over' else 'Under'} {best['line']}"
    return side


def _pred_value(best, markets):
    """Valor predicho (lambda) para el mercado seleccionado (0 para categóricos)."""
    for md in markets:
        if md['market'] == best['market']:
            if md['type'] == 'over_under':
                return md.get('lambda') or 0.0
            return 0.0
    return 0.0


class Command(BaseCommand):
    help = "Ejecuta el auto-betting multi-mercado (córners, tiros, goles, remates, 1X2, BTTS)"

    def handle(self, *args, **options):
        config = AutoBetConfig.objects.first()
        if not config:
            self.stderr.write("❌ No hay configuración. Crea AutoBetConfig en admin.")
            return
        if not config.activo:
            self.stdout.write("Sistema inactivo. Saliendo.")
            return

        # 1. Límite diario
        hoy = django_timezone.now().date()
        counter, _ = DailyCounter.objects.get_or_create(fecha=hoy)
        if counter.apuestas_colocadas >= config.max_apuestas_diarias:
            self.stdout.write(f"✅ Límite diario alcanzado ({counter.apuestas_colocadas}/{config.max_apuestas_diarias}).")
            return

        disponibles = config.max_apuestas_diarias - counter.apuestas_colocadas
        self.stdout.write(f"🎯 Auto-betting v4 multi-mercado: {disponibles} disponibles (cuota ≥ {config.cuota_minima}, P ≥ 50%, conf ≥ 0.35).")

        # 2. Login
        token, routing_key = login(config.ticket, config.punter_id)
        if not token:
            self.stderr.write("❌ Login BetPlay falló. Verifica el ticket en AutoBetConfig.")
            return

        # 3. Partidos próximos
        matches = fetch_upcoming_matches(config.horas_adelante)
        self.stdout.write(f"📋 {len(matches)} partidos en próximas {config.horas_adelante}h.")

        eventos_ya_apostados = set(
            AutoBet.objects.filter(creado__date=hoy).values_list('evento_id', flat=True)
        )

        apuestas_colocadas = 0

        for match in matches:
            if apuestas_colocadas >= disponibles:
                break
            if match['event_id'] in eventos_ya_apostados:
                continue

            league = find_predicta_league(match)
            if not league:
                continue

            home_team, away_team = map_teams(match, league)
            if not home_team:
                continue

            # Filtro: mínimo de partidos por equipo (datos insuficientes)
            from ai_predictions.simple_models import analyze_team_statistics
            MIN_TEAM_MATCHES = 10
            home_stats = analyze_team_statistics(home_team, league, 'goals')
            away_stats = analyze_team_statistics(away_team, league, 'goals')
            total_home = home_stats['home_matches'] + home_stats['away_matches']
            total_away = away_stats['home_matches'] + away_stats['away_matches']
            if total_home < MIN_TEAM_MATCHES or total_away < MIN_TEAM_MATCHES:
                self.stdout.write(f"  \u23ed\ufe0f {home_team} vs {away_team}: datos insuficientes (home={total_home}, away={total_away})")
                continue

            # 4+5. Predicciones y cuotas
            markets = _build_market_data(match, home_team, away_team, league)
            if not markets:
                continue

            # 6. Selección por EV + P>50% + confidence\u22650.35
            candidates = select_bets(markets, config.cuota_minima, min_p=0.50, min_confidence=0.35)
            if not candidates:
                continue

            best = candidates[0]
            outcome = best['offer']
            market_label = MARKET_LABELS.get(best['market'], best['market'])
            seleccion = _seleccion_label(best)
            pred_value = _pred_value(best, markets)

            event_data = {'event_id': match['event_id'], 'path': []}

            # 7. Validar
            success, val_resp = validate_coupon(token, outcome, event_data, config.stake)
            if not success:
                logger.warning(f"Validate falló {match['home']} vs {match['away']} ({market_label}): {val_resp}")
                continue

            # 8. Colocar
            success, place_resp = place_bet(token, outcome, event_data, config.stake)
            if not success:
                logger.error(f"Place falló {match['home']} vs {match['away']} ({market_label}): {place_resp}")
                continue

            # 9. Guardar
            with transaction.atomic():
                AutoBet.objects.create(
                    evento_id=match['event_id'],
                    home_team=home_team,
                    away_team=away_team,
                    liga=league.name,
                    start_time=match['start_time'],
                    mercado=market_label,
                    seleccion=seleccion,
                    linea=best['line'],
                    cuota=best['cuota'],
                    corners_predichos=pred_value,
                    predicta_prob=round(best['p'] * 100, 2),
                    edge=round((best['p'] - 1.0 / best['cuota']) * 100, 2),
                    ev=round(best['ev'], 4),
                    coupon_ref=place_resp.get('coupon_ref'),
                    bet_ref=place_resp.get('bet_ref'),
                    stake=config.stake,
                    potential_payout=place_resp.get('potential_payout'),
                    estado='OPEN',
                )
                counter.apuestas_colocadas += 1
                counter.save()

            apuestas_colocadas += 1
            self.stdout.write(
                f"✅ Apuesta {apuestas_colocadas}: {home_team} vs {away_team} | {market_label} "
                f"{seleccion} @{best['cuota']} | P={best['p']*100:.1f}% EV={best['ev']*100:+.1f}% "
                f"| coupon={place_resp.get('coupon_ref')}"
            )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🏁 Auto-betting v4 completado: {apuestas_colocadas} apuestas colocadas."
            )
        )
