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
            'shots_total':    {'lambda': float, 'confidence': float},
            'both_teams_score': {'yes': float, 'confidence': float},
        } (solo mercados con datos válidos)
    """
    _setup_django()

    from ai_predictions.official_prediction_model import official_prediction_model
    from ai_predictions.simple_models import SimplePredictionService, ModeloHibridoGeneral
    from ai_predictions.corners_model import corners_model
    from ai_predictions.shots_prediction_model import shots_prediction_model
    from ai_predictions.xg_shots_model import xg_shots_model
    from ai_predictions.enhanced_both_teams_score import enhanced_both_teams_score_model

    # Fase 3 — Validar cobertura de datos antes de ejecutar cualquier modelo
    coverage = validate_market_data(home_team, away_team, league)

    all_predictions = {}

    # ── GOLES: Dixon-Coles + Simple Average + Ensemble + Híbrido General ──
    if coverage.get('goals_total', False):
        try:
            simple_service = SimplePredictionService()
            goals_models = simple_service.get_all_simple_predictions(
                home_team, away_team, league, 'goals_total'
            )

            hybrid = ModeloHibridoGeneral()
            hybrid_pred = hybrid.predecir(home_team, away_team, league, 'goals_total')
            if hybrid_pred and hybrid_pred.get('prediction', 0) > 0:
                goals_models.append(hybrid_pred)

            if goals_models:
                all_predictions['goals_total'] = goals_models
        except Exception as e:
            logger.error(f'get_official_predictions - goals pipeline error: {e}')
    else:
        logger.info(f'get_official_predictions: saltando goals_total — datos insuficientes')

    # ── TIROS A PUERTA (shots on target): xg_shots_model ──
    # BetPlay ofrece "Total de tiros a puerta (Resuelta usando Opta Data)"
    # No ofrece "remates totales" como mercado over/under.
    if coverage.get('shots_on_target', False):
        shots_models = []
        try:
            pred1 = xg_shots_model.predict_shots_on_target_total(home_team, away_team, league)
            if pred1:
                shots_models.append(pred1)
        except Exception as e:
            logger.error(f'get_official_predictions - xg_shots_model (on target) error: {e}')
        if shots_models:
            all_predictions['shots_on_target'] = shots_models
    else:
        logger.info(f'get_official_predictions: saltando shots_on_target — datos insuficientes')

    # ── CÓRNERS: modelo único (ya alineado con la web) ──
    if coverage.get('corners_total', False):
        try:
            corner_pred = corners_model.predecir(home_team, away_team, league, 'corners_total')
            if corner_pred:
                all_predictions['corners_total'] = [corner_pred]
        except Exception as e:
            logger.error(f'get_official_predictions - corners_model error: {e}')
    else:
        logger.info(f'get_official_predictions: saltando corners_total — datos insuficientes')

    # ── BTTS: modelo único (ya alineado con la web) ──
    if coverage.get('both_teams_score', False):
        try:
            btts_prob = enhanced_both_teams_score_model.predict(home_team, away_team, league)
            if btts_prob is not None:
                all_predictions['both_teams_score'] = [{
                    'model_name': 'Enhanced Both Teams Score',
                    'prediction': float(btts_prob),
                    'confidence': 0.80,
                    'total_matches': 100,
                }]
        except Exception as e:
            logger.error(f'get_official_predictions - btts error: {e}')
    else:
        logger.info(f'get_official_predictions: saltando both_teams_score — datos insuficientes')

    # ── Calcular predicción oficial (promedio ponderado) ──
    official = official_prediction_model.calculate_official_predictions(all_predictions)

    # ── Formatear resultado ──
    result = {}

    # ── Cap de sanidad de lambda de goles (fix 2026-08-23) ──
    # Auditoría del 23-Ago: el modelo inflaba λ de goles hasta 1.75x el
    # promedio real de la liga → P(over) fantasma → 15 apuestas de goles-over
    # correlacionadas perdidas en un día (−36% ROI). Si λ > 1.25x el promedio
    # de la liga (ventana 730d, misma que validate_market_data), el mercado de
    # goles se descarta por descalibración: el "value" era error del modelo,
    # no ventaja real contra el mercado.
    GOALS_LAMBDA_MAX_RATIO = 1.25
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
        result['shots_on_target'] = {
            'lambda': official['shots_on_target']['prediction'],
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
    return result


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
    'corners':         {'min_p': 0.56, 'min_confidence': 0.35},  # reduce ~67-71%
    'shots_on_target': {'min_p': 0.56, 'min_confidence': 0.35},  # reduce 67%
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


# ── Selección unificada (por EV) ──

def _get_tier_thresholds(cuota):
    """
    Umbrales escalonados por rango de cuota.
    Más cuota = más exigencia de confianza y EV.
    P mínima es siempre 0.50 (hard floor); los tiers solo suben requisitos
    de confidence y EV para cuotas más altas.
    """
    if cuota <= 2.99:
        return 0.50, 0.35, 0.05   # cuota baja: confianza mínima, EV ≥ 5%
    elif cuota <= 3.99:
        return 0.50, 0.45, 0.10   # más confianza + EV ≥ 10%
    elif cuota <= 5.99:
        return 0.50, 0.55, 0.15   # cuota alta: señal fuerte + EV ≥ 15%
    else:
        return 0.50, 0.65, 0.20   # longshots: convicción alta + EV ≥ 20%


def _add_candidate(candidates, market, offer, line, side, p, cuota_minima,
                   confidence=None, min_p=0.50, min_confidence=0.35,
                   enabled=True, sub_min_ev=0.0, sub_min_cuota=0.0, calib_cap=0.58):
    # Submercado apagado desde la config (ej. Córners Under, BTTS No)
    if not enabled:
        return

    cuota = offer.get('odds_decimal', 0)
    if cuota <= 0 or cuota < cuota_minima:
        return
    # Cuota mínima específica del submercado (0 = usa la global/cuota_minima)
    if sub_min_cuota and cuota < sub_min_cuota:
        return

    # Fase 4 — calibrar la probabilidad antes de evaluar (cap configurable)
    p_raw = p
    p = calibrate_probability(p, cap=calib_cap)

    # Filtro primario: P mínima absoluta (hard floor, no negociable)
    if p < min_p:
        return

    # Umbrales escalonados por cuota (tiers — solo agregan requisitos)
    tier_min_p, tier_min_conf, tier_min_ev = _get_tier_thresholds(cuota)

    # El tier no puede bajar el P mínimo por debajo de min_p
    effective_min_p = max(min_p, tier_min_p)
    if p < effective_min_p:
        return
    ev = p * cuota - 1.0
    # EV mínimo: el más exigente entre el tier por cuota y el del submercado.
    # Auditoría: bucket EV 10-20% = -54.9% ROI → exigir EV≥20% en cuotas bajas.
    effective_min_ev = max(tier_min_ev, sub_min_ev)
    if ev <= effective_min_ev:
        return
    # Confidence: tomar el más exigente entre min_confidence y tier
    effective_min_conf = max(min_confidence, tier_min_conf)
    if confidence is not None and confidence < effective_min_conf:
        return
    candidates.append({
        'market': market,
        'offer': offer,
        'line': line,
        'side': side,
        'cuota': cuota,
        'p': p,
        'p_raw': p_raw,  # guardar P original para logging
        'ev': ev,
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
    )


def select_bets(markets_data, cuota_minima=2.0, min_p=0.50, min_confidence=0.35,
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
            for offer in odds:
                line = offer.get('line')
                if line is None:
                    continue
                p_over = poisson_over(line, lam)
                p_under = 1.0 - p_over
                otype = offer.get('type', '')
                if otype == 'OT_OVER':
                    p, side = p_over, 'over'
                elif otype == 'OT_UNDER':
                    p, side = p_under, 'under'
                else:
                    continue
                eff_min_p, eff_min_conf, eff_enabled, eff_min_ev, eff_min_cuota = _resolve_filters(
                    market_filters, market_key, side, min_p, min_confidence)
                _add_candidate(candidates, md['market'], offer, line, side, p, cuota_minima,
                              confidence=confidence, min_p=eff_min_p, min_confidence=eff_min_conf,
                              enabled=eff_enabled, sub_min_ev=eff_min_ev, sub_min_cuota=eff_min_cuota,
                              calib_cap=calib_cap)

        elif mtype == 'x12':
            probs = md.get('probs') or {}
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
                eff_min_p, eff_min_conf, eff_enabled, eff_min_ev, eff_min_cuota = _resolve_filters(
                    market_filters, market_key, side, min_p, min_confidence)
                _add_candidate(candidates, md['market'], offer, None, side, p, cuota_minima,
                              confidence=confidence, min_p=eff_min_p, min_confidence=eff_min_conf,
                              enabled=eff_enabled, sub_min_ev=eff_min_ev, sub_min_cuota=eff_min_cuota,
                              calib_cap=calib_cap)

        elif mtype == 'btts':
            p_yes = md.get('p_yes')
            if p_yes is None:
                continue
            for offer in odds:
                otype = offer.get('type', '')
                if otype == 'OT_YES':
                    p, side = p_yes, 'Sí'
                elif otype == 'OT_NO':
                    p, side = 1.0 - p_yes, 'No'
                else:
                    continue
                eff_min_p, eff_min_conf, eff_enabled, eff_min_ev, eff_min_cuota = _resolve_filters(
                    market_filters, market_key, side, min_p, min_confidence)
                _add_candidate(candidates, md['market'], offer, None, side, p, cuota_minima,
                              confidence=confidence, min_p=eff_min_p, min_confidence=eff_min_conf,
                              enabled=eff_enabled, sub_min_ev=eff_min_ev, sub_min_cuota=eff_min_cuota,
                              calib_cap=calib_cap)

    candidates.sort(key=lambda x: x['ev'], reverse=True)
    return candidates
