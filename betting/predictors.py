"""
Predictor de resultado 1X2 (Local / Empate / Visitante).

Usa los modelos existentes de ai_predictions como CAJA NEGRA:
- Obtiene lambda_home y lambda_away de goles esperados
- Deriva probabilidades 1X2 vía distribución de Poisson
- NO modifica, reentrena ni altera ningún modelo existente
"""

import numpy as np
import logging
from math import exp, factorial
from typing import Dict, Optional

from football_data.models import League

logger = logging.getLogger('betting')


def _get_goal_lambdas(home_team: str, away_team: str, league: League) -> Dict[str, float]:
    """
    Obtiene lambda_home y lambda_away llamando los modelos existentes
    de ai_predictions como caja negra (sin modificar nada).
    
    Retorna {'lambda_home': float, 'lambda_away': float, 'confidence': float}
    """
    try:
        # Usar SimplePredictionService para goals_home y goals_away
        from ai_predictions.simple_models import SimplePredictionService
        
        service = SimplePredictionService()
        
        # Obtener predicción de goles local
        home_pred = service.get_all_simple_predictions(
            home_team, away_team, league, 'goals_home'
        )
        
        # Obtener predicción de goles visitante
        away_pred = service.get_all_simple_predictions(
            home_team, away_team, league, 'goals_away'
        )
        
        lambda_home = 1.2  # fallback
        lambda_away = 1.0
        confidence = 0.5
        
        # Extraer predicción de goles local del ensemble
        if home_pred:
            # Buscar la predicción del ensemble (mayor peso)
            home_values = []
            home_confidences = []
            for pred in home_pred:
                if isinstance(pred, dict) and 'prediction' in pred:
                    try:
                        val = float(pred['prediction'])
                        if val > 0:
                            home_values.append(val)
                            home_confidences.append(float(pred.get('confidence', 0.5)))
                    except (ValueError, TypeError):
                        continue
            
            if home_values:
                # Promedio ponderado por confianza
                if sum(home_confidences) > 0:
                    lambda_home = float(np.average(home_values, weights=home_confidences))
                else:
                    lambda_home = float(np.mean(home_values))
        
        # Extraer predicción de goles visitante
        if away_pred:
            away_values = []
            away_confidences = []
            for pred in away_pred:
                if isinstance(pred, dict) and 'prediction' in pred:
                    try:
                        val = float(pred['prediction'])
                        if val > 0:
                            away_values.append(val)
                            away_confidences.append(float(pred.get('confidence', 0.5)))
                    except (ValueError, TypeError):
                        continue
            
            if away_values:
                if sum(away_confidences) > 0:
                    lambda_away = float(np.average(away_values, weights=away_confidences))
                else:
                    lambda_away = float(np.mean(away_values))
        
        # Confianza combinada
        if home_pred and away_pred:
            confidence = float(np.mean(
                [float(p.get('confidence', 0.5)) for p in home_pred + away_pred 
                 if isinstance(p, dict)]
            ))
        
        logger.info(
            f"[1X2] Lambdas: home={lambda_home:.2f} away={lambda_away:.2f} "
            f"conf={confidence:.3f}"
        )
        
        return {
            'lambda_home': lambda_home,
            'lambda_away': lambda_away,
            'confidence': confidence
        }
        
    except Exception as e:
        logger.warning(f"[1X2] Error obteniendo lambdas: {e}. Usando fallback.")
        return {
            'lambda_home': 1.4,
            'lambda_away': 1.1,
            'confidence': 0.3
        }


def _poisson_pmf(k: int, lam: float) -> float:
    """Probability Mass Function de Poisson: P(X = k) para lambda dada."""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return exp(-lam) * (lam ** k) / factorial(k)


def predict_1x2(
    home_team: str,
    away_team: str,
    league: League,
    max_goals: int = 10
) -> Dict[str, float]:
    """
    Predice probabilidades de resultado 1X2 para un partido.
    
    1. Llama los modelos existentes como caja negra para obtener
       lambda_home y lambda_away de goles esperados.
    2. Deriva P(local), P(empate), P(visitante) vía Poisson.
    
    Args:
        home_team: Nombre del equipo local
        away_team: Nombre del equipo visitante
        league: Instancia de League de Django
        max_goals: Máximo de goles a considerar en la suma (default 10)
    
    Returns:
        {
            'prob_local': float (0-1),
            'prob_empate': float (0-1),
            'prob_visitante': float (0-1),
            'lambda_home': float,
            'lambda_away': float,
            'confidence': float (0-1),
            'goles_esperados_total': float
        }
    """
    lambdas = _get_goal_lambdas(home_team, away_team, league)
    
    lambda_home = lambdas['lambda_home']
    lambda_away = lambdas['lambda_away']
    confidence = lambdas['confidence']
    
    # Calcular probabilidades de cada marcador exacto
    prob_local = 0.0
    prob_empate = 0.0
    prob_visitante = 0.0
    
    for h in range(max_goals + 1):
        p_h = _poisson_pmf(h, lambda_home)
        for a in range(max_goals + 1):
            p_a = _poisson_pmf(a, lambda_away)
            prob_joint = p_h * p_a
            
            if h > a:
                prob_local += prob_joint
            elif h == a:
                prob_empate += prob_joint
            else:
                prob_visitante += prob_joint
    
    # Normalizar (la suma debe ser ~1, pero ajustamos por truncamiento)
    total = prob_local + prob_empate + prob_visitante
    if total > 0:
        prob_local /= total
        prob_empate /= total
        prob_visitante /= total
    
    result = {
        'prob_local': round(prob_local, 4),
        'prob_empate': round(prob_empate, 4),
        'prob_visitante': round(prob_visitante, 4),
        'lambda_home': round(lambda_home, 2),
        'lambda_away': round(lambda_away, 2),
        'confidence': round(confidence, 4),
        'goles_esperados_total': round(lambda_home + lambda_away, 2)
    }
    
    logger.info(
        f"[1X2] {home_team} vs {away_team}: "
        f"L={prob_local:.2%} E={prob_empate:.2%} V={prob_visitante:.2%} "
        f"(λH={lambda_home:.2f} λA={lambda_away:.2f})"
    )
    
    return result
