"""
Comando de management que ejecuta el auto-betting v7 — Predicción Oficial + Validación + Calibración:
1. Login BetPlay (ticket → token)
2. Escanea partidos de próximas 24h (filtrado: sin eSports/reservas/femenil)
3. Filtro de datos insuficientes: valida cobertura por mercado (≥10 partidos por equipo)
   [Fase 3 — si un mercado no tiene datos, se salta automáticamente]
4. Predicción Oficial: ejecuta el pipeline completo de /ai/predict/ y promedia
   todos los modelos por mercado (Dixon-Coles + SimpleAvg + Ensemble + Híbrido
   para goles; shots_prediction_model + xg_shots_model para remates; etc.)
   Mercados activos: córners, goles, remates totales, BTTS.
   [Fase 1 — DESACTIVADO: tiros a puerta y 1X2]
   [Fase 2 — CONECTADO al motor oficial: promedio ponderado, no modelos individuales]
   [Fase 3 — VALIDACIÓN DE DATOS: salta mercados sin cobertura suficiente]
   [Fase 4 — CALIBRACIÓN: shrinkage de probabilidades, cap 65%, EV calibrado]
5. Trae cuotas de BetPlay para cada mercado
6. Selecciona por EV > 0 Y P > 50% Y confidence >= 0.35 Y cuota >= mínima
7. Coloca hasta N apuestas de 500 COP
"""

import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone as django_timezone

from auto_betting.models import AutoBetConfig, AutoBet, DailyCounter
from auto_betting.services import (
    login, fetch_upcoming_matches,
    fetch_corners_odds, fetch_goals_odds,
    fetch_shots_on_target_odds, fetch_btts_odds,
    validate_coupon, place_bet,
)
from auto_betting.strategy import (
    get_official_predictions, select_bets, get_market_filters, get_global_config,
)

logger = logging.getLogger('auto_betting')

MARKET_LABELS = {
    'corners': 'Total de Tiros de Esquina',
    'shots_on_target': 'Total de tiros a puerta',
    'goals': 'Total de goles',
    'total_shots': 'Número total de disparos',  # legacy, no se usa
    'x12': 'Resultado Final',
    'btts': 'Ambos Equipos Marcarán',
}

# Tope diario de apuestas por SUBMERCADO (mercado+lado, ej. goles-over).
# Fix 2026-08-23: el 23-Ago el sistema colocó 15 apuestas de goles-over el
# mismo día, todas correlacionadas al mismo error de calibración del modelo
# (λ inflado) → 13 perdidas juntas. Este tope corta la correlación: aunque el
# modelo esté mal en un submercado, el daño diario queda acotado.
MAX_BETS_PER_SUBMARKET_DAILY = 5


