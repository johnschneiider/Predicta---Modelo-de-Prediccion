"""
Cliente Python para la API de Matchbook Exchange.
Basado en documentación oficial: https://developers.matchbook.com/docs
"""

import requests
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger('matchbook')


class MatchbookAPIClient:
    """Cliente para interactuar con la API de Matchbook."""
    
    def __init__(self, username: str = None, password: str = None):
        """
        Inicializa cliente de Matchbook API.
        
        Args:
            username: Email de cuenta Matchbook
            password: Contraseña de cuenta Matchbook
        """
        self.base_url = "https://api.matchbook.com"
        self.session = requests.Session()
        self.session_token = None
        self.username = username
        self.password = password
        
        # Configurar headers por defecto
        self.session.headers.update({
            'Accept': 'application/json',
            'Content-Type': 'application/json',
            'Accept-Encoding': 'gzip',
            'User-Agent': 'PredictaBot/1.0',
        })
    
    def login(self, username: str = None, password: str = None) -> bool:
        """
        Inicia sesión en Matchbook API.
        
        Args:
            username: Email de cuenta (opcional, usa self.username si no se proporciona)
            password: Contraseña (opcional, usa self.password si no se proporciona)
        
        Returns:
            bool: True si login exitoso, False en caso contrario
        """
        username = username or self.username
        password = password or self.password
        
        if not username or not password:
            logger.error("Se requieren username y password para login")
            return False
        
        login_url = f"{self.base_url}/bpapi/rest/security/session"
        
        login_data = {
            'username': username,
            'password': password
        }
        
        try:
            response = self.session.post(
                login_url,
                json=login_data,
                timeout=10
            )
            
            logger.info(f"Login status: {response.status_code}")
            
            if response.status_code == 200:
                # Extraer session token de cookie
                if 'session-token' in response.cookies:
                    self.session_token = response.cookies['session-token']
                    logger.info("Login exitoso - Session token obtenido")
                    
                    # También guardar en headers para futuras requests
                    self.session.headers.update({
                        'session-token': self.session_token
                    })
                
                # Verificar respuesta JSON
                try:
                    data = response.json()
                    logger.info(f"Login response: {data}")
                except:
                    pass
                
                return True
                
            else:
                # Mostrar error detallado
                try:
                    error_data = response.json()
                    logger.error(f"Login error: {error_data}")
                except:
                    logger.error(f"Login failed with status: {response.status_code}")
                
                return False
                
        except Exception as e:
            logger.error(f"Error durante login: {e}")
            return False
    
    def get_account_balance(self) -> Optional[Dict[str, Any]]:
        """
        Obtiene balance de la cuenta.
        
        Returns:
            Dict con información de balance o None si error
        """
        if not self.session_token:
            logger.error("No hay sesión activa. Login primero.")
            return None
        
        balance_url = f"{self.base_url}/bpapi/rest/account/balance"
        
        try:
            response = self.session.get(balance_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Balance obtenido: {data}")
                return data
            else:
                logger.error(f"Error obteniendo balance: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo balance: {e}")
            return None
    
    def get_sports(self) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene lista de deportes disponibles.
        
        Returns:
            Lista de deportes o None si error
        """
        if not self.session_token:
            logger.error("No hay sesión activa. Login primero.")
            return None
        
        sports_url = f"{self.base_url}/edge/rest/v2/offers"
        
        try:
            response = self.session.get(sports_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Deportes obtenidos: {len(data.get('offers', []))} items")
                return data
            else:
                logger.error(f"Error obteniendo deportes: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo deportes: {e}")
            return None
    
    def get_events(self, sport_id: str = None, market_type: str = None) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene eventos para un deporte específico.
        
        Args:
            sport_id: ID del deporte (ej: 'soccer')
            market_type: Tipo de mercado (ej: 'match_odds')
        
        Returns:
            Lista de eventos o None si error
        """
        if not self.session_token:
            logger.error("No hay sesión activa. Login primero.")
            return None
        
        params = {}
        if sport_id:
            params['sport-ids'] = sport_id
        if market_type:
            params['market-types'] = market_type
        
        events_url = f"{self.base_url}/edge/rest/v2/events"
        
        try:
            response = self.session.get(events_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                events = data.get('events', [])
                logger.info(f"Eventos obtenidos: {len(events)} eventos")
                return events
            else:
                logger.error(f"Error obteniendo eventos: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo eventos: {e}")
            return None
    
    def get_markets(self, event_id: str) -> Optional[List[Dict[str, Any]]]:
        """
        Obtiene mercados para un evento específico.
        
        Args:
            event_id: ID del evento
        
        Returns:
            Lista de mercados o None si error
        """
        if not self.session_token:
            logger.error("No hay sesión activa. Login primero.")
            return None
        
        markets_url = f"{self.base_url}/edge/rest/v2/events/{event_id}/markets"
        
        try:
            response = self.session.get(markets_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                markets = data.get('markets', [])
                logger.info(f"Mercados obtenidos para evento {event_id}: {len(markets)} mercados")
                return markets
            else:
                logger.error(f"Error obteniendo mercados: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo mercados: {e}")
            return None
    
    def get_odds(self, market_id: str) -> Optional[Dict[str, Any]]:
        """
        Obtiene cuotas para un mercado específico.
        
        Args:
            market_id: ID del mercado
        
        Returns:
            Diccionario con cuotas o None si error
        """
        if not self.session_token:
            logger.error("No hay sesión activa. Login primero.")
            return None
        
        odds_url = f"{self.base_url}/edge/rest/v2/markets/{market_id}"
        
        try:
            response = self.session.get(odds_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Cuotas obtenidas para mercado {market_id}")
                return data
            else:
                logger.error(f"Error obteniendo cuotas: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo cuotas: {e}")
            return None
    
    def place_bet(self, market_id: str, runner_id: str, stake: float, 
                  odds: float, side: str = 'back') -> Optional[Dict[str, Any]]:
        """
        Coloca una apuesta (oferta) en Matchbook.
        
        Args:
            market_id: ID del mercado
            runner_id: ID del runner/selection
            stake: Cantidad a apostar
            odds: Cuota deseada
            side: 'back' (apostar a que gana) o 'lay' (apostar a que pierde)
        
        Returns:
            Dict con respuesta de la apuesta o None si error
        """
        if not self.session_token:
            logger.error("No hay sesión activa. Login primero.")
            return None
        
        bet_url = f"{self.base_url}/edge/rest/v2/offers"
        
        bet_data = {
            'offers': [{
                'market-id': market_id,
                'runner-id': runner_id,
                'side': side,
                'stake': stake,
                'odds': odds,
                'odds-type': 'DECIMAL',
                'exchange-type': 'back-lay'
            }]
        }
        
        try:
            response = self.session.post(bet_url, json=bet_data, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Apuesta colocada exitosamente: {data}")
                return data
            elif response.status_code in [400, 403]:
                # Error específico de la apuesta
                try:
                    error_data = response.json()
                    logger.error(f"Error colocando apuesta: {error_data}")
                except:
                    logger.error(f"Error colocando apuesta: {response.status_code}")
                return None
            else:
                logger.error(f"Error desconocido colocando apuesta: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error colocando apuesta: {e}")
            return None
    
    def get_bet_history(self, settled: bool = True, offset: int = 0, 
                        per_page: int = 50) -> Optional[Dict[str, Any]]:
        """
        Obtiene historial de apuestas.
        
        Args:
            settled: True para apuestas settled, False para unsettled
            offset: Offset para paginación
            per_page: Número de items por página
        
        Returns:
            Dict con historial de apuestas o None si error
        """
        if not self.session_token:
            logger.error("No hay sesión activa. Login primero.")
            return None
        
        endpoint = "settled" if settled else "unsettled"
        history_url = f"{self.base_url}/edge/rest/reports/v2/bets/{endpoint}"
        
        params = {
            'offset': offset,
            'per-page': per_page
        }
        
        try:
            response = self.session.get(history_url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                logger.info(f"Historial obtenido: {len(data.get('bets', []))} apuestas")
                return data
            else:
                logger.error(f"Error obteniendo historial: {response.status_code}")
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo historial: {e}")
            return None
    
    def logout(self) -> bool:
        """
        Cierra sesión en Matchbook API.
        
        Returns:
            bool: True si logout exitoso
        """
        if not self.session_token:
            logger.warning("No hay sesión activa para cerrar")
            return True
        
        logout_url = f"{self.base_url}/bpapi/rest/security/session/logout"
        
        try:
            response = self.session.delete(logout_url, timeout=10)
            
            if response.status_code == 200:
                logger.info("Logout exitoso")
                self.session_token = None
                self.session.headers.pop('session-token', None)
                return True
            else:
                logger.error(f"Error en logout: {response.status_code}")
                return False
                
        except Exception as e:
            logger.error(f"Error durante logout: {e}")
            return False
    
    def is_authenticated(self) -> bool:
        """
        Verifica si la sesión está activa.
        
        Returns:
            bool: True si hay sesión activa
        """
        # Intentar obtener balance como prueba
        balance = self.get_account_balance()
        return balance is not None


class MatchbookTradingBot:
    """Bot de trading para Matchbook integrado con Predicta."""
    
    def __init__(self, username: str, password: str):
        """
        Inicializa bot de trading.
        
        Args:
            username: Email de cuenta Matchbook
            password: Contraseña de cuenta Matchbook
        """
        self.client = MatchbookAPIClient(username, password)
        self.connected = False
    
    def connect(self) -> bool:
        """Conecta a Matchbook API."""
        logger.info("Conectando a Matchbook...")
        self.connected = self.client.login()
        return self.connected
    
    def disconnect(self):
        """Desconecta de Matchbook API."""
        if self.connected:
            self.client.logout()
            self.connected = False
            logger.info("Desconectado de Matchbook")
    
    def find_soccer_markets(self) -> List[Dict[str, Any]]:
        """
        Encuentra mercados de fútbol disponibles.
        
        Returns:
            Lista de mercados de fútbol
        """
        if not self.connected:
            logger.error("No conectado a Matchbook")
            return []
        
        # Obtener eventos de fútbol
        events = self.client.get_events(sport_id='soccer')
        if not events:
            return []
        
        # Obtener mercados para cada evento
        all_markets = []
        for event in events[:10]:  # Limitar a primeros 10 eventos
            event_id = event.get('id')
            markets = self.client.get_markets(event_id)
            if markets:
                for market in markets:
                    market['event'] = event  # Añadir info del evento
                    all_markets.append(market)
        
        logger.info(f"Encontrados {len(all_markets)} mercados de fútbol")
        return all_markets
    
    def calculate_edge(self, predicted_prob: float, market_odds: float) -> float:
        """
        Calcula edge (valor) entre probabilidad predicha y cuota de mercado.
        
        Args:
            predicted_prob: Probabilidad predicha por modelo (0-1)
            market_odds: Cuota decimal del mercado
        
        Returns:
            Edge como decimal (positivo = value)
        """
        if market_odds <= 1.0:
            return -1.0
        
        implied_prob = 1.0 / market_odds
        edge = predicted_prob - implied_prob
        return edge
    
    def should_place_bet(self, edge: float, min_edge: float = 0.05) -> bool:
        """
        Decide si colocar apuesta basado en edge.
        
        Args:
            edge: Edge calculado
            min_edge: Edge mínimo requerido (default 5%)
        
        Returns:
            True si debe apostar
        """
        return edge >= min_edge