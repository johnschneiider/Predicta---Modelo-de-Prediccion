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

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone as django_timezone

from auto_betting import basket_1q2q as basket_1q2q
from auto_betting.models import AutoBetConfig, AutoBet, DailyCounter
from auto_betting.services import (
    login, fetch_upcoming_matches,
    fetch_corners_odds, fetch_goals_odds,
    fetch_shots_on_target_odds, fetch_btts_odds, fetch_total_shots_odds,
    fetch_market_odds, validate_coupon, place_bet,
)
from auto_betting.strategy import (
    get_official_predictions, select_bets, get_market_filters, get_global_config,
    submarket_clv_health,
)

logger = logging.getLogger('auto_betting')

# 2026-09-04 (decisión John): anti-movimiento de línea. Si la cuota del
# outcome subió >= este % desde que la evaluamos (la casa corrige en contra),
# se aborta la apuesta. Caso real: Sparta Under 9.5 córners 2.02 -> 2.55 (+26%)
# y Betis 2.12 -> 2.33 (+10%) — ambas perdidas con CLV -20.8/-9.0.
LINE_MOVE_ABORT_PCT = 0.08

MARKET_LABELS = {
    'corners': 'Total de Tiros de Esquina',
    'shots_on_target': 'Total de tiros a puerta',
    'remates': 'Total de Tiros (Resuelta usando Opta Data)',  # motor v2.3 (integrado 2026-09-14)
    'goals': 'Total de goles',
    'total_shots': 'Número total de disparos',  # legacy, no se usa
    'x12': 'Resultado Final',
    'btts': 'Ambos Equipos Marcarán',
}

# 2026-08-29: tope diario por SUBMERCADO eliminado por decisión de John.
# Antes existía MAX_BETS_PER_SUBMARKET_DAILY = 5 (5 apuestas/día por
# mercado+lado). Sin ese tope, se apuesta TODOS los candidatos válidos
# (sujetos solo a max_apuestas_diarias + deduplicación por evento+mercado).


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


