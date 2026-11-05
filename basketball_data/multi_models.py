"""
Modelos múltiples para predicciones de NBA basados en los modelos de fútbol
"""

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.linear_model import Ridge, LinearRegression
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import TimeSeriesSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.preprocessing import StandardScaler
import logging
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta

from django.utils import timezone
from django.db import models
from .models import NBATeam, NBAGame

logger = logging.getLogger('basketball_data')


class NBAMultiModelPredictionService:
    """Servicio para predicciones de NBA con múltiples modelos estadísticos"""
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.models_cache = {}
    
    def get_team_stats_for_poisson(self, team: NBATeam, is_home: bool = True) -> Dict:
        """Obtiene estadísticas específicas para modelo de Poisson"""
        try:
            # Obtener partidos recientes (último año)
            cutoff_date = timezone.now().date() - timedelta(days=365)
            
            if is_home:
                matches = NBAGame.objects.filter(
                    home_team=team,
                    game_date__gte=cutoff_date,
                    home_points__isnull=False
                ).order_by('-game_date')[:30]
                points_data = [m.home_points for m in matches if m.home_points is not None]
            else:
                matches = NBAGame.objects.filter(
                    away_team=team,
                    game_date__gte=cutoff_date,
                    away_points__isnull=False
                ).order_by('-game_date')[:30]
                points_data = [m.away_points for m in matches if m.away_points is not None]
            
            if not points_data:
                return {'lambda': 110.0, 'matches': 0}
            
            # Calcular lambda para distribución de Poisson
            lambda_value = np.mean(points_data)
            
            return {
                'lambda': lambda_value,
                'matches': len(points_data),
                'std': np.std(points_data) if len(points_data) > 1 else 0,
                'recent_form': self._calculate_recent_form(points_data)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas Poisson para {team.full_name}: {e}")
            return {'lambda': 110.0, 'matches': 0, 'std': 0, 'recent_form': 0}
    
    def _calculate_recent_form(self, points_data: List[float]) -> float:
        """Calcula la forma reciente del equipo"""
        if len(points_data) < 5:
            return 0
        
        # Comparar últimos 5 partidos con los 5 anteriores
        recent_5 = np.mean(points_data[:5])
        previous_5 = np.mean(points_data[5:10]) if len(points_data) >= 10 else recent_5
        
        return recent_5 - previous_5
    
    def poisson_model_prediction(self, home_team: NBATeam, away_team: NBATeam) -> Dict:
        """Predicción usando modelo de Poisson para puntos totales"""
        try:
            home_stats = self.get_team_stats_for_poisson(home_team, is_home=True)
            away_stats = self.get_team_stats_for_poisson(away_team, is_home=False)
            
            # Calcular lambda combinado para puntos totales
            lambda_home = home_stats['lambda']
            lambda_away = away_stats['lambda']
            lambda_combined = lambda_home + lambda_away
            
            # Ajustar por forma reciente
            form_adjustment = (home_stats['recent_form'] - away_stats['recent_form']) * 0.1
            lambda_combined += form_adjustment
            
            # Predicción principal
            prediction = lambda_combined
            
            # Calcular probabilidades para diferentes rangos
            probabilities = {}
            for threshold in [200, 210, 220, 230, 240, 250]:
                prob = 1 - stats.poisson.cdf(threshold, lambda_combined)
                probabilities[f'over_{threshold}'] = max(0, min(1, prob))
            
            # Calcular confianza basada en cantidad de datos
            total_matches = home_stats['matches'] + away_stats['matches']
            confidence = min(0.9, 0.5 + (total_matches / 60) * 0.4)
            
            return {
                'model_name': 'Poisson NBA',
                'prediction': round(prediction, 1),
                'confidence': round(confidence, 2),
                'probabilities': probabilities,
                'total_matches': total_matches,
                'lambda_home': lambda_home,
                'lambda_away': lambda_away,
                'lambda_combined': lambda_combined
            }
            
        except Exception as e:
            logger.error(f"Error en predicción Poisson NBA: {e}")
            return {
                'model_name': 'Poisson NBA (Error)',
                'prediction': 220.0,
                'confidence': 0.3,
                'probabilities': {'over_220': 0.5},
                'total_matches': 0,
                'error': str(e)
            }
    
    def get_team_features_for_ml(self, team: NBATeam, is_home: bool = True) -> Dict:
        """Obtiene características para modelos de machine learning"""
        try:
            # Obtener partidos recientes (último año)
            cutoff_date = timezone.now().date() - timedelta(days=365)
            
            if is_home:
                matches = NBAGame.objects.filter(
                    home_team=team,
                    game_date__gte=cutoff_date,
                    home_points__isnull=False,
                    home_fg_pct__isnull=False
                ).order_by('-game_date')[:20]
                
                points_data = [m.home_points for m in matches]
                fg_pct_data = [m.home_fg_pct for m in matches]
                fg3_pct_data = [m.home_fg3_pct for m in matches if m.home_fg3_pct is not None]
                ft_pct_data = [m.home_ft_pct for m in matches if m.home_ft_pct is not None]
            else:
                matches = NBAGame.objects.filter(
                    away_team=team,
                    game_date__gte=cutoff_date,
                    away_points__isnull=False,
                    away_fg_pct__isnull=False
                ).order_by('-game_date')[:20]
                
                points_data = [m.away_points for m in matches]
                fg_pct_data = [m.away_fg_pct for m in matches]
                fg3_pct_data = [m.away_fg3_pct for m in matches if m.away_fg3_pct is not None]
                ft_pct_data = [m.away_ft_pct for m in matches if m.away_ft_pct is not None]
            
            if not points_data:
                return self._default_features()
            
            # Calcular características estadísticas
            points_array = np.array(points_data)
            fg_pct_array = np.array(fg_pct_data)
            fg3_pct_array = np.array(fg3_pct_data) if fg3_pct_data else np.array([0.35] * len(points_data))
            ft_pct_array = np.array(ft_pct_data) if ft_pct_data else np.array([0.75] * len(points_data))
            
            features = {
                'avg_points': np.mean(points_array),
                'std_points': np.std(points_array),
                'recent_points': np.mean(points_array[:5]) if len(points_array) >= 5 else np.mean(points_array),
                'avg_fg_pct': np.mean(fg_pct_array),
                'avg_fg3_pct': np.mean(fg3_pct_array),
                'avg_ft_pct': np.mean(ft_pct_array),
                'points_trend': self._calculate_trend(points_array),
                'consistency': 1 / (1 + np.std(points_array) / np.mean(points_array)) if np.mean(points_array) > 0 else 0,
                'home_advantage': 1.05 if is_home else 0.95,
                'matches_count': len(points_array)
            }
            
            return features
            
        except Exception as e:
            logger.error(f"Error obteniendo características ML para {team.full_name}: {e}")
            return self._default_features()
    
    def _default_features(self) -> Dict:
        """Características por defecto cuando no hay datos"""
        return {
            'avg_points': 110.0,
            'std_points': 15.0,
            'recent_points': 110.0,
            'avg_fg_pct': 0.45,
            'avg_fg3_pct': 0.35,
            'avg_ft_pct': 0.75,
            'points_trend': 0.0,
            'consistency': 0.5,
            'home_advantage': 1.0,
            'matches_count': 0
        }
    
    def _calculate_trend(self, data: np.ndarray) -> float:
        """Calcula la tendencia de los datos"""
        if len(data) < 3:
            return 0
        
        # Regresión lineal simple para calcular tendencia
        x = np.arange(len(data))
        slope, _ = np.polyfit(x, data, 1)
        return slope
    
    def random_forest_prediction(self, home_team: NBATeam, away_team: NBATeam) -> Dict:
        """Predicción usando Random Forest"""
        try:
            # Obtener características de ambos equipos
            home_features = self.get_team_features_for_ml(home_team, is_home=True)
            away_features = self.get_team_features_for_ml(away_team, is_home=False)
            
            # Crear vector de características combinado
            features_vector = [
                home_features['avg_points'],
                away_features['avg_points'],
                home_features['recent_points'],
                away_features['recent_points'],
                home_features['avg_fg_pct'],
                away_features['avg_fg_pct'],
                home_features['avg_fg3_pct'],
                away_features['avg_fg3_pct'],
                home_features['avg_ft_pct'],
                away_features['avg_ft_pct'],
                home_features['points_trend'],
                away_features['points_trend'],
                home_features['consistency'],
                away_features['consistency'],
                home_features['home_advantage'],
                away_features['home_advantage']
            ]
            
            # Entrenar modelo Random Forest con datos históricos
            model = self._train_random_forest_model()
            
            if model is None:
                # Fallback: predicción basada en promedios
                prediction = (home_features['avg_points'] + away_features['avg_points']) * 0.95
                confidence = 0.6
            else:
                # Hacer predicción
                prediction = model.predict([features_vector])[0]
                confidence = min(0.9, 0.5 + (home_features['matches_count'] + away_features['matches_count']) / 40 * 0.4)
            
            # Calcular probabilidades aproximadas
            probabilities = {}
            for threshold in [200, 210, 220, 230, 240, 250]:
                # Aproximación usando distribución normal
                std_dev = 15.0  # Desviación estándar típica de puntos totales NBA
                z_score = (threshold - prediction) / std_dev
                prob = 1 - stats.norm.cdf(z_score)
                probabilities[f'over_{threshold}'] = max(0, min(1, prob))
            
            return {
                'model_name': 'Random Forest NBA',
                'prediction': round(prediction, 1),
                'confidence': round(confidence, 2),
                'probabilities': probabilities,
                'total_matches': home_features['matches_count'] + away_features['matches_count'],
                'features_used': len(features_vector)
            }
            
        except Exception as e:
            logger.error(f"Error en predicción Random Forest NBA: {e}")
            return {
                'model_name': 'Random Forest NBA (Error)',
                'prediction': 220.0,
                'confidence': 0.3,
                'probabilities': {'over_220': 0.5},
                'total_matches': 0,
                'error': str(e)
            }
    
    def _train_random_forest_model(self):
        """Entrena un modelo Random Forest con datos históricos (caché diaria)."""
        try:
            today = timezone.now().date()
            cached = self.models_cache.get('rf')
            if cached and cached[0] == today:
                return cached[1]
            # Obtener datos históricos para entrenamiento
            cutoff_date = today - timedelta(days=730)  # 2 años
            
            games = NBAGame.objects.filter(
                game_date__gte=cutoff_date,
                home_points__isnull=False,
                away_points__isnull=False,
                home_fg_pct__isnull=False,
                away_fg_pct__isnull=False,
                total_points__isnull=False
            ).order_by('-game_date')[:500]  # Últimos 500 partidos
            
            if len(games) < 50:
                self.models_cache['rf'] = (today, None)
                return None
            
            # Preparar datos de entrenamiento
            X = []
            y = []
            
            for game in games:
                home_features = self.get_team_features_for_ml(game.home_team, is_home=True)
                away_features = self.get_team_features_for_ml(game.away_team, is_home=False)
                
                features_vector = [
                    home_features['avg_points'],
                    away_features['avg_points'],
                    home_features['recent_points'],
                    away_features['recent_points'],
                    home_features['avg_fg_pct'],
                    away_features['avg_fg_pct'],
                    home_features['avg_fg3_pct'],
                    away_features['avg_fg3_pct'],
                    home_features['avg_ft_pct'],
                    away_features['avg_ft_pct'],
                    home_features['points_trend'],
                    away_features['points_trend'],
                    home_features['consistency'],
                    away_features['consistency'],
                    home_features['home_advantage'],
                    away_features['home_advantage']
                ]
                
                X.append(features_vector)
                y.append(game.total_points)
            
            if len(X) < 20:
                return None
            
            # Entrenar modelo
            model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                min_samples_split=5
            )
            
            model.fit(X, y)
            self.models_cache['rf'] = (today, model)
            return model
            
        except Exception as e:
            logger.error(f"Error entrenando Random Forest NBA: {e}")
            return None
    
    def ridge_regression_prediction(self, home_team: NBATeam, away_team: NBATeam) -> Dict:
        """Predicción usando Ridge Regression"""
        try:
            # Obtener características de ambos equipos
            home_features = self.get_team_features_for_ml(home_team, is_home=True)
            away_features = self.get_team_features_for_ml(away_team, is_home=False)
            
            # Crear vector de características simplificado
            features_vector = [
                home_features['avg_points'],
                away_features['avg_points'],
                home_features['recent_points'],
                away_features['recent_points'],
                home_features['avg_fg_pct'],
                away_features['avg_fg_pct'],
                home_features['points_trend'],
                away_features['points_trend'],
                home_features['home_advantage']
            ]
            
            # Entrenar modelo Ridge con datos históricos
            model = self._train_ridge_model()
            
            if model is None:
                # Fallback: predicción basada en promedios con ajuste
                base_prediction = home_features['avg_points'] + away_features['avg_points']
                trend_adjustment = (home_features['points_trend'] + away_features['points_trend']) * 2
                prediction = base_prediction + trend_adjustment
                confidence = 0.6
            else:
                # Hacer predicción
                prediction = model.predict([features_vector])[0]
                confidence = min(0.9, 0.5 + (home_features['matches_count'] + away_features['matches_count']) / 40 * 0.4)
            
            # Calcular probabilidades aproximadas
            probabilities = {}
            for threshold in [200, 210, 220, 230, 240, 250]:
                # Aproximación usando distribución normal
                std_dev = 15.0
                z_score = (threshold - prediction) / std_dev
                prob = 1 - stats.norm.cdf(z_score)
                probabilities[f'over_{threshold}'] = max(0, min(1, prob))
            
            return {
                'model_name': 'Ridge Regression NBA',
                'prediction': round(prediction, 1),
                'confidence': round(confidence, 2),
                'probabilities': probabilities,
                'total_matches': home_features['matches_count'] + away_features['matches_count'],
                'features_used': len(features_vector)
            }
            
        except Exception as e:
            logger.error(f"Error en predicción Ridge NBA: {e}")
            return {
                'model_name': 'Ridge Regression NBA (Error)',
                'prediction': 220.0,
                'confidence': 0.3,
                'probabilities': {'over_220': 0.5},
                'total_matches': 0,
                'error': str(e)
            }
    
    def _train_ridge_model(self):
        """Entrena un modelo Ridge con datos históricos (caché diaria)."""
        try:
            today = timezone.now().date()
            cached = self.models_cache.get('ridge')
            if cached and cached[0] == today:
                return cached[1]
            # Obtener datos históricos para entrenamiento
            cutoff_date = today - timedelta(days=730)  # 2 años
            
            games = NBAGame.objects.filter(
                game_date__gte=cutoff_date,
                home_points__isnull=False,
                away_points__isnull=False,
                home_fg_pct__isnull=False,
                away_fg_pct__isnull=False,
                total_points__isnull=False
            ).order_by('-game_date')[:500]
            
            if len(games) < 30:
                return None
            
            # Preparar datos de entrenamiento
            X = []
            y = []
            
            for game in games:
                home_features = self.get_team_features_for_ml(game.home_team, is_home=True)
                away_features = self.get_team_features_for_ml(game.away_team, is_home=False)
                
                features_vector = [
                    home_features['avg_points'],
                    away_features['avg_points'],
                    home_features['recent_points'],
                    away_features['recent_points'],
                    home_features['avg_fg_pct'],
                    away_features['avg_fg_pct'],
                    home_features['points_trend'],
                    away_features['points_trend'],
                    home_features['home_advantage']
                ]
                
                X.append(features_vector)
                y.append(game.total_points)
            
            if len(X) < 15:
                self.models_cache['ridge'] = (today, None)
                return None
            
            # Entrenar modelo
            model = Ridge(alpha=1.0, random_state=42)
            model.fit(X, y)
            self.models_cache['ridge'] = (today, model)
            return model
            
        except Exception as e:
            logger.error(f"Error entrenando Ridge NBA: {e}")
            return None
    
    def ensemble_prediction(self, home_team: NBATeam, away_team: NBATeam) -> Dict:
        """Predicción ensemble combinando múltiples modelos"""
        try:
            # Obtener predicciones de todos los modelos
            poisson_result = self.poisson_model_prediction(home_team, away_team)
            rf_result = self.random_forest_prediction(home_team, away_team)
            ridge_result = self.ridge_regression_prediction(home_team, away_team)
            
            # Calcular promedio ponderado de las predicciones
            predictions = []
            weights = []
            
            # Poisson (peso 0.3)
            if 'error' not in poisson_result:
                predictions.append(poisson_result['prediction'])
                weights.append(0.3)
            
            # Random Forest (peso 0.4)
            if 'error' not in rf_result:
                predictions.append(rf_result['prediction'])
                weights.append(0.4)
            
            # Ridge (peso 0.3)
            if 'error' not in ridge_result:
                predictions.append(ridge_result['prediction'])
                weights.append(0.3)
            
            if not predictions:
                # Fallback si todos los modelos fallan
                return {
                    'model_name': 'Ensemble NBA (Fallback)',
                    'prediction': 220.0,
                    'confidence': 0.3,
                    'probabilities': {'over_220': 0.5},
                    'total_matches': 0,
                    'component_predictions': {
                        'poisson': poisson_result,
                        'random_forest': rf_result,
                        'ridge': ridge_result
                    }
                }
            
            # Calcular promedio ponderado
            total_weight = sum(weights)
            weighted_prediction = sum(p * w for p, w in zip(predictions, weights)) / total_weight
            
            # Calcular confianza promedio
            confidences = []
            if 'error' not in poisson_result:
                confidences.append(poisson_result['confidence'])
            if 'error' not in rf_result:
                confidences.append(rf_result['confidence'])
            if 'error' not in ridge_result:
                confidences.append(ridge_result['confidence'])
            
            avg_confidence = np.mean(confidences) if confidences else 0.5
            
            # Calcular probabilidades promedio
            all_probabilities = {}
            for threshold in [200, 210, 220, 230, 240, 250]:
                probs = []
                if 'error' not in poisson_result and f'over_{threshold}' in poisson_result['probabilities']:
                    probs.append(poisson_result['probabilities'][f'over_{threshold}'])
                if 'error' not in rf_result and f'over_{threshold}' in rf_result['probabilities']:
                    probs.append(rf_result['probabilities'][f'over_{threshold}'])
                if 'error' not in ridge_result and f'over_{threshold}' in ridge_result['probabilities']:
                    probs.append(ridge_result['probabilities'][f'over_{threshold}'])
                
                if probs:
                    all_probabilities[f'over_{threshold}'] = np.mean(probs)
            
            # Calcular total de partidos
            total_matches = max(
                poisson_result.get('total_matches', 0),
                rf_result.get('total_matches', 0),
                ridge_result.get('total_matches', 0)
            )
            
            return {
                'model_name': 'Ensemble NBA (Promedio)',
                'prediction': round(weighted_prediction, 1),
                'confidence': round(avg_confidence, 2),
                'probabilities': all_probabilities,
                'total_matches': total_matches,
                'component_predictions': {
                    'poisson': poisson_result,
                    'random_forest': rf_result,
                    'ridge': ridge_result
                },
                'weights_used': dict(zip(['poisson', 'random_forest', 'ridge'], weights))
            }
            
        except Exception as e:
            logger.error(f"Error en predicción ensemble NBA: {e}")
            return {
                'model_name': 'Ensemble NBA (Error)',
                'prediction': 220.0,
                'confidence': 0.3,
                'probabilities': {'over_220': 0.5},
                'total_matches': 0,
                'error': str(e)
            }


# Instancia global del servicio
nba_multi_model_service = NBAMultiModelPredictionService()











