"""
Servicio principal del motor de Value Betting v2
Conecta Kambi API (BetPlay) con Predicta para detectar value bets
Calcula probabilidades reales con Poisson bivariado
"""

import json
import logging
import math
import requests
import sqlite3
from datetime import datetime, timezone
from typing import List, Dict, Optional
from difflib import SequenceMatcher

from django.utils import timezone as django_timezone
from django.db import transaction

from football_data.models import League, Match
from auto_betting.strategy import validate_market_data, calibrate_probability, _get_tier_thresholds
from .models import KambiMatch, KambiBetOffer, ValueOpportunity, ScanRun
from .mapping import map_league, normalize_team_name, fuzzy_match_team

logger = logging.getLogger('value_betting')

# ── Configuración Kambi API ──
KAMBI_BASE = "https://us.offering-api.kambicdn.com/offering/v2018/betplay"
KAMBI_PARAMS = {
    "channel_id": 1,
    "client_id": 200,
    "lang": "es_CO",
    "market": "CO",
    "useCombined": "true",
    "useCombinedLive": "true",
}

# Categorías de mercado a escanear
MARKET_CATEGORIES = {
    12579: "Resultado Final",
    12580: "Total de goles",
    11942: "Ambos Equipos Marcarán",
    19260: "Total de Tiros de Esquina",
    12220: "Doble Oportunidad",
    11929: "Apuesta sin empate",
}

# ── DB de córners de Suramérica ──
CORNERS_DB_PATH = "/var/www/predicta.com.co/data/corners_scraped.db"

CORNERS_DB_LEAGUE_MAPPING = {
    "football/brazil/brasileirao_serie_a": "Serie A",
    "football/brazil/brasileirao_serie_b": "Serie B",
    "football/colombia/primera_a": "Primera A",
    "football/argentina/liga_profesional_argentina": "Primera Division",
    "football/mexico/liga_mx": "Liga MX",
    "football/usa/mls": "US MLS",
}

# Umbral mínimo de cuota
MIN_ODDS = 2.00


# ════════════════════════════════════════════════════════════
#  FUNCIONES MATEMÁTICAS (Poisson)
# ════════════════════════════════════════════════════════════

def poisson_pmf(k: int, lam: float) -> float:
    """Probabilidad de masa Poisson P(X=k)"""
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return (math.exp(-lam) * lam**k) / math.factorial(k)


def poisson_over(line: float, lam: float) -> float:
    """P(X > line) = 1 - P(X <= floor(line))"""
    if lam <= 0:
        return 0.0
    floor_line = math.floor(line)
    cumul = sum(poisson_pmf(k, lam) for k in range(floor_line + 1))
    return max(0, 1.0 - cumul)


def bivariate_poisson_1x2(lambda_home: float, lambda_away: float, max_goals: int = 10) -> Dict:
    """
    Calcula P(home win), P(draw), P(away win) usando Poisson bivariado independiente.
    Asume independencia entre goles de local y visitante.
    """
    p_home = 0.0
    p_draw = 0.0
    p_away = 0.0
    
    for h in range(max_goals + 1):
        p_h = poisson_pmf(h, lambda_home)
        for a in range(max_goals + 1):
            p_a = poisson_pmf(a, lambda_away)
            p_joint = p_h * p_a
            if h > a:
                p_home += p_joint
            elif h == a:
                p_draw += p_joint
            else:
                p_away += p_joint
    
    return {
        'home': p_home,
        'draw': p_draw,
        'away': p_away,
    }


def compute_poisson_probabilities(mean_value: float) -> Dict:
    """Calcula probabilidades Poisson para todas las líneas comunes."""
    if mean_value <= 0:
        return {}
    
    probs = {}
    for line in [0.5, 1, 1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5, 5.5, 6, 6.5, 7, 7.5, 8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5, 12, 12.5, 13, 14, 15]:
        over = round(poisson_over(line, mean_value), 4)
        probs[f"over_{line}"] = over
        probs[f"under_{line}"] = round(1 - over, 4)
    
    return probs


# ════════════════════════════════════════════════════════════
#  FUNCIÓN PARA GENERAR PREDICCIÓN COMPLETA DE UN PARTIDO
# ════════════════════════════════════════════════════════════

