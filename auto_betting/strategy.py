"""
Motor de estrategia v3 — multi-mercado:
- Over/Under (Poisson): córners, tiros a puerta, goles, remates totales.
- 1X2 (Resultado Final) y BTTS (Ambos Equipos Marcarán).
- Selección por EV: apuesta cuando P_modelo × cuota > 1 (edge positivo) y cuota >= mínima.
"""

import logging
import math

logger = logging.getLogger('auto_betting')


def poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.exp(-lam) * lam**k) / math.factorial(k)


def poisson_over(line, lam):
    """P(X > line) = 1 - P(X <= floor(line))."""
    if lam <= 0:
        return 0.0
    k = int(math.floor(line))
    cumul = sum(poisson_pmf(i, lam) for i in range(k + 1))
    return max(0.0, 1.0 - cumul)


# ── 2026-09-04 (auditoría SOT, decisión John): Negative Binomial ──
# El SOT real es sobredisperso: var/media = 1.24 global (n=35.280, ventana
# 730d), Poisson (var=media) subestima las colas. phi = mu^2/(var-mu).
SOT_PHI_GLOBAL = 35.77  # phi por momentos sobre datos históricos reales
# Shrinkage del lambda de SOT hacia la media de liga (el modelo usa medias
# crudas de 20 partidos por equipo, RMSE ~3.5): 50% modelo + 50% liga.
SOT_LAMBDA_SHRINK = 0.5
SOT_GLOBAL_MEAN = 8.608  # media SOT global (ventana 730d, n=35.280)

# 2026-09-14: remates totales (motor v2.3) — phi de sobredispersión medido
# sobre datos históricos reales (auditoría 2026-09-13, misma ventana que SOT).
REM_TOTAL_SHOTS_PHI = 42.36


def negbin_over(line, lam, phi=None):
    """P(X > line) con Negative Binomial (sobredispersión) — para SOT.

    Media = lam, dispersión phi (default: SOT_PHI_GLOBAL).
    Poisson es el límite phi -> inf.
    """
    try:
        from scipy.stats import nbinom
    except ImportError:
        return poisson_over(line, lam)
    if lam <= 0:
        return 0.0
    phi = phi or SOT_PHI_GLOBAL
    k = int(math.floor(line))
    n = max(1.0, phi)
    p_geom = n / (n + lam)  # parametrización: media = n(1-p)/p = lam
    return max(0.0, 1.0 - nbinom.cdf(k, n, p_geom))


def devig_two_way(odds_a, odds_b):
    """Probabilidades justas del par a/b sin el margen de la casa (devigging).

    Devuelve (p_a, p_b) o (None, None) si falta un lado o una cuota es invalida.
    """
    if not odds_a or not odds_b or odds_a <= 1.0 or odds_b <= 1.0:
        return None, None
    inv_a, inv_b = 1.0 / odds_a, 1.0 / odds_b
    total = inv_a + inv_b
    return inv_a / total, inv_b / total


def devig_three_way(odds_1, odds_x, odds_2):
    """Probabilidades justas 1X2 sin margen. Devuelve (p1, px, p2) o (None, None, None)."""
    if not all(o and o > 1.0 for o in (odds_1, odds_x, odds_2)):
        return None, None, None
    inv = [1.0 / o for o in (odds_1, odds_x, odds_2)]
    total = sum(inv)
    return inv[0] / total, inv[1] / total, inv[2] / total


def _setup_django():
    import os, django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
    if not django.apps.apps.ready:
        django.setup()


# ── Predicciones Over/Under ──

def predict_corners(home_team, away_team, league):
    """Predicción de córners usando el motor original de Predicta."""
    _setup_django()
    from ai_predictions.corners_model import corners_model
    result = corners_model.predecir(home_team, away_team, league, 'corners_total')
    if not result:
        return None
    return {
        'lambda': result.get('corners_esperados_total', result.get('prediction', 0)),
        'confidence': result.get('confidence', 0.35),
    }


def predict_shots_on_target(home_team, away_team, league):
    """Predicción de tiros a puerta usando xg_shots_model de Predicta."""
    _setup_django()
    from ai_predictions.xg_shots_model import xg_shots_model
    result = xg_shots_model.predict_shots_on_target_total(home_team, away_team, league)
    if not result:
        return None
    return {
        'lambda': result.get('prediction', 0),
        'confidence': result.get('confidence', 0.5),
    }


def predict_goals(home_team, away_team, league):
    """Predicción de goles totales (lambda) usando Dixon-Coles."""
    _setup_django()
    from ai_predictions.dixon_coles import DixonColesModel
    model = DixonColesModel()
    try:
        result = model.predict_match(home_team, away_team, league, 'goals_total')
    except Exception as e:
        logger.error(f'predict_goals error: {e}')
        return None
    if not result or result.get('prediction') is None:
        return None
    return {
        'lambda': result['prediction'],
        'confidence': result.get('confidence', 0.5),
    }


