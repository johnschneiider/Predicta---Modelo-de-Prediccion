"""
Vistas para predicciones de IA
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q, Sum, Count
from django.db.models.functions import TruncDate
from decimal import Decimal, InvalidOperation
import json
import logging
import threading
from datetime import datetime, timedelta
from collections import defaultdict
from django.utils import timezone

from football_data.models import League, Match
from .models import PredictionModel, PredictionResult, TeamStats, SavedPrediction, Apuesta
from .services import PredictionService
from .multi_models import MultiModelPredictionService
from .advanced_models import AdvancedStatisticalModels
from .model_validation import ModelValidator
from .simple_models import SimplePredictionService, ModeloHibridoCorners, ModeloHibridoGeneral
from .corners_model import corners_model
from .model_trainer import ModelTrainer
from .forms import PredictionForm

logger = logging.getLogger('ai_predictions')


# ── Mercados disponibles (los mismos que muestra Predicta) ──
def build_markets_summary(all_predictions):
    """
    Extrae la predicción oficial de cada mercado para ofrecerla en el
    selector de apuestas. Devuelve una lista de dicts con clave, etiqueta,
    valor oficial y línea sugerida (Over/Under).
    """
    markets = []
    for key, label in Apuesta.MARKET_CHOICES:
        preds = all_predictions.get(key, []) or []
        official = None
        for p in preds:
            if isinstance(p, dict) and p.get('model_name') in ('Predicción Oficial', 'Predicción oficial'):
                official = p.get('prediction')
                break

        suggested_line = None
        if key != 'both_teams_score' and official is not None:
            try:
                suggested_line = max(0.5, round(float(official) * 2) / 2)
            except (TypeError, ValueError):
                suggested_line = None

        markets.append({
            'key': key,
            'label': label,
            'official': official,
            'suggested_line': suggested_line,
            'is_bts': key == 'both_teams_score',
        })
    return markets


def compute_streak(apuestas):
    """Calcula la racha actual de resultados resueltos (W/L) en orden cronológico."""
    resueltas = apuestas.filter(status__in=('ganada', 'perdida')).order_by('resolved_at', 'created_at')
    n = 0
    tipo = None
    for a in resueltas:
        t = 'W' if a.status == 'ganada' else 'L'
        if tipo is None:
            tipo = t
            n = 1
        elif t == tipo:
            n += 1
        else:
            tipo = t
            n = 1
    return {'n': n, 'type': tipo}


def convert_numpy_to_native(obj):
    """
    Convierte tipos numpy a tipos nativos de Python para serialización JSON.
    """
    import numpy as np
    
    if isinstance(obj, np.integer):
        return int(obj)
    elif isinstance(obj, np.floating):
        return float(obj)
    elif isinstance(obj, np.ndarray):
        return obj.tolist()
    elif isinstance(obj, dict):
        return {key: convert_numpy_to_native(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_numpy_to_native(item) for item in obj]
    elif isinstance(obj, tuple):
        return tuple(convert_numpy_to_native(item) for item in obj)
    else:
        return obj


def process_predictions_background(session_key, home_team, away_team, league_id, league_name):
    """Procesa predicciones en segundo plano"""
    from django.contrib.sessions.backends.db import SessionStore
    
    try:
        logger.info(f"🔄 BACKGROUND INICIADO - Home: '{home_team}' vs Away: '{away_team}', Liga: {league_name}")
        session = SessionStore(session_key=session_key)
        league = League.objects.get(id=league_id)
        
        # No limpiar predicción anterior aquí - puede causar condición de carrera
        
        prediction_types = [
            'shots_total', 'shots_home', 'shots_away',
            'shots_on_target_total',
            'goals_total', 'goals_home', 'goals_away',
            'corners_total', 'corners_home', 'corners_away',
            'both_teams_score'
        ]
        
        all_predictions_by_type = {}
        total_types = len(prediction_types)
        
        logger.info("Generando predicciones en background...")
        logger.info(f"🔧 INICIANDO BUCLE - Home: '{home_team}' vs Away: '{away_team}', Liga: {league_name}")
        
        # LIMPIAR SESIÓN PARA FORZAR REGENERACIÓN
        session.pop('all_predictions', None)
        session.pop('prediction_data', None)
        session.modified = True
        session.save()
        logger.info("🔧 SESIÓN LIMPIADA - Forzando regeneración completa")
        
        # Procesamiento sin timeout (Windows compatible)
        logger.info(f"🔧 INICIANDO BUCLE - Total tipos: {total_types}")
        logger.info(f"🔧 TIPOS DE PREDICCIÓN: {prediction_types}")
        
        for index, pred_type in enumerate(prediction_types):
            try:
                logger.info(f"Procesando: {pred_type}")
                logger.info(f"🔧 ITERACIÓN {index+1}/{total_types} - {pred_type}")
                
                # Log específico para detectar si shots se procesa
                if 'shots' in pred_type:
                    logger.info(f"🎯 PROCESANDO SHOTS: {pred_type}")
                    logger.info(f"🎯 SHOTS DETECTADO - Iniciando procesamiento para {pred_type}")
            
                # Actualizar progreso
                session['prediction_progress'] = {
                    'current': index + 1,
                    'total': total_types,
                    'current_type': pred_type.replace('_', ' ').title(),
                    'status': 'processing'
                }
                session.modified = True
                session.save()
                
                simple_service = SimplePredictionService()
                trainer = ModelTrainer()
                
                # Generar modelos simples (3 modelos: Dixon-Coles/Poisson, Average, Ensemble)
                logger.info(f"Generando modelos simples para {pred_type}...")
                logger.info(f"🔧 PROCESANDO {pred_type} - Home: '{home_team}' vs Away: '{away_team}'")
                
                # MANEJO ESPECIAL PARA REMATES - USAR AMBOS MODELOS
                if 'shots' in pred_type or 'remates' in pred_type:
                    logger.info(f"🎯 ENTRANDO A MANEJO ESPECIAL DE REMATES (AMBOS MODELOS) para {pred_type}")
                    predictions = []
                    
                    try:
                        # Modelo 1: Shots Prediction Model (original)
                        from .shots_prediction_model import shots_prediction_model
                        logger.info(f"🎯 IMPORTACIÓN EXITOSA de shots_prediction_model para {pred_type}")
                        
                        if pred_type == 'shots_total':
                            pred1 = shots_prediction_model.predict_shots_total(home_team, away_team, league)
                        elif pred_type == 'shots_home':
                            pred1 = shots_prediction_model.predict_shots_home(home_team, away_team, league)
                        elif pred_type == 'shots_away':
                            pred1 = shots_prediction_model.predict_shots_away(home_team, away_team, league)
                        elif pred_type == 'shots_on_target_total':
                            pred1 = shots_prediction_model.predict_shots_on_target_total(home_team, away_team, league)
                        else:
                            pred1 = None
                        
                        if pred1:
                            predictions.append(pred1)
                            logger.info(f"🎯 MODELO 1 (Shots Prediction) agregado para {pred_type}")
                        
                    except Exception as e:
                        logger.error(f"❌ ERROR EN shots_prediction_model para {pred_type}: {e}")
                    
                    try:
                        # Modelo 2: XG Shots Model (nuevo)
                        from .xg_shots_model import xg_shots_model
                        logger.info(f"🎯 IMPORTACIÓN EXITOSA de xg_shots_model para {pred_type}")
                        
                        if pred_type == 'shots_total':
                            pred2 = xg_shots_model.predict_shots_total(home_team, away_team, league)
                        elif pred_type == 'shots_home':
                            pred2 = xg_shots_model.predict_shots_home(home_team, away_team, league)
                        elif pred_type == 'shots_away':
                            pred2 = xg_shots_model.predict_shots_away(home_team, away_team, league)
                        elif pred_type == 'shots_on_target_total':
                            pred2 = xg_shots_model.predict_shots_on_target_total(home_team, away_team, league)
                        else:
                            pred2 = None
                        
                        if pred2:
                            predictions.append(pred2)
                            logger.info(f"🎯 MODELO 2 (XG Shots) agregado para {pred_type}")
                        
                    except Exception as e:
                        logger.error(f"❌ ERROR EN xg_shots_model para {pred_type}: {e}")
                    
                    logger.info(f"🎯 TOTAL MODELOS DE REMATES para {pred_type}: {len(predictions)} modelos")
                    logger.info(f"🎯 PREDICCIONES GENERADAS: {predictions}")
                elif 'corners' in pred_type:
                    # ── MODELO INDEPENDIENTE DE CORNERS (40/30/15/15) ──
                    try:
                        corner_pred = corners_model.predecir(home_team, away_team, league, pred_type)
                        predictions = [corner_pred]
                        logger.info(f"[CORNERS] Nuevo modelo para {pred_type}: {corner_pred['prediction']:.2f}")
                    except Exception as e:
                        logger.error(f"[CORNERS] Error en nuevo modelo para {pred_type}: {e}")
                        predictions = [{
                            'model_name': 'Corners Avanzado (Fallback)',
                            'prediction': 10.0,
                            'confidence': 0.3,
                            'probabilities': {'over_10': 0.5},
                            'total_matches': 0
                        }]
                else:
                    try:
                        predictions = simple_service.get_all_simple_predictions(home_team, away_team, league, pred_type)
                        logger.info(f"✅ Modelos simples generados para {pred_type}: {len(predictions)}")
                    except Exception as e:
                        logger.error(f"❌ ERROR EN get_all_simple_predictions para {pred_type}: {e}")
                        logger.error(f"❌ TRACEBACK:", exc_info=True)
                        # Crear predicción de fallback
                        predictions = [{
                            'model_name': f'Fallback {pred_type}',
                            'prediction': 10.0,
                            'confidence': 0.3,
                            'probabilities': {'over_10': 0.5},
                            'total_matches': 0,
                            'error': str(e)
                        }]
                        logger.info(f"🔄 Usando predicción de fallback para {pred_type}")
                
                # Manejo específico para "both_teams_score" con modelo mejorado
                if pred_type == 'both_teams_score':
                    try:
                        from .enhanced_both_teams_score import enhanced_both_teams_score_model
                        enhanced_prob = enhanced_both_teams_score_model.predict(home_team, away_team, league)
                        
                        enhanced_prediction = {
                            'model_name': 'Enhanced Both Teams Score',
                            'prediction': enhanced_prob,
                            'confidence': 0.80,
                            'probabilities': {'both_score': enhanced_prob},
                            'total_matches': 100
                        }
                        predictions.append(enhanced_prediction)
                        logger.info(f"Modelo Enhanced Both Teams Score agregado para {pred_type}: {enhanced_prob:.3f}")
                    except Exception as e:
                        logger.error(f"Error en modelo mejorado ambos marcan: {e}")
                        # Fallback específico para ambos marcan
                        fallback_prob = 0.45  # Valor más realista que 0.5
                        enhanced_fallback = {
                            'model_name': 'Enhanced Both Teams Score (Fallback)',
                            'prediction': fallback_prob,
                            'confidence': 0.60,
                            'probabilities': {'both_score': fallback_prob},
                            'total_matches': 0
                        }
                        predictions.append(enhanced_fallback)
                        logger.info(f"Fallback ambos marcan agregado: {fallback_prob}")
                
                # Los corners ya se procesaron con el modelo independiente arriba
                elif 'corners' in pred_type:
                    pass
                else:
                    try:
                        # Usar modelo híbrido general para otros tipos
                        hybrid_model = ModeloHibridoGeneral()
                        hybrid_prediction = hybrid_model.predecir(home_team, away_team, league, pred_type)
                        predictions.append(hybrid_prediction)
                        logger.info(f"Modelo Híbrido General agregado para {pred_type}")
                    except Exception as e:
                        logger.error(f"Error agregando modelo híbrido general para {pred_type}: {e}")
                        # Crear modelo híbrido de fallback
                        hybrid_fallback = {
                            'model_name': 'Modelo Híbrido General',
                            'prediction': 10.0,
                            'confidence': 0.6,
                            'probabilities': {'over_10': 0.5, 'over_15': 0.3, 'over_20': 0.1},
                            'total_matches': 0,
                            'component_predictions': {}
                        }
                        predictions.append(hybrid_fallback)
                        logger.info(f"Modelo híbrido general fallback agregado para {pred_type}")
                
                all_predictions_by_type[pred_type] = predictions
                model_names = [pred['model_name'] for pred in predictions]
                logger.info(f"[OK] {pred_type}: {len(predictions)} modelos generados - {model_names}")
                
            except Exception as e:
                logger.error(f"❌ ERROR EN {pred_type}: {e}")
                logger.error(f"❌ TRACEBACK:", exc_info=True)
                all_predictions_by_type[pred_type] = []
        
        # AGREGAR PREDICCIÓN OFICIAL (después de todos los otros modelos)
        logger.info("🎯 OFICIAL - Iniciando cálculo de predicción oficial en background")
        try:
            from .official_prediction_model import official_prediction_model
            all_predictions_by_type = official_prediction_model.add_to_predictions(
                all_predictions_by_type, home_team=home_team, away_team=away_team, league=league)
            logger.info("🎯 OFICIAL - Predicción oficial agregada exitosamente en background")
        except Exception as e:
            logger.error(f"❌ OFICIAL - Error agregando predicción oficial en background: {e}")
            logger.error(f"❌ OFICIAL - Traceback:", exc_info=True)
        
        # Guardar resultados PRIMERO (antes de marcar como completado)
        session['last_prediction'] = {
            'home_team': home_team,
            'away_team': away_team,
            'league': league_name,
            'all_predictions': all_predictions_by_type
        }
        session.modified = True
        session.save()
        
        logger.info(f"✅ SESIÓN GUARDADA - Home: '{home_team}' vs Away: '{away_team}', Liga: {league_name}")
        logger.info(f"📝 DATOS EN SESIÓN - Total de tipos de predicción: {len(all_predictions_by_type)}")
        
        
        # Marcar como completado DESPUÉS de guardar los resultados
        session['prediction_progress'] = {
            'current': total_types,
            'total': total_types,
            'current_type': 'Completado',
            'status': 'completed'
        }
        session.modified = True
        session.save()
        
        logger.info("Predicciones completadas en background")
        
    except Exception as e:
        logger.error(f"❌ ERROR CRÍTICO EN BACKGROUND: {e}")
        logger.error(f"❌ TRACEBACK COMPLETO:", exc_info=True)
        # Marcar como error
        try:
            session['prediction_progress'] = {
                'current': 0,
                'total': 10,
                'current_type': 'Error',
                'status': 'error'
            }
            session.save()
        except:
            pass


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class PredictionDashboardView(View):
    """Dashboard principal de predicciones"""
    
    def get(self, request):
        # Usar contexto básico sin dependencias de modelos de IA
        context = {
            'leagues': League.objects.all(),
            'recent_predictions': [],
            'available_models': [],
        }
        return render(request, 'ai_predictions/dashboard.html', context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class PredictionFormView(View):
    """Vista para el formulario de predicción"""
    
    def get(self, request):
        logger.info("📋 PredictionFormView.get() - INICIANDO")
        try:
            logger.info("📋 Creando formulario...")
            form = PredictionForm()
            logger.info("📋 Obteniendo ligas...")
            leagues = League.objects.all()
            logger.info(f"📋 Ligas obtenidas: {leagues.count()}")
            
            context = {
                'form': form,
                'leagues': leagues,
            }
            logger.info("📋 Renderizando template...")
            response = render(request, 'ai_predictions/prediction_form.html', context)
            logger.info(f"📋 Template renderizado exitosamente - Status: {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"❌ ERROR en PredictionFormView.get(): {e}")
            logger.error(f"❌ TRACEBACK:", exc_info=True)
            raise
    
    def post(self, request):
        logger.info("Iniciando procesamiento de predicción...")
        form = PredictionForm(request.POST)
        
        if form.is_valid():
            logger.info("Formulario válido, procesando datos...")
            try:
                home_team = form.cleaned_data['home_team']
                away_team = form.cleaned_data['away_team']
                league = form.cleaned_data['league']
                logger.info(f"📋 FORMULARIO RECIBIDO - Home: '{home_team}' vs Away: '{away_team}', Liga: {league.name}")
                
                # Inicializar progreso en sesión (barra existente) y limpiar anterior
                if 'last_prediction' in request.session:
                    logger.info(f"🧹 LIMPIANDO PREDICCIÓN ANTERIOR: {request.session['last_prediction'].get('home_team')} vs {request.session['last_prediction'].get('away_team')}")
                    del request.session['last_prediction']
                request.session['prediction_progress'] = {
                    'current': 0,
                    'total': 11,
                    'current_type': 'Preparando...',
                    'status': 'running'
                }
                request.session.modified = True
                request.session.save()
                
                request.session['prediction_progress'] = {
                    'current': 0,
                    'total': 11,
                    'current_type': 'Iniciando...',
                    'status': 'processing'
                }
                request.session.modified = True
                request.session.save()
                
                # Procesar predicciones DIRECTAMENTE (sin threading)
                logger.info("🔄 PROCESANDO DIRECTAMENTE - sin threading")
                
                from .simple_models import SimplePredictionService, ModeloHibridoCorners, ModeloHibridoGeneral
                from .corners_model import corners_model
                from .league_calibration import league_calibration
                from .enhanced_both_teams_score import enhanced_both_teams_score_model
                
                prediction_types = [
                    'shots_total', 'shots_home', 'shots_away',
                    'shots_on_target_total',
                    'goals_total', 'goals_home', 'goals_away',
                    'corners_total', 'corners_home', 'corners_away',
                    'both_teams_score'
                ]
                
                all_predictions_by_type = {}
                simple_service = SimplePredictionService()
                
                for i, pred_type in enumerate(prediction_types, 1):
                    logger.info(f"🔧 PROCESANDO {i}/{len(prediction_types)} - {pred_type}")
                    # Actualizar progreso visible para la barra
                    try:
                        request.session['prediction_progress'] = {
                            'current': i - 1,
                            'total': len(prediction_types),
                            'current_type': pred_type,
                            'status': 'running'
                        }
                        request.session.modified = True
                        request.session.save()
                    except Exception as e:
                        logger.debug(f"No se pudo actualizar progreso: {e}")
                    
                    try:
                        # MANEJO ESPECIAL PARA REMATES - USAR AMBOS MODELOS
                        if 'shots' in pred_type or 'remates' in pred_type:
                            logger.info(f"🎯 [BACKGROUND] ENTRANDO A MANEJO ESPECIAL DE REMATES (AMBOS MODELOS) para {pred_type}")
                            predictions = []
                            
                            try:
                                # Modelo 1: Shots Prediction Model (original)
                                from .shots_prediction_model import shots_prediction_model
                                logger.info(f"🎯 [BACKGROUND] IMPORTACIÓN EXITOSA de shots_prediction_model para {pred_type}")
                                
                                if pred_type == 'shots_total':
                                    pred1 = shots_prediction_model.predict_shots_total(home_team, away_team, league)
                                elif pred_type == 'shots_home':
                                    pred1 = shots_prediction_model.predict_shots_home(home_team, away_team, league)
                                elif pred_type == 'shots_away':
                                    pred1 = shots_prediction_model.predict_shots_away(home_team, away_team, league)
                                elif pred_type == 'shots_on_target_total':
                                    pred1 = shots_prediction_model.predict_shots_on_target_total(home_team, away_team, league)
                                else:
                                    pred1 = None
                                
                                if pred1:
                                    predictions.append(pred1)
                                    logger.info(f"🎯 [BACKGROUND] MODELO 1 (Shots Prediction) agregado para {pred_type}")
                                
                            except Exception as e:
                                logger.error(f"❌ [BACKGROUND] ERROR EN shots_prediction_model para {pred_type}: {e}")
                            
                            try:
                                # Modelo 2: XG Shots Model (nuevo)
                                from .xg_shots_model import xg_shots_model
                                logger.info(f"🎯 [BACKGROUND] IMPORTACIÓN EXITOSA de xg_shots_model para {pred_type}")
                                
                                if pred_type == 'shots_total':
                                    pred2 = xg_shots_model.predict_shots_total(home_team, away_team, league)
                                elif pred_type == 'shots_home':
                                    pred2 = xg_shots_model.predict_shots_home(home_team, away_team, league)
                                elif pred_type == 'shots_away':
                                    pred2 = xg_shots_model.predict_shots_away(home_team, away_team, league)
                                elif pred_type == 'shots_on_target_total':
                                    pred2 = xg_shots_model.predict_shots_on_target_total(home_team, away_team, league)
                                else:
                                    pred2 = None
                                
                                if pred2:
                                    predictions.append(pred2)
                                    logger.info(f"🎯 [BACKGROUND] MODELO 2 (XG Shots) agregado para {pred_type}")
                                
                            except Exception as e:
                                logger.error(f"❌ [BACKGROUND] ERROR EN xg_shots_model para {pred_type}: {e}")
                            
                            logger.info(f"🎯 [BACKGROUND] TOTAL MODELOS DE REMATES para {pred_type}: {len(predictions)} modelos")
                            logger.info(f"🎯 [BACKGROUND] PREDICCIONES GENERADAS: {predictions}")
                        elif 'corners' in pred_type:
                            # ── MODELO INDEPENDIENTE DE CORNERS (40/30/15/15) ──
                            corner_pred = corners_model.predecir(home_team, away_team, league, pred_type)
                            predictions = [corner_pred]
                            logger.info(f"[CORNERS] Nuevo modelo inline para {pred_type}: {corner_pred['prediction']:.2f}")
                        else:
                            # Obtener predicciones simples para otros mercados
                            predictions = simple_service.get_all_simple_predictions(home_team, away_team, league, pred_type)
                            
                            # Agregar modelo híbrido solo para mercados no-shots
                            hybrid_model = ModeloHibridoGeneral()
                            hybrid_prediction = hybrid_model.predecir(home_team, away_team, league, pred_type)
                            predictions.append(hybrid_prediction)
                        
                        # APLICAR CALIBRACIÓN POR LIGA
                        calibrated_predictions = []
                        for pred in predictions:
                            calibrated_value = league_calibration.calibrate_prediction(
                                pred['prediction'], pred_type, league.name
                            )
                            
                            # Crear nueva predicción calibrada
                            calibrated_pred = {
                                'model_name': pred['model_name'],
                                'prediction': calibrated_value,
                                'confidence': pred['confidence'],
                                'probabilities': pred['probabilities'],
                                'total_matches': pred['total_matches']
                            }
                            calibrated_predictions.append(calibrated_pred)
                        
                        # USAR MODELO MEJORADO PARA AMBOS MARCAN
                        if pred_type == 'both_teams_score':
                            # Usar modelo mejorado que no requiere entrenamiento
                            enhanced_prob = enhanced_both_teams_score_model.predict(home_team, away_team, league)
                            
                            # Crear predicción con modelo mejorado
                            enhanced_prediction = {
                                'model_name': "Enhanced Both Teams Score",
                                'prediction': enhanced_prob,
                                'confidence': 0.80,  # Alta confianza para modelo mejorado
                                'probabilities': {'both_score': enhanced_prob},
                                'total_matches': 100  # Modelo robusto con múltiples enfoques
                            }
                            calibrated_predictions.append(enhanced_prediction)
                        
                        # Las predicciones ya están en formato diccionario
                        predictions_dict = calibrated_predictions
                        
                        all_predictions_by_type[pred_type] = predictions_dict
                        logger.info(f"✅ {pred_type}: {len(predictions_dict)} modelos generados (calibrados)")
                        
                    except Exception as e:
                        logger.error(f"❌ ERROR EN {pred_type}: {e}")
                        logger.error(f"❌ TRACEBACK:", exc_info=True)
                        all_predictions_by_type[pred_type] = []
                
                logger.info(f"✅ BUCLE DE PREDICCIONES COMPLETADO - Total tipos procesados: {len(all_predictions_by_type)}")
                logger.info(f"✅ TIPOS PROCESADOS: {list(all_predictions_by_type.keys())}")
                
                # AGREGAR PREDICCIÓN OFICIAL (después de todos los otros modelos)
                logger.info("🎯 OFICIAL - Iniciando cálculo de predicción oficial")
                try:
                    from .official_prediction_model import official_prediction_model
                    all_predictions_by_type = official_prediction_model.add_to_predictions(
                        all_predictions_by_type, home_team=home_team, away_team=away_team, league=league)
                    logger.info("🎯 OFICIAL - Predicción oficial agregada exitosamente")
                except Exception as e:
                    logger.error(f"❌ OFICIAL - Error agregando predicción oficial: {e}")
                    logger.error(f"❌ OFICIAL - Traceback:", exc_info=True)
                    # Continuar aunque falle la predicción oficial
                
                logger.info(f"📊 TOTAL PREDICCIONES GENERADAS: {len(all_predictions_by_type)} tipos")
                logger.info(f"📊 TIPOS DE PREDICCIÓN: {list(all_predictions_by_type.keys())}")
                
                # Guardar resultados persistidos para evitar pérdida en sesiones multi-worker
                logger.info("💾 INICIANDO GUARDADO EN BD - Convirtiendo numpy a nativo")
                try:
                    prediction_payload = convert_numpy_to_native(all_predictions_by_type)
                    logger.info(f"💾 CONVERSIÓN EXITOSA - Tipos de predicción: {len(prediction_payload)}")
                    
                    logger.info(f"💾 CREANDO SavedPrediction - Home: '{home_team}' vs Away: '{away_team}'")
                    saved_prediction = SavedPrediction.objects.create(
                        user=request.user if request.user.is_authenticated else None,
                        home_team=home_team,
                        away_team=away_team,
                        league=league,
                        all_predictions=prediction_payload,
                        metadata={
                            'generated_at': timezone.now().isoformat(),
                            'prediction_types': list(prediction_payload.keys()),
                        }
                    )
                    logger.info(f"✅ PREDICCIÓN GUARDADA EN BD - ID: {saved_prediction.id}")
                    
                    # Guardar resultados en sesión (compatibilidad)
                    logger.info("💾 GUARDANDO EN SESIÓN - Compatibilidad")
                    request.session['last_prediction'] = {
                        'home_team': home_team,
                        'away_team': away_team,
                        'league': league.name,
                        'all_predictions': prediction_payload,
                        'saved_prediction_id': str(saved_prediction.id),
                    }
                    request.session.modified = True
                    request.session.save()
                    logger.info(f"✅ SESIÓN GUARDADA - Session key: {request.session.session_key}")
                    
                    # Marcar progreso como completado
                    try:
                        request.session['prediction_progress'] = {
                            'current': len(prediction_types),
                            'total': len(prediction_types),
                            'current_type': 'Completado',
                            'status': 'completed'
                        }
                        request.session.modified = True
                        request.session.save()
                    except Exception as e:
                        logger.debug(f"No se pudo marcar progreso completado: {e}")
                    
                    logger.info(f"✅ PREDICCIONES COMPLETADAS - Home: '{home_team}' vs Away: '{away_team}', Liga: {league.name}")
                    logger.info(f"📝 DATOS GUARDADOS - Total de tipos: {len(all_predictions_by_type)}")
                    logger.info(f"🔗 REDIRIGIENDO A: /ai/predict/result/{saved_prediction.id}/")
                    
                    # Redirigir directamente a resultados persistidos
                    return redirect('ai_predictions:prediction_result_with_id', prediction_id=saved_prediction.id)
                    
                except Exception as e:
                    logger.error(f"❌ ERROR GUARDANDO PREDICCIÓN EN BD: {e}")
                    logger.error(f"❌ TRACEBACK:", exc_info=True)
                    # Continuar con sesión como fallback
                    request.session['last_prediction'] = {
                        'home_team': home_team,
                        'away_team': away_team,
                        'league': league.name,
                        'all_predictions': convert_numpy_to_native(all_predictions_by_type),
                    }
                    request.session.modified = True
                    request.session.save()
                    logger.info("⚠️ USANDO SESIÓN COMO FALLBACK - Redirigiendo sin ID")
                    return redirect('ai_predictions:prediction_result')
                
            except Exception as e:
                logger.error(f"Error en predicción: {e}")
                return JsonResponse({
                    'status': 'error',
                    'message': str(e)
                }, status=500)
        else:
            logger.error(f"Formulario inválido: {form.errors}")
            return JsonResponse({
                'status': 'error',
                'message': 'Formulario inválido',
                'errors': form.errors
            }, status=400)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class PredictionResultView(View):
    """Vista para mostrar resultados de predicción"""
    
    def get(self, request, prediction_id=None):
        logger.info("🎯 INICIANDO PredictionResultView.get()")
        logger.info(f"🎯 REQUEST PATH: {request.path}")
        logger.info(f"🎯 REQUEST METHOD: {request.method}")
        logger.info(f"🎯 SESSION KEY: {request.session.session_key}")

        prediction_payload = None

        if prediction_id:
            saved_prediction = get_object_or_404(SavedPrediction, id=prediction_id)
            if saved_prediction.user and saved_prediction.user != request.user and not request.user.is_staff:
                messages.error(request, "No tienes permiso para ver esta predicción.")
                return redirect('ai_predictions:prediction_form')

            prediction_payload = {
                'home_team': saved_prediction.home_team,
                'away_team': saved_prediction.away_team,
                'league': saved_prediction.league.name,
                'all_predictions': saved_prediction.all_predictions,
                'saved_prediction_id': str(saved_prediction.id),
                'created_at': saved_prediction.created_at.isoformat(),
            }
            logger.info(f"🎯 PREDICCIÓN PERSISTIDA OBTENIDA: {saved_prediction.id}")
        else:
            prediction_payload = request.session.get('last_prediction')
            logger.info(f"🎯 SESIÓN OBTENIDA: {prediction_payload is not None}")

        if not prediction_payload:
            logger.info("🎯 REDIRIGIENDO: No hay predicciones en sesión")
            messages.info(request, "No hay predicciones recientes.")
            return redirect('ai_predictions:prediction_form')

        # Log para verificar qué equipos se están mostrando
        logger.info(f"📊 MOSTRANDO RESULTADOS - Home: '{prediction_payload.get('home_team')}' vs Away: '{prediction_payload.get('away_team')}', Liga: {prediction_payload.get('league')}")
        
        # Log detallado de la estructura de la predicción
        logger.info(f"🔍 ESTRUCTURA DE PREDICCIÓN: {list(prediction_payload.keys())}")
        if 'all_predictions' in prediction_payload:
            logger.info(f"🔍 TIPOS DE PREDICCIÓN: {list(prediction_payload['all_predictions'].keys())}")
            logger.info(f"🔍 TOTAL TIPOS: {len(prediction_payload['all_predictions'])}")
        else:
            logger.error("❌ ERROR: 'all_predictions' no existe en la sesión")
        
        # Verificar que la predicción esté completa
        if 'all_predictions' not in prediction_payload or not prediction_payload['all_predictions']:
            logger.error("❌ ERROR: Predicción incompleta - faltan datos")
            logger.error(f"❌ ESTRUCTURA COMPLETA: {prediction_payload}")
            messages.error(request, "Error: La predicción no se completó correctamente. Por favor, intenta nuevamente.")
            return redirect('ai_predictions:prediction_form')
        
        # Obtener todos los nombres de modelos únicos
        model_names = set()
        total_models = 0
        if 'all_predictions' in prediction_payload:
            for pred_type, predictions in prediction_payload['all_predictions'].items():
                total_models += len(predictions)
                pred_model_names = [pred['model_name'] for pred in predictions]
                logger.info(f"Tipo {pred_type}: {len(predictions)} modelos - {pred_model_names}")
                for pred in predictions:
                    model_names.add(pred['model_name'])
        
        model_names = sorted(list(model_names))
        
        # Log para debugging
        logger.info(f"Modelos únicos encontrados: {model_names}")
        logger.info(f"Total de modelos generados: {total_models}")
        logger.info(f"Tipos de predicción: {list(prediction_payload.get('all_predictions', {}).keys())}")
        
        # Verificación de que tenemos 3 modelos únicos
        if len(model_names) < 3:
            logger.warning(f"Solo se encontraron {len(model_names)} modelos únicos, esperados 3")
            logger.warning(f"Modelos encontrados: {model_names}")
        else:
            logger.info(f"[OK] Se encontraron {len(model_names)} modelos únicos correctamente")
        
        # Calcular recomendación de corners (línea Poisson + UNDER/OVER)
        corners_recommendation = None
        try:
            if 'all_predictions' in prediction_payload:
                corners_preds = prediction_payload['all_predictions'].get('corners_total', [])
                for cp in corners_preds:
                    if cp.get('model_name') == 'Predicción Oficial':
                        total = cp.get('prediction', 0)
                        if total > 0:
                            # Encontrar la línea más cercana
                            lines = [5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5, 14.5, 15.5, 16.5, 17.5, 18.5]
                            closest = min(lines, key=lambda x: abs(x - total))
                            # Calcular Poisson
                            from scipy.stats import poisson
                            k = int(closest)
                            p_over = 1.0 - poisson.cdf(k, total)
                            p_under = 1.0 - p_over
                            # Determinar la recomendación
                            if p_over > p_under:
                                direction = 'OVER'
                                prob = p_over
                            else:
                                direction = 'UNDER'
                                prob = p_under
                            corners_recommendation = {
                                'line': closest,
                                'direction': direction,
                                'probability': round(prob * 100, 1),
                                'cuota_justa': round(1.0 / prob, 2),
                            }
                        break
        except Exception as e:
            logger.warning(f"No se pudo calcular recomendación de corners: {e}")
        
        # Verificar si la liga tiene datos de goles (para Ambos Marcan)
        has_goals_data = True
        try:
            from football_data.models import Match, League
            league_name = prediction_payload.get('league', '')
            league_obj = League.objects.filter(name=league_name).first()
            if league_obj:
                goal_matches = Match.objects.filter(league=league_obj, fthg__isnull=False).count()
                has_goals_data = goal_matches >= 10
        except Exception:
            pass
        
        # ── Mercados disponibles para registrar apuesta (mismos que Predicta) ──
        all_preds = prediction_payload.get('all_predictions', {}) or {}
        markets = build_markets_summary(all_preds)

        # Apuestas ya registradas por el usuario sobre esta predicción
        existing_apuestas = []
        saved_id = prediction_payload.get('saved_prediction_id')
        if saved_id and request.user.is_authenticated:
            existing_apuestas = Apuesta.objects.filter(
                prediction_id=saved_id, user=request.user
            ).order_by('-created_at')

        context = {
            'prediction': prediction_payload,
            'model_names': model_names,
            'corners_recommendation': corners_recommendation,
            'has_goals_data': has_goals_data,
            'markets': markets,
            'markets_json': json.dumps(markets),
            'existing_apuestas': existing_apuestas,
        }
        return render(request, 'ai_predictions/prediction_result_new.html', context)


@method_decorator(login_required, name='dispatch')
class SaveApuestaView(View):
    """Registra la apuesta seleccionada desde la página de predicción."""

    def post(self, request, prediction_id=None):
        saved_prediction = get_object_or_404(SavedPrediction, id=prediction_id)
        if saved_prediction.user and saved_prediction.user != request.user and not request.user.is_staff:
            messages.error(request, "No tienes permiso para registrar apuestas sobre esta predicción.")
            return redirect('ai_predictions:prediction_form')

        market = request.POST.get('market')
        selection = request.POST.get('selection')
        line = request.POST.get('line') or None

        valid_markets = dict(Apuesta.MARKET_CHOICES)
        if market not in valid_markets:
            messages.error(request, "Mercado inválido.")
            return redirect('ai_predictions:prediction_result_with_id', prediction_id=prediction_id)

        if market == 'both_teams_score':
            if selection not in ('si', 'no'):
                messages.error(request, "Selección inválida para Ambos Marcan.")
                return redirect('ai_predictions:prediction_result_with_id', prediction_id=prediction_id)
        else:
            if selection not in ('over', 'under'):
                messages.error(request, "Selección inválida.")
                return redirect('ai_predictions:prediction_result_with_id', prediction_id=prediction_id)

        # Valor oficial de la predicción para este mercado (snapshot)
        predicted_value = None
        all_preds = saved_prediction.all_predictions or {}
        for p in all_preds.get(market, []) or []:
            if isinstance(p, dict) and p.get('model_name') in ('Predicción Oficial', 'Predicción oficial'):
                predicted_value = p.get('prediction')
                break

        try:
            line_dec = Decimal(str(line)) if line else None
        except (InvalidOperation, ValueError):
            line_dec = None

        Apuesta.objects.create(
            user=request.user,
            prediction=saved_prediction,
            home_team=saved_prediction.home_team,
            away_team=saved_prediction.away_team,
            league_name=saved_prediction.league.name if saved_prediction.league else '',
            market=market,
            selection=selection,
            line=line_dec,
            predicted_value=predicted_value,
            status='pendiente',
        )
        messages.success(request, "Apuesta registrada correctamente.")
        return redirect('ai_predictions:prediction_result_with_id', prediction_id=prediction_id)


@method_decorator(login_required, name='dispatch')
class ResolveApuestaView(View):
    """Marca una apuesta como ganada / perdida / anulada (solo el dueño)."""

    def post(self, request, pk):
        apuesta = get_object_or_404(Apuesta, pk=pk, user=request.user)
        new_status = request.POST.get('status')
        if new_status not in dict(Apuesta.STATUS_CHOICES):
            messages.error(request, "Estado inválido.")
            return redirect('ai_predictions:mis_apuestas')

        apuesta.status = new_status
        apuesta.resolved_at = timezone.now() if new_status in ('ganada', 'perdida', 'anulada') else None
        apuesta.save()
        messages.success(request, f"Apuesta marcada como {apuesta.get_status_display().lower()}.")
        return redirect('ai_predictions:mis_apuestas')


@method_decorator(login_required, name='dispatch')
class MisApuestasView(View):
    """Historial de apuestas del usuario + métricas de desempeño."""

    template_name = 'ai_predictions/mis_apuestas.html'

    def get(self, request):
        apuestas = Apuesta.objects.filter(user=request.user).select_related('prediction').order_by('-created_at')

        status_filter = request.GET.get('estado')
        if status_filter in dict(Apuesta.STATUS_CHOICES):
            apuestas = apuestas.filter(status=status_filter)

        total = apuestas.count()
        ganadas = apuestas.filter(status='ganada').count()
        perdidas = apuestas.filter(status='perdida').count()
        pendientes = apuestas.filter(status='pendiente').count()
        anuladas = apuestas.filter(status='anulada').count()
        resueltas = ganadas + perdidas
        acierto = round((ganadas / resueltas) * 100, 1) if resueltas else 0

        racha = compute_streak(apuestas)

        by_market = []
        for key, label in Apuesta.MARKET_CHOICES:
            qs = apuestas.filter(market=key)
            m_total = qs.count()
            m_gan = qs.filter(status='ganada').count()
            m_per = qs.filter(status='perdida').count()
            m_res = m_gan + m_per
            by_market.append({
                'key': key,
                'label': label,
                'total': m_total,
                'ganadas': m_gan,
                'perdidas': m_per,
                'pendientes': qs.filter(status='pendiente').count(),
                'acierto': round((m_gan / m_res) * 100, 1) if m_res else None,
            })

        paginator = Paginator(apuestas, 25)
        page_obj = paginator.get_page(request.GET.get('page'))

        context = {
            'page_obj': page_obj,
            'total': total,
            'ganadas': ganadas,
            'perdidas': perdidas,
            'pendientes': pendientes,
            'anuladas': anuladas,
            'acierto': acierto,
            'racha': racha,
            'by_market': by_market,
            'status_choices': Apuesta.STATUS_CHOICES,
            'selected_status': status_filter or '',
        }
        return render(request, self.template_name, context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class TrainingView(View):
    """Vista para entrenar modelos"""
    
    def get(self, request):
        leagues = League.objects.all()
        
        # Usar lista vacía en lugar de consulta a modelo inexistente
        context = {
            'leagues': leagues,
            'models': [],  # Lista vacía para evitar errores de DB
        }
        return render(request, 'ai_predictions/training.html', context)
    
    def post(self, request):
        try:
            league_id = request.POST.get('league_id')
            prediction_type = request.POST.get('prediction_type', 'shots_total')
            
            league = League.objects.get(id=league_id)
            trainer = ModelTrainer()
            
            # Entrenar modelo optimizado
            train_result = trainer.train_optimized_model(league, prediction_type)
            
            if 'error' in train_result:
                messages.error(request, f"Error entrenando modelo: {train_result['error']}")
            else:
                messages.success(request, 
                    f"Modelo {train_result['model_name']} entrenado exitosamente para {league.name}. "
                    f"Score: {train_result['score']:.3f}, "
                    f"Muestras: {train_result['samples_count']}, "
                    f"Características: {train_result['features_count']}"
                )
            
        except Exception as e:
            logger.error(f"Error entrenando modelo: {e}")
            messages.error(request, f"Error entrenando modelo: {str(e)}")
        
        return redirect('ai_predictions:training')


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class GetTeamsView(View):
    """API para obtener equipos de una liga (Django + SQLite fallback)."""
    
    def get(self, request, league_id):
        try:
            league = League.objects.get(id=league_id)
            
            # Obtener equipos únicos de Django
            home_teams = Match.objects.filter(league=league).values_list('home_team', flat=True).distinct()
            away_teams = Match.objects.filter(league=league).values_list('away_team', flat=True).distinct()
            all_teams = sorted(list(set(list(home_teams) + list(away_teams))))
            logger.info(f"[TEAMS] Django teams for {league.name} (id={league.id}): {len(all_teams)}")
            
            # Si no hay equipos en Django, buscar en SQLite
            if not all_teams:
                try:
                    import sqlite3
                    # Mapear nombre Django → nombre SQLite
                    LEAGUE_MAP = {'Serie A (Brasil)': 'Serie A', 'Serie B (Brasil)': 'Serie B',
        'Primera A (Colombia)': 'Primera A', 'Primera Division (Argentina)': 'Primera Division',
        'Liga MX (Mexico)': 'Liga MX',
        'US MLS (USA)': 'US MLS'}
                    sqlite_league = LEAGUE_MAP.get(league.name, league.name)
                    conn = sqlite3.connect('/var/www/predicta.com.co/data/corners_scraped.db')
                    home = conn.execute(
                        "SELECT DISTINCT home_team FROM corners_matches WHERE league=?",
                        (sqlite_league,)
                    ).fetchall()
                    away = conn.execute(
                        "SELECT DISTINCT away_team FROM corners_matches WHERE league=?",
                        (sqlite_league,)
                    ).fetchall()
                    conn.close()
                    all_teams = sorted(set([r[0] for r in home] + [r[0] for r in away]))
                    logger.info(f"[TEAMS] SQLite teams for {sqlite_league}: {len(all_teams)}")
                except Exception as e:
                    logger.error(f"[TEAMS] SQLite fallback failed: {e}")
            
            return JsonResponse({'teams': all_teams})
            
        except League.DoesNotExist:
            return JsonResponse({'error': 'Liga no encontrada'}, status=404)
        except Exception as e:
            logger.error(f"Error obteniendo equipos: {e}")
            return JsonResponse({'error': str(e)}, status=500)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class PredictionProgressView(View):
    """API para obtener el progreso de la predicción"""
    
    def get(self, request):
        try:
            progress = request.session.get('prediction_progress', {
                'current': 0,
                'total': 11,
                'current_type': 'Iniciando...',
                'status': 'idle'
            })
            
            return JsonResponse(progress)
            
        except Exception as e:
            logger.error(f"Error obteniendo progreso: {e}")
            return JsonResponse({'error': str(e)}, status=500)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class PredictionHistoryView(View):
    """Historial de predicciones consultadas por el usuario (privadas)."""

    @method_decorator(login_required)
    def get(self, request):
        predictions = SavedPrediction.objects.filter(user=request.user).select_related('league').order_by('-created_at')

        league_filter = request.GET.get('league')
        if league_filter:
            predictions = predictions.filter(league_id=league_filter)

        paginator = Paginator(predictions, 20)
        page_obj = paginator.get_page(request.GET.get('page'))

        context = {
            'page_obj': page_obj,
            'leagues': League.objects.all(),
            'selected_league': league_filter or '',
        }
        return render(request, 'ai_predictions/prediction_history.html', context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class ModelPerformanceView(View):
    """Vista para rendimiento de modelos"""
    
    def get(self, request):
        # Usar lista vacía para evitar errores de DB
        models = []
        
        context = {
            'models': models,
        }
        return render(request, 'ai_predictions/model_performance.html', context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class QuickPredictionView(View):
    """Vista para predicción rápida con AJAX"""
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            home_team = data.get('home_team')
            away_team = data.get('away_team')
            league_id = data.get('league_id')
            prediction_type = data.get('prediction_type', 'shots_total')
            
            league = League.objects.get(id=league_id)
            
            advanced_service = AdvancedStatisticalModels()
            all_predictions = advanced_service.get_all_advanced_predictions(home_team, away_team, league, prediction_type)
            
            multi_service = MultiModelPredictionService()
            backtest_results = multi_service.backtest_models(league, prediction_type)
            
            return JsonResponse({
                'predictions': all_predictions,
                'backtest_results': backtest_results
            })
            
        except Exception as e:
            logger.error(f"Error en predicción rápida: {e}")
            return JsonResponse({'error': str(e)}, status=500)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class TestPredictionsView(View):
    """Vista de prueba para verificar predicciones avanzadas"""
    
    def get(self, request):
        try:
            league = League.objects.first()
            if not league:
                return JsonResponse({'error': 'No hay ligas disponibles'})
            
            advanced_service = AdvancedStatisticalModels()
            predictions = advanced_service.get_all_advanced_predictions('Dortmund', 'Hannover', league, 'shots_total')
            
            return JsonResponse({
                'success': True,
                'predictions': predictions,
                'count': len(predictions)
            })
            
        except Exception as e:
            logger.error(f"Error en vista de prueba: {e}")
            return JsonResponse({'error': str(e)})


# @method_decorator(login_required, name='dispatch')
@method_decorator(login_required, name='dispatch')
class LeagueHistoricalDataView(View):
    """Vista para obtener datos históricos de una liga para gráficas"""
    
    def get(self, request, league_id):
        try:
            league = League.objects.get(id=league_id)
            
            # Obtener partidos de la liga de los últimos 6 meses
            six_months_ago = datetime.now() - timedelta(days=180)
            matches = Match.objects.filter(
                league=league,
                date__gte=six_months_ago
            ).exclude(
                Q(hs__isnull=True) | Q(as_field__isnull=True) | 
                Q(fthg__isnull=True) | Q(ftag__isnull=True) |
                Q(hc__isnull=True) | Q(ac__isnull=True)
            ).order_by('date')
            
            # Agrupar datos por fecha
            daily_data = defaultdict(lambda: {
                'date': None,
                'shots_total': 0,
                'goals_total': 0,
                'corners_total': 0,
                'matches_count': 0
            })
            
            for match in matches:
                date_key = match.date.strftime('%Y-%m-%d')
                
                # Calcular totales del partido
                shots_total = (match.hs or 0) + (match.as_field or 0)
                goals_total = (match.fthg or 0) + (match.ftag or 0)
                corners_total = (match.hc or 0) + (match.ac or 0)
                
                daily_data[date_key]['date'] = date_key
                daily_data[date_key]['shots_total'] += shots_total
                daily_data[date_key]['goals_total'] += goals_total
                daily_data[date_key]['corners_total'] += corners_total
                daily_data[date_key]['matches_count'] += 1
            
            # Convertir a lista y ordenar por fecha
            chart_data = []
            for date_key in sorted(daily_data.keys()):
                data = daily_data[date_key]
                chart_data.append({
                    'date': data['date'],
                    'shots_total': data['shots_total'],
                    'goals_total': data['goals_total'],
                    'corners_total': data['corners_total'],
                    'matches_count': data['matches_count']
                })
            
            # Limitar a los últimos 60 días con datos
            chart_data = chart_data[-60:] if len(chart_data) > 60 else chart_data
            
            return JsonResponse({
                'success': True,
                'league_name': league.name,
                'data': chart_data,
                'total_days': len(chart_data),
                'date_range': {
                    'start': chart_data[0]['date'] if chart_data else None,
                    'end': chart_data[-1]['date'] if chart_data else None
                }
            })
            
        except League.DoesNotExist:
            return JsonResponse({'error': 'Liga no encontrada'}, status=404)
        except Exception as e:
            logger.error(f"Error obteniendo datos históricos: {e}")
            return JsonResponse({'error': str(e)}, status=500)


# ── SCRAPER UI ──

import subprocess, sqlite3
from django.contrib.auth.mixins import LoginRequiredMixin


class ScraperCornersView(LoginRequiredMixin, View):
    """Vista para la UI del scraper de corners."""
    def get(self, request):
        return render(request, 'ai_predictions/scraper.html')


class ScraperCornersAPIView(LoginRequiredMixin, View):
    """API endpoint para ejecutar scraping o consultar stats."""

    DB_PATH = '/var/www/predicta.com.co/data/corners_scraped.db'

    def get(self, request):
        """Devuelve estadísticas de la DB SQLite."""
        try:
            conn = sqlite3.connect(self.DB_PATH)
            conn.row_factory = sqlite3.Row
            total = conn.execute("SELECT COUNT(*) FROM corners_matches").fetchone()[0]
            teams = conn.execute("SELECT COUNT(DISTINCT home_team) FROM corners_matches").fetchone()[0]
            leagues = conn.execute(
                "SELECT league, country, COUNT(*) as n FROM corners_matches GROUP BY league, country ORDER BY n DESC"
            ).fetchall()
            conn.close()
            return JsonResponse({
                'total_matches': total,
                'total_teams': teams,
                'total_leagues': len(leagues),
                'leagues': [[l[0], l[1], l[2]] for l in leagues],
            })
        except Exception as e:
            return JsonResponse({'error': str(e), 'total_matches': 0, 'total_teams': 0, 'total_leagues': 0})

    def post(self, request):
        """Ejecuta el scraper."""
        country = request.POST.get('country', 'Brazil')
        league = request.POST.get('league', 'Serie A')
        season = request.POST.get('season', '2026')

        script = '/var/www/predicta.com.co/scripts/scrape_corners.py'
        venv_python = '/var/www/predicta.com.co/venv/bin/python3'

        try:
            result = subprocess.run(
                [venv_python, script,
                 '--country', country,
                 '--league', league,
                 '--season', season,
                 '--db', self.DB_PATH],
                capture_output=True, text=True, timeout=120
            )
            if result.returncode == 0:
                return JsonResponse({
                    'success': True,
                    'message': f'Scraping completado para {country} / {league} / {season}',
                    'output': result.stdout[-2000:],
                })
            else:
                return JsonResponse({
                    'success': False,
                    'error': result.stderr[-500:] or result.stdout[-500:],
                })
        except subprocess.TimeoutExpired:
            return JsonResponse({'success': False, 'error': 'Timeout (120s). La página tardó demasiado.'})
        except Exception as e:
            return JsonResponse({'success': False, 'error': str(e)})