def _side_prefix(side):
    """Prefijo de selección para agrupar por lado (Over/Under/Sí/No/1/X/2)."""
    if side == 'over':
        return 'Over'
    if side == 'under':
        return 'Under'
    return side


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
    """
    Construye la lista de datos de mercado usando la Predicción Oficial de Predicta
    (promedio ponderado de todos los modelos, igual que /ai/predict/).

    Fase 2 — reemplaza las llamadas a modelos individuales crudos por el pipeline oficial.
    Mercarios activos: córners, goles, remates totales, BTTS.
    """
    markets = []

    official = get_official_predictions(home_team, away_team, league)
    if not official:
        return markets

    # Córners
    if 'corners_total' in official:
        corners = official['corners_total']
        markets.append({
            'market': 'corners', 'type': 'over_under',
            'lambda': corners['lambda'],
            'confidence': corners.get('confidence', 0.35),
            'odds': fetch_corners_odds(match['event_id']),
        })

    # Goles totales
    if 'goals_total' in official:
        goals = official['goals_total']
        markets.append({
            'market': 'goals', 'type': 'over_under',
            'lambda': goals['lambda'],
            'confidence': goals.get('confidence', 0.5),
            'odds': fetch_goals_odds(match['event_id']),
        })

    # Tiros a puerta (shots on target) — el mercado real en BetPlay
    if 'shots_on_target' in official:
        sot = official['shots_on_target']
        markets.append({
            'market': 'shots_on_target', 'type': 'over_under',
            'lambda': sot['lambda'],
            'confidence': sot.get('confidence', 0.5),
            'odds': fetch_shots_on_target_odds(match['event_id']),
        })

    # Ambos marcan
    if 'both_teams_score' in official:
        btts = official['both_teams_score']
        markets.append({
            'market': 'btts', 'type': 'btts',
            'p_yes': btts['yes'],
            'confidence': btts.get('confidence', 0.5),
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

    def add_arguments(self, parser):
        parser.add_argument(
            '--email', type=str, default=None,
            help='Correo del usuario. Si se omite, ejecuta para todos los usuarios con config activa.',
        )

    def handle(self, *args, **options):
        email = options.get('email')
        configs = AutoBetConfig.objects.filter(activo=True).select_related('usuario')
        if email:
            configs = configs.filter(usuario__email=email)
        if not configs.exists():
            self.stderr.write("❌ No hay configuraciones activas. Crea AutoBetConfig en admin.")
            return
        for config in configs:
            self._run_for_config(config)

    def _pnl_sistema_hoy(self, owner, hoy):
        """
        P&L neto (COP) de las apuestas del SISTEMA asentadas hoy, para el
        usuario dado. Se calcula sobre HistorialApuesta (fuente de verdad de
        resultados) filtrando is_system=True y placed_date de hoy.
        Devuelve negativo cuando hay pérdida. Si no hay historial, devuelve 0.
        """
        from auto_betting.models import HistorialApuesta
        qs = HistorialApuesta.objects.filter(
            usuario=owner, is_system=True,
            placed_date__date=hoy, bet_status__in=['WON', 'LOST'],
        )
        agg = qs.aggregate(st=Sum('stake'), pay=Sum('payout'))
        stake = agg['st'] or 0
        payout = agg['pay'] or 0
        return (payout - stake) / 1000.0

    def _run_for_config(self, config):
        owner = config.usuario
        self.stdout.write(f"\n👤 Usuario: {owner.email}")

        # 1. Límite diario + reconciliación (Fix 3)
        hoy = django_timezone.localdate()
        counter, _ = DailyCounter.objects.get_or_create(usuario=owner, fecha=hoy)
        # Reconciliar contador desde el conteo real de AutoBet hoy
        # Protege contra runs manuales que no persistieron el counter (bug v3)
        count_real = AutoBet.objects.filter(usuario=owner, creado__date=hoy).count()
        if counter.apuestas_colocadas != count_real:
            self.stdout.write(
                f"⚠️ DailyCounter desincronizado: DB={counter.apuestas_colocadas} "
                f"vs real={count_real}. Reconciliando."
            )
            counter.apuestas_colocadas = count_real
            counter.save()
        if counter.apuestas_colocadas >= config.max_apuestas_diarias:
            self.stdout.write(f"✅ Límite diario alcanzado ({counter.apuestas_colocadas}/{config.max_apuestas_diarias}).")
            return

        disponibles = config.max_apuestas_diarias - counter.apuestas_colocadas

        # Controles globales (auditoría 2026-08-23): cuota mínima global,
        # stop-loss diario, tope de exposición por evento, cap de calibración.
        gcfg = get_global_config()
        # Cuota por usuario (2026-08-25): la cuota mínima de cada cuenta se toma
        # SOLO de su propia config (/auto-betting/configuracion/). El piso global
        # (cuota_minima_global) ya no pisa la config per-user.
        cuota_minima_efectiva = config.cuota_minima
        stop_loss_diario = gcfg.get('stop_loss_diario_cop', 0) or 0
        max_exp_evento = gcfg.get('max_exposicion_evento_cop', 0) or 0
        calib_cap = gcfg.get('calib_cap', 0.58) or 0.58

        # Stop-loss diario: P&L (solo sistema) del día de HOY. Si ya cayó por
        # debajo del umbral (negativo), no se colocan más apuestas.
        if stop_loss_diario < 0:
            pnl_hoy = self._pnl_sistema_hoy(owner, hoy)
            if pnl_hoy <= stop_loss_diario:
                self.stdout.write(
                    f"🛑 Stop-loss diario activado: P&L hoy={pnl_hoy:,.0f} COP ≤ "
                    f"{stop_loss_diario:,.0f} COP. Auto-betting detenido para {owner.email}."
                )
                return

        self.stdout.write(
            f"🎯 Auto-betting v5 multi-mercado: {disponibles} disponibles "
            f"(cuota ≥ {cuota_minima_efectiva}, P ≥ 50%, conf ≥ 0.35, cap calib {calib_cap})."
        )

        # 2. Login
        token, routing_key = login(config.ticket, config.punter_id)
        if not token:
            self.stderr.write("❌ Login BetPlay falló. Verifica el ticket en AutoBetConfig.")
            return

        # 3. Partidos próximos
        matches = fetch_upcoming_matches(config.horas_adelante)
        self.stdout.write(f"📋 {len(matches)} partidos en próximas {config.horas_adelante}h.")

        apuestas_colocadas = 0

        for match in matches:
            if apuestas_colocadas >= disponibles:
                break

            league = find_predicta_league(match)
            if not league:
                continue

            home_team, away_team = map_teams(match, league)
            if not home_team:
                continue

            # Filtro: mínimo de partidos por equipo (datos insuficientes)
            # Fase 3 — valida por mercado específico, no solo goles.
            # Fix 2026-08-23: NO descartar el partido entero por falta de datos
            # de goles. get_official_predictions() ya filtra mercado por mercado
            # según coverage, así que aquí solo se salta el partido si NINGÚN
            # mercado tiene datos suficientes (ej. córners con datos perfectos
            # debe poder apostarse aunque no haya datos de goles).
            from auto_betting.strategy import validate_market_data
            coverage = validate_market_data(home_team, away_team, league)
            if not any(coverage.values()):
                self.stdout.write(
                    f"  \u23ed\ufe0f {home_team} vs {away_team}: sin datos suficientes "
                    f"en ningún mercado {coverage}. Partido saltado."
                )
                continue
            if not coverage.get('goals_total', False):
                mercados_ok = [k for k, v in coverage.items() if v]
                self.stdout.write(
                    f"  \u2139\ufe0f {home_team} vs {away_team}: sin datos de goles, "
                    f"pero continúa con mercados disponibles: {mercados_ok}"
                )

            # 4+5. Predicciones y cuotas
            markets = _build_market_data(match, home_team, away_team, league)
            if not markets:
                continue

            # 6. Selección por EV + filtros por SUBMERCADO (mercado+lado, ej.
            # corners_over vs corners_under). Fuente: MarketFilterConfig
            # (global, editable solo por admin en /auto-betting/configuracion/).
            # Cuota por usuario (2026-08-25): las cuotas mínimas globales por
            # submercado (MarketFilterConfig.*_min_cuota) ya no se aplican —
            # serían un piso global que pisaría la cuota mínima per-user.
            # Se neutralizan (0) y queda solo cuota_minima_efectiva del usuario.
            market_filters = get_market_filters()
            market_filters = {k: {**v, 'min_cuota': 0.0} for k, v in market_filters.items()}

            candidates = select_bets(
                markets, cuota_minima_efectiva,
                min_p=0.50, min_confidence=0.35,
                market_filters=market_filters,
                calib_cap=calib_cap,
            )
            if not candidates:
                continue

            event_data = {'event_id': match['event_id'], 'path': []}

            # Iterar sobre TODOS los candidates (múltiples mercados por partido)
            for best in candidates:
                if apuestas_colocadas >= disponibles:
                    break

                # Deduplicación por evento + mercado (sin restricción de fecha)
                # Fix 2026-08-21: antes solo miraba creado__date=hoy, lo que permitía
                # duplicar apuestas de partidos futuros apostadas en días anteriores.
                mercado_label_check = MARKET_LABELS.get(best['market'], best['market'])
                ya_apostado_este_mercado = AutoBet.objects.filter(
                    usuario=owner,
                    evento_id=match['event_id'], mercado=mercado_label_check,
                    estado__in=['OPEN', 'WIN', 'LOSE', 'VOID']
                ).exists()
                if ya_apostado_este_mercado:
                    continue

                # Tope diario por submercado (mercado+lado). Fix 2026-08-23:
                # evita que un modelo descalibrado queme el día entero en un
                # solo tipo de apuesta correlacionada (ej. 15 goles-over).
                side_prefix = _side_prefix(best['side'])
                count_submercado = AutoBet.objects.filter(
                    usuario=owner, creado__date=hoy,
                    mercado=mercado_label_check,
                    seleccion__startswith=side_prefix,
                ).count()
                if count_submercado >= MAX_BETS_PER_SUBMARKET_DAILY:
                    self.stdout.write(
                        f"  ⛔ Tope diario por submercado alcanzado "
                        f"({mercado_label_check} {side_prefix}: "
                        f"{count_submercado}/{MAX_BETS_PER_SUBMARKET_DAILY}). "
                        f"Saltando {home_team} vs {away_team}."
                    )
                    continue

                # Tope de exposición combinada (todas las cuentas) por
                # evento+mercado. Suma stake ya colocado (OPEN/WIN/LOSE/VOID)
                # de TODOS los usuarios + el stake propuesto.
                if max_exp_evento > 0:
                    market_label_exp = MARKET_LABELS.get(best['market'], best['market'])
                    stake_existente = AutoBet.objects.filter(
                        evento_id=match['event_id'], mercado=market_label_exp,
                        estado__in=['OPEN', 'WIN', 'LOSE', 'VOID'],
                    ).aggregate(s=Sum('stake'))['s'] or 0
                    # stake en unidades Kambi (÷1000 = COP)
                    exp_actual_cop = stake_existente / 1000.0
                    exp_nueva_cop = config.stake / 1000.0
                    if exp_actual_cop + exp_nueva_cop > max_exp_evento:
                        self.stdout.write(
                            f"  ⚠️ Exposición máxima por evento alcanzada "
                            f"({exp_actual_cop:,.0f}+{exp_nueva_cop:,.0f} > {max_exp_evento:,.0f} COP) "
                            f"en {home_team} vs {away_team} [{market_label_exp}]. Saltando."
                        )
                        continue

                outcome = best['offer']
                market_label = MARKET_LABELS.get(best['market'], best['market'])
                seleccion = _seleccion_label(best)
                pred_value = _pred_value(best, markets)

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
                        usuario=owner,
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
                    f"{seleccion} @{best['cuota']} | P={best['p']*100:.1f}% (raw={best.get('p_raw',best['p'])*100:.1f}%) "
                    f"EV={best['ev']*100:+.1f}% | coupon={place_resp.get('coupon_ref')}"
                )

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🏁 Auto-betting v4 completado: {apuestas_colocadas} apuestas colocadas."
            )
        )
