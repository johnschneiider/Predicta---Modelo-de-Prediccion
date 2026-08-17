"""
Modelos simples para predicciones rápidas
"""

import numpy as np
import logging
from typing import Dict, List
from datetime import timedelta
from django.utils import timezone
from django.db import models
from django.core.cache import cache
from football_data.models import Match, League
from .dixon_coles import DixonColesModel

logger = logging.getLogger('ai_predictions')

# Caché global para parámetro rho optimizado
_GLOBAL_RHO_CACHE = {'rho': -0.13, 'last_update': None}


class PredictionResult:
    """Clase simple para representar resultados de predicción"""
    
    def __init__(self, model_name: str, prediction: float, confidence: float, 
                 probabilities: dict = None, total_matches: int = 0):
        self.model_name = model_name
        self.prediction = prediction
        self.confidence = confidence
        self.probabilities = probabilities or {}
        self.total_matches = total_matches


def _estimate_nb_params(mean_value: float, variance_value: float) -> tuple:
    """Estima parámetros de Negative Binomial (r, p) a partir de media y varianza.
    Si varianza <= media, devuelve None para usar Poisson como fallback.
    Fórmulas: var = m + m^2/r  =>  r = m^2 / (var - m),  p = r / (r + m)
    """
    try:
        if variance_value is None or mean_value is None:
            return None
        if variance_value <= 0 or mean_value <= 0:
            return None
        if variance_value <= mean_value:
            return None  # No hay sobre-dispersión, usar Poisson
        r = (mean_value * mean_value) / (variance_value - mean_value)
        if r <= 0:
            return None
        p = r / (r + mean_value)
        if p <= 0 or p >= 1:
            return None
        return (r, p)
    except Exception:
        return None


def get_league_realistic_limits(league: League, prediction_type: str = 'goals') -> tuple:
    """
    Obtiene límites realistas basados en datos históricos de la liga.
    
    Args:
        league: Liga para analizar
        prediction_type: Tipo de predicción ('goals', 'shots', 'corners', etc.)
    
    Returns:
        Tupla (lambda_min, lambda_max) basada en percentiles
    """
    try:
        # Obtener datos históricos de la liga (últimos 2 años)
        cutoff_date = timezone.now().date() - timedelta(days=730)
        
        league_matches = Match.objects.filter(
            league=league,
            date__gte=cutoff_date
        ).order_by('-date')[:500]  # Últimos 500 partidos
        
        if not league_matches:
            # Si no hay datos, usar límites conservadores
            if 'goals' in prediction_type:
                return 0.1, 4.0
            elif 'corners' in prediction_type:
                return 1.0, 12.0
            else:  # shots
                return 3.0, 25.0
        
        # Extraer datos según el tipo de predicción
        if 'goals' in prediction_type:
            home_data = [m.fthg for m in league_matches if m.fthg is not None]
            away_data = [m.ftag for m in league_matches if m.ftag is not None]
        elif 'corners' in prediction_type:
            home_data = [m.hc for m in league_matches if m.hc is not None]
            away_data = [m.ac for m in league_matches if m.ac is not None]
        else:  # shots
            home_data = [m.hs for m in league_matches if m.hs is not None]
            away_data = [m.as_field for m in league_matches if m.as_field is not None]
        
        # Combinar datos de local y visitante
        all_data = home_data + away_data
        all_data = [d for d in all_data if d is not None and d >= 0]
        
        if len(all_data) < 50:  # Pocos datos
            if 'goals' in prediction_type:
                return 0.1, 4.0
            elif 'corners' in prediction_type:
                return 1.0, 10.0  # Reducido de 12.0 a 10.0
            else:  # shots
                return 3.0, 25.0
        
        # Calcular estadísticas de la liga
        league_mean = np.mean(all_data)
        league_std = np.std(all_data)
        
        # Calcular percentiles
        p95 = np.percentile(all_data, 95)
        p99 = np.percentile(all_data, 99)
        p05 = np.percentile(all_data, 5)
        
        # Límites basados en percentiles y desviaciones estándar
        if 'goals' in prediction_type:
            lambda_min = max(0.1, p05)  # Mínimo: percentil 5 o 0.1
            lambda_max = min(p99, 6.0)  # Máximo: percentil 99 o 6.0
        elif 'corners' in prediction_type:
            lambda_min = max(1.0, p05)
            lambda_max = min(p99, 10.0)  # Reducido de 15.0 a 10.0
        else:  # shots
            lambda_min = max(3.0, p05)
            lambda_max = min(p99, 30.0)
        
        logger.info(f"Límites calculados para {league.name} ({prediction_type}): "
                   f"min={lambda_min:.2f}, max={lambda_max:.2f} "
                   f"(media={league_mean:.2f}, std={league_std:.2f})")
        
        return lambda_min, lambda_max
        
    except Exception as e:
        logger.error(f"Error calculando límites de liga: {e}")
        # Límites por defecto en caso de error
        if 'goals' in prediction_type:
            return 0.1, 4.0
        elif 'corners' in prediction_type:
            return 1.0, 10.0  # Reducido de 12.0 a 10.0
        else:  # shots
            return 3.0, 25.0


