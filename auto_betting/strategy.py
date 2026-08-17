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


# ── Selección unificada (por EV) ──

def _add_candidate(candidates, market, offer, line, side, p, cuota_minima,
                   confidence=None, min_p=0.50, min_confidence=0.35):
    cuota = offer.get('odds_decimal', 0)
    if cuota <= 0 or cuota < cuota_minima:
        return
    if p < min_p:
        return
    ev = p * cuota - 1.0
    if ev <= 0:
        return
    if confidence is not None and confidence < min_confidence:
        return
    candidates.append({
        'market': market,
        'offer': offer,
        'line': line,
        'side': side,
        'cuota': cuota,
        'p': p,
        'ev': ev,
        'confidence': confidence or 0,
    })


def select_bets(markets_data, cuota_minima=2.0, min_p=0.50, min_confidence=0.35):
    """
    Selecciona apuestas por EV positivo + P >= min_p + confidence >= min_confidence.
    `markets_data`: lista de dicts:
      - over/under: {'market', 'type':'over_under', 'lambda', 'confidence', 'odds'}
      - x12:        {'market', 'type':'x12', 'probs':{'home','draw','away'}, 'confidence', 'odds'}
      - btts:       {'market', 'type':'btts', 'p_yes', 'confidence', 'odds'}
    Devuelve lista de candidatos ordenados por EV descendente.
    """
    candidates = []

    for md in markets_data:
        mtype = md.get('type')
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
                _add_candidate(candidates, md['market'], offer, line, side, p, cuota_minima,
                              confidence=confidence, min_p=min_p, min_confidence=min_confidence)

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
                _add_candidate(candidates, md['market'], offer, None, side, p, cuota_minima,
                              confidence=confidence, min_p=min_p, min_confidence=min_confidence)

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
                _add_candidate(candidates, md['market'], offer, None, side, p, cuota_minima,
                              confidence=confidence, min_p=min_p, min_confidence=min_confidence)

    candidates.sort(key=lambda x: x['ev'], reverse=True)
    return candidates
