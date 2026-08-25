"""
Servicio de mapeo entre ligas/equipos de Kambi y Predicta
"""

import logging
import re
from typing import Optional, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger('value_betting')


# ── Mapeo de ligas Kambi → Predicta ──
LEAGUE_MAPPING = {
    # España
    'football/spain/la_liga': 'La Liga',
    'football/spain/la_liga_2': 'Segunda División',
    # Inglaterra
    'football/england/the_championship': 'Championship',
    'football/england/league_one': 'League One',
    'football/england/league_two': 'League Two',
    # Alemania
    'football/germany/bundesliga': 'Bundesliga',
    'football/germany/2__bundesliga': '2. Bundesliga',
    # Italia
    'football/italy/serie_a': 'Serie A',
    'football/italy/serie_b': 'Serie B',
    'football/italy/coppa_italia': None,  # No hay en Predicta
    # Francia
    'football/france/ligue_1': 'Ligue 1',
    'football/france/ligue_2': 'Ligue 2',
    # Países Bajos
    'football/netherlands/eredivisie': 'Eredivisie',
    # Portugal
    'football/portugal/primeira_liga': 'Primeira Liga',
    # Bélgica
    'football/belgium/jupiler_pro_league': 'Jupiler Pro League',
    # Turquía
    'football/turkey/super_lig': 'Süper Lig',
    # Escocia
    'football/scotland/premier_league': 'Scottish Premiership',
    'football/scotland/championship': 'Scottish Championship',
    # Grecia
    'football/greece/super_league': 'SuperLiga (Grecia)',
    # México
    'football/mexico/liga_mx': 'Liga MX (Mexico)',
    'football/mexico/liga_de_expansion_mx': 'Liga de Expansion MX (Mexico)',
    # USA
    'football/usa/mls': 'US MLS (USA)',
    # Brasil
    'football/brazil/brasileirao_serie_a': 'Serie A (Brasil)',
    'football/brazil/brasileirao_serie_b': 'Serie B (Brasil)',
    # Argentina
    'football/argentina/liga_profesional_argentina': 'Primera Division (Argentina)',
    # Colombia
    'football/colombia/primera_a': 'Primera A (Colombia)',
    'football/colombia/torneo_betplay_dimayor': 'Primera B (Colombia)',
    # ── 14 ligas nuevas (2026-08-17) ──
    'football/ecuador/liga_pro': 'Liga Pro (Ecuador)',
    'football/ecuador/serie_b': 'Serie B (Ecuador)',
    'football/chile/primera_chile': 'Primera Division (Chile)',
    'football/denmark/superligaen': 'Superligaen (Dinamarca)',
    'football/sweden/allsvenskan': 'Allsvenskan (Suecia)',
    'football/finland/veikkausliiga': 'Veikkausliiga (Finlandia)',
    'football/hungary/nb_1': 'NB I (Hungria)',
    'football/serbia/super_liga': 'Super Liga (Serbia)',
    'football/bulgaria/pfl_1': 'PFL 1 (Bulgaria)',
    'football/romania/liga_i': 'Liga I (Rumania)',
    'football/bosnia___herzegovina/premijer_liga': 'Premijer Liga (Bosnia)',
    'football/azerbaijan/premier_league': 'Premier Liga (Azerbaiyan)',
    'football/iceland/urvalsdeild': 'Urvalsdeild (Islandia)',
    'football/costa_rica/primera_division_costa_rica': 'Primera Division (Costa Rica)',
    'football/argentina/primera_nacional': 'Primera Nacional (Argentina)',
}


def map_league(kambi_league_path: str) -> Optional[str]:
    """Mapea el path de liga de Kambi al nombre de liga de Predicta"""
    return LEAGUE_MAPPING.get(kambi_league_path)