def predict_total_shots(home_team, away_team, league):
    """Predicción de remates totales (lambda) usando xg_shots_model."""
    _setup_django()
    from ai_predictions.xg_shots_model import xg_shots_model
    result = xg_shots_model.predict_shots_total(home_team, away_team, league)
    if not result or result.get('prediction') is None:
        return None
    return {
        'lambda': result['prediction'],
        'confidence': result.get('confidence', 0.5),
    }


# ── Predicciones categóricas ──

def predict_x12(home_team, away_team, league):
    """Probabilidades 1X2 (local/empate/visitante) usando Dixon-Coles."""
    _setup_django()
    from ai_predictions.dixon_coles import DixonColesModel
    model = DixonColesModel()
    try:
        lh, la = model.calculate_lambda_parameters(home_team, away_team, league, True)
        outcome = model._calculate_match_outcome(lh, la)
    except Exception as e:
        logger.error(f'predict_x12 error: {e}')
        return None
    return {
        'home': outcome['home_win'],
        'draw': outcome['draw'],
        'away': outcome['away_win'],
    }


def predict_btts(home_team, away_team, league):
    """Probabilidad de que ambos equipos marquen (0..1)."""
    _setup_django()
    from ai_predictions.enhanced_both_teams_score import enhanced_both_teams_score_model
    try:
        p = enhanced_both_teams_score_model.predict(home_team, away_team, league)
    except Exception as e:
        logger.error(f'predict_btts error: {e}')
        return None
    if p is None:
        return None
    return {'yes': float(p)}


# ── Validación de cobertura de datos (Fase 3) ──

def validate_market_data(home_team, away_team, league):
    """
    Valida la cobertura de datos para cada mercado antes de apostar.

    Exige ≥10 partidos con datos NO NULL por equipo (suma local+visitante)
    en el campo relevante para cada mercado, dentro de la ventana de 730 días.

    Returns:
        dict: {market_name: True/False} indicando si hay datos suficientes.
    """
    from football_data.models import Match
    from django.utils import timezone
    from datetime import timedelta

    cutoff = timezone.now().date() - timedelta(days=730)
    MIN_MATCHES = 10

    # Goles (fthg/ftag) — siempre 100% cobertura, pero validar igual
    home_goals = Match.objects.filter(
        home_team=home_team, league=league, date__gte=cutoff, fthg__isnull=False
    ).count() + Match.objects.filter(
        away_team=home_team, league=league, date__gte=cutoff, ftag__isnull=False
    ).count()
    away_goals = Match.objects.filter(
        home_team=away_team, league=league, date__gte=cutoff, fthg__isnull=False
    ).count() + Match.objects.filter(
        away_team=away_team, league=league, date__gte=cutoff, ftag__isnull=False
    ).count()

    # Remates totales (hs/as_field)
    home_shots = Match.objects.filter(
        home_team=home_team, league=league, date__gte=cutoff, hs__isnull=False
    ).count() + Match.objects.filter(
        away_team=home_team, league=league, date__gte=cutoff, as_field__isnull=False
    ).count()
    away_shots = Match.objects.filter(
        home_team=away_team, league=league, date__gte=cutoff, hs__isnull=False
    ).count() + Match.objects.filter(
        away_team=away_team, league=league, date__gte=cutoff, as_field__isnull=False
    ).count()

    # Córners (hc/ac)
    home_corners = Match.objects.filter(
        home_team=home_team, league=league, date__gte=cutoff, hc__isnull=False
    ).count() + Match.objects.filter(
        away_team=home_team, league=league, date__gte=cutoff, ac__isnull=False
    ).count()
    away_corners = Match.objects.filter(
        home_team=away_team, league=league, date__gte=cutoff, hc__isnull=False
    ).count() + Match.objects.filter(
        away_team=away_team, league=league, date__gte=cutoff, ac__isnull=False
    ).count()

    goals_ok = home_goals >= MIN_MATCHES and away_goals >= MIN_MATCHES
    shots_ok = home_shots >= MIN_MATCHES and away_shots >= MIN_MATCHES
    corners_ok = home_corners >= MIN_MATCHES and away_corners >= MIN_MATCHES

    result = {
        'goals_total': goals_ok,
        'shots_on_target': shots_ok,
        'corners_total': corners_ok,
        'both_teams_score': goals_ok,  # BTTS usa datos de goles
    }

    # Log de mercados saltados por datos insuficientes
    skipped = [k for k, v in result.items() if not v]
    if skipped:
        logger.info(
            f'validate_market_data: {home_team} vs {away_team} ({league.name}) '
            f'— mercados sin datos: {skipped} '
            f'(goals: h={home_goals}/a={away_goals}, '
            f'shots: h={home_shots}/a={away_shots}, '
            f'corners: h={home_corners}/a={away_corners})'
        )

    # ── Gate de frescura de datos (fix 2026-08-23) ──
    # Auditoría 23-Ago: se apostó 2 veces en Serie B (Italia) con datos solo
    # hasta el 29-May (3 meses viejos) → ambas perdidas. Si el último partido
    # con datos de la liga tiene más de MAX_DATA_AGE_DAYS, la liga entera se
    # considera desactualizada y TODOS los mercados se bloquean: un modelo
    # alimentado con datos viejos no predice el presente.
    MAX_DATA_AGE_DAYS = 30
    try:
        last_match = Match.objects.filter(
            league=league, fthg__isnull=False
        ).order_by('-date').values_list('date', flat=True).first()
        if last_match:
            age_days = (timezone.now().date() - last_match).days
            if age_days > MAX_DATA_AGE_DAYS:
                logger.warning(
                    f'validate_market_data: liga {league.name} con datos stale '
                    f'(último partido {last_match}, {age_days} días > '
                    f'{MAX_DATA_AGE_DAYS}). TODOS los mercados bloqueados para '
                    f'{home_team} vs {away_team}.'
                )
                return {k: False for k in result}
    except Exception as e:
        logger.error(f'validate_market_data - freshness gate error: {e}')

    return result


