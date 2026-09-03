"""
web_pipeline.py — MOTOR ÚNICO DE PREDICCIÓN (2026-09-01, decisión de John)
═══════════════════════════════════════════════════════════════════════════
FUENTE OFICIAL DE VERDAD: el pipeline de la web https://predicta.com.co/ai/predict/
(vistas `PredictionFormView` / `PredictionResultView` en ai_predictions/views.py).

Este módulo replica EXACTAMENTE ese pipeline (mismos modelos por mercado,
mismo orden, misma agregación oficial = promedio ponderado por confianza)
para que auto_betting y value_betting usen EL MISMO dato que la web.

Por mercado (idéntico a la web):
  - shots_*            : shots_prediction_model + xg_shots_model          (2 modelos)
  - corners_*          : corners_model (40/30/15/15)                      (1 modelo)
  - goals_*            : Dixon-Coles + Simple Average + Ensemble + Híbrido (4 modelos)
  - both_teams_score   : Dixon-Coles + Simple Average + Ensemble
                         + Enhanced BTS + Híbrido                          (5 modelos)
  - Al final: official_prediction_model.add_to_predictions() agrega la
    "Predicción Oficial" (promedio ponderado por confidence).

Nota de fidelidad: en caso de error de un modelo individual, aquí se omite ese
modelo (la vista web insertaría un fallback genérico 10.0/15.0); en operación
normal sin errores ambos caminos producen resultados idénticos.

IMPORTANTE: este módulo NO debe importarse desde poisson_ratings ni usar el
motor ridge — el motor único es el pipeline de la web. (Kill-switch histórico
POISSON_RATINGS_ENABLED en auto_betting/strategy.py quedó en False.)
"""
import logging

logger = logging.getLogger('ai_predictions')

# Tipos de predicción que genera la web (views.process_predictions_background)
WEB_PREDICTION_TYPES = [
    'shots_total', 'shots_home', 'shots_away',
    'shots_on_target_total',
    'goals_total', 'goals_home', 'goals_away',
    'corners_total', 'corners_home', 'corners_away',
    'both_teams_score',
]

# Mapeo pred_type -> método de los modelos de remates (igual que la web)
_SHOTS_METHODS = {
    'shots_total': 'predict_shots_total',
    'shots_home': 'predict_shots_home',
    'shots_away': 'predict_shots_away',
    'shots_on_target_total': 'predict_shots_on_target_total',
}


def build_web_predictions(home_team: str, away_team: str, league, prediction_types=None) -> dict:
    """
    Construye el dict `{pred_type: [modelos..., 'Predicción Oficial']}`
    EXACTAMENTE como lo hace la web (/ai/predict/), incluida la
    "Predicción Oficial" final.

    Args:
        home_team, away_team: nombres de equipos (formato predicta).
        league: instancia de football_data.models.League.
        prediction_types: lista opcional de pred_types a calcular
                          (default: WEB_PREDICTION_TYPES completo).

    Returns:
        dict {pred_type: [dict_modelo, ...]} donde el ÚLTIMO elemento de cada
        lista es la "Predicción Oficial" (model_name == 'Predicción Oficial').
        Las listas vacías indican mercados sin predicción.
    """
    from .simple_models import SimplePredictionService, ModeloHibridoGeneral
    from .corners_model import corners_model
    from .shots_prediction_model import shots_prediction_model
    from .xg_shots_model import xg_shots_model
    from .enhanced_both_teams_score import enhanced_both_teams_score_model
    from .official_prediction_model import official_prediction_model

    if prediction_types is None:
        prediction_types = WEB_PREDICTION_TYPES

    svc = SimplePredictionService()
    all_predictions_by_type = {}

    for pred_type in prediction_types:
        predictions = []

        if 'shots' in pred_type or 'remates' in pred_type:
            # ── Manejo especial de remates: AMBOS modelos (igual que la web) ──
            method = _SHOTS_METHODS.get(pred_type)
            if method:
                try:
                    p1 = getattr(shots_prediction_model, method)(home_team, away_team, league)
                    if p1:
                        predictions.append(p1)
                except Exception as e:
                    logger.warning(f'web_pipeline: shots_prediction_model falló para {pred_type}: {e}')
                try:
                    p2 = getattr(xg_shots_model, method)(home_team, away_team, league)
                    if p2:
                        predictions.append(p2)
                except Exception as e:
                    logger.warning(f'web_pipeline: xg_shots_model falló para {pred_type}: {e}')

        elif 'corners' in pred_type:
            # ── Modelo independiente de córners (igual que la web) ──
            try:
                corner_pred = corners_model.predecir(home_team, away_team, league, pred_type)
                if corner_pred:
                    predictions.append(corner_pred)
            except Exception as e:
                logger.warning(f'web_pipeline: corners_model falló para {pred_type}: {e}')

        else:
            # ── goals_* y both_teams_score: modelos simples + extras (igual que la web) ──
            try:
                predictions = svc.get_all_simple_predictions(home_team, away_team, league, pred_type)
            except Exception as e:
                logger.warning(f'web_pipeline: get_all_simple_predictions falló para {pred_type}: {e}')
                predictions = []

            # Enhanced BTS (igual que la vista web)
            if pred_type == 'both_teams_score':
                try:
                    enhanced_prob = enhanced_both_teams_score_model.predict(home_team, away_team, league)
                    if enhanced_prob is not None:
                        predictions.append({
                            'model_name': 'Enhanced Both Teams Score',
                            'prediction': float(enhanced_prob),
                            'confidence': 0.80,
                            'probabilities': {'both_score': float(enhanced_prob)},
                            'total_matches': 100,
                        })
                except Exception as e:
                    logger.warning(f'web_pipeline: enhanced_both_teams_score falló: {e}')

            # Híbrido general (la web lo agrega en el else para goals y BTS)
            try:
                hybrid_prediction = ModeloHibridoGeneral().predecir(home_team, away_team, league, pred_type)
                if hybrid_prediction and hybrid_prediction.get('prediction') is not None:
                    predictions.append(hybrid_prediction)
            except Exception as e:
                logger.warning(f'web_pipeline: ModeloHibridoGeneral falló para {pred_type}: {e}')

        all_predictions_by_type[pred_type] = predictions

    # ── Agregar "Predicción Oficial" (igual que la web) + híbrido xG (Fase 2) ──
    try:
        all_predictions_by_type = official_prediction_model.add_to_predictions(
            all_predictions_by_type, home_team=home_team, away_team=away_team, league=league)
    except Exception as e:
        logger.error(f'web_pipeline: official_prediction_model falló: {e}')

    return all_predictions_by_type


def get_official_prediction(all_predictions_by_type: dict, pred_type: str):
    """
    Devuelve el dict de la "Predicción Oficial" para un pred_type, o None.
    """
    for pred in (all_predictions_by_type.get(pred_type) or []):
        if isinstance(pred, dict) and pred.get('model_name') in ('Predicción Oficial', 'Predicción oficial'):
            return pred
    return None