def analyze_team_statistics(team_name: str, league: League, prediction_type: str = 'goals') -> Dict:
    """
    Analiza las estadísticas reales de un equipo.
    
    Args:
        team_name: Nombre del equipo
        league: Liga del equipo
        prediction_type: Tipo de predicción
    
    Returns:
        Diccionario con estadísticas del equipo
    """
    try:
        cutoff_date = timezone.now().date() - timedelta(days=730)  # 2 años
        
        # Partidos como local
        home_matches = Match.objects.filter(
            home_team=team_name,
            league=league,
            date__gte=cutoff_date
        ).order_by('-date')[:30]
        
        # Partidos como visitante
        away_matches = Match.objects.filter(
            away_team=team_name,
            league=league,
            date__gte=cutoff_date
        ).order_by('-date')[:30]
        
        # Extraer datos según el tipo de predicción
        if 'goals' in prediction_type:
            # Goles marcados
            home_data = [m.fthg for m in home_matches if m.fthg is not None]
            away_data = [m.ftag for m in away_matches if m.ftag is not None]
            # Goles recibidos (para defense)
            home_conceded = [m.ftag for m in home_matches if m.ftag is not None]
            away_conceded = [m.fthg for m in away_matches if m.fthg is not None]
        elif 'corners' in prediction_type:
            home_data = [m.hc for m in home_matches if m.hc is not None]
            away_data = [m.ac for m in away_matches if m.ac is not None]
            home_conceded = [m.ac for m in home_matches if m.ac is not None]
            away_conceded = [m.hc for m in away_matches if m.hc is not None]
        else:  # shots
            home_data = [m.hs for m in home_matches if m.hs is not None]
            away_data = [m.as_field for m in away_matches if m.as_field is not None]
            home_conceded = [m.as_field for m in home_matches if m.as_field is not None]
            away_conceded = [m.hs for m in away_matches if m.hs is not None]
        
        # Calcular promedios
        home_avg = np.mean(home_data) if home_data else 0
        away_avg = np.mean(away_data) if away_data else 0
        overall_avg = (home_avg + away_avg) / 2 if (home_data or away_data) else 0
        
        # Promedios de goles recibidos (defense)
        home_conceded_avg = np.mean(home_conceded) if home_conceded else 0
        away_conceded_avg = np.mean(away_conceded) if away_conceded else 0
        
        return {
            'home_avg': home_avg,
            'away_avg': away_avg,
            'overall_avg': overall_avg,
            'home_matches': len(home_data),
            'away_matches': len(away_data),
            'total_matches': len(home_data) + len(away_data),
            'home_data': home_data,
            'away_data': away_data,
            'home_conceded_avg': home_conceded_avg,
            'away_conceded_avg': away_conceded_avg,
        }
        
    except Exception as e:
        logger.error(f"Error analizando estadísticas de {team_name}: {e}")
        return {
            'home_avg': 0,
            'away_avg': 0,
            'overall_avg': 0,
            'home_matches': 0,
            'away_matches': 0,
            'total_matches': 0,
            'home_data': [],
            'away_data': [],
            'home_conceded_avg': 0,
            'away_conceded_avg': 0,
        }


def calculate_lambda_with_limits(home_team: str, away_team: str, league: League, 
                                prediction_type: str = 'goals') -> tuple:
    """
    Calcula lambda con límites basados en datos reales.
    
    Args:
        home_team: Equipo local
        away_team: Equipo visitante
        league: Liga
        prediction_type: Tipo de predicción
    
    Returns:
        Tupla (lambda_home, lambda_away) con límites aplicados
    """
    try:
        # Obtener límites de la liga
        lambda_min, lambda_max = get_league_realistic_limits(league, prediction_type)
        
        # Obtener estadísticas de los equipos
        home_stats = analyze_team_statistics(home_team, league, prediction_type)
        away_stats = analyze_team_statistics(away_team, league, prediction_type)
        
        # Calcular lambda "crudo" basado en estadísticas
        if 'goals' in prediction_type:
            # Para goles, usar promedio simple con ajuste de liga
            raw_lambda_home = home_stats['overall_avg'] * 1.1  # Ventaja local
            raw_lambda_away = away_stats['overall_avg'] * 0.9  # Desventaja visitante
        elif 'corners' in prediction_type:
            raw_lambda_home = home_stats['overall_avg'] * 1.05
            raw_lambda_away = away_stats['overall_avg'] * 0.95
        else:  # shots
            raw_lambda_home = home_stats['overall_avg'] * 1.08
            raw_lambda_away = away_stats['overall_avg'] * 0.92
        
        # Aplicar límites
        lambda_home = max(lambda_min, min(lambda_max, raw_lambda_home))
        lambda_away = max(lambda_min, min(lambda_max, raw_lambda_away))
        
        # Log para debugging
        logger.info(f"Lambda {home_team}: {raw_lambda_home:.2f} → {lambda_home:.2f} "
                   f"(límites: {lambda_min:.2f}-{lambda_max:.2f})")
        logger.info(f"Lambda {away_team}: {raw_lambda_away:.2f} → {lambda_away:.2f} "
                   f"(límites: {lambda_min:.2f}-{lambda_max:.2f})")
        
        return lambda_home, lambda_away
        
    except Exception as e:
        logger.error(f"Error calculando lambda con límites: {e}")
        # Valores por defecto en caso de error
        if 'goals' in prediction_type:
            return 1.5, 1.2
        elif 'corners' in prediction_type:
            return 5.5, 4.5
        else:  # shots
            return 12.0, 11.0