def generate_full_prediction(home_team: str, away_team: str, league: League) -> Optional[Dict]:
    """
    Genera TODAS las predicciones de Predicta para un partido usando el MISMO motor
    que la app original de Predicta (/ai/predict/result/).
    
    Usa:
    - SimplePredictionService + ModeloHibridoGeneral para goles
    - corners_model.predecir() para córners (modelo 40/30/15/15)
    - EnhancedBothTeamsScore para BTS
    - Poisson bivariado para 1X2 desde lambda_home y lambda_away
    """
    try:
        from ai_predictions.simple_models import SimplePredictionService, ModeloHibridoGeneral
        from ai_predictions.corners_model import corners_model
        from ai_predictions.enhanced_both_teams_score import enhanced_both_teams_score_model
        
        svc = SimplePredictionService()
        
        # ── 1. Goles local y visitante por separado ──
        # Usar SimplePredictionService + ModeloHibridoGeneral (igual que la app original)
        home_goals_simple = svc.get_all_simple_predictions(home_team, away_team, league, 'goals_home')
        away_goals_simple = svc.get_all_simple_predictions(home_team, away_team, league, 'goals_away')
        
        if not home_goals_simple or not away_goals_simple:
            return None
        
        # Verificar si hay datos reales (total_matches > 0)
        # Si no hay datos, no podemos calcular goles/1X2/BTS
        has_real_data = any(r.get('total_matches', 0) > 0 for r in home_goals_simple) or \
                         any(r.get('total_matches', 0) > 0 for r in away_goals_simple)
        
        if not has_real_data:
            logger.info(f"Sin datos históricos de goles para {home_team} vs {away_team} en {league.name}. Solo córners.")
            # No calcular goles/1X2/BTS. Solo retornar córners si corners_model tiene datos.
            corners_prediction = None
            try:
                corners_result = corners_model.predecir(home_team, away_team, league, 'corners_total')
                if corners_result and 'poisson_lines' in corners_result:
                    corners_probs = {}
                    for line_key, line_data in corners_result['poisson_lines'].items():
                        line_val = line_data['line']
                        corners_probs[f'over_{line_val}'] = line_data['p_over']
                        corners_probs[f'under_{line_val}'] = line_data['p_under']
                    corners_prediction = {
                        'prediction': corners_result.get('corners_esperados_total', corners_result.get('prediction', 0)),
                        'confidence': corners_result.get('confidence', 0.35),
                        'model_name': corners_result.get('model_name', 'Corners Model'),
                        'probabilities': corners_probs,
                    }
            except Exception as e:
                logger.warning(f"corners_model falló para {home_team} vs {away_team}: {e}")
            
            if not corners_prediction:
                return None
            
            return {
                'lambda_home': 0,
                'lambda_away': 0,
                'lambda_total': 0,
                'confidence': corners_prediction['confidence'],
                'model_name': 'Solo Córners (sin datos de goles en DB)',
                'probs_1x2': {},
                'goals_probs': {},
                'p_bts_yes': 0,
                'p_bts_no': 0,
                'corners': corners_prediction,
                'corners_total_pred': corners_prediction['prediction'],
                'corners_probs': corners_prediction['probabilities'],
            }
        
        # Agregar ModeloHibridoGeneral (igual que la app original)
        try:
            hybrid_home = ModeloHibridoGeneral().predecir(home_team, away_team, league, 'goals_home')
            if hybrid_home:
                home_goals_simple.append(hybrid_home)
        except Exception as e:
            logger.warning(f"ModeloHibridoGeneral goals_home falló: {e}")
        
        try:
            hybrid_away = ModeloHibridoGeneral().predecir(home_team, away_team, league, 'goals_away')
            if hybrid_away:
                away_goals_simple.append(hybrid_away)
        except Exception as e:
            logger.warning(f"ModeloHibridoGeneral goals_away falló: {e}")
        
        # Usar Ensemble como predicción principal, fallback al primero
        home_ensemble = next((r for r in home_goals_simple if 'Ensemble' in r.get('model_name', '')), home_goals_simple[0])
        away_ensemble = next((r for r in away_goals_simple if 'Ensemble' in r.get('model_name', '')), away_goals_simple[0])
        
        lambda_home = home_ensemble['prediction']
        lambda_away = away_ensemble['prediction']
        lambda_total = lambda_home + lambda_away
        
        # ── 2. 1X2 con Poisson bivariado ──
        probs_1x2 = bivariate_poisson_1x2(lambda_home, lambda_away)
        
        # ── 3. Over/Under goles con Poisson ──
        goals_probs = compute_poisson_probabilities(lambda_total)
        
        # ── 4. BTS: usar EnhancedBothTeamsScore (igual que la app original) ──
        p_bts_yes = 0.45  # fallback
        try:
            enhanced_prob = enhanced_both_teams_score_model.predict(home_team, away_team, league)
            p_bts_yes = enhanced_prob
        except Exception as e:
            logger.warning(f"EnhancedBothTeamsScore falló, usando Poisson: {e}")
            # Fallback: P(home>0) * P(away>0)
            p_home_scores = 1.0 - poisson_pmf(0, lambda_home)
            p_away_scores = 1.0 - poisson_pmf(0, lambda_away)
            p_bts_yes = p_home_scores * p_away_scores
        
        p_bts_no = 1.0 - p_bts_yes
        
        # ── 5. Córners: usar corners_model.predecir() (igual que la app original) ──
        corners_prediction = None
        try:
            corners_result = corners_model.predecir(home_team, away_team, league, 'corners_total')
            if corners_result and 'poisson_lines' in corners_result:
                corners_prediction = {
                    'prediction': corners_result.get('corners_esperados_total', corners_result.get('prediction', 0)),
                    'confidence': corners_result.get('confidence', 0.35),
                    'model_name': corners_result.get('model_name', 'Corners Model'),
                    'probabilities': {},
                }
                # Convertir poisson_lines a formato de probs dict
                for line_key, line_data in corners_result['poisson_lines'].items():
                    line_val = line_data['line']
                    corners_prediction['probabilities'][f'over_{line_val}'] = line_data['p_over']
                    corners_prediction['probabilities'][f'under_{line_val}'] = line_data['p_under']
        except Exception as e:
            logger.warning(f"Error en corners_model para {home_team} vs {away_team}: {e}")
        
        # Fallback: usar SimplePredictionService para corners
        if not corners_prediction:
            corners_result = svc.get_all_simple_predictions(home_team, away_team, league, 'corners_total')
            if corners_result:
                corners_ensemble = next((r for r in corners_result if 'Ensemble' in r.get('model_name', '')), corners_result[0])
                pred_val = corners_ensemble['prediction']
                corners_prediction = {
                    'prediction': pred_val,
                    'confidence': corners_ensemble.get('confidence', 0.35),
                    'model_name': corners_ensemble.get('model_name', ''),
                    'probabilities': compute_poisson_probabilities(pred_val),
                }
        
        return {
            'lambda_home': lambda_home,
            'lambda_away': lambda_away,
            'lambda_total': lambda_total,
            'confidence': min(home_ensemble.get('confidence', 0.4), away_ensemble.get('confidence', 0.4)),
            'model_name': 'Poisson Bivariado + ModeloHibridoGeneral + EnhancedBTS + CornersModel',
            'probs_1x2': probs_1x2,
            'goals_probs': goals_probs,
            'p_bts_yes': p_bts_yes,
            'p_bts_no': p_bts_no,
            'corners': corners_prediction,
            'corners_total_pred': corners_prediction['prediction'] if corners_prediction else 0,
            'corners_probs': corners_prediction['probabilities'] if corners_prediction else {},
        }
        
    except Exception as e:
        logger.error(f"Error generando predicción completa {home_team} vs {away_team}: {e}")
        return None