# ── Normalización de nombres de equipos ──
TEAM_NAME_REPLACEMENTS = {
    # Quitar acentos y caracteres especiales
    'Múnich': 'Munich',
    'Mönchengladbach': 'Mgladbach',
    'Leverkusen': 'Leverkusen',
    'Köln': 'Koln',
    'München': 'Munich',
    # Nombres que difieren entre Kambi y Predicta
    'Bayern Munich': 'Bayern Munich',
    'Bayern Múnich': 'Bayern Munich',
    'Borussia Dortmund': 'Dortmund',
    'Borussia Mönchengladbach': 'Mgladbach',
    'VfB Stuttgart': 'Stuttgart',
    'VfL Wolfsburg': 'Wolfsburg',
    'SC Freiburg': 'Freiburg',
    'SC Paderborn 07': 'Paderborn',
    '1. FC Köln': 'Koln',
    '1. FC Union Berlin': 'Union Berlin',
    '1. FC Kaiserslautern': 'Kaiserslautern',
    'TSG Hoffenheim': 'Hoffenheim',
    'FC Augsburg': 'Augsburg',
    'FC Schalke 04': 'Schalke 04',
    'SV Werder Bremen': 'Werder Bremen',
    'Eintracht Frankfurt': 'Eintracht Frankfurt',
    'RB Leipzig': 'RB Leipzig',
    'VfL Bochum': 'Bochum',
    'FC St. Pauli': 'St Pauli',
    'Holstein Kiel': 'Holstein Kiel',
    'Darmstadt 98': 'Darmstadt',
    'SSV Jahn Regensburg': 'Jahn Regensburg',
    'SV Elversberg': 'Elversberg',
    'Hamburger SV': 'Hamburgo',
    'Hannover 96': 'Hannover 96',
    'Hertha BSC': 'Hertha',
    'Karlsruher SC': 'Karlsruher',
    'Fortuna Düsseldorf': 'Düsseldorf',
    'Greuther Fürth': 'Greuther Furth',
    '1. FC Nürnberg': 'Nürnberg',
    '1. FC Magdeburg': 'Magdeburg',
    'SC Paderborn': 'Paderborn',
    'Wolverhampton Wanderers': 'Wolves',
    'Brighton and Hove Albion': 'Brighton',
    'Manchester United': 'Man United',
    'Manchester City': 'Man City',
    'Newcastle United': 'Newcastle',
    'Tottenham Hotspur': 'Tottenham',
    'West Ham United': 'West Ham',
    'Nottingham Forest': 'Nottm Forest',
    'Sheffield United': 'Sheffield United',
    'Leicester City': 'Leicester',
    'Ipswich Town': 'Ipswich',
    'Aston Villa': 'Aston Villa',
    'Crystal Palace': 'Crystal Palace',
    'AFC Bournemouth': 'Bournemouth',
    'Burnley': 'Burnley',
    'Fulham': 'Fulham',
    'Everton': 'Everton',
    'Arsenal': 'Arsenal',
    'Chelsea': 'Chelsea',
    'Liverpool': 'Liverpool',
    'Brentford': 'Brentford',
    'Leeds United': 'Leeds',
    'Norwich City': 'Norwich',
    'West Bromwich Albion': 'West Brom',
    'Sunderland': 'Sunderland',
    'Sheffield Wednesday': 'Sheffield Wed',
    'Hull City': 'Hull',
    'Middlesbrough': 'Middlesbrough',
    'Coventry City': 'Coventry',
    'Watford': 'Watford',
    'Stoke City': 'Stoke',
    'Norwich': 'Norwich',
    'Preston North End': 'Preston',
    'Blackburn Rovers': 'Blackburn',
    'Bristol City': 'Bristol City',
    'Cardiff City': 'Cardiff',
    'Swansea City': 'Swansea',
    'Queens Park Rangers': 'QPR',
    'Luton Town': 'Luton',
    'Plymouth Argyle': 'Plymouth',
    'Oxford United': 'Oxford Utd',
    'Portsmouth': 'Portsmouth',
    'Real Madrid': 'Real Madrid',
    'Barcelona': 'Barcelona',
    'Atlético Madrid': 'Atletico Madrid',
    'Atletico Madrid': 'Atletico Madrid',
    'Athletic Club': 'Athletic Bilbao',
    'Real Sociedad': 'Real Sociedad',
    'Real Betis': 'Real Betis',
    'Villarreal': 'Villarreal',
    'Sevilla': 'Sevilla',
    'Valencia': 'Valencia',
    'Getafe': 'Getafe',
    'Girona': 'Girona',
    'Rayo Vallecano': 'Rayo Vallecano',
    'Mallorca': 'Mallorca',
    'Osasuna': 'Osasuna',
    'Celta Vigo': 'Celta',
    'Alavés': 'Alaves',
    'Alaves': 'Alaves',
    'Espanyol': 'Espanyol',
    'Leganes': 'Leganes',
    'Las Palmas': 'Las Palmas',
    'Valladolid': 'Valladolid',
    'Racing Santander': 'Racing Santander',
    'Elche': 'Elche',
    'Córdoba': 'Cordoba',
    'Cordoba': 'Cordoba',
    'Levante': 'Levante',
    'Castellon': 'Castellon',
    'Eibar': 'Eibar',
    'Burgos': 'Burgos',
    'Andorra': 'Andorra',
    'Tenerife': 'Tenerife',
    'Zaragoza': 'Zaragoza',
    'Almeria': 'Almeria',
    'Oviedo': 'Oviedo',
    'Deportivo La Coruna': 'La Coruna',
    'La Coruna': 'La Coruna',
    'Racing Ferrol': 'Racing Ferrol',
    'Ponferradina': 'Ponferradina',
    'Eldense': 'Eldense',
    'Cartagena': 'Cartagena',
    'Mirandas': 'Mirandas',
    'Cádiz': 'Cadiz',
    'Cadiz': 'Cadiz',
    'Juventus': 'Juventus',
    'Inter': 'Inter',
    'Internazionale': 'Inter',
    'AC Milan': 'Milan',
    'Milan': 'Milan',
    'AS Roma': 'Roma',
    'Roma': 'Roma',
    'SS Lazio': 'Lazio',
    'Lazio': 'Lazio',
    'Napoli': 'Napoli',
    'Napoles': 'Napoli',
    'Atalanta': 'Atalanta',
    'Fiorentina': 'Fiorentina',
    'Bologna': 'Bologna',
    'Torino': 'Torino',
    'Udinese': 'Udinese',
    'Sassuolo': 'Sassuolo',
    'Genoa': 'Genoa',
    'Cagliari': 'Cagliari',
    'Monza': 'Monza',
    'Lecce': 'Lecce',
    'Verona': 'Verona',
    'Hellas Verona': 'Verona',
    'Empoli': 'Empoli',
    'Salernitana': 'Salernitana',
    'Frosinone': 'Frosinone',
    'Como': 'Como',
    'Parma': 'Parma',
    'Venezia': 'Venezia',
    'Pisa': 'Pisa',
    'Brescia': 'Brescia',
    'Catanzaro': 'Catanzaro',
    'Bari': 'Bari',
    'Cittadella': 'Cittadella',
    'Feralpisalo': 'Feralpisalo',
    'Palermo': 'Palermo',
    'Sampdoria': 'Sampdoria',
    'Modena': 'Modena',
    'Reggiana': 'Reggiana',
    'Cremonese': 'Cremonese',
    'Ternana': 'Ternana',
    'Cesena': 'Cesena',
    'Cosenza': 'Cosenza',
    'PSV': 'PSV',
    'PSV Eindhoven': 'PSV',
    'Ajax': 'Ajax',
    'Feyenoord': 'Feyenoord',
    'AZ Alkmaar': 'AZ Alkmaar',
    'Twente': 'Twente',
    'Utrecht': 'Utrecht',
    'Sparta Rotterdam': 'Sparta',
    'NEC Nijmegen': 'NEC',
    'NEC': 'NEC',
    'Heerenveen': 'Heerenveen',
    'Go Ahead Eagles': 'Go Ahead Eagles',
    'Go Ahead': 'Go Ahead Eagles',
    'Fortuna Sittard': 'Fortuna Sittard',
    'PEC Zwolle': 'Zwolle',
    'Zwolle': 'Zwolle',
    'RKC Waalwijk': 'RKC Waalwijk',
    'Almere City': 'Almere City',
    'Heracles': 'Heracles',
    'Sparta': 'Sparta',
    'Benfica': 'Benfica',
    'Porto': 'Porto',
    'FC Porto': 'Porto',
    'Sporting CP': 'Sporting',
    'Sporting': 'Sporting',
    'Braga': 'Braga',
    'Vitoria SC': 'Vitoria SC',
    'Guimaraes': 'Vitoria SC',
    'Boavista': 'Boavista',
    'Famalicao': 'Famalicao',
    'Casa Pia': 'Casa Pia',
    'Estoril': 'Estoril',
    'Rio Ave': 'Rio Ave',
    'Vizela': 'Vizela',
    'Gil Vicente': 'Gil Vicente',
    'Moreirense': 'Moreirense',
    'Arouca': 'Arouca',
    'Farense': 'Farense',
    'Nacional': 'Nacional',
    'Santa Clara': 'Santa Clara',
    'Club Brugge': 'Club Brugge',
    'Anderlecht': 'Anderlecht',
    'Genk': 'Genk',
    'Antwerp': 'Antwerp',
    'Union Saint-Gilloise': 'Union SG',
    'Standard Liege': 'Standard Liege',
    'Gent': 'Gent',
    'Kortrijk': 'Kortrijk',
    'Cercle Brugge': 'Cercle Brugge',
    'Westerlo': 'Westerlo',
    'Mechelen': 'Mechelen',
    'KV Mechelen': 'Mechelen',
    'Oud-Heverlee Leuven': 'OH Leuven',
    'OH Leuven': 'OH Leuven',
    'Charleroi': 'Charleroi',
    'Sint-Truiden': 'Sint-Truiden',
    'Dender': 'Dender',
    'Beerschot': 'Beerschot',
    'Galatasaray': 'Galatasaray',
    'Fenerbahce': 'Fenerbahce',
    'Fenerbahçe': 'Fenerbahce',
    'Besiktas': 'Besiktas',
    'Beşiktaş': 'Besiktas',
    'Trabzonspor': 'Trabzonspor',
    'Basaksehir': 'Basaksehir',
    'Antalyaspor': 'Antalyaspor',
    'Konyaspor': 'Konyaspor',
    'Sivasspor': 'Sivasspor',
    'Alanyaspor': 'Alanyaspor',
    'Gaziantep FK': 'Gaziantep FK',
    'Gazisehir Gaziantep': 'Gaziantep FK',
    'Hatayspor': 'Hatayspor',
    'Kasimpasa': 'Kasimpasa',
    'Kayserispor': 'Kayserispor',
    'Rizespor': 'Rizespor',
    'Eyupspor': 'Eyupspor',
    'Goztepe': 'Goztepe',
    'Bodrum FK': 'Bodrum FK',
    'Celtic': 'Celtic',
    'Rangers': 'Rangers',
    'Heart of Midlothian': 'Hearts',
    'Hearts': 'Hearts',
    'Hibernian': 'Hibernian',
    'Hibs': 'Hibernian',
    'Aberdeen': 'Aberdeen',
    'St Mirren': 'St Mirren',
    'Motherwell': 'Motherwell',
    'Kilmarnock': 'Kilmarnock',
    'Dundee United': 'Dundee Utd',
    'Dundee FC': 'Dundee FC',
    'Dundee': 'Dundee FC',
    'Ross County': 'Ross County',
    'St Johnstone': 'St Johnstone',
    'Dundee Utd': 'Dundee Utd',
    'Olympiakos': 'Olympiakos',
    'Olympiacos': 'Olympiakos',
    'Panathinaikos': 'Panathinaikos',
    'PAOK': 'PAOK',
    'AEK Athens': 'AEK Athens',
    'AEK': 'AEK Athens',
    'Panathinaikos': 'Panathinaikos',
    'Aris': 'Aris',
    'Aris Thessaloniki': 'Aris',
    'Volos': 'Volos',
    'Atromitos': 'Atromitos',
    'OFI': 'OFI',
    'Lamia': 'Lamia',
    'Asteras Tripolis': 'Asteras Tripolis',
    
    # ── MLS — Kambi usa nombres largos, DB usa cortos ──
    'Atlanta United FC': 'Atlanta Utd',
    'CF Montréal': 'CF Montreal',
    'D.C. United': 'DC United',
    'Los Ángeles Galaxy': 'Los Angeles Galaxy',
    'Inter Miami CF': 'Inter Miami',
    'St. Louis City SC': 'St. Louis City',
    'Minnesota United FC': 'Minnesota United',
    'New York City FC': 'New York City',
    'San Jose Earthquakes': 'San Jose Earthquakes',
    
    # ── Liga MX ──
    'Club Atlas': 'Atlas',
    'Deportivo Toluca FC': 'Toluca',
    'CF Monterrey': 'Monterrey',
    'FC Juárez': 'Juarez',
    'Pumas UNAM': 'UNAM Pumas',
    'Querétaro FC': 'Queretaro',
    'Club América': 'Club America',
    'Atlético San Luis': 'Atl. San Luis',
    'Club León': 'Club Leon',
    'Club Necaxa': 'Necaxa',
    'CF Pachuca': 'Pachuca',
    'Puebla FC': 'Puebla',
    
    # ── Liga de Expansion MX ──
    'Tepatitlán de Morelos': 'Tepatitlan de Morelos',
    'Coyotes de Tlaxcala': 'Tlaxcala',
    'Correcaminos UAT': 'Correcaminos',
    'Club Atlético La Paz': 'Atletico La Paz',
    'Venados FC': 'Venados',
    
    # ── Brasil Serie A — Kambi usa acentos, DB no ──
    'Atlético Mineiro-MG': 'Atletico-MG',
    'Grêmio-RS': 'Gremio',
    'São Paulo-SP': 'Sao Paulo',
    'Vitória-BA': 'Vitoria',
    'Botafogo-RJ': 'Botafogo RJ',
    'Flamengo-RJ': 'Flamengo RJ',
    'Corinthians-SP': 'Corinthians',
    'Cruzeiro-MG': 'Cruzeiro',
    'Internacional P. A.': 'Internacional',
    'Remo-PA': 'Remo',
    'Mirassol-SP': 'Mirassol',
    
    # ── Brasil Serie B ──
    'Criciúma-SC': 'Criciuma',
    'Goiás-GO': 'Goias',
    'Ceará-CE': 'Ceara',
    'Cuiabá-MT': 'Cuiaba',
    'Atlético-GO': 'Atletico GO',
    'Vila Nova-GO': 'Vila Nova FC',
    'Juventude-RS': 'Juventude',
    'Fortaleza-CE': 'Fortaleza',
    'Operário-PR': 'Operario-PR',
    'Avaí-SC': 'Avai',
    'América-MG': 'America MG',
    'Athletic Club-MG': 'Athletic Club',
    'CRB-AL': 'CRB',
    'Novorizontino-SP': 'Novorizontino',
    'Náutico-PE': 'Nautico',
    'Botafogo-SP': 'Botafogo SP',
    'Sport Recife-PE': 'Sport Recife',
    'FC São Bernardo-SP': 'Sao Bernardo',
    'Ponte Preta-SP': 'Ponte Preta',
    'Londrina-PR': 'Londrina',
    
    # ── Argentina ──
    'Unión de Santa Fe': 'Union de Santa Fe',
    'Estudiantes de La Plata': 'Estudiantes L.P.',
    'Gimnasia de La Plata': 'Gimnasia L.P.',
    'Gimnasia y Esgrima de Mendoza': 'Gimnasia Mendoza',
    'Club Atlético Tucumán': 'Atl. Tucuman',
    'Club Atlético Vélez Sarsfield': 'Velez Sarsfield',
    'Estudiantes de Río Cuarto': 'Estudiantes Rio Cuarto',
    'Central Córdoba': 'Central Cordoba',
    'Huracán': 'Huracan',
    'Lanús': 'Lanus',
    'Deportivo Riestra': 'Dep. Riestra',
    'Club Atletico Guemes': 'Club A. Guemes',
    'Deportivo Morón': 'Deportivo Moron',
    
    # ── Eredivisie ──
    'Excelsior Rotterdam': 'Excelsior',
    'Cambuur Leeuwarden': 'Cambuur',
    'ADO Den Haag': 'Den Haag',
    
    # ── Jupiler Pro League ──
    'SK Beveren': 'Beveren',
    'Standard de Lieja': 'Standard',
    'Sporting de Charleroi': 'Charleroi',
    
    # ── La Liga ──
    'Deportivo La Coruña': 'La Coruna',
    'Málaga': 'Malaga',
    
    # ── La Liga 2 ──
    'Sporting de Gijón': 'Sporting Gijon',
    
    # ── League Two ──
    'Salford City FC': 'Salford',
    
    # ── Liga I (Rumania) ──
    'Universitatea Cluj': 'U. Cluj',
    
    # ── Primeira Liga ──
    'Marítimo Funchal': 'Maritimo',
    'S.C. Braga': 'Sp Braga',
    
    # ── Serie B Ecuador ──
    'El Nacional (ECU)': 'EL Nacional',
    
    # ── Süper Lig ──
    'İstanbul Başakşehir': 'Basaksehir',
    'Gençlerbirliği SK': 'Genclerbirligi',
    
    # ── The Championship ──
    'Cardiff City': 'Cardiff',
    
    # ── Costa Rica ──
    'Municipal Pérez Zeledón': 'Municipal Perez Zeledon',
    
    # ── Veikkausliiga ──
    'SJK Seinäjoki': 'SJK',
    
    # ── Úrvalsdeild ──
    'Stjarnan Gardabae': 'Stjarnan',
    
    # ── Ligue 2 ──
    'Dunkerque': 'Dunkerque',
    'Pau FC': 'Pau FC',
}


def normalize_team_name(name: str) -> str:
    """Normaliza un nombre de equipo para comparación"""
    if not name:
        return ""
    name = name.strip()
    # Aplicar reemplazos
    if name in TEAM_NAME_REPLACEMENTS:
        return TEAM_NAME_REPLACEMENTS[name]
    return name


def fuzzy_match_team(kambi_name: str, candidates: list, threshold: float = 0.7) -> Optional[Tuple[str, float]]:
    """
    Hace fuzzy matching del nombre de equipo de Kambi contra candidatos de Predicta.
    Devuelve (mejor_match, score) o None.
    """
    kambi_normalized = normalize_team_name(kambi_name).lower()
    kambi_normalized = re.sub(r'[^a-z0-9 ]', '', kambi_normalized).strip()
    
    best_match = None
    best_score = 0.0
    
    for candidate in candidates:
        cand_normalized = normalize_team_name(candidate).lower()
        cand_normalized = re.sub(r'[^a-z0-9 ]', '', cand_normalized).strip()
        
        score = SequenceMatcher(None, kambi_normalized, cand_normalized).ratio()
        if score > best_score:
            best_score = score
            best_match = candidate
    
    if best_score >= threshold:
        return (best_match, best_score)
    return None