def _build_market_data(match, home_team, away_team, league, sot_test=False):
    """
    Construye la lista de datos de mercado usando la Predicción Oficial de Predicta
    (promedio ponderado de todos los modelos, igual que /ai/predict/).

    Fase 2 — reemplaza las llamadas a modelos individuales crudos por el pipeline oficial.
    Mercarios activos: córners, goles, remates totales, BTTS.
    """
    markets = []

    # ── Remates totales — MOTOR v2.3 (integración 2026-09-14, decisión John) ──
    # Independiente del pipeline legacy por nombres: ancla por IDs de
    # API-Football (sin fuzzy de clubes) + GBM v2.3 calibrado. Las compuertas
    # de cada usuario y de edge se aplican igual (select_bets: devig, edge
    # vs cuota justa >= 5pp, tiers por cuota, EV mínimo, distancia línea-λ y
    # filtros del submercado remates_over/under de MarketFilterConfig).
    try:
        # Orden: primero las cuotas (1 llamada, barato); el modelo solo se
        # ejecuta si el evento realmente tiene el mercado (≈3% de eventos).
        _odds_rem = fetch_total_shots_odds(match['event_id'])
        if _odds_rem:
            from auto_betting.remates_engine import predict_remates_for_kambi
            rp = predict_remates_for_kambi(match)
            if rp:
                clv_ok, avg_clv, n_clv = submarket_clv_health(
                    'Total de Tiros (Resuelta usando Opta Data)', n=30)
                if not clv_ok:
                    logger.warning(
                        f'CLV BREAKER: remates totales SALTADO — CLV promedio '
                        f'{avg_clv:.2f} en {n_clv} asentadas ({home_team} vs {away_team})')
                else:
                    markets.append({
                        'market': 'remates', 'type': 'over_under',
                        'lambda': rp['lambda'],
                        'confidence': 0.5,
                        'odds': _odds_rem,
                    })
                    logger.info(
                        f'remates_v2: λ={rp["lambda"]} para {home_team} vs {away_team} '
                        f'(fixture {rp["fixture_api_id"]}, n={rp["n_home"]}/{rp["n_away"]})')
    except Exception as e:
        logger.error(f'remates_v2: error en {home_team} vs {away_team}: {e}')

    # Resultado Final 1X2 — motor x12_v2 migrado del paperbet (2026-10-03,
    # pedido de John). Usa el MISMO modelo/features/margen que el paper
    # (auto_betting/x12_engine.py): la probabilidad que llega aquí ya está
    # calibrada (precalibrated=True), así que select_bets no la vuelve a
    # encoger. La compuerta (P>=0.45, edge>=5pp vs fair devig, cuota>=1.80)
    # es la misma del ROI en papel y vive en MarketFilterConfig['x12'].
    # Es independiente de la Predicción Oficial (no usa `official`), por eso
    # va antes del early-return de abajo.
    # OJO: a diferencia del paper, producción excluye domingos y aplica el
    # anti-movimiento de línea + dedup por evento/mercado (reglas vigentes).
    try:
        from auto_betting.x12_engine import predict_x12_probs
        probs_x12 = predict_x12_probs(match, home_team, away_team, league)
        if probs_x12:
            markets.append({
                'market': 'x12', 'type': 'x12',
                'probs': probs_x12,
                'confidence': 1.0,
                'precalibrated': True,
                'odds': fetch_market_odds(match['event_id'], 'Resultado Final'),
            })
    except Exception as e:
        logger.error(f'x12_v2: error en {home_team} vs {away_team}: {e}')

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
    # 2026-09-04: CLV breaker (paso 4 auditoría SOT). Si el CLV móvil de las
    # últimas 30 apuestas asentadas del submercado es < 0, se salta hoy.
    if 'shots_on_target' in official:
        clv_ok, avg_clv, n_clv = submarket_clv_health('Total de tiros a puerta', n=30)
        if not clv_ok and not sot_test:
            logger.warning(
                f'CLV BREAKER: submercado tiros a puerta SALTADO hoy — '
                f'CLV promedio {avg_clv:.2f} en {n_clv} apuestas asentadas '
                f'({home_team} vs {away_team})')
        elif not clv_ok and sot_test:
            logger.warning(
                f'CLV BREAKER BYPASS (--sot-test): tiros a puerta incluido a '
                f'pesar de CLV {avg_clv:.2f} en {n_clv} asentadas — TEST de '
                f'modelo nuevo ({home_team} vs {away_team})')
            sot = official['shots_on_target']
            markets.append({
                'market': 'shots_on_target', 'type': 'over_under',
                'lambda': sot['lambda'],
                'confidence': sot.get('confidence', 0.5),
                'odds': fetch_shots_on_target_odds(match['event_id']),
            })
        else:
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
        parser.add_argument(
            '--today', action='store_true', default=False,
            help='Solo partidos que arrancan HOY (fecha local Bogotá). El cron normal sigue con las 24h completas.',
        )
        parser.add_argument(
            '--sot-test', action='store_true', default=False,
            help='Bypass del CLV breaker SOLO para tiros a puerta en esta corrida (test de modelo nuevo). El cron no usa este flag.',
        )
        parser.add_argument(
            '--dry-run', action='store_true', default=False,
            help='Simula la corrida completa SIN apostar: no hace login, no valida ni coloca, no escribe AutoBet. Útil para probar umbrales/mercados nuevos con --email.',
        )

    def handle(self, *args, **options):
        email = options.get('email')
        only_today = options.get('today', False)
        sot_test = options.get('sot_test', False)
        dry_run = options.get('dry_run', False)
        configs = AutoBetConfig.objects.filter(activo=True).select_related('usuario')
        if email:
            configs = configs.filter(usuario__email=email)
        if not configs.exists():
            self.stderr.write("❌ No hay configuraciones activas. Crea AutoBetConfig en admin.")
            return
        for config in configs:
            self._run_for_config(config, only_today=only_today, sot_test=sot_test, dry_run=dry_run)

    def _run_for_config(self, config, only_today=False, sot_test=False, dry_run=False):
        owner = config.usuario
        self.stdout.write(f"\n👤 Usuario: {owner.email}{' [DRY-RUN]' if dry_run else ''}")

        # 1. Límite diario + reconciliación (Fix 3)
        # Dry-run: lectura pura, sin crear/reconciliar el contador.
        hoy = django_timezone.localdate()
        if dry_run:
            counter = DailyCounter.objects.filter(usuario=owner, fecha=hoy).first()
            if counter is None:
                counter = DailyCounter(usuario=owner, fecha=hoy, apuestas_colocadas=0)
        else:
            counter, _ = DailyCounter.objects.get_or_create(usuario=owner, fecha=hoy)
        # Reconciliar contador desde el conteo real de AutoBet hoy
        # Protege contra runs manuales que no persistieron el counter (bug v3)
        count_real = (AutoBet.objects
                      .filter(usuario=owner, creado__date=hoy)
                      .exclude(mercado=basket_1q2q.MERCADO)
                      .count())
        if counter.apuestas_colocadas != count_real:
            self.stdout.write(
                f"⚠️ DailyCounter desincronizado: DB={counter.apuestas_colocadas} "
                f"vs real={count_real}. Reconciliando."
            )
            counter.apuestas_colocadas = count_real
            if not dry_run:
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
        max_exp_evento = gcfg.get('max_exposicion_evento_cop', 0) or 0
        calib_cap = gcfg.get('calib_cap', 0.58) or 0.58

        # 2026-09-04 (decisión John): stop-loss diario GLOBAL eliminado.
        # La administración de capital es responsabilidad de cada usuario
        # (stake fijo o % del balance en su config, vía resolve_stake abajo).

        # Gestor de capital (2026-09-01): el stake puede ser FIJO (config.stake,
        # comportamiento histórico) o COMPUESTO (% del balance paralelo).
        # `None` => NO apostar para este usuario (sin balance declarado, sin
        # saldo o % por debajo del mínimo). Nadie se perjudica: nunca se
        # apuesta más de lo que el usuario eligió.
        from capital.services import resolve_stake
        stake_kambi, stake_motivo = resolve_stake(config)
        if stake_kambi is None:
            razones = {
                'sin_balance': 'modo compuesto sin balance declarado',
                'sin_saldo': 'balance paralelo agotado (≤ 0 COP)',
            }
            self.stdout.write(
                f"⛔ {owner.email}: sin apuestas ({razones.get(stake_motivo, stake_motivo)})."
            )
            return
        stake_cop_efectivo = stake_kambi / 1000.0

        self.stdout.write(
            f"🎯 Auto-betting v5 multi-mercado: {disponibles} disponibles "
            f"(cuota ≥ {cuota_minima_efectiva}, P ≥ 50%, conf ≥ 0.35, cap calib {calib_cap})."
            f" Stake: {stake_cop_efectivo:,.0f} COP [{stake_motivo}]."
        )

        # 2. Login
        token = routing_key = None
        if dry_run:
            self.stdout.write("🧪 DRY-RUN: sin login BetPlay (no se valida ni coloca nada).")
        else:
            token, routing_key = login(config.ticket, config.punter_id)
            if not token:
                self.stderr.write("❌ Login BetPlay falló. Verifica el ticket en AutoBetConfig.")
                # WhatsApp: alerta al usuario (forzar=False → respeta dedupe del chequeo hourly)
                try:
                    from notificaciones.services import notificar_usuario
                    from notificaciones.models import NotificacionEstado
                    est, _ = NotificacionEstado.objects.get_or_create(
                        usuario=config.usuario, evento='token_betplay_vencido',
                        defaults={'estado': ''}
                    )
                    if est.estado != 'FALLO':
                        nombre = config.usuario.first_name or config.usuario.username or 'usuario'
                        msg = (
                            f"🔴 *Predicta — No se pudieron colocar tus apuestas*\n\n"
                            f"Hola {nombre}, tu sesión BetPlay venció y el sistema "
                            f"no pudo colocar tus apuestas automáticas de hoy.\n\n"
                            f"Renueva tu ticket cuanto antes:\n"
                            f"👉 https://www.predicta.com.co/auto-betting/configuracion/\n\n"
                            f"— Predicta · Monitoreo automático"
                        )
                        notificar_usuario(config.usuario, 'token_betplay_vencido', msg,
                                         estado_evento='FALLO', forzar=False)
                        self.stdout.write("📱 WhatsApp enviado por ticket vencido.")
                except Exception as e:
                    logger.error(f"No se pudo enviar WhatsApp por ticket vencido: {e}")
                return

        # 3. Partidos próximos
        matches = fetch_upcoming_matches(config.horas_adelante)
        if only_today:
            _today_local = django_timezone.localdate()
            matches = [
                m for m in matches
                if django_timezone.localtime(m['start_time']).date() == _today_local
            ]
        self.stdout.write(
            f"📋 {len(matches)} partidos {'de HOY' if only_today else f'en próximas {config.horas_adelante}h'}.")

        apuestas_colocadas = 0
        v2_skipped = 0
        apuestas_hechas = []
        # Opinión IA real (informativa, no operativa): tope de llamadas por corrida.
        ai_calls = 0
        ai_max = int(getattr(settings, 'LLM_REAL_MAX_CALLS', 8) or 8)

        # 2026-10-03 (decisión John): restricción de domingos ELIMINADA.
        # El control por día ahora vive en el Filtro V2 (liga × mercado × día),

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
            markets = _build_market_data(match, home_team, away_team, league, sot_test=sot_test)
            if not markets:
                continue

            # 6. Selección por EV + filtros por SUBMERCADO (mercado+lado, ej.
            # corners_over vs corners_under). Fuente: MarketFilterConfig
            # (global, editable solo por admin en /auto-betting/configuracion/).
            # Cuota por usuario (2026-08-25): las cuotas mínimas globales por
            # submercado (MarketFilterConfig.*_min_cuota) ya no se aplican —
            # serían un piso global que pisaría la cuota mínima per-user.
            # Se neutralizan (0) y queda solo cuota_minima_efectiva del usuario.
            # EXCEPCIÓN x12_v2 (2026-10-03): su cuota mínima (1.80) es parte de
            # la compuerta exacta del ROI en papel, no un piso global; se
            # conserva solo para x12 (ver select_bets, rama 'x12').
            all_filters = get_market_filters()
            x12_min_cuota = (all_filters.get('x12') or {}).get('min_cuota') or 0.0
            market_filters = {k: {**v, 'min_cuota': 0.0} for k, v in all_filters.items()}
            if x12_min_cuota:
                market_filters.setdefault('x12', {})['min_cuota'] = x12_min_cuota

            candidates = select_bets(
                markets, cuota_minima_efectiva,
                min_p=0.45, min_confidence=0.35,
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

                # ── FILTRO V2 (2026-10-03, regla de dinero real) ──
                # Solo combinaciones liga × mercado × día con ROI positivo
                # observado. Clave = submercado real (market + lado), ej.
                # 'remates_over', 'btts_si', 'x12'. Editable en /configuracion/v2/.
                from auto_betting.v2_filter import (
                    is_allowed as _v2_allowed, v2_activo as _v2_on, submarket_key as _v2_key)
                if _v2_on():
                    _local_dt = django_timezone.localtime(match['start_time'])
                    _v2_mkt = _v2_key(best['market'], best.get('side'))
                    if not _v2_allowed(league.name, _v2_mkt, _local_dt):
                        v2_skipped += 1
                        if v2_skipped <= 8:
                            self.stdout.write(
                                f"  ⏭️ v2 fuera: {home_team} vs {away_team} "
                                f"[{_v2_mkt} · {league.name} · "
                                f"{_local_dt.strftime('%a')}]"
                            )
                        continue

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
                    exp_nueva_cop = stake_cop_efectivo
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

                # 6b. Anti-movimiento de línea (2026-09-04, decisión John):
                # re-fetchear la cuota actual de ESTE outcome. Si subió
                # >= LINE_MOVE_ABORT_PCT desde la evaluación, la casa corrigió
                # en contra y abortamos (apostar tarde contra el mercado).
                try:
                    _odds_now = fetch_market_odds(match['event_id'], market_label)
                    _oid = outcome.get('outcome_id')
                    _cuota_now = next(
                        (o.get('odds_decimal') for o in _odds_now
                         if o.get('outcome_id') == _oid), None)
                    if _cuota_now and best['cuota'] > 0:
                        _mov = (_cuota_now - best['cuota']) / best['cuota']
                        if _mov >= LINE_MOVE_ABORT_PCT:
                            self.stdout.write(
                                f"  🚫 Línea movida en contra {_mov*100:+.1f}% "
                                f"({best['cuota']} → {_cuota_now}) en {home_team} vs "
                                f"{away_team} [{market_label} {seleccion}]. Apuesta abortada."
                            )
                            continue
                except Exception as e:
                    logger.warning(f"Anti-movimiento check error: {e}")

                # Dry-run: reportar el candidato sin tocar BetPlay ni la BD.
                if dry_run:
                    self.stdout.write(
                        f"🧪 [DRY-RUN] Apostaría {apuestas_colocadas + 1}: "
                        f"{home_team} vs {away_team} | {market_label} {seleccion} "
                        f"@{best['cuota']} | P={best['p']*100:.1f}% "
                        f"EV={best['ev']*100:+.1f}% "
                        f"edge={best.get('edge_vs_market', 0)*100:+.1f}pp"
                    )
                    apuestas_colocadas += 1
                    continue

                # 7. Validar
                success, val_resp = validate_coupon(token, outcome, event_data, stake_kambi)
                if not success:
                    logger.warning(f"Validate falló {match['home']} vs {match['away']} ({market_label}): {val_resp}")
                    continue

                # 8. Colocar
                success, place_resp = place_bet(token, outcome, event_data, stake_kambi)
                if not success:
                    logger.error(f"Place falló {match['home']} vs {match['away']} ({market_label}): {place_resp}")
                    continue

                # 9. Guardar
                with transaction.atomic():
                    nueva_apuesta = AutoBet.objects.create(
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
                        predicta_prob_raw=round((best.get('p_raw') or best['p']) * 100, 2),
                        confidence=round(best.get('confidence', 0) * 100, 2),
                        edge=round((best['p'] - 1.0 / best['cuota']) * 100, 2),
                        ev=round(best['ev'], 4),
                        coupon_ref=place_resp.get('coupon_ref'),
                        bet_ref=place_resp.get('bet_ref'),
                        stake=stake_kambi,
                        potential_payout=place_resp.get('potential_payout'),
                        estado='OPEN',
                    )
                    counter.apuestas_colocadas += 1
                    counter.save()

                # Opinión IA INFORMATIVA (LLM_MODEL_REAL) — se pide DESPUÉS de
                # colocar y NUNCA bloquea ni filtra: si falla, queda NULL.
                # Desde 2026-10-16 la consulta se traslada a T-X (config web):
                # solo se pide aquí si el partido ya entró en esa ventana; si
                # no, la hará el job ask_llm_real_ventana (una sola por partido).
                from auto_betting.llm_validator import llm_ventana_alcanzada
                if ai_calls < ai_max and llm_ventana_alcanzada(nueva_apuesta.start_time):
                    ai_calls += 1
                    try:
                        from auto_betting.llm_validator import opinar_apuesta
                        ok_ia, why_ia = opinar_apuesta(nueva_apuesta, {
                            'home': home_team, 'away': away_team, 'liga': league.name,
                            'mercado': market_label, 'motor': best.get('market', ''),
                            'seleccion': seleccion, 'linea': best.get('line'),
                            'cuota': best['cuota'], 'prob': best['p'],
                            'ev': best['ev'],
                            'edge_pp': best.get('edge_vs_market', 0) * 100,
                            'lambda': pred_value, 'start_time': match['start_time'],
                        })
                        _tag_ia = ('🧠 IA APROBÓ' if ok_ia is True else
                                   ('🧠 IA RECHAZÓ' if ok_ia is False else '🧠 IA SIN RESPUESTA'))
                        self.stdout.write(
                            f"  {_tag_ia}: {home_team} vs {away_team} [{seleccion}] "
                            f"— {(why_ia or '')[:110]}"
                        )
                    except Exception as e:
                        logger.warning(f"Opinión IA falló (no afecta la apuesta): {e}")

                apuestas_colocadas += 1
                self.stdout.write(
                    f"✅ Apuesta {apuestas_colocadas}: {home_team} vs {away_team} | {market_label} "
                    f"{seleccion} @{best['cuota']} | P={best['p']*100:.1f}% (raw={best.get('p_raw',best['p'])*100:.1f}%) "
                    f"EV={best['ev']*100:+.1f}% | coupon={place_resp.get('coupon_ref')}"
                )
                apuestas_hechas.append({
                    'partido': f"{home_team} vs {away_team}",
                    'mercado': market_label,
                    'seleccion': seleccion,
                    'cuota': best['cuota'],
                    'stake_cop': stake_cop_efectivo,
                })

        self.stdout.write(
            self.style.SUCCESS(
                f"\n🏁 Auto-betting v2 completado: {apuestas_colocadas} "
                f"{'apuestas simuladas [DRY-RUN]' if dry_run else 'apuestas colocadas'}"
                + (f" · {v2_skipped} descartadas por filtro v2." if v2_skipped else ".")
            )
        )

        # Resumen WhatsApp al usuario (solo real y solo si hubo apuestas)
        if apuestas_hechas and not dry_run:
            try:
                from notificaciones.services import notificar_apuestas
                wa = notificar_apuestas(owner, apuestas_hechas, 'Fútbol')
                self.stdout.write(f"📱 WhatsApp resumen a {owner.email}: {wa}")
            except Exception as e:
                logger.warning(f"WhatsApp resumen apuestas falló: {e}")