# ── Predicción Oficial (Fase 2) ──

def get_official_predictions(home_team, away_team, league):
    """
    Ejecuta el pipeline completo de Predicta y devuelve las predicciones oficiales
    (promedio ponderado por confianza de todos los modelos), igual que /ai/predict/.

    Esto reemplaza el uso de modelos individuales crudos (que tomaban el modelo
    más extremo) por el promedio oficial que muestra la web.

    Returns:
        dict: {
            'corners_total': {'lambda': float, 'confidence': float},
            'goals_total':   {'lambda': float, 'confidence': float},
            'shots_on_target': {'lambda': float, 'confidence': float},
            'both_teams_score': {'yes': float, 'confidence': float},
        } (solo mercados con datos válidos)
    """
    _setup_django()

    from ai_predictions.web_pipeline import build_web_predictions, get_official_prediction

    # Fase 3 — Validar cobertura de datos antes de ejecutar cualquier modelo
    coverage = validate_market_data(home_team, away_team, league)

    # ── MOTOR ÚNICO (2026-09-01, decisión de John) ──
    # Los 4 mercados se calculan con build_web_predictions(), que replica
    # EXACTAMENTE el pipeline de la web /ai/predict/ (mismos modelos por
    # mercado + "Predicción Oficial" = promedio ponderado por confianza).
    # Ya NO se usa el motor poisson_ratings (ridge): la fuente oficial es la web.
    #
    # Mercado auto_betting -> pred_type web:
    #   goals_total      -> goals_total          (Dixon+Avg+Ens+Híbrido)
    #   shots_on_target  -> shots_on_target_total (shots_prediction + xg_shots)
    #   corners_total    -> corners_total        (corners_model 40/30/15/15)
    #   both_teams_score -> both_teams_score     (simples+Enhanced+Híbrido)
    market_to_web_type = {
        'goals_total': 'goals_total',
        'shots_on_target': 'shots_on_target_total',
        'corners_total': 'corners_total',
        'both_teams_score': 'both_teams_score',
    }

    all_predictions = {}
    pred_types_needed = [
        web_type for market_key, web_type in market_to_web_type.items()
        if coverage.get(market_key, False)
    ]
    if pred_types_needed:
        all_predictions = build_web_predictions(
            home_team, away_team, league, prediction_types=pred_types_needed
        )

    # ── Predicción Oficial por mercado (la misma que muestra la web) ──
    official = {}
    for market_key, web_type in market_to_web_type.items():
        off = get_official_prediction(all_predictions, web_type)
        if off:
            official[market_key] = off
        else:
            logger.info(f'get_official_predictions: sin predicción oficial para {market_key} '
                        f'({home_team} vs {away_team}) — mercado omitido')


    # ── Formatear resultado ──
    result = {}

    # ── Cap de sanidad de lambda de goles (red de seguridad) ──
    # Si λ > 1.6x el promedio real de la liga (ventana 730d, misma que
    # validate_market_data), el mercado de goles se descarta: un λ tan alto
    # indicaría descalibración del pipeline (histórico: 15 apuestas de
    # goles-over correlacionadas perdidas en un día, −36% ROI).
    # Con el motor único web (web_pipeline) rara vez se activa; se mantiene
    # como protección extrema sin alterar el dato de la web.
    GOALS_LAMBDA_MAX_RATIO = 1.6
    if 'goals_total' in official:
        try:
            from football_data.models import Match
            from django.utils import timezone as _tz
            from datetime import timedelta as _td
            from django.db.models import Avg as _Avg, F as _F
            _cutoff = _tz.now().date() - _td(days=730)
            _league_avg = Match.objects.filter(
                league=league, date__gte=_cutoff,
                fthg__isnull=False, ftag__isnull=False,
            ).aggregate(avg=_Avg(_F('fthg') + _F('ftag')))['avg']
            _lam = official['goals_total']['prediction']
            if _league_avg and _league_avg > 0 and _lam > GOALS_LAMBDA_MAX_RATIO * _league_avg:
                logger.warning(
                    f'get_official_predictions: λ goles {_lam:.2f} > '
                    f'{GOALS_LAMBDA_MAX_RATIO}x promedio liga {_league_avg:.2f} '
                    f'({league.name}). Mercado de goles DESCARTADO por '
                    f'descalibración ({home_team} vs {away_team}).'
                )
                del official['goals_total']
        except Exception as e:
            logger.error(f'get_official_predictions - goals lambda sanity check error: {e}')

    if 'goals_total' in official:
        result['goals_total'] = {
            'lambda': official['goals_total']['prediction'],
            'confidence': official['goals_total']['confidence'],
        }
    if 'shots_on_target' in official:
        # ── 2026-09-04 (auditoría SOT): shrinkage del lambda hacia la media
        # de liga. El lambda crudo del pipeline (medias de 20 partidos por
        # equipo) tiene RMSE ~3.5 y subestima en unders. Media de liga real
        # (ventana 730d, mismo corte que validate_market_data); fallback a la
        # media global (8.608). Peso 50/50 (SOT_LAMBDA_SHRINK).
        lam_raw = official['shots_on_target']['prediction']
        try:
            from football_data.models import Match
            from django.utils import timezone as _tz2
            from datetime import timedelta as _td2
            from django.db.models import Avg as _Avg2, F as _F2
            _cut2 = _tz2.now().date() - _td2(days=730)
            _lig_avg = Match.objects.filter(
                league=league, date__gte=_cut2,
                hst__isnull=False, ast__isnull=False,
            ).aggregate(avg=_Avg2(_F2('hst') + _F2('ast')))['avg']
            league_mean = _lig_avg if (_lig_avg and _lig_avg > 0) else SOT_GLOBAL_MEAN
        except Exception as e:
            logger.warning(f'get_official_predictions - SOT league mean fallback: {e}')
            league_mean = SOT_GLOBAL_MEAN
        lam_shrunk = (1.0 - SOT_LAMBDA_SHRINK) * lam_raw + SOT_LAMBDA_SHRINK * league_mean
        logger.info(
            f'SOT shrinkage: lambda crudo {lam_raw:.2f} -> {lam_shrunk:.2f} '
            f'(media liga {league_mean:.2f}) para {home_team} vs {away_team}')
        result['shots_on_target'] = {
            'lambda': lam_shrunk,
            'confidence': official['shots_on_target']['confidence'],
        }
    if 'corners_total' in official:
        result['corners_total'] = {
            'lambda': official['corners_total']['prediction'],
            'confidence': official['corners_total']['confidence'],
        }
    if 'both_teams_score' in official:
        result['both_teams_score'] = {
            'yes': official['both_teams_score']['prediction'],
            'confidence': official['both_teams_score']['confidence'],
        }

    # ── MOTOR ÚNICO (2026-09-01): fin del override poisson_ratings ──
    # El motor ridge fue removido del flujo por decisión de John: la fuente
    # oficial de predicción es la web (/ai/predict/), replicada por
    # ai_predictions/web_pipeline.py. El λ de goles, córners y tiros a puerta
    # es EXACTAMENTE el de la "Predicción Oficial" que muestra la web.
    # (El motor poisson_ratings sigue en el repo solo para análisis/backtests.)

    return result


