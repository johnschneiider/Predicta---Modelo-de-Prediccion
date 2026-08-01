"""
Orquestador principal para integración Predicta + Matchbook.
"""

import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any

from django.conf import settings

from matchbook.client import MatchbookTradingBot
from betting.predictors import predict_1x2
from football_data.models import League

logger = logging.getLogger('matchbook_bot')


class PredictaMatchbookOrchestrator:
    """
    Orquestador que integra predicciones de Predicta con Matchbook Exchange.
    
    Flujo:
    1. Obtiene eventos de fútbol de Matchbook
    2. Predice resultados usando modelos de Predicta
    3. Compara probabilidades predichas vs cuotas de Matchbook
    4. Coloca apuestas cuando hay edge positivo
    """
    
    def __init__(self, username: str, password: str):
        """
        Inicializa orquestador.
        
        Args:
            username: Email de cuenta Matchbook
            password: Contraseña de cuenta Matchbook
        """
        self.bot = MatchbookTradingBot(username, password)
        self.connected = False
        self.leagues_cache = {}
        
    def connect(self) -> bool:
        """Conecta a Matchbook."""
        logger.info("Conectando a Matchbook Exchange...")
        self.connected = self.bot.connect()
        return self.connected
    
    def disconnect(self):
        """Desconecta de Matchbook."""
        if self.connected:
            self.bot.disconnect()
            self.connected = False
    
    def normalize_team_name(self, team_name: str) -> str:
        """
        Normaliza nombres de equipos para match con base de datos Predicta.
        
        Args:
            team_name: Nombre de equipo de Matchbook
        
        Returns:
            Nombre normalizado
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
    
    def find_corresponding_league(self, event_name: str, market_name: str) -> Optional[League]:
        """
        Encuentra la liga correspondiente en Predicta para un evento.
        
        Args:
            event_name: Nombre del evento
            market_name: Nombre del mercado
        
        Returns:
            Objeto League o None si no se encuentra
        """
        # Cache de ligas para mejor performance
        if not self.leagues_cache:
            leagues = League.objects.all()
            for league in leagues:
                self.leagues_cache[league.name.lower()] = league
        
        # Buscar pistas en event_name y market_name
        search_text = (event_name + " " + market_name).lower()
        
        # Buscar ligas por nombre
        for league_name, league_obj in self.leagues_cache.items():
            if league_name in search_text:
                logger.info(f"Liga encontrada: {league_name} en evento '{event_name}'")
                return league_obj
        
        # Fallback: usar Premier League
        premier_league = self.leagues_cache.get('premier league')
        if premier_league:
            logger.warning(f"Usando Premier League como fallback para evento: {event_name}")
            return premier_league
        
        return None
    
    def extract_teams_from_market(self, market: Dict[str, Any]) -> Optional[Dict[str, str]]:
        """
        Extrae nombres de equipos del mercado.
        
        Args:
            market: Diccionario de mercado de Matchbook
        
        Returns:
            Dict con home_team y away_team o None
        """
        try:
            event = market.get('event', {})
            event_name = event.get('name', '')
            
            # Intentar extraer del event_name
            if ' v ' in event_name:
                home, away = event_name.split(' v ')
                return {
                    'home_team': home.strip(),
                    'away_team': away.strip()
                }
            elif ' vs ' in event_name:
                home, away = event_name.split(' vs ')
                return {
                    'home_team': home.strip(),
                    'away_team': away.strip()
                }
                
            # Intentar extraer de runners del mercado
            runners = market.get('runners', [])
            if len(runners) >= 2 and market.get('name') == 'Match Odds':
                home_runner = runners[0].get('name', '')
                away_runner = runners[1].get('name', '')
                
                return {
                    'home_team': home_runner.strip(),
                    'away_team': away_runner.strip()
                }
                
        except Exception as e:
            logger.error(f"Error extrayendo equipos del mercado: {e}")
        
        return None
    
    def analyze_market(self, market: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Analiza un mercado para posible apuesta.
        
        Args:
            market: Mercado de Matchbook
        
        Returns:
            Dict con análisis o None si no aplica
        """
        try:
            # Solo analizar mercados Match Odds (1X2)
            if market.get('name') != 'Match Odds':
                return None
            
            # Extraer equipos
            teams = self.extract_teams_from_market(market)
            if not teams:
                return None
            
            home_team = self.normalize_team_name(teams['home_team'])
            away_team = self.normalize_team_name(teams['away_team'])
            
            # Encontrar liga correspondiente
            league = self.find_corresponding_league(
                market.get('event', {}).get('name', ''),
                market.get('name', '')
            )
            
            if not league:
                logger.warning(f"No se encontró liga para {home_team} vs {away_team}")
                return None
            
            # Predecir probabilidades con Predicta
            logger.info(f"Prediciendo: {home_team} vs {away_team} ({league.name})")
            prediction = predict_1x2(home_team, away_team, league)
            
            if not prediction:
                return None
            
            # Obtener cuotas de Matchbook
            runners = market.get('runners', [])
            
            # Buscar cuotas para cada resultado
            odds = {}
            for runner in runners:
                runner_name = runner.get('name', '').lower()
                prices = runner.get('prices', [])
                
                if not prices:
                    continue
                
                # Tomar mejor cuota disponible
                best_price = None
                for price in prices:
                    if price.get('odds'):
                        decimal_odds = price.get('decimal-odds')
                        if decimal_odds and (best_price is None or decimal_odds > best_price):
                            best_price = decimal_odds
                
                if best_price:
                    # Determinar tipo de resultado
                    if 'home' in runner_name or home_team.lower() in runner_name.lower():
                        odds['home'] = best_price
                    elif 'away' in runner_name or away_team.lower() in runner_name.lower():
                        odds['away'] = best_price
                    elif 'draw' in runner_name:
                        odds['draw'] = best_price
            
            if not odds:
                return None
            
            # Calcular edge para cada resultado
            edges = {}
            if 'home' in odds:
                edges['home'] = self.bot.calculate_edge(prediction['prob_local'], odds['home'])
            if 'away' in odds:
                edges['away'] = self.bot.calculate_edge(prediction['prob_visitante'], odds['away'])
            if 'draw' in odds:
                edges['draw'] = self.bot.calculate_edge(prediction['prob_empate'], odds['draw'])
            
            # Encontrar mejor edge
            best_edge = -1.0
            best_result = None
            best_odds = None
            
            for result_type, edge in edges.items():
                if edge > best_edge:
                    best_edge = edge
                    best_result = result_type
                    best_odds = odds[result_type]
            
            analysis = {
                'market_id': market.get('id'),
                'event_id': market.get('event', {}).get('id'),
                'home_team': home_team,
                'away_team': away_team,
                'league': league.name,
                'prediction': prediction,
                'odds': odds,
                'edges': edges,
                'best_edge': best_edge,
                'best_result': best_result,
                'best_odds': best_odds,
                'should_bet': best_edge >= getattr(settings, 'BETTING_MIN_EDGE', 0.05)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Error analizando mercado: {e}")
            return None
    
    def execute_trading_cycle(self, dry_run: bool = True):
        """
        Ejecuta un ciclo completo de trading.
        
        Args:
            dry_run: True para simular, False para apuestas reales
        """
        if not self.connected:
            logger.error("No conectado a Matchbook")
            return
        
        logger.info("=== INICIANDO CICLO DE TRADING ===")
        
        # Obtener mercados de fútbol
        markets = self.bot.find_soccer_markets()
        
        if not markets:
            logger.warning("No se encontraron mercados de fútbol")
            return
        
        logger.info(f"Analizando {len(markets)} mercados de fútbol")
        
        bets_placed = 0
        bets_identified = 0
        
        for market in markets:
            try:
                # Analizar mercado
                analysis = self.analyze_market(market)
                
                if not analysis:
                    continue
                
                logger.info(f"Mercado: {analysis['home_team']} vs {analysis['away_team']}")
                logger.info(f"  Predicción: L={analysis['prediction']['prob_local']:.1%} "
                          f"D={analysis['prediction']['prob_empate']:.1%} "
                          f"A={analysis['prediction']['prob_visitante']:.1%}")
                logger.info(f"  Cuotas: {analysis['odds']}")
                logger.info(f"  Edges: {analysis['edges']}")
                logger.info(f"  Mejor edge: {analysis['best_edge']:.1%} "
                          f"({analysis['best_result']} @ {analysis['best_odds']:.2f})")
                
                # Verificar si debe apostar
                if analysis['should_bet']:
                    bets_identified += 1
                    logger.info(f"  ✅ VALUE IDENTIFIED: {analysis['best_edge']:.1%} edge!")
                    
                    if not dry_run:
                        # Colocar apuesta real
                        runner_id = None
                        # Encontrar runner_id correspondiente al resultado
                        for runner in market.get('runners', []):
                            runner_name = runner.get('name', '').lower()
                            target_result = analysis['best_result']
                            
                            if (target_result == 'home' and 
                               ('home' in runner_name or analysis['home_team'].lower() in runner_name)):
                                runner_id = runner.get('id')
                                break
                            elif (target_result == 'away' and 
                                 ('away' in runner_name or analysis['away_team'].lower() in runner_name)):
                                runner_id = runner.get('id')
                                break
                            elif target_result == 'draw' and 'draw' in runner_name:
                                runner_id = runner.get('id')
                                break
                        
                        if runner_id:
                            # Calcular stake
                            balance = self.bot.client.get_account_balance()
                            available_balance = balance.get('available', 0) if balance else 100.0
                            stake_percent = getattr(settings, 'BETTING_STAKE_PERCENTAGE', 0.02)
                            max_stake = getattr(settings, 'BETTING_MAX_STAKE', 10.0)
                            
                            stake = min(available_balance * stake_percent, max_stake)
                            stake = max(stake, 2.0)  # Mínimo $2
                            
                            logger.info(f"  Colocando apuesta: {stake:.2f} @ {analysis['best_odds']:.2f}")
                            
                            # Determinar side (back o lay)
                            side = 'back'  # Por defecto back (apostar a que gana)
                            
                            bet_result = self.bot.client.place_bet(
                                market_id=analysis['market_id'],
                                runner_id=runner_id,
                                stake=stake,
                                odds=analysis['best_odds'],
                                side=side
                            )
                            
                            if bet_result:
                                bets_placed += 1
                                logger.info(f"  ✅ APUESTA COLOCADA EXITOSAMENTE")
                            else:
                                logger.error(f"  ❌ ERROR COLOCANDO APUESTA")
                    else:
                        logger.info(f"  [DRY RUN] Simulando apuesta (stake: ~$10)")
                
            except Exception as e:
                logger.error(f"Error procesando mercado: {e}")
                continue
        
        # Resumen del ciclo
        logger.info("=== RESUMEN CICLO ===")
        logger.info(f"Mercados analizados: {len(markets)}")
        logger.info(f"Valor identificado: {bets_identified}")
        if not dry_run:
            logger.info(f"Apuestas colocadas: {bets_placed}")
        logger.info("=====================")
    
    def run_continuous(self, interval_minutes: int = 30, dry_run: bool = True):
        """
        Ejecuta trading continuo.
        
        Args:
            interval_minutes: Minutos entre ciclos
            dry_run: True para simular, False para apuestas reales
        """
        logger.info(f"Iniciando trading continuo - Intervalo: {interval_minutes}min, Dry Run: {dry_run}")
        
        cycle_count = 0
        
        try:
            while True:
                cycle_count += 1
                cycle_start = datetime.now()
                
                logger.info(f"\n=== CICLO {cycle_count} - {cycle_start} ===")
                
                if not self.connected:
                    logger.info("Reconectando a Matchbook...")
                    self.connect()
                
                if self.connected:
                    self.execute_trading_cycle(dry_run=dry_run)
                else:
                    logger.error("No se pudo conectar a Matchbook")
                
                # Esperar para próximo ciclo
                cycle_end = datetime.now()
                cycle_duration = (cycle_end - cycle_start).total_seconds() / 60.0
                
                wait_minutes = max(1, interval_minutes - cycle_duration)
                logger.info(f"Ciclo completado en {cycle_duration:.1f}min. Esperando {wait_minutes:.1f}min...")
                
                time.sleep(wait_minutes * 60)
                
        except KeyboardInterrupt:
            logger.info("Trading detenido por usuario")
        except Exception as e:
            logger.error(f"Error fatal en trading continuo: {e}")
        finally:
            self.disconnect()