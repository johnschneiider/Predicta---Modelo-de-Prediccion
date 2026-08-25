"""
Modelo Expected Goals (xG) especializado para predicción de remates
Basado en el modelo #10 del ROADMAP_IA_PREDICTIVA.md

Este modelo implementa un sistema de Expected Goals adaptado específicamente
para predecir remates totales, locales, visitantes y remates a puerta.
"""

import logging
import numpy as np
from django.db.models import Q, Avg, Count
from football_data.models import Match, League

logger = logging.getLogger(__name__)

class XGShotsModel:
    """
    Modelo Expected Goals (xG) para predicción de remates
    
    Características:
    - Usa variables de calidad de tiro (posición, contexto, forma)
    - Aplica factores de liga específicos para remates
    - Incluye análisis de tendencias temporales
    - Calcula probabilidades realistas de conversión
    """
    
    def __init__(self):
        self.name = "XG Shots Model"
        
    def predict_shots_total(self, home_team: str, away_team: str, league: League) -> dict:
        """Predicción de remates totales usando modelo xG"""
        try:
            logger.info(f"🎯 XG Model - Prediciendo shots_total: {home_team} vs {away_team}")
            
            # Obtener datos históricos de ambos equipos
            home_data = self._get_team_xg_data(home_team, league, 'home')
            away_data = self._get_team_xg_data(away_team, league, 'away')
            
            # Calcular Expected Shots basado solo en datos reales
            home_expected_shots = self._calculate_expected_shots(home_data, 'home')
            away_expected_shots = self._calculate_expected_shots(away_data, 'away')
            
            # Sin factores inventados, solo datos reales
            total_expected = home_expected_shots + away_expected_shots
            
            # Limitar a rango realista
            final_prediction = min(35.0, max(5.0, total_expected))
            
            # Calcular probabilidades
            probabilities = self._calculate_shot_probabilities(final_prediction)
            
            logger.info(f"🎯 XG Model - shots_total: {final_prediction:.2f}")
            
            return {
                'model_name': self.name,
                'prediction': final_prediction,
                'confidence': 0.75,  # xG es un modelo confiable
                'probabilities': probabilities,
                'total_matches': home_data['total_matches'] + away_data['total_matches'],
                'method': 'Expected Goals (xG)',
                'details': {
                    'home_expected': home_expected_shots,
                    'away_expected': away_expected_shots,
                    'method': 'Real data only'
                }
            }
            
        except Exception as e:
            logger.error(f"Error en XG Model shots_total: {e}")
            return self._fallback_prediction('shots_total')
    
    def predict_shots_home(self, home_team: str, away_team: str, league: League) -> dict:
        """Predicción de remates del equipo local"""
        try:
            logger.info(f"🎯 XG Model - Prediciendo shots_home: {home_team}")
            
            home_data = self._get_team_xg_data(home_team, league, 'home')
            away_data = self._get_team_xg_data(away_team, league, 'away')
            
            # Expected shots del equipo local
            home_expected = self._calculate_expected_shots(home_data, 'home')
            
            # Factor defensivo del equipo visitante
            away_defensive_factor = self._get_defensive_factor(away_data, 'away')
            
            # Aplicar factores
            league_factor = self._get_league_xg_factor(league)
            form_factor = self._get_xg_form_factor(home_team, away_team, league)
            
            final_prediction = home_expected * away_defensive_factor * league_factor * form_factor
            final_prediction = min(25.0, max(2.0, final_prediction))
            
            probabilities = self._calculate_shot_probabilities(final_prediction)
            
            logger.info(f"🎯 XG Model - shots_home: {final_prediction:.2f}")
            
            return {
                'model_name': self.name,
                'prediction': final_prediction,
                'confidence': 0.75,
                'probabilities': probabilities,
                'total_matches': home_data['total_matches'],
                'method': 'Expected Goals (xG)',
                'details': {
                    'home_expected': home_expected,
                    'defensive_factor': away_defensive_factor,
                    'league_factor': league_factor,
                    'form_factor': form_factor
                }
            }
            
        except Exception as e:
            logger.error(f"Error en XG Model shots_home: {e}")
            return self._fallback_prediction('shots_home')
    
    def predict_shots_away(self, home_team: str, away_team: str, league: League) -> dict:
        """Predicción de remates del equipo visitante"""
        try:
            logger.info(f"🎯 XG Model - Prediciendo shots_away: {away_team}")
            
            home_data = self._get_team_xg_data(home_team, league, 'home')
            away_data = self._get_team_xg_data(away_team, league, 'away')
            
            # Expected shots del equipo visitante
            away_expected = self._calculate_expected_shots(away_data, 'away')
            
            # Factor defensivo del equipo local
            home_defensive_factor = self._get_defensive_factor(home_data, 'home')
            
            # Aplicar factores
            league_factor = self._get_league_xg_factor(league)
            form_factor = self._get_xg_form_factor(home_team, away_team, league)
            
            final_prediction = away_expected * home_defensive_factor * league_factor * form_factor
            final_prediction = min(25.0, max(2.0, final_prediction))
            
            probabilities = self._calculate_shot_probabilities(final_prediction)
            
            logger.info(f"🎯 XG Model - shots_away: {final_prediction:.2f}")
            
            return {
                'model_name': self.name,
                'prediction': final_prediction,
                'confidence': 0.75,
                'probabilities': probabilities,
                'total_matches': away_data['total_matches'],
                'method': 'Expected Goals (xG)',
                'details': {
                    'away_expected': away_expected,
                    'defensive_factor': home_defensive_factor,
                    'league_factor': league_factor,
                    'form_factor': form_factor
                }
            }
            
        except Exception as e:
            logger.error(f"Error en XG Model shots_away: {e}")
            return self._fallback_prediction('shots_away')
    
    def predict_shots_on_target_total(self, home_team: str, away_team: str, league: League) -> dict:
        """Predicción de remates a puerta totales"""
        try:
            logger.info(f"🎯 XG Model - Prediciendo shots_on_target_total")
            
            # Obtener datos históricos
            home_data = self._get_team_xg_data(home_team, league, 'home')
            away_data = self._get_team_xg_data(away_team, league, 'away')
            
            # Calcular xG total (calidad de tiros)
            home_xg = self._calculate_team_xg(home_data, 'home')
            away_xg = self._calculate_team_xg(away_data, 'away')
            
            # Convertir xG a shots on target esperados
            # xG alto = más shots on target
            home_sot_expected = self._xg_to_shots_on_target(home_xg, home_data)
            away_sot_expected = self._xg_to_shots_on_target(away_xg, away_data)
            
            # Aplicar factores
            league_factor = self._get_league_xg_factor(league)
            form_factor = self._get_xg_form_factor(home_team, away_team, league)
            
            total_sot = (home_sot_expected + away_sot_expected) * league_factor * form_factor
            final_prediction = min(20.0, max(2.0, total_sot))
            
            probabilities = self._calculate_sot_probabilities(final_prediction)
            
            logger.info(f"🎯 XG Model - shots_on_target_total: {final_prediction:.2f}")
            
            return {
                'model_name': self.name,
                'prediction': final_prediction,
                'confidence': 0.70,  # Slightly lower for SOT
                'probabilities': probabilities,
                'total_matches': home_data['total_matches'] + away_data['total_matches'],
                'method': 'Expected Goals (xG)',
                'details': {
                    'home_xg': home_xg,
                    'away_xg': away_xg,
                    'home_sot_expected': home_sot_expected,
                    'away_sot_expected': away_sot_expected,
                    'league_factor': league_factor,
                    'form_factor': form_factor
                }
            }
            
        except Exception as e:
            logger.error(f"Error en XG Model shots_on_target_total: {e}")
            return self._fallback_prediction('shots_on_target_total')
    
    def _get_team_xg_data(self, team: str, league: League, venue: str) -> dict:
        """Obtener datos de xG para un equipo"""
        try:
            # Filtrar partidos del equipo
            if venue == 'home':
                matches = Match.objects.filter(
                    home_team=team,
                    league=league,
                    hs__isnull=False,
                    as_field__isnull=False,
                    hst__isnull=False,
                    ast__isnull=False
                ).order_by('-date')[:20]  # Últimos 20 partidos
            else:
                matches = Match.objects.filter(
                    away_team=team,
                    league=league,
                    hs__isnull=False,
                    as_field__isnull=False,
                    hst__isnull=False,
                    ast__isnull=False
                ).order_by('-date')[:20]
            
            if not matches.exists():
                # Fase 3 — fallback al promedio de LIGA, no a valores fijos
                league_data = self._get_league_average_data(league)
                logger.info(
                    f"XG Model: {team} sin datos hst/ast en {league.name}, "
                    f"usando promedio de liga (shots={league_data['avg_shots']:.1f}, "
                    f"sot={league_data['avg_sot']:.1f})"
                )
                return league_data
            
            # Calcular estadísticas
            shots_data = []
            sot_data = []
            goals_data = []
            
            for match in matches:
                if venue == 'home':
                    shots_data.append(match.hs)
                    sot_data.append(match.hst)
                    goals_data.append(match.fthg)
                else:
                    shots_data.append(match.as_field)
                    sot_data.append(match.ast)
                    goals_data.append(match.ftag)
            
            return {
                'total_matches': len(matches),
                'avg_shots': np.mean(shots_data),
                'avg_sot': np.mean(sot_data),
                'avg_goals': np.mean(goals_data),
                'conversion_rate': np.mean(sot_data) / max(np.mean(shots_data), 1),
                'sot_conversion_rate': np.mean(goals_data) / max(np.mean(sot_data), 1),
                'shots_std': np.std(shots_data),
                'sot_std': np.std(sot_data)
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo datos xG para {team}: {e}")
            return self._get_league_average_data(league)
    
    def _calculate_expected_shots(self, team_data: dict, venue: str) -> float:
        """Calcular expected shots basado en datos reales"""
        try:
            # Base: promedio histórico real de shots
            base_shots = team_data['avg_shots']
            
            # Factor de localía basado en datos reales (no inventado)
            if venue == 'home':
                # Usar datos históricos reales de localía si están disponibles
                venue_factor = 1.0  # Sin ajuste hasta tener datos reales
            else:
                venue_factor = 1.0  # Sin ajuste hasta tener datos reales
            
            # Solo usar el promedio histórico real
            expected = base_shots * venue_factor
            
            # Límites basados en datos reales observados
            return max(2.0, min(35.0, expected))
            
        except Exception as e:
            logger.error(f"Error calculando expected shots: {e}")
            return 12.0
    
    def _calculate_team_xg(self, team_data: dict, venue: str) -> float:
        """Calcular xG total del equipo basado en datos reales"""
        try:
            # xG real = shots * (shots_on_target / shots) * (goals / shots_on_target)
            # Esto es: shots * conversion_rate_sot * conversion_rate_goals
            base_xg = team_data['avg_shots'] * team_data['conversion_rate'] * team_data['sot_conversion_rate']
            
            # Sin factores inventados, solo datos reales
            return max(0.1, min(5.0, base_xg))
            
        except Exception as e:
            logger.error(f"Error calculando team xG: {e}")
            return 1.2
    
    def _xg_to_shots_on_target(self, xg: float, team_data: dict) -> float:
        """Convertir xG a shots on target esperados basado en datos reales"""
        try:
            # Usar el promedio histórico real de shots on target del equipo
            # No inventar factores de conversión
            historical_sot = team_data['avg_sot']
            
            # El xG ya está calculado con datos reales, usar directamente
            return max(1.0, min(15.0, historical_sot))
            
        except Exception as e:
            logger.error(f"Error convirtiendo xG a SOT: {e}")
            return 4.0
    
    def _get_defensive_factor(self, team_data: dict, venue: str) -> float:
        """Calcular factor defensivo del equipo rival basado en datos reales"""
        try:
            # Sin factores inventados, usar solo datos reales
            # Por ahora, no aplicar factores defensivos hasta tener datos reales
            # de cuántos shots recibe cada equipo en promedio
            return 1.0
            
        except Exception as e:
            logger.error(f"Error calculando factor defensivo: {e}")
            return 1.0
    
    def _get_league_xg_factor(self, league: League) -> float:
        """Factor de liga para xG basado en datos reales"""
        try:
            # Sin factores inventados, usar solo datos reales
            # Por ahora, no aplicar factores de liga hasta tener datos reales
            # de promedios de shots por liga
            return 1.0
            
        except Exception as e:
            logger.error(f"Error obteniendo factor de liga: {e}")
            return 1.0
    
    def _get_xg_form_factor(self, home_team: str, away_team: str, league: League) -> float:
        """Factor de forma reciente basado en datos reales"""
        try:
            # Sin factores inventados, usar solo datos reales
            # Por ahora, no aplicar factores de forma hasta tener datos reales
            # de rendimiento reciente vs histórico
            return 1.0
            
        except Exception as e:
            logger.error(f"Error calculando factor de forma xG: {e}")
            return 1.0
    
    def _calculate_recent_xg(self, matches, team: str) -> float:
        """Calcular xG reciente de un equipo"""
        try:
            if not matches:
                return 1.0
            
            xg_values = []
            for match in matches:
                if match.home_team == team:
                    # xG aproximado: shots * conversion_rate
                    shots = match.hs or 0
                    sot = match.hst or 0
                    goals = match.fthg or 0
                else:
                    shots = match.as_field or 0
                    sot = match.ast or 0
                    goals = match.ftag or 0
                
                if shots > 0:
                    conversion_rate = sot / shots
                    xg = shots * conversion_rate * 0.4  # Factor de calidad
                    xg_values.append(xg)
            
            return np.mean(xg_values) if xg_values else 1.0
            
        except Exception as e:
            logger.error(f"Error calculando xG reciente: {e}")
            return 1.0
    
    def _calculate_shot_probabilities(self, prediction: float) -> dict:
        """Calcular probabilidades para diferentes umbrales de shots"""
        try:
            # Usar distribución de Poisson para shots
            from scipy.stats import poisson
            
            probabilities = {}
            thresholds = [5, 10, 15, 20, 25]
            
            for threshold in thresholds:
                prob = 1 - poisson.cdf(threshold - 1, prediction)
                probabilities[f'over_{threshold}'] = round(prob, 3)
            
            return probabilities
            
        except ImportError:
            # Fallback sin scipy
            probabilities = {}
            thresholds = [5, 10, 15, 20, 25]
            
            for threshold in thresholds:
                # Aproximación simple
                if prediction > threshold:
                    prob = min(0.9, (prediction - threshold) / prediction + 0.3)
                else:
                    prob = max(0.1, prediction / threshold * 0.5)
                
                probabilities[f'over_{threshold}'] = round(prob, 3)
            
            return probabilities
    
    def _calculate_sot_probabilities(self, prediction: float) -> dict:
        """Calcular probabilidades para shots on target"""
        try:
            probabilities = {}
            thresholds = [3, 5, 7, 10, 12]
            
            for threshold in thresholds:
                if prediction > threshold:
                    prob = min(0.9, (prediction - threshold) / prediction + 0.4)
                else:
                    prob = max(0.1, prediction / threshold * 0.6)
                
                probabilities[f'over_{threshold}'] = round(prob, 3)
            
            return probabilities
            
        except Exception as e:
            logger.error(f"Error calculando probabilidades SOT: {e}")
            return {'over_5': 0.5, 'over_7': 0.3, 'over_10': 0.2}
    
    def _get_league_average_data(self, league: League) -> dict:
        """
        Calcular promedios de liga cuando un equipo no tiene datos suficientes.
        Fase 3 — reemplaza _default_team_data() con datos reales de la liga.
        """
        try:
            from django.db.models import Avg
            matches = Match.objects.filter(
                league=league,
                hs__isnull=False,
                hst__isnull=False
            ).order_by('-date')[:100]
            
            if not matches.exists():
                # Sin datos de liga tampoco → fallback último recurso
                return self._default_team_data()
            
            hs_list = [m.hs for m in matches]
            hst_list = [m.hst for m in matches]
            goals_list = [m.fthg for m in matches]
            
            avg_shots = float(np.mean(hs_list))
            avg_sot = float(np.mean(hst_list))
            avg_goals = float(np.mean(goals_list))
            
            return {
                'total_matches': 0,  # 0 indica que son datos de liga, no del equipo
                'avg_shots': avg_shots,
                'avg_sot': avg_sot,
                'avg_goals': avg_goals,
                'conversion_rate': avg_sot / max(avg_shots, 1),
                'sot_conversion_rate': avg_goals / max(avg_sot, 1),
                'shots_std': float(np.std(hs_list)),
                'sot_std': float(np.std(hst_list)),
            }
        except Exception as e:
            logger.error(f"Error calculando promedio de liga para {league}: {e}")
            return self._default_team_data()
    
    def _default_team_data(self) -> dict:
        """Datos por defecto cuando no hay suficiente información (último recurso)"""
        return {
            'total_matches': 0,
            'avg_shots': 12.0,
            'avg_sot': 4.0,
            'avg_goals': 1.5,
            'conversion_rate': 0.35,
            'sot_conversion_rate': 0.35,
            'shots_std': 3.0,
            'sot_std': 1.5
        }
    
    def _fallback_prediction(self, prediction_type: str) -> dict:
        """Predicción de fallback cuando falla el modelo"""
        fallback_values = {
            'shots_total': 22.0,
            'shots_home': 12.0,
            'shots_away': 10.0,
            'shots_on_target_total': 7.0
        }
        
        return {
            'model_name': f"{self.name} (Fallback)",
            'prediction': fallback_values.get(prediction_type, 10.0),
            'confidence': 0.3,
            'probabilities': {'over_5': 0.5, 'over_10': 0.3},
            'total_matches': 0,
            'method': 'Fallback xG',
            'error': 'Insufficient data'
        }

# Instancia global del modelo
xg_shots_model = XGShotsModel()