# 2026-09-04 (decisión de John): edge mínimo exigido entre la P calibrada
# del modelo y la probabilidad JUSTA del mercado (devigged) para apostar.
# 5pp es conservador; sin par de cuotas no hay referencia justa → no se apuesta.
MIN_EDGE_VS_MARKET = 0.05

# 2026-09-04 (decisión de John): distancia mínima entre el lambda del modelo
# y la línea apostada. Apostar pegada al número esperado = moneda al aire con
# vig (82% del volumen histórico de córners). Solo se apuesta cuando el
# modelo DISCREPA materialmente de la línea. Escala por mercado: goles
# (stdev ~1.4) más chico; córners/SOT (stdev ~3) más grande.
MIN_LINE_DISTANCE = {
    'goals': 0.40,
    'corners': 0.75,
    'shots_on_target': 0.75,
    'remates': 0.75,
}
MIN_LINE_DISTANCE_DEFAULT = 0.75


# ── Calibración de probabilidades (Fase 4) ──

def calibrate_probability(p, cap=0.58):
    """
    Calibra la probabilidad predicha basada en backtest real.

    Auditoría (2026-08-23):
    - P 50-60%: zona rentable.
    - P > 60%: ANTI-SEÑAL (WR ~31% cuando el modelo dice 65%+). Sobreconfianza
      creciente (8pp → 14pp). El modelo no demuestra capacidad de predecir
      arriba de 60%; por eso el cap baja de 0.65 a 0.58 (configurable).

    Estrategia:
    1. P ≤ 60%: shrinkage ligero (factor 0.95 hacia 50%) — apenas ajusta.
    2. P > 60%: shrinkage fuerte (factor 0.50) con cap duro configurable.

    `cap` proviene de MarketFilterConfig.calib_cap (default 0.58).
    """
    if p <= 0.60:
        p_cal = 0.5 + (p - 0.5) * 0.95
    else:
        p_cal = min(cap, 0.5 + (p - 0.5) * 0.50)
    return max(0.05, min(0.95, min(cap, p_cal)))