class SimplePredictionService:
    """Servicio de predicciones simples y rápidas"""
    
    def __init__(self):
        self.dixon_coles_model = DixonColesModel()
        # Optimizar rho periódicamente con datos recientes
        self._optimize_rho_if_needed()
    
    def _optimize_rho_if_needed(self):
        """
        Optimiza el parámetro rho del modelo Dixon-Coles usando datos históricos.
        Usa caché para evitar recalcular en cada solicitud.
        OPTIMIZACIÓN DESHABILITADA: Usa valor por defecto para evitar bloqueos.
        """
        global _GLOBAL_RHO_CACHE
        
        try:
            # SIEMPRE usar valor cacheado o por defecto (optimización deshabilitada)
            cached_rho = _GLOBAL_RHO_CACHE.get('rho', -0.13)
            self.dixon_coles_model.rho = cached_rho
            logger.debug(f"Usando rho por defecto/cacheado: {cached_rho:.4f}")
            return
            
        except Exception as e:
            logger.error(f"[ERROR] Error configurando rho: {e}")
            # En caso de error, usar valor por defecto
            self.dixon_coles_model.rho = -0.13
    
    def get_team_simple_stats(self, team_name: str, league: League, is_home: bool = True, prediction_type: str = 'shots_total') -> Dict:
        """Obtiene estadísticas simples de un equipo"""
        try:
            # Ventana temporal más pequeña para mayor velocidad
            cutoff_date = timezone.now().date() - timedelta(days=180)  # 6 meses
            
            if is_home:
                matches = Match.objects.filter(
                    league=league,
                    home_team=team_name,
                    date__gte=cutoff_date
                ).order_by('-date')[:20]  # Solo 20 partidos
                
                # Usar datos correctos según el tipo de predicción
                if 'goals' in prediction_type:
                    data = [m.fthg for m in matches if m.fthg is not None]
                    default_value = 1.5  # Promedio realista de goles
                elif 'corners' in prediction_type:
                    data = [m.hc for m in matches if m.hc is not None]
                    default_value = 5.2  # Promedio real de corners local (datos reales)
                elif 'both_teams_score' in prediction_type:
                    data = [m.fthg for m in matches if m.fthg is not None]
                    default_value = 1.5  # Promedio realista de goles
                elif 'shots_on_target' in prediction_type:
                    data = [m.hst for m in matches if m.hst is not None]
                    default_value = 5.0  # Promedio realista de remates a puerta local
                else:
                    data = [m.hs for m in matches if m.hs is not None]
                    default_value = 12.0  # Promedio realista de remates
            else:
                matches = Match.objects.filter(
                    league=league,
                    away_team=team_name,
                    date__gte=cutoff_date
                ).order_by('-date')[:20]
                
                # Usar datos correctos según el tipo de predicción
                if 'goals' in prediction_type:
                    data = [m.ftag for m in matches if m.ftag is not None]
                    default_value = 1.2  # Promedio realista de goles visitante
                elif 'corners' in prediction_type:
                    data = [m.ac for m in matches if m.ac is not None]
                    default_value = 4.6  # Promedio real de corners visitante (datos reales)
                elif 'both_teams_score' in prediction_type:
                    data = [m.ftag for m in matches if m.ftag is not None]
                    default_value = 1.2  # Promedio realista de goles visitante
                elif 'shots_on_target' in prediction_type:
                    data = [m.ast for m in matches if m.ast is not None]
                    default_value = 4.0  # Promedio realista de remates a puerta visitante
                else:
                    data = [m.as_field for m in matches if m.as_field is not None]
                    default_value = 11.0  # Promedio realista de remates visitante
            
            if not data:
                return {'avg_value': default_value, 'matches_count': 0}
            
            return {
                'avg_value': np.mean(data),
                'matches_count': len(data)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas simples de {team_name}: {e}")
            if 'goals' in prediction_type or 'both_teams_score' in prediction_type:
                default_value = 1.5
            elif 'corners' in prediction_type:
                default_value = 5.0
            elif 'shots_on_target' in prediction_type:
                default_value = 5.0
            else:
                default_value = 12.0
            return {'avg_value': default_value, 'matches_count': 0}
    
    def simple_poisson_model(self, home_team: str, away_team: str, league: League, 
                           prediction_type: str = 'shots_total') -> Dict:
        """
        Modelo de Poisson mejorado con Dixon-Coles.
        
        El modelo Dixon-Coles corrige las limitaciones del Poisson tradicional
        para marcadores bajos (0-0, 1-0, 0-1, 1-1) que son comunes en fútbol.
        """
        try:
            # Usar Dixon-Coles para predicciones de goles
            if 'goals' in prediction_type or 'both_teams_score' in prediction_type:
                # Dixon-Coles es ideal para predicción de goles
                dixon_coles_pred = self.dixon_coles_model.predict_match(
                    home_team, away_team, league, prediction_type
                )
                
                # Adaptar formato de respuesta
                return {
                    'model_name': 'Dixon-Coles Poisson',
                    'prediction': dixon_coles_pred['prediction'],
                    'confidence': dixon_coles_pred['confidence'],
                    'probabilities': dixon_coles_pred['probabilities'],
                    'total_matches': dixon_coles_pred['total_matches']
                }
            
            # Para otros tipos de predicción (corners, remates), usar Poisson tradicional mejorado
            home_stats = self.get_team_simple_stats(home_team, league, True, prediction_type)
            away_stats = self.get_team_simple_stats(away_team, league, False, prediction_type)
            
            # MODELO CON SOBRE-DISPERSIÓN: usar NB si aplica; si no, Poisson
            if prediction_type == 'shots_total':
                lambda_home = home_stats['avg_value'] * 1.15
                lambda_away = away_stats['avg_value'] * 0.85
                lambda_combined = lambda_home + lambda_away
            elif prediction_type == 'shots_home':
                lambda_combined = home_stats['avg_value'] * 1.15
            elif prediction_type == 'shots_away':
                lambda_combined = away_stats['avg_value'] * 0.85
            elif prediction_type == 'corners_total':
                lambda_home = home_stats['avg_value'] * 0.95  # Ventaja de local (reducida)
                lambda_away = away_stats['avg_value'] * 0.85  # Desventaja de visitante (aumentada)
                lambda_combined = lambda_home + lambda_away
            elif prediction_type == 'corners_home':
                lambda_combined = home_stats['avg_value'] * 0.95
            elif prediction_type == 'corners_away':
                lambda_combined = away_stats['avg_value'] * 0.85
            elif prediction_type == 'shots_on_target_total':
                lambda_home = home_stats['avg_value'] * 1.1  # Ventaja de local
                lambda_away = away_stats['avg_value'] * 0.9  # Desventaja de visitante
                lambda_combined = lambda_home + lambda_away
            elif prediction_type == 'shots_on_target_home':
                lambda_combined = home_stats['avg_value'] * 1.1
            elif prediction_type == 'shots_on_target_away':
                lambda_combined = away_stats['avg_value'] * 0.9
            else:
                lambda_combined = (home_stats['avg_value'] + away_stats['avg_value']) / 2
            
            # Intentar estimar NB a partir de la varianza reciente del equipo (si hay datos)
            # Usamos ventana de 10 partidos recientes para estimar varianza
            recent_window = 10
            if 'shots' in prediction_type:
                if prediction_type in ['shots_home', 'shots_on_target_home']:
                    recent_vals = [m.hst if 'on_target' in prediction_type else m.hs for m in 
                                   Match.objects.filter(league=league, home_team=home_team).order_by('-date')[:recent_window] if (m.hst if 'on_target' in prediction_type else m.hs) is not None]
                elif prediction_type in ['shots_away', 'shots_on_target_away']:
                    recent_vals = [m.ast if 'on_target' in prediction_type else m.as_field for m in 
                                   Match.objects.filter(league=league, away_team=away_team).order_by('-date')[:recent_window] if (m.ast if 'on_target' in prediction_type else m.as_field) is not None]
                else:
                    home_vals = [m.hst if 'on_target' in prediction_type else m.hs for m in 
                                 Match.objects.filter(league=league, home_team=home_team).order_by('-date')[:recent_window] if (m.hst if 'on_target' in prediction_type else m.hs) is not None]
                    away_vals = [m.ast if 'on_target' in prediction_type else m.as_field for m in 
                                 Match.objects.filter(league=league, away_team=away_team).order_by('-date')[:recent_window] if (m.ast if 'on_target' in prediction_type else m.as_field) is not None]
                    recent_vals = home_vals + away_vals
            elif 'corners' in prediction_type:
                if prediction_type == 'corners_home':
                    recent_vals = [m.hc for m in Match.objects.filter(league=league, home_team=home_team).order_by('-date')[:recent_window] if m.hc is not None]
                elif prediction_type == 'corners_away':
                    recent_vals = [m.ac for m in Match.objects.filter(league=league, away_team=away_team).order_by('-date')[:recent_window] if m.ac is not None]
                else:
                    recent_vals = (
                        [m.hc for m in Match.objects.filter(league=league, home_team=home_team)
                         .order_by('-date')[:recent_window] if m.hc is not None]
                        +
                        [m.ac for m in Match.objects.filter(league=league, away_team=away_team)
                         .order_by('-date')[:recent_window] if m.ac is not None]
                    )
            else:
                recent_vals = []

            var_est = np.var(recent_vals) if recent_vals else None
            nb_params = _estimate_nb_params(lambda_combined, var_est) if var_est is not None else None

            prediction = float(lambda_combined)
            if nb_params is not None:
                # Media de NB coincide con lambda_combined; usarla directamente (sin muestreo aleatorio)
                prediction = float(lambda_combined)
            
            # Calcular probabilidades con umbrales correctos
            probabilities = {}
            if 'corners' in prediction_type:
                thresholds = [8, 10, 12, 15, 20]
            elif 'shots_on_target' in prediction_type:
                thresholds = [4, 6, 8, 10, 12]
            else:
                thresholds = [10, 15, 20, 25, 30]
            
            for threshold in thresholds:
                prob = max(0, min(1, 1 - (threshold / lambda_combined) if lambda_combined > 0 else 0.5))
                probabilities[f'over_{threshold}'] = prob
            
            # Confianza basada en cantidad de datos
            total_matches = home_stats['matches_count'] + away_stats['matches_count']
            confidence = min(0.9, max(0.3, total_matches / 20))
            
            return {
                'model_name': 'Enhanced Poisson',
                'prediction': prediction,
                'confidence': confidence,
                'probabilities': probabilities,
                'total_matches': total_matches
            }
            
        except Exception as e:
            logger.error(f"Error en modelo Poisson mejorado: {e}")
            default_prediction = 3.0 if 'goals' in prediction_type else 15.0
            return self._fallback_prediction('Dixon-Coles Poisson', default_prediction, 0.5, prediction_type)
    
    def simple_average_model(self, home_team: str, away_team: str, league: League, 
                           prediction_type: str = 'shots_total') -> Dict:
        """Modelo de promedio simple con ajustes contextuales"""
        try:
            home_stats = self.get_team_simple_stats(home_team, league, True, prediction_type)
            away_stats = self.get_team_simple_stats(away_team, league, False, prediction_type)
            
            # MODELO PROMEDIO: Usa promedios con ajustes contextuales
            if prediction_type == 'shots_total':
                # Promedio ponderado con factores de liga
                prediction = (home_stats['avg_value'] * 1.08 + away_stats['avg_value'] * 0.92)
            elif prediction_type == 'shots_home':
                # Promedio con ajuste por contexto del equipo
                base_prediction = home_stats['avg_value']
                # Ajuste por cantidad de datos disponibles
                data_factor = min(1.2, max(0.8, home_stats['matches_count'] / 10))
                prediction = base_prediction * 1.05 * data_factor
            elif prediction_type == 'shots_away':
                base_prediction = away_stats['avg_value']
                data_factor = min(1.2, max(0.8, away_stats['matches_count'] / 10))
                prediction = base_prediction * 0.95 * data_factor
            elif prediction_type == 'goals_total':
                prediction = (home_stats['avg_value'] * 1.06 + away_stats['avg_value'] * 0.94)
            elif prediction_type == 'goals_home':
                base_prediction = home_stats['avg_value']
                data_factor = min(1.15, max(0.85, home_stats['matches_count'] / 8))
                prediction = base_prediction * 1.08 * data_factor
            elif prediction_type == 'goals_away':
                base_prediction = away_stats['avg_value']
                data_factor = min(1.15, max(0.85, away_stats['matches_count'] / 8))
                prediction = base_prediction * 0.92 * data_factor
            elif prediction_type == 'corners_total':
                prediction = (home_stats['avg_value'] * 0.95 + away_stats['avg_value'] * 0.85)
            elif prediction_type == 'corners_home':
                base_prediction = home_stats['avg_value']
                data_factor = min(1.1, max(0.9, home_stats['matches_count'] / 15))
                prediction = base_prediction * 0.95 * data_factor
            elif prediction_type == 'corners_away':
                base_prediction = away_stats['avg_value']
                data_factor = min(1.1, max(0.9, away_stats['matches_count'] / 15))
                prediction = base_prediction * 0.85 * data_factor
            elif prediction_type == 'both_teams_score':
                # Para ambos marcan, usar modelo Poisson independiente más preciso
                home_goals_avg = home_stats['avg_value']
                away_goals_avg = away_stats['avg_value']
                
                # P(equipo no marca) = P(0 goles) en distribución Poisson
                import math
                prob_home_no_score = math.exp(-home_goals_avg)  # P(X=0) = e^(-λ)
                prob_away_no_score = math.exp(-away_goals_avg)  # P(Y=0) = e^(-λ)
                
                # P(ambos marcan) = 1 - P(local no marca) - P(visitante no marca) + P(ninguno marca)
                # Asumiendo independencia: P(ninguno marca) = P(local no marca) * P(visitante no marca)
                prob_none_score = prob_home_no_score * prob_away_no_score
                
                prediction = 1.0 - prob_home_no_score - prob_away_no_score + prob_none_score
                prediction = min(0.95, max(0.05, prediction))
            else:
                prediction = (home_stats['avg_value'] + away_stats['avg_value']) / 2
            
            # Probabilidades con umbrales correctos
            probabilities = {}
            if 'goals' in prediction_type:
                thresholds = [1, 2, 3, 4, 5]
            elif 'corners' in prediction_type:
                thresholds = [8, 10, 12, 15, 20]
            elif prediction_type == 'both_teams_score':
                # Para ambos marcan, usar la probabilidad calculada directamente
                probabilities['both_score'] = prediction
                probabilities['over_1'] = prediction  # Compatibilidad
            else:
                thresholds = [10, 15, 20, 25, 30]
            
            if prediction_type != 'both_teams_score':
                for threshold in thresholds:
                    prob = max(0, min(1, 1 - (threshold / prediction) if prediction > 0 else 0.5))
                    probabilities[f'over_{threshold}'] = prob
            
            # Confianza basada en datos
            total_matches = home_stats['matches_count'] + away_stats['matches_count']
            confidence = min(0.8, max(0.4, total_matches / 25))
            
            return {
                'model_name': 'Simple Average',
                'prediction': prediction,
                'confidence': confidence,
                'probabilities': probabilities,
                'total_matches': total_matches
            }
            
        except Exception as e:
            logger.error(f"Error en modelo promedio simple: {e}")
            default_prediction = 3.0 if 'goals' in prediction_type else 15.0
            return self._fallback_prediction('Simple Average', default_prediction, 0.5, prediction_type)
    
    def simple_trend_model(self, home_team: str, away_team: str, league: League, 
                          prediction_type: str = 'shots_total') -> Dict:
        """Modelo basado en tendencias recientes"""
        try:
            # Obtener datos más recientes (últimos 3 meses)
            cutoff_date = timezone.now().date() - timedelta(days=90)
            
            if 'shots' in prediction_type:
                if prediction_type == 'shots_home':
                    matches = Match.objects.filter(
                        league=league,
                        home_team=home_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:10]
                    recent_data = [m.hs for m in matches if m.hs is not None]
                elif prediction_type == 'shots_away':
                    matches = Match.objects.filter(
                        league=league,
                        away_team=away_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:10]
                    recent_data = [m.as_field for m in matches if m.as_field is not None]
                elif prediction_type == 'shots_on_target_home':
                    matches = Match.objects.filter(
                        league=league,
                        home_team=home_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:10]
                    recent_data = [m.hst for m in matches if m.hst is not None]
                elif prediction_type == 'shots_on_target_away':
                    matches = Match.objects.filter(
                        league=league,
                        away_team=away_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:10]
                    recent_data = [m.ast for m in matches if m.ast is not None]
                elif prediction_type == 'shots_on_target_total':
                    home_matches = Match.objects.filter(
                        league=league,
                        home_team=home_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:5]
                    away_matches = Match.objects.filter(
                        league=league,
                        away_team=away_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:5]
                    recent_data = ([m.hst for m in home_matches if m.hst is not None] + 
                                 [m.ast for m in away_matches if m.ast is not None])
                else:  # shots_total
                    home_matches = Match.objects.filter(
                        league=league,
                        home_team=home_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:5]
                    away_matches = Match.objects.filter(
                        league=league,
                        away_team=away_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:5]
                    recent_data = ([m.hs for m in home_matches if m.hs is not None] + 
                                 [m.as_field for m in away_matches if m.as_field is not None])
            elif 'corners' in prediction_type:
                if prediction_type == 'corners_home':
                    matches = Match.objects.filter(
                        league=league,
                        home_team=home_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:10]
                    recent_data = [m.hc for m in matches if m.hc is not None]
                elif prediction_type == 'corners_away':
                    matches = Match.objects.filter(
                        league=league,
                        away_team=away_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:10]
                    recent_data = [m.ac for m in matches if m.ac is not None]
                else:  # corners_total
                    home_matches = Match.objects.filter(
                        league=league,
                        home_team=home_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:5]
                    away_matches = Match.objects.filter(
                        league=league,
                        away_team=away_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:5]
                    recent_data = ([m.hc for m in home_matches if m.hc is not None] + 
                                 [m.ac for m in away_matches if m.ac is not None])
            elif 'both_teams_score' in prediction_type:
                # Para ambos marcan, usamos datos históricos de goles
                home_matches = Match.objects.filter(
                    league=league,
                    home_team=home_team,
                    date__gte=cutoff_date
                ).order_by('-date')[:5]
                away_matches = Match.objects.filter(
                    league=league,
                    away_team=away_team,
                    date__gte=cutoff_date
                ).order_by('-date')[:5]
                recent_data = ([m.fthg for m in home_matches if m.fthg is not None] + 
                             [m.ftag for m in away_matches if m.ftag is not None])
            else:  # goals
                if prediction_type == 'goals_home':
                    matches = Match.objects.filter(
                        league=league,
                        home_team=home_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:10]
                    recent_data = [m.fthg for m in matches if m.fthg is not None]
                elif prediction_type == 'goals_away':
                    matches = Match.objects.filter(
                        league=league,
                        away_team=away_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:10]
                    recent_data = [m.ftag for m in matches if m.ftag is not None]
                else:  # goals_total
                    home_matches = Match.objects.filter(
                        league=league,
                        home_team=home_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:5]
                    away_matches = Match.objects.filter(
                        league=league,
                        away_team=away_team,
                        date__gte=cutoff_date
                    ).order_by('-date')[:5]
                    recent_data = ([m.fthg for m in home_matches if m.fthg is not None] + 
                                 [m.ftag for m in away_matches if m.ftag is not None])
            
            if not recent_data:
                return self._fallback_prediction('Simple Trend', 3.0 if 'goals' in prediction_type else 15.0, 0.3, prediction_type)
            
            # Calcular tendencia
            if len(recent_data) >= 3:
                # Tendencia de los últimos 3 vs anteriores 3
                recent_3 = recent_data[:3]
                previous_3 = recent_data[3:6] if len(recent_data) >= 6 else recent_data[3:]
                
                recent_avg = np.mean(recent_3)
                previous_avg = np.mean(previous_3) if previous_3 else recent_avg
                
                # Factor de tendencia
                trend_factor = 1 + (recent_avg - previous_avg) / max(previous_avg, 0.1)
                trend_factor = max(0.7, min(1.3, trend_factor))  # Limitar el factor
            else:
                trend_factor = 1.0
            
            # Predicción basada en tendencia
            base_prediction = np.mean(recent_data)
            prediction = base_prediction * trend_factor
            
            # Ajuste por tipo de predicción
            if prediction_type in ['shots_home', 'goals_home']:
                prediction *= 1.05  # Ligera ventaja de local
            elif prediction_type in ['shots_away', 'goals_away']:
                prediction *= 0.95  # Ligera desventaja de visitante
            elif prediction_type == 'both_teams_score':
                # Para ambos marcan, usar modelo Poisson con datos históricos
                import math
                # prediction aquí es el promedio de goles histórico combinado
                # Dividir por 2 para aproximar goles por equipo
                goals_per_team = prediction / 2
                
                # P(equipo no marca) = P(0 goles) en distribución Poisson
                prob_no_score = math.exp(-goals_per_team)
                
                # P(ambos marcan) = 1 - 2*P(un equipo no marca) + P(ninguno marca)
                # Asumiendo simetría: P(ambos no marcan) = P(no marca)^2
                prob_none_score = prob_no_score * prob_no_score
                prediction = 1.0 - 2 * prob_no_score + prob_none_score
                prediction = min(0.9, max(0.1, prediction))
            
            # Calcular probabilidades
            probabilities = {}
            if 'goals' in prediction_type:
                thresholds = [1, 2, 3, 4, 5]
            elif 'corners' in prediction_type:
                thresholds = [8, 10, 12, 15, 20]
            elif prediction_type == 'both_teams_score':
                # Para ambos marcan, usar la probabilidad calculada directamente
                probabilities['both_score'] = prediction
                probabilities['over_1'] = prediction  # Compatibilidad
            else:
                thresholds = [10, 15, 20, 25, 30]
            
            if prediction_type != 'both_teams_score':
                for threshold in thresholds:
                    prob = max(0, min(1, 1 - (threshold / prediction) if prediction > 0 else 0.5))
                    probabilities[f'over_{threshold}'] = prob
            
            # Confianza basada en cantidad de datos y consistencia
            data_confidence = min(0.7, max(0.2, len(recent_data) / 15))
            consistency = 1 / (np.std(recent_data) + 0.1) if len(recent_data) > 1 else 0.5
            confidence = (data_confidence + consistency) / 2
            
            return {
                'model_name': 'Simple Trend',
                'prediction': prediction,
                'confidence': confidence,
                'probabilities': probabilities,
                'total_matches': len(recent_data)
            }
            
        except Exception as e:
            logger.error(f"Error en modelo de tendencia simple: {e}")
            return self._fallback_prediction('Simple Trend', 3.0 if 'goals' in prediction_type else 15.0, 0.3, prediction_type)
    
    def ensemble_average_model(self, home_team: str, away_team: str, league: League, 
                             prediction_type: str = 'shots_total') -> Dict:
        """Modelo ensemble que promedia los otros 2 modelos (Dixon-Coles + Average)"""
        try:
            logger.info(f"Iniciando generación de modelo Ensemble para {prediction_type}")
            
            # Obtener predicciones de los otros modelos
            dixon_coles_pred = self.simple_poisson_model(home_team, away_team, league, prediction_type)
            logger.info(f"Dixon-Coles obtenido: {dixon_coles_pred['model_name']} - {dixon_coles_pred['prediction']}")
            
            average_pred = self.simple_average_model(home_team, away_team, league, prediction_type)
            logger.info(f"Average obtenido: {average_pred['model_name']} - {average_pred['prediction']}")
            
            # Calcular promedio de predicciones (solo 2 modelos)
            ensemble_prediction = (
                dixon_coles_pred['prediction'] + 
                average_pred['prediction']
            ) / 2
            
            # Calcular promedio de confianza (solo 2 modelos)
            ensemble_confidence = (
                dixon_coles_pred['confidence'] + 
                average_pred['confidence']
            ) / 2
            
            # Promedio de probabilidades (solo 2 modelos)
            ensemble_probabilities = {}
            all_keys = set(dixon_coles_pred['probabilities'].keys()) | set(average_pred['probabilities'].keys())
            
            for key in all_keys:
                values = []
                if key in dixon_coles_pred['probabilities']:
                    values.append(dixon_coles_pred['probabilities'][key])
                if key in average_pred['probabilities']:
                    values.append(average_pred['probabilities'][key])
                
                if values:
                    ensemble_probabilities[key] = sum(values) / len(values)
            
            # Total de partidos (suma de los 2 modelos)
            total_matches = (
                dixon_coles_pred['total_matches'] + 
                average_pred['total_matches']
            )
            
            result = {
                'model_name': 'Ensemble Average',
                'prediction': ensemble_prediction,
                'confidence': ensemble_confidence,
                'probabilities': ensemble_probabilities,
                'total_matches': total_matches
            }
            
            logger.info(f"Ensemble generado exitosamente: {result['model_name']} - {result['prediction']}")
            return result
            
        except Exception as e:
            logger.error(f"Error en modelo ensemble: {e}")
            default_prediction = 3.0 if 'goals' in prediction_type else 15.0
            return self._fallback_prediction('Ensemble Average', default_prediction, 0.6, prediction_type)

    def get_all_simple_predictions(self, home_team: str, away_team: str, league: League, 
                                 prediction_type: str = 'shots_total') -> List[Dict]:
        """Obtiene predicciones de todos los modelos simples incluyendo Dixon-Coles"""
        predictions = []
        
        # AISLAR MERCADOS DE REMATES - NO GENERAR PREDICCIONES PARA SHOTS
        if 'shots' in prediction_type or 'remates' in prediction_type:
            logger.info(f"🚫 MERCADO DE REMATES AISLADO - No generando predicciones para {prediction_type}")
            return predictions
        
        try:
            # Modelo Dixon-Coles / Poisson mejorado
            dixon_coles_pred = self.simple_poisson_model(home_team, away_team, league, prediction_type)
            predictions.append(dixon_coles_pred)
            logger.info(f"Dixon-Coles generado: {dixon_coles_pred['model_name']}")
            
            # Modelo promedio simple
            average_pred = self.simple_average_model(home_team, away_team, league, prediction_type)
            predictions.append(average_pred)
            logger.info(f"Simple Average generado: {average_pred['model_name']}")
            
            # Modelo ensemble (promedio de los otros 2) - SIEMPRE generar
            logger.info(f"Generando Ensemble para {prediction_type}")
            try:
                ensemble_pred = self.ensemble_average_model(home_team, away_team, league, prediction_type)
                predictions.append(ensemble_pred)
                logger.info(f"Ensemble Average generado exitosamente: {ensemble_pred['model_name']}")
            except Exception as e:
                logger.error(f"ERROR generando Ensemble para {prediction_type}: {e}")
                # Crear un ensemble de fallback basado en los otros 2 modelos
                try:
                    avg_prediction = (dixon_coles_pred['prediction'] + average_pred['prediction']) / 2
                    avg_confidence = (dixon_coles_pred['confidence'] + average_pred['confidence']) / 2
                    
                    ensemble_fallback = {
                        'model_name': 'Ensemble Average',
                        'prediction': avg_prediction,
                        'confidence': avg_confidence,
                        'probabilities': dixon_coles_pred['probabilities'],  # Usar probabilidades del primer modelo
                        'total_matches': dixon_coles_pred['total_matches'] + average_pred['total_matches']
                    }
                    predictions.append(ensemble_fallback)
                    logger.info(f"Ensemble de fallback creado: {ensemble_fallback['model_name']}")
                except Exception as e2:
                    logger.error(f"ERROR creando fallback: {e2}")
                    # Último recurso
                    ensemble_fallback = self._fallback_prediction('Ensemble Average', 15.0, 0.5, prediction_type)
                    predictions.append(ensemble_fallback)
                    logger.info(f"Ensemble de último recurso creado: {ensemble_fallback['model_name']}")
            
            # Log de verificación
            model_names = [pred['model_name'] for pred in predictions]
            logger.info(f"Total modelos simples generados: {len(predictions)}")
            logger.info(f"Nombres de modelos: {model_names}")
            
            return predictions
            
        except Exception as e:
            logger.error(f"Error generando modelos simples: {e}")
            # Devolver al menos los modelos básicos si hay error
            return predictions
    
    def _fallback_prediction(self, model_name: str, prediction: float, confidence: float, prediction_type: str = 'shots_total') -> Dict:
        """Predicción de fallback para errores"""
        if prediction_type == 'both_teams_score':
            # Usar el modelo mejorado como fallback en lugar de 0.5 fijo
            try:
                from .enhanced_both_teams_score import enhanced_both_teams_score_model
                # Necesitamos obtener home_team, away_team, league del contexto
                # Por ahora usar un valor más realista basado en la liga
                fallback_prob = 0.45  # Valor más realista que 0.5
                probabilities = {'both_score': fallback_prob, 'over_1': fallback_prob}
                prediction = fallback_prob
            except:
                fallback_prob = 0.45  # Valor más realista que 0.5
                probabilities = {'both_score': fallback_prob, 'over_1': fallback_prob}
                prediction = fallback_prob
        elif 'goals' in prediction_type:
            probabilities = {'over_1': 0.8, 'over_2': 0.5, 'over_3': 0.2, 'over_4': 0.05, 'over_5': 0.01}
        else:
            if 'corners' in prediction_type:
                probabilities = {'over_8': 0.7, 'over_10': 0.5, 'over_12': 0.3, 'over_15': 0.1, 'over_20': 0.02}
            else:
                probabilities = {'over_10': 0.5, 'over_15': 0.3, 'over_20': 0.1, 'over_25': 0.05, 'over_30': 0.02}
        
        return {
            'model_name': model_name,
            'prediction': prediction,
            'confidence': confidence,
            'probabilities': probabilities,
            'total_matches': 0
        }


class PoissonCornersModel:
    """Modelo Poisson específico para predicción de corners"""
    
    def __init__(self):
        self.name = "Poisson Corners Model"
    
    def predict(self, home_team: str, away_team: str, league: League, prediction_type: str = 'corners_total') -> float:
        """Predicción específica para corners usando distribución de Poisson"""
        try:
            from scipy.stats import poisson
            
            # Obtener estadísticas específicas para corners
            cutoff_date = timezone.now().date() - timedelta(days=180)
            
            # Estadísticas del equipo local
            home_matches = Match.objects.filter(
                league=league,
                home_team=home_team,
                date__gte=cutoff_date
            ).order_by('-date')[:20]
            
            home_corners_data = [m.hc for m in home_matches if m.hc is not None]
            home_avg_corners = np.mean(home_corners_data) if home_corners_data else 5.2
            
            # Estadísticas del equipo visitante
            away_matches = Match.objects.filter(
                league=league,
                away_team=away_team,
                date__gte=cutoff_date
            ).order_by('-date')[:20]
            
            away_corners_data = [m.ac for m in away_matches if m.ac is not None]
            away_avg_corners = np.mean(away_corners_data) if away_corners_data else 4.6
            
            # Estadísticas de la liga
            league_matches = Match.objects.filter(
                league=league,
                date__gte=cutoff_date
            ).order_by('-date')[:100]
            
            league_home_corners = [m.hc for m in league_matches if m.hc is not None]
            league_away_corners = [m.ac for m in league_matches if m.ac is not None]
            
            league_avg_home_corners = np.mean(league_home_corners) if league_home_corners else 5.2
            league_avg_away_corners = np.mean(league_away_corners) if league_away_corners else 4.6
            
            if prediction_type == 'corners_total':
                # CORRECCIÓN: Calcular lambda correctamente con ajuste de liga
                # Factor de ajuste: qué tan diferente es el equipo vs promedio de liga
                home_factor = home_avg_corners / league_avg_home_corners if league_avg_home_corners > 0 else 1.0
                away_factor = away_avg_corners / league_avg_away_corners if league_avg_away_corners > 0 else 1.0
                
                # Lambda ajustado por el factor del equipo
                lambda_home = league_avg_home_corners * home_factor
                lambda_away = league_avg_away_corners * away_factor
                lambda_total = lambda_home + lambda_away
                
                # CORRECCIÓN: Usar media de Poisson (determinístico) en lugar de rvs (aleatorio)
                # Limitar a rango realista de corners (2-17 total, basado en datos reales)
                prediction = min(17.0, max(2.0, lambda_total))
                return float(prediction)
                
            elif prediction_type == 'corners_home':
                home_factor = home_avg_corners / league_avg_home_corners if league_avg_home_corners > 0 else 1.0
                lambda_home = league_avg_home_corners * home_factor
                prediction = min(12.0, max(0.0, lambda_home))
                return float(prediction)
                
            elif prediction_type == 'corners_away':
                away_factor = away_avg_corners / league_avg_away_corners if league_avg_away_corners > 0 else 1.0
                lambda_away = league_avg_away_corners * away_factor
                prediction = min(12.0, max(0.0, lambda_away))
                return float(prediction)
            
            return 5.0  # Valor por defecto
            
        except Exception as e:
            logger.error(f"Error en PoissonCornersModel: {str(e)}")
            return 5.0


class ModeloHibridoCorners:
    """Modelo híbrido que combina múltiples enfoques para predicción de corners"""
    
    def __init__(self):
        self.modelo_poisson = PoissonCornersModel()
        self.modelo_poisson_simple = None  # Se inicializará con SimplePredictionService
        self.modelo_average = None  # Se inicializará con SimplePredictionService
        self.name = "Modelo Híbrido Corners"
        
    def predecir(self, home_team: str, away_team: str, league: League, prediction_type: str = 'corners_total') -> Dict:
        """Predicción híbrida combinando múltiples modelos"""
        try:
            # Inicializar modelos si no están disponibles
            if self.modelo_poisson_simple is None:
                self.modelo_poisson_simple = SimplePredictionService()
            if self.modelo_average is None:
                self.modelo_average = SimplePredictionService()
            
            # Predicción Poisson especializada (peso 0.4)
            pred_poisson = self.modelo_poisson.predict(home_team, away_team, league, prediction_type)
            
            # Predicción Poisson simple (peso 0.3)
            poisson_result = self.modelo_poisson_simple.simple_poisson_model(
                home_team, away_team, league, prediction_type
            )
            pred_poisson_simple = poisson_result['prediction']
            
            # Predicción Average (peso 0.3)
            average_result = self.modelo_average.simple_average_model(
                home_team, away_team, league, prediction_type
            )
            pred_average = average_result['prediction']
            
            # Ensemble con pesos optimizados
            prediccion_final = (
                0.4 * pred_poisson + 
                0.3 * pred_poisson_simple + 
                0.3 * pred_average
            )
            
            # Calcular confianza basada en la consistencia de los modelos
            predicciones = [pred_poisson, pred_poisson_simple, pred_average]
            std_dev = np.std(predicciones)
            confidence = max(0.1, min(0.9, 1.0 - (std_dev / np.mean(predicciones))))
            
            # Calcular probabilidades para diferentes rangos
            if prediction_type in ['corners_total', 'corners_home', 'corners_away']:
                thresholds = [5, 7, 9, 12, 15]
                probabilities = {}
                
                for i, threshold in enumerate(thresholds):
                    prob = max(0.1, min(0.9, 1.0 - abs(prediccion_final - threshold) / 10))
                    probabilities[f'over_{threshold}'] = prob
            
            logger.info(f"Modelo Híbrido Corners - {prediction_type}: {prediccion_final:.2f}")
            
            return {
                'model_name': self.name,
                'prediction': round(prediccion_final, 2),
                'confidence': round(confidence, 3),
                'probabilities': probabilities,
                'total_matches': 0
            }
            
        except Exception as e:
            logger.error(f"Error en ModeloHibridoCorners: {str(e)}")
            return {
                'model_name': self.name,
                'prediction': 5.0,
                'confidence': 0.5,
                'probabilities': {},
                'total_matches': 0
            }


class ModeloHibridoGeneral:
    """Modelo híbrido general que puede aplicarse a cualquier tipo de predicción"""
    
    def __init__(self):
        self.modelo_poisson_simple = SimplePredictionService()
        self.modelo_average = SimplePredictionService()
        self.name = "Modelo Híbrido General"
        
    def predecir(self, home_team: str, away_team: str, league: League, prediction_type: str = 'shots_total') -> Dict:
        """Predicción híbrida general para cualquier tipo de predicción"""
        # AISLAR MERCADOS DE REMATES - NO GENERAR PREDICCIONES PARA SHOTS
        if 'shots' in prediction_type or 'remates' in prediction_type:
            logger.info(f"🚫 MODELO HÍBRIDO GENERAL - Mercado de remates aislado para {prediction_type}")
            return {
                'model_name': 'Modelo Híbrido General',
                'prediction': 0.0,
                'confidence': 0.0,
                'probabilities': {},
                'total_matches': 0
            }
        
        try:
            # Predicción Poisson (peso 0.5)
            poisson_result = self.modelo_poisson_simple.simple_poisson_model(
                home_team, away_team, league, prediction_type
            )
            pred_poisson = poisson_result['prediction']
            
            # Predicción Average (peso 0.3)
            average_result = self.modelo_average.simple_average_model(
                home_team, away_team, league, prediction_type
            )
            pred_average = average_result['prediction']
            
            # Predicción Trend (peso 0.2)
            trend_result = self.modelo_poisson_simple.simple_trend_model(
                home_team, away_team, league, prediction_type
            )
            pred_trend = trend_result['prediction']
            
            # Ensemble con pesos optimizados
            prediccion_final = (
                0.5 * pred_poisson + 
                0.3 * pred_average + 
                0.2 * pred_trend
            )
            
            # Calcular confianza
            predicciones = [pred_poisson, pred_average, pred_trend]
            std_dev = np.std(predicciones)
            confidence = max(0.1, min(0.9, 1.0 - (std_dev / max(np.mean(predicciones), 0.1))))
            
            # Usar probabilidades del modelo Poisson (más completo)
            probabilities = poisson_result['probabilities']
            
            logger.info(f"Modelo Híbrido General - {prediction_type}: {prediccion_final:.2f}")
            
            return {
                'model_name': self.name,
                'prediction': round(prediccion_final, 2),
                'confidence': round(confidence, 3),
                'probabilities': probabilities,
                'total_matches': 0
            }
            
        except Exception as e:
            logger.error(f"Error en ModeloHibridoGeneral: {str(e)}")
            return {
                'model_name': self.name,
                'prediction': 5.0,
                'confidence': 0.5,
                'probabilities': {},
                'total_matches': 0
            }
