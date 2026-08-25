import logging
from django.db.models import Q, Avg
from football_data.models import League, Match
import numpy as np

logger = logging.getLogger(__name__)

class ShotsPredictionModel:
    def __init__(self):
        self.name = "Shots Prediction Model"
    
    def predict_shots_total(self, home_team: str, away_team: str, league: League) -> dict:
        """Predicción de remates totales en el partido"""
        try:
            # Obtener estadísticas ofensivas
            home_shots_avg = self._get_team_shots_average(home_team, league, 'home')
            away_shots_avg = self._get_team_shots_average(away_team, league, 'away')
            
            # Obtener estadísticas defensivas
            home_conceded = self._get_team_shots_conceded_average(home_team, league, 'home')
            away_conceded = self._get_team_shots_conceded_average(away_team, league, 'away')
            
            # Calcular predicción usando enfoque ofensivo-defensivo
            home_expected_shots = (home_shots_avg + away_conceded) / 2
            away_expected_shots = (away_shots_avg + home_conceded) / 2
            
            total_shots = home_expected_shots + away_expected_shots
            
            logger.info(f"🎯 REMATES TOTALES - Cálculo inicial:")
            logger.info(f"   {home_team}: shots_avg={home_shots_avg:.2f}, conceded={away_conceded:.2f} → expected={home_expected_shots:.2f}")
            logger.info(f"   {away_team}: shots_avg={away_shots_avg:.2f}, conceded={home_conceded:.2f} → expected={away_expected_shots:.2f}")
            logger.info(f"   Total inicial: {total_shots:.2f}")
            
            # Aplicar factor de liga
            league_factor = self._get_league_shots_factor(league)
            total_shots *= league_factor
            logger.info(f"🎯 REMATES TOTALES - Después factor liga ({league_factor}): {total_shots:.2f}")
            
            # Aplicar factor de forma reciente
            form_factor = self._get_recent_form_factor(home_team, away_team, league)
            total_shots *= form_factor
            logger.info(f"🎯 REMATES TOTALES - Después factor forma ({form_factor:.3f}): {total_shots:.2f}")
            
            # Limitar a rango realista
            total_shots = max(5.0, min(35.0, total_shots))
            logger.info(f"🎯 REMATES TOTALES - Final (limitado): {total_shots:.2f}")
            
            # Calcular probabilidades
            probabilities = self._calculate_shots_probabilities(total_shots)
            
            return {
                'model_name': 'Shots Prediction Model',
                'prediction': round(total_shots, 1),
                'confidence': 0.75,
                'probabilities': probabilities,
                'total_matches': 50  # Estimación
            }
            
        except Exception as e:
            logger.error(f"Error en predicción de remates totales: {e}")
            return self._fallback_prediction('shots_total')
    
    def predict_shots_home(self, home_team: str, away_team: str, league: League) -> dict:
        """Predicción de remates del equipo local"""
        try:
            # Obtener estadísticas del equipo local
            home_shots_avg = self._get_team_shots_average(home_team, league, 'home')
            away_conceded = self._get_team_shots_conceded_average(away_team, league, 'away')
            
            # Calcular predicción
            home_expected_shots = (home_shots_avg + away_conceded) / 2
            
            # Aplicar factor de liga
            league_factor = self._get_league_shots_factor(league)
            home_expected_shots *= league_factor
            
            # Aplicar factor de forma reciente
            form_factor = self._get_recent_form_factor(home_team, away_team, league)
            home_expected_shots *= form_factor
            
            # Limitar a rango realista
            home_expected_shots = max(2.0, min(25.0, home_expected_shots))
            
            # Calcular probabilidades
            probabilities = self._calculate_shots_probabilities(home_expected_shots)
            
            return {
                'model_name': 'Shots Prediction Model',
                'prediction': round(home_expected_shots, 1),
                'confidence': 0.75,
                'probabilities': probabilities,
                'total_matches': 50
            }
            
        except Exception as e:
            logger.error(f"Error en predicción de remates local: {e}")
            return self._fallback_prediction('shots_home')
    
    def predict_shots_away(self, home_team: str, away_team: str, league: League) -> dict:
        """Predicción de remates del equipo visitante"""
        try:
            # Obtener estadísticas del equipo visitante
            away_shots_avg = self._get_team_shots_average(away_team, league, 'away')
            home_conceded = self._get_team_shots_conceded_average(home_team, league, 'home')
            
            # Calcular predicción
            away_expected_shots = (away_shots_avg + home_conceded) / 2
            
            # Aplicar factor de liga
            league_factor = self._get_league_shots_factor(league)
            away_expected_shots *= league_factor
            
            # Aplicar factor de forma reciente
            form_factor = self._get_recent_form_factor(home_team, away_team, league)
            away_expected_shots *= form_factor
            
            # Limitar a rango realista
            away_expected_shots = max(2.0, min(25.0, away_expected_shots))
            
            # Calcular probabilidades
            probabilities = self._calculate_shots_probabilities(away_expected_shots)
            
            return {
                'model_name': 'Shots Prediction Model',
                'prediction': round(away_expected_shots, 1),
                'confidence': 0.75,
                'probabilities': probabilities,
                'total_matches': 50
            }
            
        except Exception as e:
            logger.error(f"Error en predicción de remates visitante: {e}")
            return self._fallback_prediction('shots_away')
    
    def predict_shots_on_target_total(self, home_team: str, away_team: str, league: League) -> dict:
        """Predicción de remates a puerta totales"""
        try:
            # Obtener estadísticas de remates a puerta
            home_shots_on_target = self._get_team_shots_on_target_average(home_team, league, 'home')
            away_shots_on_target = self._get_team_shots_on_target_average(away_team, league, 'away')
            
            # Obtener estadísticas defensivas (remates a puerta concedidos)
            home_conceded_on_target = self._get_team_shots_on_target_conceded_average(home_team, league, 'home')
            away_conceded_on_target = self._get_team_shots_on_target_conceded_average(away_team, league, 'away')
            
            # Calcular predicción
            home_expected = (home_shots_on_target + away_conceded_on_target) / 2
            away_expected = (away_shots_on_target + home_conceded_on_target) / 2
            
            total_shots_on_target = home_expected + away_expected
            
            # Aplicar factor de liga específico para remates a puerta
            league_factor = self._get_league_shots_on_target_factor(league)
            total_shots_on_target *= league_factor
            
            # Aplicar factor de forma reciente
            form_factor = self._get_recent_form_factor(home_team, away_team, league)
            total_shots_on_target *= form_factor
            
            # Limitar a rango realista
            total_shots_on_target = max(2.0, min(20.0, total_shots_on_target))
            
            # Calcular probabilidades específicas para remates a puerta
            probabilities = self._calculate_shots_on_target_probabilities(total_shots_on_target)
            
            return {
                'model_name': 'Shots Prediction Model',
                'prediction': round(total_shots_on_target, 1),
                'confidence': 0.7,
                'probabilities': probabilities,
                'total_matches': 50
            }
            
        except Exception as e:
            logger.error(f"Error en predicción de remates a puerta: {e}")
            return self._fallback_prediction('shots_on_target_total')
    
    def _get_team_shots_average(self, team_name: str, league: League, home_away: str) -> float:
        """Obtiene el promedio de remates de un equipo"""
        try:
            if home_away == 'home':
                matches = Match.objects.filter(
                    home_team=team_name,
                    league=league,
                    hs__isnull=False
                ).exclude(hs=0)
                if matches.exists():
                    return matches.aggregate(avg=Avg('hs'))['avg'] or 12.0
            else:
                matches = Match.objects.filter(
                    away_team=team_name,
                    league=league,
                    as_field__isnull=False
                ).exclude(as_field=0)
                if matches.exists():
                    return matches.aggregate(avg=Avg('as_field'))['avg'] or 10.0
            
            # Fase 3 — fallback al promedio de liga
            return self._get_league_avg_shots(league, home_away)
            
        except Exception as e:
            logger.error(f"Error obteniendo promedio de remates: {e}")
            return self._get_league_avg_shots(league, home_away)
    
    def _get_team_shots_conceded_average(self, team_name: str, league: League, home_away: str) -> float:
        """Obtiene el promedio de remates recibidos por un equipo"""
        try:
            if home_away == 'home':
                matches = Match.objects.filter(
                    home_team=team_name,
                    league=league,
                    as_field__isnull=False
                ).exclude(as_field=0)
                if matches.exists():
                    return matches.aggregate(avg=Avg('as_field'))['avg'] or 12.0
            else:
                matches = Match.objects.filter(
                    away_team=team_name,
                    league=league,
                    hs__isnull=False
                ).exclude(hs=0)
                if matches.exists():
                    return matches.aggregate(avg=Avg('hs'))['avg'] or 12.0
            
            return self._get_league_avg_shots(league, 'home' if home_away == 'away' else 'away')
            
        except Exception as e:
            logger.error(f"Error obteniendo promedio de remates recibidos: {e}")
            return self._get_league_avg_shots(league, 'home' if home_away == 'away' else 'away')
    
    def _get_team_shots_on_target_average(self, team_name: str, league: League, home_away: str) -> float:
        """Obtiene el promedio de remates a puerta de un equipo"""
        try:
            if home_away == 'home':
                matches = Match.objects.filter(
                    home_team=team_name,
                    league=league,
                    hst__isnull=False
                ).exclude(hst=0)
                if matches.exists():
                    return matches.aggregate(avg=Avg('hst'))['avg'] or 4.5
            else:
                matches = Match.objects.filter(
                    away_team=team_name,
                    league=league,
                    ast__isnull=False
                ).exclude(ast=0)
                if matches.exists():
                    return matches.aggregate(avg=Avg('ast'))['avg'] or 4.0
            
            return self._get_league_avg_sot(league, home_away)
            
        except Exception as e:
            logger.error(f"Error obteniendo promedio de remates a puerta: {e}")
            return self._get_league_avg_sot(league, home_away)
    
    def _get_team_shots_on_target_conceded_average(self, team_name: str, league: League, home_away: str) -> float:
        """Obtiene el promedio de remates a puerta recibidos por un equipo"""
        try:
            if home_away == 'home':
                matches = Match.objects.filter(
                    home_team=team_name,
                    league=league,
                    ast__isnull=False
                ).exclude(ast=0)
                if matches.exists():
                    return matches.aggregate(avg=Avg('ast'))['avg'] or 4.5
            else:
                matches = Match.objects.filter(
                    away_team=team_name,
                    league=league,
                    hst__isnull=False
                ).exclude(hst=0)
                if matches.exists():
                    return matches.aggregate(avg=Avg('hst'))['avg'] or 4.5
            
            return 4.5
            
        except Exception as e:
            logger.error(f"Error obteniendo promedio de remates a puerta recibidos: {e}")
            return 4.5
    
    def _get_league_avg_shots(self, league: League, home_away: str) -> float:
        """Fase 3 — promedio de remates de la liga cuando el equipo no tiene datos."""
        try:
            if home_away == 'home':
                matches = Match.objects.filter(
                    league=league, hs__isnull=False
                ).exclude(hs=0).order_by('-date')[:200]
                if matches.exists():
                    avg = matches.aggregate(avg=Avg('hs'))['avg']
                    if avg:
                        logger.info(
                            f"shots_prediction_model: fallback liga {league.name} "
                            f"hs={avg:.1f}"
                        )
                        return float(avg)
            else:
                matches = Match.objects.filter(
                    league=league, as_field__isnull=False
                ).exclude(as_field=0).order_by('-date')[:200]
                if matches.exists():
                    avg = matches.aggregate(avg=Avg('as_field'))['avg']
                    if avg:
                        logger.info(
                            f"shots_prediction_model: fallback liga {league.name} "
                            f"as={avg:.1f}"
                        )
                        return float(avg)
            # Último recurso
            return 12.0 if home_away == 'home' else 10.0
        except Exception as e:
            logger.error(f"Error en _get_league_avg_shots: {e}")
            return 12.0 if home_away == 'home' else 10.0
    
    def _get_league_avg_sot(self, league: League, home_away: str) -> float:
        """Fase 3 — promedio de tiros a puerta de la liga cuando el equipo no tiene datos."""
        try:
            if home_away == 'home':
                matches = Match.objects.filter(
                    league=league, hst__isnull=False
                ).exclude(hst=0).order_by('-date')[:200]
                if matches.exists():
                    avg = matches.aggregate(avg=Avg('hst'))['avg']
                    if avg:
                        logger.info(
                            f"shots_prediction_model: fallback liga {league.name} "
                            f"hst={avg:.1f}"
                        )
                        return float(avg)
            else:
                matches = Match.objects.filter(
                    league=league, ast__isnull=False
                ).exclude(ast=0).order_by('-date')[:200]
                if matches.exists():
                    avg = matches.aggregate(avg=Avg('ast'))['avg']
                    if avg:
                        logger.info(
                            f"shots_prediction_model: fallback liga {league.name} "
                            f"ast={avg:.1f}"
                        )
                        return float(avg)
            return 4.5 if home_away == 'home' else 4.0
        except Exception as e:
            logger.error(f"Error en _get_league_avg_sot: {e}")
            return 4.5 if home_away == 'home' else 4.0
    
    def _get_league_shots_factor(self, league: League) -> float:
        """Factor de ajuste por liga para remates"""
        league_factors = {
            'Premier League': 1.1,  # Más remates
            'Bundesliga': 1.0,     # Promedio
            'La Liga': 0.95,       # Menos remates
            'Serie A': 0.9,        # Menos remates
            'Ligue 1': 1.0         # Promedio
        }
        return league_factors.get(league.name, 1.0)
    
    def _get_league_shots_on_target_factor(self, league: League) -> float:
        """Factor de ajuste por liga para remates a puerta"""
        league_factors = {
            'Premier League': 1.05,
            'Bundesliga': 1.0,
            'La Liga': 0.95,
            'Serie A': 0.9,
            'Ligue 1': 1.0
        }
        return league_factors.get(league.name, 1.0)
    
    def _get_recent_form_factor(self, home_team: str, away_team: str, league: League) -> float:
        """Factor de forma reciente basado en remates recientes"""
        try:
            # Obtener últimos 5 partidos de cada equipo
            home_matches = Match.objects.filter(
                Q(home_team=home_team) | Q(away_team=home_team),
                league=league
            ).order_by('-date')[:5]
            
            away_matches = Match.objects.filter(
                Q(home_team=away_team) | Q(away_team=away_team),
                league=league
            ).order_by('-date')[:5]
            
            # Calcular factor basado en REMATES recientes (no goles)
            home_shots_recent = []
            away_shots_recent = []
            
            # Remates recientes del equipo local
            for match in home_matches:
                if match.hs is not None and match.as_field is not None:
                    if match.home_team == home_team:
                        home_shots_recent.append(match.hs)
                    else:
                        home_shots_recent.append(match.as_field)
            
            # Remates recientes del equipo visitante
            for match in away_matches:
                if match.hs is not None and match.as_field is not None:
                    if match.home_team == away_team:
                        away_shots_recent.append(match.hs)
                    else:
                        away_shots_recent.append(match.as_field)
            
            # Calcular promedios de remates recientes
            if len(home_shots_recent) > 0 and len(away_shots_recent) > 0:
                home_shots_avg = sum(home_shots_recent) / len(home_shots_recent)
                away_shots_avg = sum(away_shots_recent) / len(away_shots_recent)
                
                # Factor basado en remates recientes vs promedio histórico
                # Si remates recientes > promedio histórico → factor > 1.0
                # Si remates recientes < promedio histórico → factor < 1.0
                
                # Obtener promedios históricos para comparar
                home_historical_avg = self._get_team_shots_average(home_team, league, 'home')
                away_historical_avg = self._get_team_shots_average(away_team, league, 'away')
                
                # Calcular factores (más conservadores que antes)
                if home_historical_avg > 0:
                    home_factor = 0.95 + ((home_shots_avg - home_historical_avg) / home_historical_avg) * 0.1
                else:
                    home_factor = 1.0
                    
                if away_historical_avg > 0:
                    away_factor = 0.95 + ((away_shots_avg - away_historical_avg) / away_historical_avg) * 0.1
                else:
                    away_factor = 1.0
                
                # Limitar factores a rango razonable (0.8 - 1.2)
                home_factor = max(0.8, min(1.2, home_factor))
                away_factor = max(0.8, min(1.2, away_factor))
                
                factor_promedio = (home_factor + away_factor) / 2
                
                logger.info(f"🎯 FACTOR FORMA REMATES - {home_team}: {home_factor:.3f}, {away_team}: {away_factor:.3f}, Promedio: {factor_promedio:.3f}")
                
                return factor_promedio
            
            return 1.0
            
        except Exception as e:
            logger.error(f"Error calculando factor de forma basado en remates: {e}")
            return 1.0
    
    def _calculate_shots_probabilities(self, expected_shots: float) -> dict:
        """Calcula probabilidades para diferentes rangos de remates"""
        return {
            'over_5': min(0.95, max(0.05, 0.7 + (expected_shots - 15) * 0.02)),
            'over_10': min(0.95, max(0.05, 0.5 + (expected_shots - 15) * 0.02)),
            'over_15': min(0.95, max(0.05, 0.3 + (expected_shots - 15) * 0.02)),
            'over_20': min(0.95, max(0.05, 0.1 + (expected_shots - 15) * 0.01)),
            'over_25': min(0.95, max(0.05, 0.05 + (expected_shots - 15) * 0.005))
        }
    
    def _calculate_shots_on_target_probabilities(self, expected_shots_on_target: float) -> dict:
        """Calcula probabilidades para diferentes rangos de remates a puerta"""
        return {
            'over_2': min(0.95, max(0.05, 0.7 + (expected_shots_on_target - 8) * 0.03)),
            'over_4': min(0.95, max(0.05, 0.5 + (expected_shots_on_target - 8) * 0.03)),
            'over_6': min(0.95, max(0.05, 0.3 + (expected_shots_on_target - 8) * 0.02)),
            'over_8': min(0.95, max(0.05, 0.1 + (expected_shots_on_target - 8) * 0.01)),
            'over_10': min(0.95, max(0.05, 0.05 + (expected_shots_on_target - 8) * 0.005))
        }
    
    def _fallback_prediction(self, prediction_type: str) -> dict:
        """Predicción de fallback cuando no hay datos suficientes"""
        fallback_values = {
            'shots_total': 15.0,
            'shots_home': 8.0,
            'shots_away': 7.0,
            'shots_on_target_total': 6.0
        }
        
        return {
            'model_name': 'Shots Prediction Model (Fallback)',
            'prediction': fallback_values.get(prediction_type, 10.0),
            'confidence': 0.3,
            'probabilities': {'over_5': 0.5, 'over_10': 0.3, 'over_15': 0.1, 'over_20': 0.05, 'over_25': 0.05},
            'total_matches': 0
        }

# Instancia global del modelo
shots_prediction_model = ShotsPredictionModel()