# ── Filtros por mercado (Fase 5, legacy) ──
# Umbrales calibrados con datos reales (80 partidos, 2026-08-22) para
# reducir volumen de córners y tiros a puerta ≥60% sin tocar el resto.
# NOTA (Fase 6, 2026-08-23): estos valores siguen usándose como FALLBACK
# genérico por mercado (cuando no hay override específico por submercado
# over/under). El origen de verdad para producción es ahora
# `MarketFilterConfig` (modelo Django, editable en /auto-betting/configuracion/
# solo por el admin) vía `get_market_filters()`.
MARKET_FILTERS = {
    'goals':           {'min_p': 0.50, 'min_confidence': 0.35},
    'btts':            {'min_p': 0.50, 'min_confidence': 0.35},
    'x12':             {'min_p': 0.50, 'min_confidence': 0.35},
    'corners':         {'min_p': 0.45, 'min_confidence': 0.35},  # reduce ~67-71%
    'shots_on_target': {'min_p': 0.45, 'min_confidence': 0.35},  # reduce 67%
}


def get_market_filters():
    """
    Devuelve el dict de filtros por SUBMERCADO (market_side, ej. 'corners_over',
    'corners_under') leyendo la configuración global editable `MarketFilterConfig`.

    Fallback seguro: si el modelo no existe todavía (antes de migrar) o hay
    cualquier error, devuelve `MARKET_FILTERS` (legacy, por mercado sin separar
    lado) para no romper el auto-betting.
    """
    try:
        _setup_django()
        from auto_betting.models import MarketFilterConfig
        cfg = MarketFilterConfig.get_solo()
        return cfg.as_market_filters()
    except Exception as e:
        logger.warning(f'get_market_filters: usando MARKET_FILTERS legacy por error: {e}')
        return MARKET_FILTERS


def get_global_config():
    """
    Devuelve los controles globales (cuota mínima global, stop-loss, exposición
    máxima, cap de calibración) desde `MarketFilterConfig`. Fallback seguro a
    los defaults de la auditoría si el modelo no existe o hay error.
    """
    defaults = {
        'cuota_minima_global': 2.5,
        'stop_loss_diario_cop': -30000.0,
        'max_exposicion_evento_cop': 20000.0,
        'calib_cap': 0.58,
    }
    try:
        _setup_django()
        from auto_betting.models import MarketFilterConfig
        cfg = MarketFilterConfig.get_solo()
        return cfg.as_globals()
    except Exception as e:
        logger.warning(f'get_global_config: usando defaults por error: {e}')
        return defaults


def submarket_clv_health(mercado_label, n=30, threshold=-0.5):
    """
    CLV breaker (2026-09-04, paso 4 auditoría SOT): devuelve (ok, avg_clv, n)
    para las últimas n apuestas asentadas de un mercado. Si el CLV promedio
    móvil cae por debajo de `threshold`, el submercado se considera sin edge
    y run_auto_bets lo salta ese día.

    Umbral (2026-09-04, decisión John): -0.5 en vez de 0.0 — el CLV del modelo
    viejo contaminaba la media móvil; con -0.5 solo bloquea sangrado claro,
    no ruido histórico.
    """
    _setup_django()
    try:
        from auto_betting.models import HistorialApuesta
        from django.db.models import Avg
        qs = HistorialApuesta.objects.filter(
            mercado__icontains=mercado_label, clv__isnull=False,
        ).exclude(bet_status='OPEN').order_by('-placed_date')[:n]
        if qs.count() == 0:
            return True, None, 0
        agg = qs.aggregate(avg=Avg('clv'))
        avg_clv = agg['avg'] or 0.0
        return avg_clv >= threshold, avg_clv, qs.count()
    except Exception as e:
        logger.error(f'submarket_clv_health error: {e}')
        return True, None, 0


