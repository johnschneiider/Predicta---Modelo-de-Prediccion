"""
Implementación del modelo Dixon-Coles para predicciones de fútbol
Mejora el modelo Poisson tradicional aplicando correcciones para marcadores bajos
"""

import numpy as np
from scipy.stats import poisson
from scipy.optimize import minimize
import logging
from typing import Dict, List, Tuple
from datetime import timedelta
from django.utils import timezone
from django.db import models as django_models
from football_data.models import Match, League

logger = logging.getLogger('ai_predictions')


class DixonColesModel:
    """
    Modelo Dixon-Coles para predicción de resultados de fútbol.
    
    El modelo Dixon-Coles es una extensión del modelo Poisson doble que introduce
    un parámetro de corrección (rho/tau) para ajustar las probabilidades de marcadores
    bajos, especialmente 0-0, 1-0, 0-1 y 1-1, que el modelo Poisson tradicional
    tiende a subestimar o sobrestimar.
    """
    
    def __init__(self, rho: float = -0.13):
        """
        Inicializa el modelo Dixon-Coles.
        
        Args:
            rho: Parámetro de corrección para marcadores bajos.
                 Valores típicos están entre -0.2 y 0.
                 Por defecto: -0.13 (valor comúnmente encontrado en fútbol)
        """
        self.rho = rho
        self.name = "Dixon-Coles"
        self.fitted_params = {}
    
    def tau_correction(self, home_goals: int, away_goals: int, lambda_home: float, 
                      lambda_away: float) -> float:
        """
        Factor de corrección τ (tau) de Dixon-Coles para marcadores bajos.
        
        Args:
            home_goals: Goles del equipo local
            away_goals: Goles del equipo visitante
            lambda_home: Tasa esperada de goles del local (Poisson)
            lambda_away: Tasa esperada de goles del visitante (Poisson)
        
        Returns:
            Factor de corrección multiplicativo
        """
        # Aplicar corrección solo para marcadores bajos
        if home_goals == 0 and away_goals == 0:
            return 1 - lambda_home * lambda_away * self.rho
        elif home_goals == 0 and away_goals == 1:
            return 1 + lambda_home * self.rho
        elif home_goals == 1 and away_goals == 0:
            return 1 + lambda_away * self.rho
        elif home_goals == 1 and away_goals == 1:
            return 1 - self.rho
        else:
            # Sin corrección para otros marcadores
            return 1.0
    
    def probability(self, home_goals: int, away_goals: int, lambda_home: float, 
                   lambda_away: float) -> float:
        """
        Calcula la probabilidad de un marcador específico usando Dixon-Coles.
        
        Args:
            home_goals: Goles del equipo local
            away_goals: Goles del equipo visitante
            lambda_home: Tasa esperada de goles del local
            lambda_away: Tasa esperada de goles del visitante
        
        Returns:
            Probabilidad del marcador
        """
        # Probabilidad base usando Poisson doble independiente
        poisson_prob = poisson.pmf(home_goals, lambda_home) * poisson.pmf(away_goals, lambda_away)
        
        # Aplicar corrección de Dixon-Coles
        tau = self.tau_correction(home_goals, away_goals, lambda_home, lambda_away)
        
        return poisson_prob * tau
    
    def calculate_lambda_parameters(self, home_team: str, away_team: str, league: League,
                                   is_goals: bool = True, original_prediction_type: str = 'goals_total') -> Tuple[float, float]:
        """
        Calcula los parámetros lambda (tasas de Poisson) para ambos equipos.
        
        Mejoras aplicadas:
        1. Piso de λ por liga: si el λ calculado es menor que el promedio real de la liga, usa el promedio.
        2. Mínimo de partidos por equipo: si un equipo tiene <10 partidos, usa el promedio de la liga.
        3. Fix bug defense: home_defense ahora usa goles RECIBIDOS como local, no goles marcados.
        """
        try:
            from .simple_models import get_league_realistic_limits, analyze_team_statistics
            
            if is_goals:
                prediction_type = 'goals'
            elif 'corners' in original_prediction_type:
                prediction_type = 'corners'
            else:
                prediction_type = 'shots'
            
            lambda_min, lambda_max = get_league_realistic_limits(league, prediction_type)
            
            home_stats = analyze_team_statistics(home_team, league, prediction_type)
            away_stats = analyze_team_statistics(away_team, league, prediction_type)
            
            cutoff_date = timezone.now().date() - timedelta(days=730)
            league_matches = Match.objects.filter(
                league=league,
                date__gte=cutoff_date
            ).order_by('-date')[:200]
            
            # ── Estadísticas de la liga ──
            if is_goals:
                league_home_avg = np.mean([m.fthg for m in league_matches if m.fthg is not None]) or 1.5
                league_away_avg = np.mean([m.ftag for m in league_matches if m.ftag is not None]) or 1.2
            else:
                league_home_avg = np.mean([m.hs for m in league_matches if m.hs is not None]) or 12.0
                league_away_avg = np.mean([m.as_field for m in league_matches if m.as_field is not None]) or 11.0
            
            # ── FIX 2: Mínimo de partidos por equipo ──
            # Si un equipo tiene <10 partidos en la BD, usar directamente el promedio de la liga
            MIN_MATCHES = 10
            
            if home_stats['home_matches'] >= MIN_MATCHES:
                home_attack = home_stats['home_avg']  # goles marcados como local
            else:
                home_attack = league_home_avg
                logger.info(f"[DC] {home_team}: solo {home_stats['home_matches']} partidos home (<{MIN_MATCHES}), usando liga avg={home_attack:.2f}")
            
            if away_stats['away_matches'] >= MIN_MATCHES:
                away_attack = away_stats['away_avg']  # goles marcados como visitante
            else:
                away_attack = league_away_avg
                logger.info(f"[DC] {away_team}: solo {away_stats['away_matches']} partidos away (<{MIN_MATCHES}), usando liga avg={away_attack:.2f}")
            
            # ── FIX 3: home_defense y away_defense deben ser goles RECIBIDOS, no marcados ──
            # home_defense = promedio de goles que el equipo local recibe cuando juega de local
            #   = ftag (goles del visitante) en partidos donde home_team es local
            # away_defense = promedio de goles que el equipo visitante recibe cuando juega de visitante  
            #   = fthg (goles del local) en partidos donde away_team es visitante
            
            # Calcular defense stats separadamente
            home_defense_matches = Match.objects.filter(
                league=league, home_team=home_team, date__gte=cutoff_date
            ).order_by('-date')[:30]
            away_defense_matches = Match.objects.filter(
                league=league, away_team=away_team, date__gte=cutoff_date
            ).order_by('-date')[:30]
            
            if is_goals:
                # Goles recibidos: local recibe goles del visitante (ftag), visitante recibe goles del local (fthg)
                home_defense_data = [m.ftag for m in home_defense_matches if m.ftag is not None]
                away_defense_data = [m.fthg for m in away_defense_matches if m.fthg is not None]
            else:
                home_defense_data = [m.as_field for m in home_defense_matches if m.as_field is not None]
                away_defense_data = [m.hs for m in away_defense_matches if m.hs is not None]
            
            home_defense = np.mean(home_defense_data) if home_defense_data and len(home_defense_data) >= MIN_MATCHES else league_away_avg
            away_defense = np.mean(away_defense_data) if away_defense_data and len(away_defense_data) >= MIN_MATCHES else league_home_avg
            
            # Calcular lambda usando el enfoque Dixon-Coles
            # FIX λ (walk-forward 2026-09-12, aplicado 2026-09-15 orden John):
            # divisores normalizados por el lado correcto — away_defense se mide en
            # goles de LOCAL (fthg) → dividir por media LOCAL; home_defense se mide en
            # goles de VISITANTE (ftag) → dividir por media VISITANTE.
            # Antes estaban cruzados → λ total inflado +20.5%.
            # Multiplicadores fijos 1.15/0.95 eliminados (agravaban la inflación).
            raw_lambda_home = home_attack * away_defense / league_home_avg
            raw_lambda_away = away_attack * home_defense / league_away_avg
            
            # ── FIX 1: Piso de λ por liga ──
            # Si el λ calculado es menor que el promedio real de la liga, usar el promedio de liga como piso
            # (evita que equipos con pocos datos arrastren el λ a valores irreales)
            if is_goals:
                league_total_avg = league_home_avg + league_away_avg
                if raw_lambda_home + raw_lambda_away < league_total_avg:
                    # Si el total está por debajo del promedio de liga, escalar ambos proporcionalmente al promedio
                    scale = league_total_avg / (raw_lambda_home + raw_lambda_away) if (raw_lambda_home + raw_lambda_away) > 0 else 1.0
                    raw_lambda_home *= scale
                    raw_lambda_away *= scale
                    logger.info(f"[DC] Piso de liga aplicado: total {raw_lambda_home + raw_lambda_away:.2f} < {league_total_avg:.2f}, escalado")
            
            # Aplicar límites calculados dinámicamente
            lambda_home = max(lambda_min, min(lambda_max, raw_lambda_home))
            lambda_away = max(lambda_min, min(lambda_max, raw_lambda_away))
            
            logger.info(f"Dixon-Coles Lambda {home_team}: {raw_lambda_home:.2f} → {lambda_home:.2f} "
                       f"(límites: {lambda_min:.2f}-{lambda_max:.2f})")
            logger.info(f"Dixon-Coles Lambda {away_team}: {raw_lambda_away:.2f} → {lambda_away:.2f} "
                       f"(límites: {lambda_min:.2f}-{lambda_max:.2f})")
            
            return lambda_home, lambda_away
            
        except Exception as e:
            logger.error(f"Error calculando parámetros lambda Dixon-Coles: {e}")
            if is_goals:
                return 1.5, 1.2
            else:
                return 12.0, 11.0
    
    def optimize_rho(self, matches: List[Match], is_goals: bool = True, max_iter: int = 100) -> float:
        """
        Optimiza el parámetro rho usando máxima verosimilitud.
        
        Args:
            matches: Lista de partidos históricos
            is_goals: True para goles, False para otros eventos
            max_iter: Número máximo de iteraciones para la optimización
        
        Returns:
            Valor óptimo de rho
        """
        try:
            if len(matches) < 20:
                logger.warning("Pocos datos para optimización, usando rho por defecto")
                return -0.13
            
            def negative_log_likelihood(rho_candidate):
                """Función objetivo para minimización"""
                self.rho = rho_candidate
                total_log_likelihood = 0
                
                for match in matches:
                    try:
                        # Calcular lambdas para este partido
                        lambda_home, lambda_away = self.calculate_lambda_parameters(
                            match.home_team, match.away_team, match.league, is_goals
                        )
                        
                        # Resultado real
                        if is_goals:
                            home_score = match.fthg or 0
                            away_score = match.ftag or 0
                        else:
                            home_score = match.hs or 0
                            away_score = match.as_field or 0
                        
                        # Limitar marcadores para evitar desbordamiento
                        home_score = min(home_score, 10)
                        away_score = min(away_score, 10)
                        
                        # Calcular probabilidad del resultado
                        prob = self.probability(home_score, away_score, lambda_home, lambda_away)
                        
                        # Evitar log(0)
                        if prob > 0:
                            total_log_likelihood += np.log(prob)
                        
                    except Exception as e:
                        continue
                
                return -total_log_likelihood  # Negativo para minimización
            
            # Optimizar rho en un rango razonable
            result = minimize(
                negative_log_likelihood,
                x0=[-0.13],
                bounds=[(-0.5, 0.2)],
                method='L-BFGS-B',
                options={'maxiter': max_iter}
            )
            
            optimal_rho = result.x[0]
            logger.info(f"Rho optimizado: {optimal_rho:.4f}")
            
            return optimal_rho
            
        except Exception as e:
            logger.error(f"Error optimizando rho: {e}")
            return -0.13  # Valor por defecto
    
    def predict_match(self, home_team: str, away_team: str, league: League,
                     prediction_type: str = 'goals_total') -> Dict:
        """
        Predice un partido usando el modelo Dixon-Coles.
        
        Args:
            home_team: Nombre del equipo local
            away_team: Nombre del equipo visitante
            league: Liga del partido
            prediction_type: Tipo de predicción
        
        Returns:
            Diccionario con la predicción y probabilidades
        """
        try:
            is_goals = 'goals' in prediction_type or prediction_type == 'both_teams_score'
            
            # Calcular lambdas
            lambda_home, lambda_away = self.calculate_lambda_parameters(
                home_team, away_team, league, is_goals, prediction_type
            )
            
            # Calcular predicción base
            if prediction_type in ['goals_total', 'shots_total']:
                prediction = lambda_home + lambda_away
            elif prediction_type in ['goals_home', 'shots_home']:
                prediction = lambda_home
            elif prediction_type in ['goals_away', 'shots_away']:
                prediction = lambda_away
            elif prediction_type == 'both_teams_score':
                # Probabilidad de que ambos equipos marquen al menos 1 gol
                max_goals = 8
                
                # P(local no marca) = suma de P(0, i) para i = 0 a max_goals
                prob_home_no_score = sum(
                    self.probability(0, away_score, lambda_home, lambda_away)
                    for away_score in range(max_goals + 1)
                )
                
                # P(visitante no marca) = suma de P(i, 0) para i = 0 a max_goals
                prob_away_no_score = sum(
                    self.probability(home_score, 0, lambda_home, lambda_away)
                    for home_score in range(max_goals + 1)
                )
                
                # P(ninguno marca) = P(0, 0)
                prob_none_score = self.probability(0, 0, lambda_home, lambda_away)
                
                # P(ambos marcan) = 1 - P(local no marca) - P(visitante no marca) + P(ninguno marca)
                # (Principio de inclusión-exclusión)
                raw_prediction = 1.0 - prob_home_no_score - prob_away_no_score + prob_none_score
                
                # CALIBRACIÓN CRÍTICA: Ajustar probabilidades sobreconfiadas
                # En fútbol real, "ambos marcan" ocurre ~45-55% de las veces
                # Aplicar transformación logística para calibración
                import math
                
                # Si la predicción es muy alta (>0.8), aplicar calibración agresiva
                if raw_prediction > 0.8:
                    # Transformación logística inversa: logit(p) = ln(p/(1-p))
                    # Luego aplicar factor de calibración
                    logit_raw = math.log(raw_prediction / (1 - raw_prediction + 1e-10))
                    # Reducir la confianza aplicando factor de 0.6
                    logit_calibrated = logit_raw * 0.6
                    # Convertir de vuelta a probabilidad
                    prediction = 1 / (1 + math.exp(-logit_calibrated))
                elif raw_prediction > 0.7:
                    # Calibración moderada para predicciones altas
                    prediction = raw_prediction * 0.85
                else:
                    # Mantener predicciones moderadas sin cambios
                    prediction = raw_prediction
                
                # Límites finales: entre 0.15 y 0.75 (más realista para fútbol)
                prediction = max(0.15, min(0.75, prediction))
            else:
                prediction = lambda_home + lambda_away
            
            # Calcular probabilidades para diferentes marcadores
            probabilities = self._calculate_probabilities(
                lambda_home, lambda_away, prediction_type
            )
            
            # Calcular distribución de resultados (1X2)
            match_outcome = self._calculate_match_outcome(lambda_home, lambda_away)
            
            # Confianza basada en cantidad de datos
            cutoff_date = timezone.now().date() - timedelta(days=730)
            home_matches_count = Match.objects.filter(
                league=league, home_team=home_team, date__gte=cutoff_date
            ).count()
            away_matches_count = Match.objects.filter(
                league=league, away_team=away_team, date__gte=cutoff_date
            ).count()
            
            total_matches = home_matches_count + away_matches_count
            confidence = min(0.92, max(0.4, total_matches / 40))
            
            return {
                'model_name': 'Dixon-Coles',
                'prediction': prediction,
                'confidence': confidence,
                'probabilities': probabilities,
                'total_matches': total_matches
            }
            
        except Exception as e:
            logger.error(f"Error en predicción Dixon-Coles: {e}")
            return self._fallback_prediction(prediction_type)
    
    def _calculate_probabilities(self, lambda_home: float, lambda_away: float,
                                prediction_type: str) -> Dict:
        """Calcula probabilidades para diferentes umbrales"""
        probabilities = {}
        
        # Manejo especial para "both_teams_score"
        if prediction_type == 'both_teams_score':
            # Probabilidad de que ambos equipos marquen al menos 1 gol
            max_goals = 8
            
            # P(ambos marcan) = 1 - P(local no marca) - P(visitante no marca) + P(ninguno marca)
            prob_home_no_score = sum(
                self.probability(0, away_score, lambda_home, lambda_away)
                for away_score in range(max_goals + 1)
            )
            prob_away_no_score = sum(
                self.probability(home_score, 0, lambda_home, lambda_away)
                for home_score in range(max_goals + 1)
            )
            prob_none_score = self.probability(0, 0, lambda_home, lambda_away)
            
            prob_both_score = 1.0 - prob_home_no_score - prob_away_no_score + prob_none_score
            probabilities['both_score'] = min(1.0, max(0.0, prob_both_score))
            
            # También calcular over_1 (al menos 2 goles totales) para compatibilidad
            prob_over_1 = 0.0
            for home_score in range(max_goals + 1):
                for away_score in range(max_goals + 1):
                    if home_score + away_score > 1:
                        prob_over_1 += self.probability(
                            home_score, away_score, lambda_home, lambda_away
                        )
            probabilities['over_1'] = min(1.0, max(0.0, prob_over_1))
            
            return probabilities
        
        if 'goals' in prediction_type:
            thresholds = [1, 2, 3, 4, 5]
            max_goals = 8
        elif 'shots' in prediction_type:
            thresholds = [10, 15, 20, 25, 30]
            max_goals = 35
        else:
            thresholds = [1, 2, 3, 4, 5]
            max_goals = 8
        
        for threshold in thresholds:
            if 'total' in prediction_type:
                # Probabilidad de over X goles/remates totales
                prob_over = 0.0
                for home_score in range(max_goals + 1):
                    for away_score in range(max_goals + 1):
                        if home_score + away_score > threshold:
                            prob_over += self.probability(
                                home_score, away_score, lambda_home, lambda_away
                            )
                probabilities[f'over_{threshold}'] = min(1.0, max(0.0, prob_over))
                
            elif 'home' in prediction_type:
                # Probabilidad de over X para equipo local
                prob_over = 0.0
                for home_score in range(threshold + 1, max_goals + 1):
                    for away_score in range(max_goals + 1):
                        prob_over += self.probability(
                            home_score, away_score, lambda_home, lambda_away
                        )
                probabilities[f'over_{threshold}'] = min(1.0, max(0.0, prob_over))
                
            elif 'away' in prediction_type:
                # Probabilidad de over X para equipo visitante
                prob_over = 0.0
                for home_score in range(max_goals + 1):
                    for away_score in range(threshold + 1, max_goals + 1):
                        prob_over += self.probability(
                            home_score, away_score, lambda_home, lambda_away
                        )
                probabilities[f'over_{threshold}'] = min(1.0, max(0.0, prob_over))
        
        return probabilities
    
    def _calculate_match_outcome(self, lambda_home: float, lambda_away: float) -> Dict:
        """
        Calcula probabilidades de victoria local (1), empate (X) y victoria visitante (2)
        """
        prob_home_win = 0.0
        prob_draw = 0.0
        prob_away_win = 0.0
        
        max_goals = 8
        
        for home_score in range(max_goals + 1):
            for away_score in range(max_goals + 1):
                prob = self.probability(home_score, away_score, lambda_home, lambda_away)
                
                if home_score > away_score:
                    prob_home_win += prob
                elif home_score == away_score:
                    prob_draw += prob
                else:
                    prob_away_win += prob
        
        return {
            'home_win': min(1.0, max(0.0, prob_home_win)),
            'draw': min(1.0, max(0.0, prob_draw)),
            'away_win': min(1.0, max(0.0, prob_away_win))
        }
    
    def _fallback_prediction(self, prediction_type: str) -> Dict:
        """Predicción de fallback para errores"""
        if 'goals' in prediction_type:
            default_prediction = 2.7 if 'total' in prediction_type else 1.5
            probabilities = {'over_1': 0.75, 'over_2': 0.55, 'over_3': 0.3, 'over_4': 0.12, 'over_5': 0.04}
        else:
            default_prediction = 23.0 if 'total' in prediction_type else 12.0
            probabilities = {'over_10': 0.7, 'over_15': 0.5, 'over_20': 0.3, 'over_25': 0.12, 'over_30': 0.04}
        
        return {
            'model_name': 'Dixon-Coles (Fallback)',
            'prediction': default_prediction,
            'confidence': 0.3,
            'probabilities': probabilities,
            'total_matches': 0
        }
    
    def calculate_exact_score_probabilities(self, lambda_home: float, lambda_away: float,
                                          max_goals: int = 6) -> Dict:
        """
        Calcula probabilidades para marcadores exactos usando Dixon-Coles.
        
        Args:
            lambda_home: Tasa de goles del local
            lambda_away: Tasa de goles del visitante
            max_goals: Máximo de goles a considerar por equipo
        
        Returns:
            Diccionario con probabilidades de marcadores exactos
        """
        score_probs = {}
        
        for home_goals in range(max_goals + 1):
            for away_goals in range(max_goals + 1):
                prob = self.probability(home_goals, away_goals, lambda_home, lambda_away)
                score_probs[f"{home_goals}-{away_goals}"] = prob
        
        # Ordenar por probabilidad descendente
        sorted_scores = dict(sorted(score_probs.items(), key=lambda x: x[1], reverse=True))
        
        return sorted_scores


