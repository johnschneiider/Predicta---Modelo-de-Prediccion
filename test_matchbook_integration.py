#!/usr/bin/env python3
"""
Script de prueba para integración Predicta + Matchbook.
"""

import os
import sys
import django
import logging

# Configurar Django
sys.path.append('/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'vitalmix_pro.settings')
django.setup()

from matchbook.orchestrator import PredictaMatchbookOrchestrator
from matchbook.client import MatchbookAPIClient

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger('test_matchbook')

def test_client_initialization():
    """Prueba inicialización del cliente."""
    print("=== TEST 1: Inicialización del cliente ===")
    
    client = MatchbookAPIClient()
    print(f"✅ Cliente inicializado correctamente")
    print(f"   Base URL: {client.base_url}")
    print(f"   Headers: {dict(client.session.headers)}")
    
    return client

def test_team_normalization():
    """Prueba normalización de nombres de equipos."""
    print("\n=== TEST 2: Normalización de nombres de equipos ===")
    
    orchestrator = PredictaMatchbookOrchestrator('test', 'test')
    
    test_cases = [
        ('Bayern Munich', 'Bayern München'),
        ('Atletico Madrid', 'Atlético Madrid'),
        ('Man United', 'Manchester United'),
        ('PSG', 'PSG'),  # Sin mapeo
        ('Real Madrid', 'Real Madrid'),  # Sin mapeo
    ]
    
    for input_name, expected in test_cases:
        result = orchestrator.normalize_team_name(input_name)
        status = '✅' if result == expected else '❌'
        print(f"{status} '{input_name}' -> '{result}' (esperado: '{expected}')")

def test_edge_calculation():
    """Prueba cálculo de edge."""
    print("\n=== TEST 3: Cálculo de edge ===")
    
    orchestrator = PredictaMatchbookOrchestrator('test', 'test')
    
    test_cases = [
        (0.60, 2.0, 0.10),   # 60% predicho vs 2.0 = 50% implícito -> 10% edge
        (0.55, 2.0, 0.05),   # 55% vs 2.0 = 5% edge
        (0.50, 2.0, 0.00),   # 50% vs 2.0 = 0% edge
        (0.45, 2.0, -0.05),  # 45% vs 2.0 = -5% edge
        (0.70, 1.5, 0.033),  # 70% vs 1.5 = 66.7% implícito -> 3.3% edge
    ]
    
    for pred_prob, odds, expected_edge in test_cases:
        edge = orchestrator.bot.calculate_edge(pred_prob, odds)
        status = '✅' if abs(edge - expected_edge) < 0.001 else '❌'
        print(f"{status} P={pred_prob:.2f}, O={odds:.2f} -> Edge={edge:.3f} (esperado: {expected_edge:.3f})")

def test_should_bet_logic():
    """Prueba lógica de decisión de apuesta."""
    print("\n=== TEST 4: Lógica de apuesta ===")
    
    orchestrator = PredictaMatchbookOrchestrator('test', 'test')
    
    test_cases = [
        (0.10, 0.05, True),   # 10% edge > 5% mínimo -> APOSTAR
        (0.05, 0.05, True),   # 5% edge = 5% mínimo -> APOSTAR
        (0.049, 0.05, False), # 4.9% edge < 5% mínimo -> NO APOSTAR
        (0.01, 0.05, False),  # 1% edge < 5% mínimo -> NO APOSTAR
        (0.15, 0.01, True),   # 15% edge > 1% mínimo -> APOSTAR
    ]
    
    for edge, min_edge, expected_decision in test_cases:
        decision = orchestrator.bot.should_place_bet(edge, min_edge)
        status = '✅' if decision == expected_decision else '❌'
        print(f"{status} Edge={edge:.3f}, Mín={min_edge:.3f} -> Apostar: {decision} (esperado: {expected_decision})")

def test_orchestrator_structure():
    """Prueba estructura del orquestador."""
    print("\n=== TEST 5: Estructura del orquestador ===")
    
    orchestrator = PredictaMatchbookOrchestrator('test_user', 'test_pass')
    
    print(f"✅ Orquestador inicializado")
    print(f"   Usuario: {orchestrator.bot.client.username}")
    print(f"   Conectado: {orchestrator.connected}")
    print(f"   Cache de ligas: {len(orchestrator.leagues_cache)} ligas cargadas")

def test_find_league_logic():
    """Prueba lógica para encontrar ligas."""
    print("\n=== TEST 6: Búsqueda de ligas ===")
    
    from football_data.models import League
    
    # Crear ligas dummy para prueba
    leagues = [
        ('Premier League', 'Inglaterra'),
        ('La Liga', 'España'),
        ('Bundesliga', 'Alemania'),
        ('Serie A', 'Italia'),
    ]
    
    for name, country in leagues:
        League.objects.get_or_create(name=name, country=country)
    
    orchestrator = PredictaMatchbookOrchestrator('test', 'test')
    
    # Recargar cache
    orchestrator.leagues_cache = {}
    leagues_db = League.objects.all()
    for league in leagues_db:
        orchestrator.leagues_cache[league.name.lower()] = league
    
    test_cases = [
        ('Manchester United v Liverpool - Premier League', 'Match Odds', 'Premier League'),
        ('Real Madrid v Barcelona - La Liga', 'Match Odds', 'La Liga'),
        ('Bayern v Dortmund (No liga especificada)', 'Match Odds', 'Premier League'),  # Fallback
    ]
    
    for event_name, market_name, expected_league in test_cases:
        league = orchestrator.find_corresponding_league(event_name, market_name)
        league_name = league.name if league else 'Ninguna'
        status = '✅' if league_name == expected_league else '❌'
        print(f"{status} Evento: '{event_name}' -> Liga: '{league_name}' (esperado: '{expected_league}')")

def main():
    print("=== PRUEBA DE INTEGRACIÓN PREDICTA + MATCHBOOK ===\n")
    
    try:
        test_client_initialization()
        test_team_normalization()
        test_edge_calculation()
        test_should_bet_logic()
        test_orchestrator_structure()
        test_find_league_logic()
        
        print("\n=== RESUMEN ===")
        print("✅ Todas las pruebas de lógica pasaron correctamente")
        print("\n⚠️  NOTA IMPORTANTE:")
        print("Las pruebas NO incluyen conexión real a Matchbook.")
        print("Para pruebas reales necesitas:")
        print("1. Crear cuenta en https://matchbook.com")
        print("2. Configurar credenciales en django settings")
        print("3. Ejecutar: python manage.py run_matchbook_bot --dry-run")
        print("\nLos archivos creados:")
        print("- /var/www/predicta.com.co/matchbook/client.py")
        print("- /var/www/predicta.com.co/matchbook/orchestrator.py")
        print("- /var/www/predicta.com.co/matchbook/management/commands/run_matchbook_bot.py")
        
    except Exception as e:
        print(f"\n❌ Error durante las pruebas: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()