# ── Selección unificada (por EV) ──

def _get_tier_thresholds(cuota):
    """
    Umbrales escalonados por rango de cuota.
    Más cuota = más exigencia de confianza y EV.
    P mínima es 0.45 (hard floor relajado, 2026-09-04): el edge contra la
    cuota justa del mercado (§24) es la defensa principal; el floor solo
    descarta ruido extremo.
    """
    if cuota <= 2.99:
        return 0.45, 0.35, 0.05   # cuota baja: confianza mínima, EV ≥ 5%
    elif cuota <= 3.99:
        return 0.45, 0.45, 0.10   # más confianza + EV ≥ 10%
    elif cuota <= 5.99:
        return 0.45, 0.55, 0.15   # cuota alta: señal fuerte + EV ≥ 15%
    else:
        return 0.45, 0.65, 0.20   # longshots: convicción alta + EV ≥ 20%


# 2026-09-03 (auditoría P6, §19): cuota justa mínima por línea en tiros a
# puerta Under. El modelo subestima ~2 SOT (RMSE 3.19 contra líneas cada
# 0.5) y las cuotas cortas no pagan ese sesgo (WR Under histórico 27-40%).
SHOTS_UNDER_FAIR_ODDS = {7.5: 2.53, 8.5: 1.92, 9.5: 1.56}


def _add_candidate(candidates, market, offer, line, side, p, cuota_minima,
                   confidence=None, min_p=0.45, min_confidence=0.35,
                   enabled=True, sub_min_ev=0.0, sub_min_cuota=0.0, calib_cap=0.58,
                   min_line=0.0, max_line=0.0, fair_odds=None,
                   min_edge_vs_market=MIN_EDGE_VS_MARKET):
    # Submercado apagado desde la config (ej. Córners Under, BTTS No)
    if not enabled:
        return

    cuota = offer.get('odds_decimal', 0)
    if cuota <= 0 or cuota < cuota_minima:
        return
    # Cuota mínima específica del submercado (0 = usa la global/cuota_minima)
    if sub_min_cuota and cuota < sub_min_cuota:
        return
    # 2026-09-14: filtro por línea (min_line/max_line) — se pasaba desde la
    # config por submercado pero no se aplicaba. 0 = sin tope.
    if line is not None:
        if min_line and line < min_line:
            return
        if max_line and line > max_line:
            return

    # Fase 4 — calibrar la probabilidad antes de evaluar (cap configurable)
    p_raw = p
    # 2026-09-03 (auditoría P2a): calibrar TODOS los mercados. El bypass de
    # ENGINE_MARKETS asumía que el motor ridge producía P honesta, pero el
    # ridge fue removido el 2026-09-01 (motor único = web, pipeline legacy
    # Dixon-Coles). Con la P cruda de vuelta, la sobreconfianza regresó:
    # WR real ~37% vs P 55-65% durante 7 días. Vuelve el shrinkage + cap
    # para goles/tiros/córners.
    p = calibrate_probability(p, cap=calib_cap)
    p = min(0.97, max(0.03, p))

    # Filtro primario: P mínima absoluta (hard floor, no negociable)
    if p < min_p:
        return

    # Umbrales escalonados por cuota (tiers — solo agregan requisitos)
    tier_min_p, tier_min_conf, tier_min_ev = _get_tier_thresholds(cuota)

    # El tier no puede bajar el P mínimo por debajo de min_p
    effective_min_p = max(min_p, tier_min_p)
    if p < effective_min_p:
        return
    # 2026-09-04 (decisión de John): la decisión se toma contra la CUOTA JUSTA
    # del mercado (devigged). Sin par no hay referencia justa → se descarta
    # (no se apuesta contra un precio sin benchmark). El edge mínimo exigido
    # es sobre la probabilidad justa, no sobre la cuota con vig.
    if not fair_odds or fair_odds <= 1.0:
        logger.warning(
            f'_add_candidate: sin cuota justa para {market} {side} {line} — descartado')
        return
    market_p = 1.0 / fair_odds
    edge_vs_market = p - market_p
    if edge_vs_market < min_edge_vs_market:
        return
    ev = p * fair_odds - 1.0
    # EV mínimo: el más exigente entre el tier por cuota y el del submercado.
    # Auditoría: bucket EV 10-20% = -54.9% ROI → exigir EV≥20% en cuotas bajas.
    effective_min_ev = max(tier_min_ev, sub_min_ev)
    if ev <= effective_min_ev:
        return
    # 2026-09-04 (simplificación de cadena, decisión John): filtro de
    # confidence ELIMINADO — los modelos reportan confidences casi fijas
    # (0.70-0.75 hardcodeadas) y no discriminan nada real.
    candidates.append({
        'market': market,
        'offer': offer,
        'line': line,
        'side': side,
        'cuota': cuota,
        'p': p,
        'p_raw': p_raw,  # guardar P original para logging
        'ev': ev,
        'fair_odds': fair_odds,
        'market_p': market_p,
        'edge_vs_market': edge_vs_market,
        'confidence': confidence or 0,
    })


