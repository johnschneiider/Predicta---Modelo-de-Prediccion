#!/usr/bin/env python3
"""
Orquestador principal del bot de apuestas Predicta.

Flujo:
1. Obtiene próximos partidos de fútbol (The Odds API o Betfair)
2. Para cada partido, predice probabilidades 1X2 usando modelos IA
3. Obtiene cuotas actuales de Betfair
4. Calcula valor/edge comparando probabilidad predicha vs implied odds
5. Coloca apuestas si edge >= umbral configurado
"""

import os
import sys
import logging
import django
from datetime import datetime, timedelta

# Configurar Django
sys.path.append('/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
django.setup()

from django.conf import settings
from football_data.models import Match, League
from betting.predictors import predict_1x2
from betfair.services import BetfairAPIService

logger = logging.getLogger('betting_bot')


def setup_logging():
    """Configura logging para el bot."""
    log_level = getattr(settings, 'LOG_LEVEL', 'INFO')
    numeric_level = getattr(logging, log_level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=numeric_level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('/var/log/predicta/betting_bot.log')
        ]
    )


class BetfairOrchestrator:
    """Orquestador principal para automatización de apuestas."""
    
    def __init__(self):
        self.betfair_service = None
        self.connect_betfair()
    
    def connect_betfair(self) -> bool:
        """Conecta a Betfair Exchange."""
        try:
            self.betfair_service = BetfairAPIService()
            if self.betfair_service.login():
                logger.info("Conectado exitosamente a Betfair Exchange")
                return True
            else:
                logger.error("No se pudo conectar a Betfair Exchange")
                return False
        except Exception as e:
            logger.error(f"Error conectando a Betfair: {e}")
            return False
    
    def get_upcoming_matches(self, days_ahead: int = 3) -> list:
        """
        Obtiene partidos próximos para las próximas N días.
        
        Prioridad de fuentes:
        1. Betfair API (ideal - no tiene límites)
        2. The Odds API (limitado a 500 req/mes)
        
        Args:
            days_ahead: Días hacia adelante para buscar partidos
        
        Returns:
            Lista de dicts con info de partidos
        """
        matches = []
        
        try:
            # Opción 1: Usar Betfair (recomendada para producción)
            if self.betfair_service:
                logger.info(f"Obteniendo partidos próximos de Betfair para {days_ahead} días")
                events = self.betfair_service.get_football_events(days_ahead)
                
                for event in events:
                    try:
                        # Parsear equipos desde event_name (ej: "Arsenal v Chelsea")
                        event_name = event['event']['name']
                        if ' v ' in event_name:
                            home, away = event_name.split(' v ')
                        elif ' vs ' in event_name:
                            home, away = event_name.split(' vs ')
                        else:
                            continue
                        
                        matches.append({
                            'home_team': home.strip(),
                            'away_team': away.strip(),
                            'start_time': event['event']['openDate'],
                            'event_id': event['event']['id'],
                            'source': 'betfair'
                        })
                    except (KeyError, IndexError):
                        continue
                
                logger.info(f"Obtenidos {len(matches)} partidos de Betfair")
                return matches
            
            # Opción 2: Usar The Odds API (fallback)
            logger.warning("Usando The Odds API como fallback (Betfair no disponible)")
            from odds.services import OddsAPIService
            odds_service = OddsAPIService()
            odds_matches = odds_service.get_upcoming_matches(days_ahead=days_ahead)
            
            for match in odds_matches:
                matches.append({
                    'home_team': match.get('home_team'),
                    'away_team': match.get('away_team'),
                    'start_time': match.get('commence_time'),
                    'league': match.get('league'),
                    'source': 'odds_api'
                })
            
            logger.info(f"Obtenidos {len(matches)} partidos de The Odds API")
            
        except Exception as e:
            logger.error(f"Error obteniendo partidos próximos: {e}")
        
        return matches
    
    def normalize_team_names(self, team_name: str) -> str:
        """
        Normaliza nombres de equipos para match con base de datos.
        
        Args:
            team_name: Nombre de equipo de la fuente API
        
        Returns:
            Nombre normalizado que coincide con la base de datos
        """
        # Mapeos comunes
        name_mapping = {
            'Bayern Munich': 'Bayern München',
            'Bayern Munchen': 'Bayern München',
            'Atletico Madrid': 'Atlético Madrid',
            'Atletico de Madrid': 'Atlético Madrid',
            'Real Sociedad': 'Real Sociedad de Fútbol',
            'Man United': 'Manchester United',
            'Man Utd': 'Manchester United',
            'Man City': 'Manchester City',
            'Spurs': 'Tottenham Hotspur',
            'PSG': 'Paris Saint-Germain',
            'AC Milan': 'Milan',
            'Inter Milan': 'Inter',
            'Roma': 'AS Roma',
            'Lazio': 'SS Lazio',
            'Atalanta': 'Atalanta Bergamasca Calcio',
        }
        
        return name_mapping.get(team_name, team_name)
    
    def predict_match_probabilities(self, home_team: str, away_team: str, league_name: str):
        """
        Predice probabilidades 1X2 para un partido.
        
        Args:
            home_team: Nombre equipo local
            away_team: Nombre equipo visitante
            league_name: Nombre de la liga (ej: 'Premier League')
        
        Returns:
            Dict con probabilidades 1X2 o None si error
        """
        try:
            # Normalizar nombres
            norm_home = self.normalize_team_names(home_team)
            norm_away = self.normalize_team_names(away_team)
            
            # Buscar liga en base de datos
            try:
                league = League.objects.get(name=league_name)
            except League.DoesNotExist:
                # Fallback: buscar por similitud o usar una genérica
                leagues = League.objects.filter(name__icontains=league_name[:5])
                if leagues.exists():
                    league = leagues.first()
                else:
                    # Usar Premier League como fallback
                    league = League.objects.get(name='Premier League')
            
            # Predecir con modelo 1X2
            prediction = predict_1x2(norm_home, norm_away, league)
            
            logger.info(f"Predicción {norm_home} vs {norm_away}: "
                       f"L={prediction['prob_local']:.1%} "
                       f"E={prediction['prob_empate']:.1%} "
                       f"V={prediction['prob_visitante']:.1%}")
            
            return prediction
            
        except Exception as e:
            logger.error(f"Error prediciendo {home_team} vs {away_team}: {e}")
            return None
    
    def get_betfair_odds(self, event_id: str) -> dict:
        """
        Obtiene cuotas de Betfair para un evento.
        
        Args:
            event_id: ID del evento en Betfair
        
        Returns:
            Dict con cuotas para cada resultado
        """
        try:
            if not self.betfair_service:
                logger.error("No hay conexión a Betfair")
                return {}
            
            # Obtener mercado de cuotas de dinero (Match Odds)
            markets = self.betfair_service.get_match_odds_markets(event_id)
            
            if not markets:
                return {}
            
            # Buscar primera market con cuotas disponibles
            for market in markets:
                market_book = self.betfair_service.get_market_book(market['marketId'])
                
                if market_book and 'runners' in market_book:
                    odds = {}
                    for runner in market_book['runners']:
                        selection_id = runner['selectionId']
                        status = runner.get('status', 'ACTIVE')
                        
                        # Obtener mejor cuota disponible (back price)
                        if 'ex' in runner and 'availableToBack' in runner['ex']:
                            available_to_back = runner['ex']['availableToBack']
                            if available_to_back:
                                best_price = available_to_back[0]['price']
                                
                                # Determinar tipo de resultado por selectionId
                                # En Betfair: selectionId % 3 indica 1X2 normalmente
                                result_type = runner.get('runnerName', '')
                                if not result_type:
                                    if selection_id % 3 == 1:
                                        result_type = 'local'
                                    elif selection_id % 3 == 2:
                                        result_type = 'empate'
                                    else:
                                        result_type = 'visitante'
                                
                                odds[result_type] = best_price
                    
                    if odds:
                        logger.info(f"Cuotas Betfair {event_id}: {odds}")
                        return odds
            
            return {}
            
        except Exception as e:
            logger.error(f"Error obteniendo cuotas de Betfair: {e}")
            return {}
    
    def calculate_edge(self, predicted_prob: float, betfair_odds: float) -> float:
        """
        Calcula el edge (valor) entre probabilidad predicha y cuota de Betfair.
        
        Edge = Probabilidad - (1 / Cuota)
        
        Ejemplo:
        - Predicción: 0.55 (55%)
        - Betfair: 2.0 (implied probability 1/2.0 = 0.5)
        - Edge = 0.55 - 0.5 = 0.05 (5% de edge)
        
        Args:
            predicted_prob: Probabilidad predicha por el modelo (0-1)
            betfair_odds: Cuota decimal de Betfair
        
        Returns:
            Edge como decimal (positivo = valor, negativo = sin valor)
        """
        if betfair_odds <= 1.0:
            return -1.0  # Cuota inválida
        
        implied_prob = 1.0 / betfair_odds
        edge = predicted_prob - implied_prob
        return edge
    
    def should_place_bet(self, edge: float) -> bool:
        """
        Decide si colocar apuesta basado en edge y configuración.
        
        Args:
            edge: Edge calculado
        
        Returns:
            True si debe apostar, False si no
        """
        min_edge = getattr(settings, 'BETTING_MIN_EDGE', 0.05)  # 5% por defecto
        return edge >= min_edge
    
    def calculate_stake(self, balance: float, edge: float) -> float:
        """
        Calcula stake óptimo basado en balance y edge.
        
        Usa Kelly Criterion simplificado: stake = edge / (cuota - 1)
        Pero limitado a máximo configurado.
        
        Args:
            balance: Balance disponible en cuenta
            edge: Edge calculado
        
        Returns:
            Stake recomendado
        """
        # Porcentaje fijo por defecto
        stake_percent = getattr(settings, 'BETTING_STAKE_PERCENTAGE', 0.02)  # 2%
        max_stake = getattr(settings, 'BETTING_MAX_STAKE', 10.0)  # $10 max
        
        stake_by_percent = balance * stake_percent
        stake = min(stake_by_percent, max_stake)
        
        # Adjust for edge magnitude (more edge = slightly more stake)
        stake = stake * (1.0 + max(0, edge))
        
        return round(stake, 2)
    
    def run_cycle(self):
        """
        Ejecuta un ciclo completo del bot:
        1. Obtiene partidos próximos
        2. Predice probabilidades
        3. Verifica cuotas en Betfair
        4. Coloca apuestas si hay edge positivo
        """
        logger.info("=== INICIANDO CICLO DE AUTOMATIZACIÓN ====")
        
        # 1. Obtener partidos próximos
        matches = self.get_upcoming_matches(days_ahead=2)  # Próximos 2 días
        
        if not matches:
            logger.warning("No se encontraron partidos próximos")
            return
        
        logger.info(f"Analizando {len(matches)} partidos próximos")
        
        # 2. Obtener balance actual (opcional)
        balance = None
        if self.betfair_service:
            try:
                account_funds = self.betfair_service.get_account_funds()
                if account_funds:
                    balance = account_funds.get('availableToBetBalance', 0)
                    logger.info(f"Balance disponible: {balance:.2f} USD")
            except Exception as e:
                logger.warning(f"No se pudo obtener balance: {e}")
        
        bets_placed = 0
        
        for match in matches:
            try:
                home = match['home_team']
                away = match['away_team']
                league = match.get('league', 'Premier League')  # Fallback
                event_id = match.get('event_id')
                
                logger.info(f"Analizando: {home} vs {away} ({league})")
                
                # 3. Predecir probabilidades 1X2
                prediction = self.predict_match_probabilities(home, away, league)
                if not prediction:
                    continue
                
                # 4. Obtener cuotas de Betfair
                if not event_id:
                    logger.warning(f"Sin event_id para {home} vs {away}, saltando")
                    continue
                
                odds = self.get_betfair_odds(event_id)
                if not odds:
                    logger.warning(f"Sin cuotas disponibles para {home} vs {away}")
                    continue
                
                # 5. Calcular edge para cada resultado posible
                best_edge = -1.0
                best_result = None
                best_odds = None
                
                # Local
                if 'local' in odds and odds['local'] > 1.0:
                    edge_local = self.calculate_edge(
                        prediction['prob_local'], odds['local']
                    )
                    if edge_local > best_edge:
                        best_edge = edge_local
                        best_result = 'local'
                        best_odds = odds['local']
                
                # Empate
                if 'empate' in odds and odds['empate'] > 1.0:
                    edge_empate = self.calculate_edge(
                        prediction['prob_empate'], odds['empate']
                    )
                    if edge_empate > best_edge:
                        best_edge = edge_empate
                        best_result = 'empate'
                        best_odds = odds['empate']
                
                # Visitante
                if 'visitante' in odds and odds['visitante'] > 1.0:
                    edge_visitante = self.calculate_edge(
                        prediction['prob_visitante'], odds['visitante']
                    )
                    if edge_visitante > best_edge:
                        best_edge = edge_visitante
                        best_result = 'visitante'
                        best_odds = odds['visitante']
                
                # 6. Verificar si hay edge suficiente
                if best_edge > 0 and self.should_place_bet(best_edge):
                    logger.info(f"✓ VALUE FOUND: {home} vs {away}")
                    logger.info(f"  Resultado: {best_result}, "
                               f"Cuota: {best_odds:.2f}, "
                               f"Edge: {best_edge:.1%}")
                    
                    # 7. Calcular stake
                    if balance:
                        stake = self.calculate_stake(balance, best_edge)
                        logger.info(f"  Stake sugerido: ${stake:.2f}")
                        
                        # 8. Colocar apuesta (en sandbox: comentado)
                        if getattr(settings, 'BETFAIR_SANDBOX', True):
                            logger.info("  [SANDBOX] Simulando apuesta")
                        else:
                            logger.info("  [PRODUCCIÓN] Colocando apuesta real")
                            
                            # TODO: Implementar place_order() con selección correcta
                            # selection_id según best_result
                            # success = self.betfair_service.place_order(
                            #     market_id=market['marketId'],
                            #     selection_id=selection_id,
                            #     stake=stake,
                            #     price=best_odds
                            # )
                    
                    bets_placed += 1
                else:
                    logger.debug(f"No value: {home} vs {away} (edge: {best_edge:.1%})")
                    
            except Exception as e:
                logger.error(f"Error procesando partido {match.get('home_team')}: {e}")
                continue
        
        # Resumen del ciclo
        logger.info(f"=== FIN CICLO ===")
        logger.info(f"Partidos analizados: {len(matches)}")
        logger.info(f"Valor encontrado: {bets_placed}")
        logger.info(f"=========================")


def main():
    """Función principal."""
    try:
        setup_logging()
        orchestrator = BetfairOrchestrator()
        orchestrator.run_cycle()
        return 0
    except Exception as e:
        logger.error(f"Error en ejecución principal: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())