def predict_corners_from_southamerica_db(home_team: str, away_team: str, league_path: str) -> Optional[Dict]:
    """Predice total de córners usando la DB de Suramérica con Poisson."""
    league_name = CORNERS_DB_LEAGUE_MAPPING.get(league_path)
    if not league_name:
        return None
    
    try:
        conn = sqlite3.connect(CORNERS_DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute(
            "SELECT avg_corners, matches_count FROM team_corner_stats WHERE team_name = ? AND league = ? AND role = 'home'",
            (home_team, league_name)
        )
        home_row = cursor.fetchone()
        
        cursor.execute(
            "SELECT avg_corners, matches_count FROM team_corner_stats WHERE team_name = ? AND league = ? AND role = 'away'",
            (away_team, league_name)
        )
        away_row = cursor.fetchone()
        
        if not home_row or not away_row:
            # Fuzzy match
            cursor.execute("SELECT team_name, avg_corners, matches_count FROM team_corner_stats WHERE league = ? AND role = 'home'", (league_name,))
            home_candidates = cursor.fetchall()
            cursor.execute("SELECT team_name, avg_corners, matches_count FROM team_corner_stats WHERE league = ? AND role = 'away'", (league_name,))
            away_candidates = cursor.fetchall()
            conn.close()
            
            def best_match(name, candidates):
                best, best_score = None, 0
                for c in candidates:
                    score = SequenceMatcher(None, name.lower(), c[0].lower()).ratio()
                    if score > best_score:
                        best, best_score = c, score
                return best if best_score >= 0.6 else None
            
            if not home_row:
                m = best_match(home_team, home_candidates)
                if m: home_row = (m[1], m[2])
            if not away_row:
                m = best_match(away_team, away_candidates)
                if m: away_row = (m[1], m[2])
        else:
            conn.close()
        
        if not home_row or not away_row:
            return None
        
        total_corners = (home_row[0] or 0) + (away_row[0] or 0)
        probs = compute_poisson_probabilities(total_corners)
        
        return {
            'prediction': round(total_corners, 2),
            'confidence': min(0.85, max(0.3, (home_row[1] + away_row[1]) / 40)),
            'model_name': 'South America Corners DB (Poisson)',
            'probabilities': probs,
        }
    except Exception as e:
        logger.error(f"Error prediciendo corners desde DB Suramérica: {e}")
        return None


# ════════════════════════════════════════════════════════════
#  EXTRACCIÓN DE PROBABILIDAD SEGÚN MERCADO
# ════════════════════════════════════════════════════════════

def extract_probability_from_prediction(bet_offer: KambiBetOffer, full_prediction: Dict) -> Optional[float]:
    """
    Extrae la probabilidad de la predicción completa según el mercado de BetPlay.
    Usa Poisson bivariado para 1X2, Doble Oportunidad, Draw No Bet.
    Usa Poisson para Over/Under goles y córners.
    """
    label = bet_offer.criterion_label.lower()
    outcome = bet_offer.outcome_label.lower()
    line = bet_offer.line
    
    probs_1x2 = full_prediction.get('probs_1x2', {})
    goals_probs = full_prediction.get('goals_probs', {})
    p_bts_yes = full_prediction.get('p_bts_yes', 0)
    p_bts_no = full_prediction.get('p_bts_no', 0)
    corners_probs = full_prediction.get('corners_probs', {})
    
    # ── Resultado Final (1X2) ──
    if 'resultado final' in label:
        if outcome in ['1', 'local', '1 (tiempo completo)']:
            return probs_1x2.get('home', 0)
        elif outcome in ['x', 'empate', 'empate (tiempo completo)']:
            return probs_1x2.get('draw', 0)
        elif outcome in ['2', 'visitante', '2 (tiempo completo)']:
            return probs_1x2.get('away', 0)
    
    # ── Total de goles (Over/Under) ──
    elif 'total de goles' in label or ('goles' in label and ('más' in outcome or 'menos' in outcome)):
        if line is not None:
            over_key = f'over_{line}'
            under_key = f'under_{line}'
            if 'más' in outcome or 'over' in outcome:
                return goals_probs.get(over_key, goals_probs.get(f'over_{int(line)}', 0))
            elif 'menos' in outcome or 'under' in outcome:
                return goals_probs.get(under_key, goals_probs.get(f'under_{int(line)}', 0))
    
    # ── Total de Córners (Over/Under) ──
    elif 'esquina' in label or 'corner' in label:
        if line is not None:
            over_key = f'over_{line}'
            under_key = f'under_{line}'
            if 'más' in outcome or 'over' in outcome:
                return corners_probs.get(over_key, corners_probs.get(f'over_{int(line)}', 0))
            elif 'menos' in outcome or 'under' in outcome:
                return corners_probs.get(under_key, corners_probs.get(f'under_{int(line)}', 0))
    
    # ── Ambos Equipos Marcarán ──
    elif 'ambos' in label and 'marc' in label:
        if 'sí' in outcome or 'si' in outcome or 'yes' in outcome:
            return p_bts_yes
        elif 'no' in outcome:
            return p_bts_no
    
    # ── Doble Oportunidad ──
    elif 'doble' in label:
        if '1x' in outcome:
            return probs_1x2.get('home', 0) + probs_1x2.get('draw', 0)
        elif '12' in outcome:
            return probs_1x2.get('home', 0) + probs_1x2.get('away', 0)
        elif 'x2' in outcome:
            return probs_1x2.get('draw', 0) + probs_1x2.get('away', 0)
    
    # ── Apuesta sin empate (Draw No Bet) ──
    elif 'sin empate' in label or 'draw no bet' in label:
        # DNB: si es empate se devuelve la apuesta
        # P(local) = P(home win) / (1 - P(draw))
        p_home = probs_1x2.get('home', 0)
        p_draw = probs_1x2.get('draw', 0)
        p_away = probs_1x2.get('away', 0)
        no_draw = 1.0 - p_draw
        if no_draw > 0:
            if outcome in ['1', 'local']:
                return p_home / no_draw
            elif outcome in ['2', 'visitante']:
                return p_away / no_draw
    
    return None


# ════════════════════════════════════════════════════════════
#  INSTRUCCIÓN DE APUESTA LEGIBLE
# ════════════════════════════════════════════════════════════

def build_bet_instruction(bet_offer: KambiBetOffer) -> str:
    """Construye una instrucción legible de qué apostar en BetPlay"""
    market = bet_offer.criterion_label
    selection = bet_offer.outcome_label
    line = bet_offer.line
    home = bet_offer.match.home_team
    away = bet_offer.match.away_team
    
    market_lower = market.lower()
    sel_lower = selection.lower()
    
    if 'resultado final' in market_lower:
        if sel_lower in ['1']:
            return f"Gana {home} (Local)"
        elif sel_lower in ['x']:
            return "Empate"
        elif sel_lower in ['2']:
            return f"Gana {away} (Visitante)"
    
    if 'total de goles' in market_lower or ('goles' in market_lower and ('más' in sel_lower or 'menos' in sel_lower)):
        if line is not None:
            if 'más' in sel_lower:
                return f"Más de {line} goles"
            elif 'menos' in sel_lower:
                return f"Menos de {line} goles"
    
    if 'esquina' in market_lower or 'corner' in market_lower:
        if line is not None:
            if 'más' in sel_lower:
                return f"Más de {line} tiros de esquina"
            elif 'menos' in sel_lower:
                return f"Menos de {line} tiros de esquina"
    
    if 'ambos' in market_lower and 'marc' in market_lower:
        if 'sí' in sel_lower or 'si' in sel_lower:
            return "Ambos equipos marcan: SÍ"
        elif 'no' in sel_lower:
            return "Ambos equipos marcan: NO"
    
    if 'doble' in market_lower:
        if '1x' in sel_lower:
            return f"{home} gana o empata (1X)"
        elif '12' in sel_lower:
            return f"{home} o {away} gana (12)"
        elif 'x2' in sel_lower:
            return f"{away} gana o empata (X2)"
    
    if 'sin empate' in market_lower or 'draw no bet' in market_lower:
        if sel_lower in ['1']:
            return f"{home} gana o devuelven (DNB Local)"
        elif sel_lower in ['2']:
            return f"{away} gana o devuelven (DNB Visitante)"
    
    if line is not None:
        return f"{market}: {selection} ({line})"
    return f"{market}: {selection}"


# ════════════════════════════════════════════════════════════
#  COMPARACIÓN CUOTA vs PREDICCIÓN
# ════════════════════════════════════════════════════════════

def compute_value_bet(bet_offer: KambiBetOffer, full_prediction: Dict) -> Optional[ValueOpportunity]:
    """Compara la cuota de BetPlay con la predicción de Predicta.
    
    Aplica los mismos filtros que auto_betting (select_bets/_add_candidate):
    - Cuota >= 2.0 (MIN_ODDS)
    - Calibración de probabilidad (shrinkage)
    - P >= 50% (hard floor)
    - Tiers por cuota: confidence mínima y EV mínimo escalonados
    - EV > 0
    """
    cuota = bet_offer.odds_decimal
    if cuota <= 0 or cuota < MIN_ODDS:
        return None
    
    betplay_prob = 1.0 / cuota if cuota > 0 else 0
    
    raw_prob = extract_probability_from_prediction(bet_offer, full_prediction)
    
    if raw_prob is None or raw_prob <= 0:
        return None
    
    # ── Calibrar probabilidad (shrinkage, igual que auto_betting) ──
    predicta_prob = calibrate_probability(raw_prob)
    
    # ── Hard floor: P >= 50% ──
    if predicta_prob < 0.50:
        return None
    
    # ── Tiers por cuota (solo agregan requisitos) ──
    tier_min_p, tier_min_conf, tier_min_ev = _get_tier_thresholds(cuota)
    effective_min_p = max(0.50, tier_min_p)
    if predicta_prob < effective_min_p:
        return None
    
    # ── EV mínimo del tier ──
    ev = (predicta_prob * cuota) - 1.0
    if ev <= tier_min_ev:
        return None
    
    # ── Confidence mínima del tier ──
    confidence = full_prediction.get('confidence', 0)
    effective_min_conf = max(0.35, tier_min_conf)
    if confidence < effective_min_conf:
        return None
    
    # ── Edge para display ──
    edge = (predicta_prob - betplay_prob) * 100
    is_value = True  # Si pasó todos los filtros, es value
    
    opp = ValueOpportunity(
        match=bet_offer.match,
        market=bet_offer.criterion_label,
        selection=bet_offer.outcome_label,
        bet_instruction=build_bet_instruction(bet_offer),
        betplay_odds=cuota,
        betplay_implied_prob=betplay_prob,
        predicta_probability=predicta_prob,
        predicta_prediction=full_prediction.get('lambda_total'),
        predicta_confidence=confidence,
        predicta_model=full_prediction.get('model_name', ''),
        edge=round(edge, 2),
        ev=round(ev, 4),
        is_value=is_value,
        line=bet_offer.line,
    )
    
    return opp


# ════════════════════════════════════════════════════════════
#  KAMBI API
# ════════════════════════════════════════════════════════════

def fetch_kambi_football_matches() -> List[Dict]:
    """Obtiene todos los partidos de fútbol de Kambi (BetPlay)"""
    url = f"{KAMBI_BASE}/listView/football.json"
    params = {**KAMBI_PARAMS}
    
    resp = requests.get(url, params=params, timeout=15,
                        headers={"Accept": "application/json",
                                 "Origin": "https://betplay.com.co",
                                 "Referer": "https://betplay.com.co/"})
    resp.raise_for_status()
    data = resp.json()
    
    events = data.get('events', [])
    matches = []
    
    for e in events:
        ev = e.get('event', {})
        path = ev.get('path', [])
        if len(path) < 3:
            continue
        
        league_path = f"{path[0].get('termKey')}/{path[1].get('termKey')}/{path[2].get('termKey')}"
        league_name = path[2].get('localizedName', path[2].get('englishName', ''))
        
        predicta_league_name = map_league(league_path)
        if not predicta_league_name:
            continue
        
        if ev.get('state') != 'NOT_STARTED':
            continue
        
        start_str = ev.get('start', '')
        try:
            start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
        except (ValueError, TypeError):
            continue
        
        matches.append({
            'kambi_event_id': ev['id'],
            'home_team': ev.get('homeName', ''),
            'away_team': ev.get('awayName', ''),
            'league_name_kambi': league_name,
            'league_path_kambi': league_path,
            'start_time': start_time,
            'sport': ev.get('sport', 'FOOTBALL'),
            'state': ev.get('state', 'NOT_STARTED'),
            'predicta_league_name': predicta_league_name,
        })
    
    return matches


def fetch_kambi_bet_offers(kambi_league_path: str, category_id: int) -> List[Dict]:
    """Obtiene las cuotas de una liga y categoría específica de Kambi"""
    url = f"{KAMBI_BASE}/listView/{kambi_league_path}/all/matches.json"
    params = {**KAMBI_PARAMS, "category": category_id}
    
    try:
        resp = requests.get(url, params=params, timeout=15,
                            headers={"Accept": "application/json",
                                     "Origin": "https://betplay.com.co",
                                     "Referer": "https://betplay.com.co/"})
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        logger.warning(f"Error fetching offers for {kambi_league_path} cat={category_id}: {e}")
        return []
    
    offers = []
    for event_data in data.get('events', []):
        ev = event_data.get('event', {})
        ev_id = ev.get('id')
        
        for bo in event_data.get('betOffers', []):
            criterion = bo.get('criterion', {})
            bo_type = bo.get('betOfferType', {})
            
            for outcome in bo.get('outcomes', []):
                odds_raw = outcome.get('odds', 0)
                odds_decimal = odds_raw / 1000.0 if odds_raw else 0.0
                
                if odds_decimal < MIN_ODDS:
                    continue
                
                line = outcome.get('line')
                if line is not None:
                    line = line / 1000.0
                
                offers.append({
                    'kambi_event_id': ev_id,
                    'kambi_offer_id': bo.get('id'),
                    'criterion_label': criterion.get('label', ''),
                    'criterion_id': criterion.get('id'),
                    'offer_type': bo_type.get('name', ''),
                    'outcome_label': outcome.get('label', ''),
                    'outcome_type': outcome.get('type', ''),
                    'odds': odds_raw,
                    'odds_decimal': odds_decimal,
                    'line': line,
                    'status': outcome.get('status', 'OPEN'),
                    'category_id': category_id,
                })
    
    return offers


def map_teams_to_predicta(kambi_home: str, kambi_away: str, league: League) -> Dict:
    """Mapea los nombres de equipos de Kambi a los de Predicta usando fuzzy matching"""
    matches = Match.objects.filter(league=league).order_by('-date')[:500]
    all_teams = set()
    for m in matches:
        if m.home_team: all_teams.add(m.home_team)
        if m.away_team: all_teams.add(m.away_team)
    
    all_teams_list = list(all_teams)
    
    home_result = fuzzy_match_team(kambi_home, all_teams_list, threshold=0.65)
    away_result = fuzzy_match_team(kambi_away, all_teams_list, threshold=0.65)
    
    mapped_home = home_result[0] if home_result else None
    mapped_away = away_result[0] if away_result else None
    confidence = 0.0
    if home_result and away_result:
        confidence = (home_result[1] + away_result[1]) / 2
    elif home_result:
        confidence = home_result[1] * 0.5
    elif away_result:
        confidence = away_result[1] * 0.5
    
    return {'mapped_home': mapped_home, 'mapped_away': mapped_away, 'confidence': confidence}


# ════════════════════════════════════════════════════════════
#  MOTOR DE ESCANEO PRINCIPAL
# ════════════════════════════════════════════════════════════

def run_scan() -> ScanRun:
    """
    Ejecuta el escaneo completo:
    1. Trae partidos de Kambi
    2. Mapea a Predicta
    3. Genera predicción completa (goles home/away, corners, BTS)
    4. Compara con cuotas de BetPlay
    5. Guarda oportunidades con value y cuota >= 2.00
    """
    scan = ScanRun.objects.create(status='running')
    errors = []
    
    try:
        # ── Paso 1: Fetch partidos ──
        logger.info(" Paso 1: Obteniendo partidos de Kambi...")
        kambi_matches = fetch_kambi_football_matches()
        scan.matches_fetched = len(kambi_matches)
        scan.save()
        logger.info(f"  → {len(kambi_matches)} partidos obtenidos")
        
        if not kambi_matches:
            scan.status = 'completed'
            scan.finished_at = django_timezone.now()
            scan.save()
            return scan
        
        # ── Paso 2: Mapear ──
        logger.info(" Paso 2: Mapeando ligas y equipos...")
        mapped_count = 0
        kambi_match_objs = []
        
        for km_data in kambi_matches:
            try:
                predicta_league = League.objects.filter(name=km_data['predicta_league_name']).first()
                if not predicta_league:
                    continue
                
                kambi_match, _ = KambiMatch.objects.update_or_create(
                    kambi_event_id=km_data['kambi_event_id'],
                    defaults={
                        'home_team': km_data['home_team'],
                        'away_team': km_data['away_team'],
                        'league_name_kambi': km_data['league_name_kambi'],
                        'league_path_kambi': km_data['league_path_kambi'],
                        'start_time': km_data['start_time'],
                        'sport': km_data['sport'],
                        'state': km_data['state'],
                        'predicta_league': predicta_league,
                        'fetched_at': django_timezone.now(),
                    }
                )
                
                mapping_result = map_teams_to_predicta(km_data['home_team'], km_data['away_team'], predicta_league)
                kambi_match.mapped_home_team = mapping_result['mapped_home']
                kambi_match.mapped_away_team = mapping_result['mapped_away']
                kambi_match.mapping_confidence = mapping_result['confidence']
                
                # Si no se mapeó pero es liga suramericana, usar nombres originales para corners
                if not kambi_match.mapped_home_team and km_data['league_path_kambi'] in CORNERS_DB_LEAGUE_MAPPING:
                    kambi_match.mapped_home_team = km_data['home_team']
                    kambi_match.mapped_away_team = km_data['away_team']
                    kambi_match.mapping_confidence = 0.5
                
                kambi_match.save()
                
                if kambi_match.mapped_home_team and kambi_match.mapped_away_team:
                    mapped_count += 1
                
                kambi_match_objs.append(kambi_match)
            except Exception as e:
                errors.append(f"Error mapeando {km_data.get('home_team')}: {str(e)}")
        
        scan.matches_mapped = mapped_count
        scan.save()
        logger.info(f"  → {mapped_count} partidos mapeados")
        
        # ── Paso 3: Fetch cuotas ──
        logger.info(" Paso 3: Obteniendo cuotas de BetPlay...")
        league_paths = set()
        for km in kambi_match_objs:
            if km.mapped_home_team and km.mapped_away_team:
                league_paths.add(km.league_path_kambi)
        
        all_offers_by_event = {}
        for league_path in league_paths:
            for cat_id, cat_name in MARKET_CATEGORIES.items():
                offers = fetch_kambi_bet_offers(league_path, cat_id)
                for offer in offers:
                    ev_id = offer['kambi_event_id']
                    if ev_id not in all_offers_by_event:
                        all_offers_by_event[ev_id] = []
                    all_offers_by_event[ev_id].append(offer)
        
        # Guardar cuotas
        offers_saved = 0
        for km in kambi_match_objs:
            if not (km.mapped_home_team and km.mapped_away_team):
                continue
            event_offers = all_offers_by_event.get(km.kambi_event_id, [])
            km.bet_offers.all().delete()
            for offer_data in event_offers:
                KambiBetOffer.objects.create(
                    match=km,
                    kambi_offer_id=offer_data['kambi_offer_id'],
                    criterion_label=offer_data['criterion_label'],
                    criterion_id=offer_data['criterion_id'],
                    offer_type=offer_data['offer_type'],
                    outcome_label=offer_data['outcome_label'],
                    outcome_type=offer_data['outcome_type'],
                    odds=offer_data['odds'],
                    odds_decimal=offer_data['odds_decimal'],
                    line=offer_data['line'],
                    status=offer_data['status'],
                    category_id=offer_data['category_id'],
                )
                offers_saved += 1
        
        logger.info(f"  → {offers_saved} cuotas guardadas (filtradas >= {MIN_ODDS})")
        
        # ── Paso 4: Generar predicciones completas y detectar value ──
        logger.info(" Paso 4: Generando predicciones completas...")
        ValueOpportunity.objects.all().delete()
        
        predictions_count = 0
        value_count = 0
        all_opportunities = []
        
        for km in kambi_match_objs:
            if not (km.mapped_home_team and km.mapped_away_team):
                continue
            if not km.predicta_league:
                continue
            
            bet_offers = km.bet_offers.all()
            if not bet_offers:
                continue
            
            # ── Validar cobertura de datos (alineado con auto_betting) ──
            # Exige ≥10 partidos por equipo con datos NO NULL en cada campo
            coverage = validate_market_data(
                km.mapped_home_team, km.mapped_away_team, km.predicta_league
            )
            
            # Mapear mercados de Kambi a claves de coverage
            # Si un mercado no tiene datos suficientes, filtrar sus bet_offers
            market_coverage_map = {
                'Total de goles': 'goals_total',
                'Total de Tiros de Esquina': 'corners_total',
                'Total de tiros a puerta': 'shots_total',
                'Ambos Equipos Marcarán': 'both_teams_score',
                'Resultado Final': 'goals_total',  # 1X2 usa datos de goles
                'Doble Oportunidad': 'goals_total',
                'Apuesta sin empate': 'goals_total',
            }
            
            # Filtrar bet_offers: solo incluir mercados con datos suficientes
            filtered_offers = []
            for bo in bet_offers:
                market_key = market_coverage_map.get(bo.criterion_label)
                if market_key and not coverage.get(market_key, False):
                    continue  # Saltar este mercado por datos insuficientes
                filtered_offers.append(bo)
            
            if not filtered_offers:
                # Todos los mercados saltados por datos insuficientes
                continue
            
            bet_offers = filtered_offers
            is_sa_league = km.league_path_kambi in CORNERS_DB_LEAGUE_MAPPING
            
            # Generar predicción completa usando el mismo motor que la app original
            full_prediction = generate_full_prediction(
                km.mapped_home_team, km.mapped_away_team, km.predicta_league
            )
            
            # Para ligas suramericanas: si generate_full_prediction no pudo calcular goles
            # (porque no hay datos en DB principal), seguir usando corners_model para córners
            if not full_prediction and is_sa_league:
                # corners_model.predecir() funciona para SA porque lee scraped_db internamente
                try:
                    from ai_predictions.corners_model import corners_model
                    corners_result = corners_model.predecir(
                        km.mapped_home_team, km.mapped_away_team, km.predicta_league, 'corners_total'
                    )
                    if corners_result and 'poisson_lines' in corners_result:
                        corners_probs = {}
                        for line_key, line_data in corners_result['poisson_lines'].items():
                            line_val = line_data['line']
                            corners_probs[f'over_{line_val}'] = line_data['p_over']
                            corners_probs[f'under_{line_val}'] = line_data['p_under']
                        
                        full_prediction = {
                            'lambda_home': 0,
                            'lambda_away': 0,
                            'lambda_total': 0,
                            'confidence': corners_result.get('confidence', 0.35),
                            'model_name': corners_result.get('model_name', 'Corners Model'),
                            'probs_1x2': {},
                            'goals_probs': {},
                            'p_bts_yes': 0,
                            'p_bts_no': 0,
                            'corners': {'prediction': corners_result.get('corners_esperados_total', corners_result.get('prediction', 0)),
                                       'confidence': corners_result.get('confidence', 0.35),
                                       'model_name': corners_result.get('model_name', 'Corners Model'),
                                       'probabilities': corners_probs},
                            'corners_total_pred': corners_result.get('corners_esperados_total', corners_result.get('prediction', 0)),
                            'corners_probs': corners_probs,
                        }
                except Exception as e:
                    logger.warning(f"corners_model falló para {km.home_team} vs {km.away_team}: {e}")
            
            if not full_prediction:
                continue
            
            predictions_count += 1
            
            # Comparar cada cuota con la predicción
            for bo in bet_offers:
                opp = compute_value_bet(bo, full_prediction)
                if opp:
                    all_opportunities.append(opp)
                    if opp.is_value:
                        value_count += 1
        
        ValueOpportunity.objects.bulk_create(all_opportunities)
        
        scan.predictions_generated = predictions_count
        scan.opportunities_found = len(all_opportunities)
        scan.value_bets_found = value_count
        scan.save()
        
        logger.info(f"  → {predictions_count} predicciones generadas")
        logger.info(f"  → {len(all_opportunities)} oportunidades analizadas")
        logger.info(f"  → {value_count} value bets encontrados")
        
        scan.status = 'completed'
        scan.finished_at = django_timezone.now()
        scan.errors = "\n".join(errors[:50]) if errors else ""
        scan.save()
        
    except Exception as e:
        logger.error(f"Error en escaneo: {e}", exc_info=True)
        scan.status = 'failed'
        scan.finished_at = django_timezone.now()
        scan.errors = f"Error fatal: {str(e)}\n" + "\n".join(errors[:50])
        scan.save()
    
    return scan


# ════════════════════════════════════════════════════════════
#  HEALTHCHECK DE LA API DE KAMBI
# ════════════════════════════════════════════════════════════

def check_kambi_api_health() -> Dict:
    """
    Verifica que la API de Kambi (BetPlay) esté funcionando.
    Devuelve un dict con el estado y detalles.
    """
    result = {
        'healthy': False,
        'api_url': '',
        'matches_found': 0,
        'error': '',
        'checked_at': django_timezone.now().isoformat(),
    }
    
    try:
        url = f"{KAMBI_BASE}/listView/football.json"
        params = {**KAMBI_PARAMS}
        
        resp = requests.get(url, params=params, timeout=15,
                            headers={"Accept": "application/json",
                                     "Origin": "https://betplay.com.co",
                                     "Referer": "https://betplay.com.co/"})
        
        if resp.status_code != 200:
            result['error'] = f"HTTP {resp.status_code}"
            return result
        
        data = resp.json()
        events = data.get('events', [])
        
        if len(events) == 0:
            result['error'] = "API responde pero no hay eventos de fútbol"
            return result
        
        result['healthy'] = True
        result['matches_found'] = len(events)
        return result
        
    except requests.exceptions.Timeout:
        result['error'] = "Timeout: la API no respondió en 15 segundos"
        return result
    except requests.exceptions.ConnectionError as e:
        result['error'] = f"Error de conexión: {str(e)[:200]}"
        return result
    except Exception as e:
        result['error'] = f"Error inesperado: {str(e)[:200]}"
        return result