# Normaliza el 'side' interno de cada tipo de mercado a la clave de submercado
# usada en `MarketFilterConfig`/`get_market_filters()` (ej. 'corners_over',
# 'btts_si'). Mercados sin distinción de lado configurada (x12) caen al
# fallback por mercado genérico.
_SIDE_KEY_SUFFIX = {
    'over': 'over',
    'under': 'under',
    'Sí': 'si',
    'No': 'no',
}


def _resolve_filters(market_filters, market_key, side, min_p, min_confidence):
    """
    Resuelve los filtros efectivos para un submercado.
    Prioridad: 'market_side' (ej. 'corners_over') > 'market' genérico > defaults.
    Devuelve: (min_p, min_confidence, enabled, min_ev, min_cuota).
    """
    mf_all = market_filters or {}
    suffix = _SIDE_KEY_SUFFIX.get(side)
    sub_key = f'{market_key}_{suffix}' if suffix else None
    if sub_key and sub_key in mf_all:
        mf = mf_all[sub_key]
    else:
        mf = mf_all.get(market_key, {})
    return (
        mf.get('min_p', min_p),
        mf.get('min_confidence', min_confidence),
        mf.get('enabled', True),
        mf.get('min_ev', 0.0),
        mf.get('min_cuota', 0.0),
        mf.get('min_line', 0.0),
        mf.get('max_line', 0.0),
    )


def select_bets(markets_data, cuota_minima=2.0, min_p=0.45, min_confidence=0.35,
                market_filters=None, calib_cap=0.58):
    """
    Selecciona apuestas por EV positivo + P >= min_p + confidence >= min_confidence.
    `market_filters`: dict opcional con umbrales por SUBMERCADO (mercado+lado),
    ej. {'corners_over': {'min_p': 0.52, 'min_confidence': 0.35},
         'corners_under': {'min_p': 0.65, 'min_confidence': 0.35}, ...}.
    También acepta claves por mercado genérico (ej. 'corners') como fallback
    si no hay override específico por lado (compatibilidad con MARKET_FILTERS
    legacy). Ver `get_market_filters()` para la fuente de verdad en producción
    (config editable `MarketFilterConfig`).
    `markets_data`: lista de dicts:
      - over/under: {'market', 'type':'over_under', 'lambda', 'confidence', 'odds'}
      - x12:        {'market', 'type':'x12', 'probs':{'home','draw','away'}, 'confidence', 'odds'}
      - btts:       {'market', 'type':'btts', 'p_yes', 'confidence', 'odds'}
    Devuelve lista de candidatos ordenados por EV descendente.
    """
    candidates = []

    for md in markets_data:
        mtype = md.get('type')
        market_key = md.get('market')
        odds = md.get('odds') or []
        confidence = md.get('confidence', 0.5)

        if mtype == 'over_under':
            lam = md.get('lambda')
            if lam is None:
                continue
            # 2026-09-04 (decisión de John): agrupar cuotas por línea para
            # devigging del par over/under antes de evaluar cada oferta.
            line_pairs = {}
            for offer in odds:
                _line = offer.get('line')
                if _line is None:
                    continue
                _otype = offer.get('type', '')
                _cuota = offer.get('odds_decimal', 0)
                if _otype in ('OT_OVER', 'OT_UNDER') and _cuota > 1.0:
                    line_pairs.setdefault(_line, {})[_otype] = _cuota
            for offer in odds:
                line = offer.get('line')
                if line is None:
                    continue
                # 2026-09-04: distancia mínima lambda-línea. Líneas pegadas al
                # número esperado (moneda al aire con vig) se descartan.
                min_dist = MIN_LINE_DISTANCE.get(md['market'], MIN_LINE_DISTANCE_DEFAULT)
                if abs(lam - line) < min_dist:
                    continue
                if md['market'] == 'shots_on_target':
                    # 2026-09-04: SOT usa Negative Binomial (sobredispersión real)
                    p_over = negbin_over(line, lam)
                elif md['market'] == 'remates':
                    # 2026-09-14 (motor remates v2.3): NegBin phi=42.36
                    # (sobredispersión real de remates totales).
                    p_over = negbin_over(line, lam, phi=REM_TOTAL_SHOTS_PHI)
                else:
                    p_over = poisson_over(line, lam)
                p_under = 1.0 - p_over
                otype = offer.get('type', '')
                if otype == 'OT_OVER':
                    p, side = p_over, 'over'
                elif otype == 'OT_UNDER':
                    p, side = p_under, 'under'
                else:
                    continue
                pair = line_pairs.get(line, {})
                p_fair_over, p_fair_under = devig_two_way(pair.get('OT_OVER'), pair.get('OT_UNDER'))
                fair_p = p_fair_over if side == 'over' else p_fair_under
                fair_odds = (1.0 / fair_p) if fair_p else None
                eff_min_p, eff_min_conf, eff_enabled, eff_min_ev, eff_min_cuota, eff_min_line, eff_max_line = _resolve_filters(
                    market_filters, market_key, side, min_p, min_confidence)
                _add_candidate(candidates, md['market'], offer, line, side, p, cuota_minima,
                              confidence=confidence, min_p=eff_min_p, min_confidence=eff_min_conf,
                              enabled=eff_enabled, sub_min_ev=eff_min_ev, sub_min_cuota=eff_min_cuota,
                              calib_cap=calib_cap, min_line=eff_min_line, max_line=eff_max_line,
                              fair_odds=fair_odds)

        elif mtype == 'x12':
            probs = md.get('probs') or {}
            # 2026-09-04 (decisión de John): devigging 1X2 (tres vías)
            c1 = cx = c2 = 0.0
            for offer in odds:
                _otype = offer.get('type', '')
                _cuota = offer.get('odds_decimal', 0)
                if _otype == 'OT_ONE' and _cuota > 1.0:
                    c1 = _cuota
                elif _otype == 'OT_CROSS' and _cuota > 1.0:
                    cx = _cuota
                elif _otype == 'OT_TWO' and _cuota > 1.0:
                    c2 = _cuota
            pf1, pfx, pf2 = devig_three_way(c1, cx, c2)
            fair_map = {'1': pf1, 'X': pfx, '2': pf2}
            for offer in odds:
                otype = offer.get('type', '')
                if otype == 'OT_ONE':
                    p, side = probs.get('home', 0), '1'
                elif otype == 'OT_CROSS':
                    p, side = probs.get('draw', 0), 'X'
                elif otype == 'OT_TWO':
                    p, side = probs.get('away', 0), '2'
                else:
                    continue
                if not p:
                    continue
                fair_p = fair_map.get(side)
                fair_odds = (1.0 / fair_p) if fair_p else None
                eff_min_p, eff_min_conf, eff_enabled, eff_min_ev, eff_min_cuota, eff_min_line, eff_max_line = _resolve_filters(
                    market_filters, market_key, side, min_p, min_confidence)
                _add_candidate(candidates, md['market'], offer, None, side, p, cuota_minima,
                              confidence=confidence, min_p=eff_min_p, min_confidence=eff_min_conf,
                              enabled=eff_enabled, sub_min_ev=eff_min_ev, sub_min_cuota=eff_min_cuota,
                              calib_cap=calib_cap, min_line=eff_min_line, max_line=eff_max_line,
                              fair_odds=fair_odds)

        elif mtype == 'btts':
            p_yes = md.get('p_yes')
            if p_yes is None:
                continue
            # 2026-09-04 (decisión de John): devigging Sí/No
            c_yes = c_no = 0.0
            for offer in odds:
                _otype = offer.get('type', '')
                _cuota = offer.get('odds_decimal', 0)
                if _otype == 'OT_YES' and _cuota > 1.0:
                    c_yes = _cuota
                elif _otype == 'OT_NO' and _cuota > 1.0:
                    c_no = _cuota
            p_fair_yes, p_fair_no = devig_two_way(c_yes, c_no)
            for offer in odds:
                otype = offer.get('type', '')
                if otype == 'OT_YES':
                    p, side = p_yes, 'Sí'
                    fair_p = p_fair_yes
                elif otype == 'OT_NO':
                    # FIX A (2026-09-15, orden John): solo apostar "No" si el
                    # modelo favorece No (p_no >= 0.50). Antes con min_p 0.45 el
                    # bot apostaba contra su propia lectura (ej. Sí 53% y aun así No).
                    p_no = 1.0 - p_yes
                    if p_no < 0.50:
                        continue
                    p, side = p_no, 'No'
                    fair_p = p_fair_no
                else:
                    continue
                fair_odds = (1.0 / fair_p) if fair_p else None
                eff_min_p, eff_min_conf, eff_enabled, eff_min_ev, eff_min_cuota, eff_min_line, eff_max_line = _resolve_filters(
                    market_filters, market_key, side, min_p, min_confidence)
                _add_candidate(candidates, md['market'], offer, None, side, p, cuota_minima,
                              confidence=confidence, min_p=eff_min_p, min_confidence=eff_min_conf,
                              enabled=eff_enabled, sub_min_ev=eff_min_ev, sub_min_cuota=eff_min_cuota,
                              calib_cap=calib_cap, min_line=eff_min_line, max_line=eff_max_line,
                              fair_odds=fair_odds)

    candidates.sort(key=lambda x: x['ev'], reverse=True)
    return candidates
