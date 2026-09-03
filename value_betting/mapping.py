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
    'football/colombia/liga_betplay_dimayor': 'Primera A (Colombia)',  # BetPlay renombró el path (25-Ago-2026)
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
    # ── 25 ligas nuevas BetPlay (2026-08-25) ──
    'football/england/efl_cup': 'Copa EFL',
    'football/england/fa_cup': 'FA Cup',
    'football/england/efl_trophy': 'EFL Trophy',
    'football/england/northern_league_premier_division': 'Northern Premier League (Inglaterra)',
    'football/denmark/dbu_pokalen': 'DBU Pokalen',
    'football/argentina/primera_b_metropolitana': 'Primera B Metropolitana (Argentina)',
    'football/bulgaria/pfl_2': 'PFL 2 (Bulgaria)',
    'football/paraguay/primera_paraguay': 'Primera Division (Paraguay)',
    'football/south_africa/psl': 'PSL (Sudáfrica)',
    'football/south_korea/k-league_1': 'K-League 1',
    'football/saudi_arabia/professional_league': 'Pro League (Arabia Saudí)',
    'football/kuwait/premier_league': 'Premier League (Kuwait)',
    'football/bolivia/liga_profesional_bolivia': 'Liga Profesional (Bolivia)',
    'football/czech_republic/cup': 'Copa (Rep. Checa)',
    'football/lithuania/1_lyga': '1 Lyga (Lituania)',
    'football/latvia/virsliga': 'Virsliga (Letonia)',
    'football/slovenia/cup': 'Copa (Eslovenia)',
    'football/tanzania/premier_league': 'Ligi Kuu Bara (Tanzania)',
    'football/brazil/copa_do_brasil': 'Copa de Brasil',
    'football/club_tournaments/leagues_cup': 'Leagues Cup',
    'football/australia/australia_cup': 'Copa Australia',
    'football/uruguay/copa_uruguay': 'Copa Uruguay',
    'football/sweden/superettan': 'Superettan (Suecia)',
    'football/sweden/svenska_cupen': 'Svenska Cupen',
    'football/iceland/1__deild': '1. Deild (Islandia)',
    # ── 74 ligas catálogo completo BetPlay (2026-08-25) ──
    'football/argentina/copa_argentina': 'Copa Argentina',
    'football/australia/a-league': 'A-League (Australia)',
    'football/australia/npl_nsw': 'NPL NSW',
    'football/australia/npl_queensland': 'NPL Queensland',
    'football/australia/npl_south_australia': 'NPL South Australia',
    'football/australia/npl_victoria': 'NPL Victoria',
    'football/austria/bundesliga': 'Bundesliga (Austria)',
    'football/austria/regional_league_east': 'Regionalliga Este (Austria)',
    'football/belgium/challenger_pro_league': 'Challenger Pro League (Bélgica)',
    'football/brazil/gaucho_2': 'Gaúcho 2 (Brasil)',
    'football/canada/cpl': 'Canadian Premier League',
    'football/chile/primera_b': 'Primera B (Chile)',
    'football/china/league_one': 'League One (China)',
    'football/china/super_league': 'Super League (China)',
    'football/costa_rica/liga_de_ascenso': 'Liga de Ascenso (Costa Rica)',
    'football/czech_republic/cfl': 'CFL (Rep. Checa)',
    'football/czech_republic/first_league': 'Czech Liga',
    'football/denmark/1st_division': '1. Division (Dinamarca)',
    'football/denmark/2nd_division': '2. Division (Dinamarca)',
    'football/egypt/premier_league': 'Premier League (Egipto)',
    'football/el_salvador/primera_el_salvador': 'Primera Division (El Salvador)',
    'football/england/premier_league': 'Premier League',
    'football/england/national_league': 'National League (Inglaterra)',
    'football/england/national_league_north': 'National League North',
    'football/england/national_league_south': 'National League South',
    'football/england/isthmian_league_division_one': 'Isthmian League Division One',
    'football/estonia/premium_liiga': 'Meistriliiga (Estonia)',
    'football/finland/ykkonen': 'Ykkönen (Finlandia)',
    'football/finland/ykkosliiga': 'Ykkösliiga (Finlandia)',
    'football/france/coupe_de_france': 'Coupe de France',
    'football/france/ligue_3': 'Ligue 3',
    'football/guatemala/liga_nacional_guatemala': 'Liga Nacional (Guatemala)',
    'football/honduras/liga_nacional_honduras': 'Liga Nacional (Honduras)',
    'football/hungary/nb_2': 'NB II (Hungria)',
    'football/ireland/1st_division': 'First Division (Irlanda)',
    'football/ireland/premier_division': 'Premier Division (Irlanda)',
    'football/italy/coppa_italia': 'Coppa Italia',
    'football/japan/j1-league': 'J1 League',
    'football/japan/j2-league': 'J2 League',
    'football/kazakhstan/premier_league': 'Premier League (Kazajistán)',
    'football/netherlands/eerste_divisie': 'Eerste Divisie',
    'football/netherlands/knvb_beker': 'KNVB Beker',
    'football/nicaragua/primera_division_nicaragua': 'Primera Division (Nicaragua)',
    'football/norway/eliteserien': 'Eliteserien',
    'football/norway/obos-ligaen': 'OBOS-ligaen',
    'football/peru/liga_1': 'Liga 1 (Perú)',
    'football/peru/segunda_division': 'Segunda División (Perú)',
    'football/peru/copa_de_la_liga': 'Copa de la Liga (Perú)',
    'football/poland/ekstraklasa': 'Ekstraklasa',
    'football/poland/i_liga': 'I Liga (Polonia)',
    'football/portugal/liga_2': 'Segunda Liga (Portugal)',
    'football/scotland/scottish_cup': 'FA Cup (Escocia)',
    'football/scotland/scottish_premiership': 'Scottish Premiership',
    'football/scotland/league_cup': 'League Cup (Escocia)',
    'football/slovenia/prva_liga': '1. SNL (Eslovenia)',
    'football/south_korea/k-league_2': 'K-League 2',
    'football/spain/copa_del_rey': 'Copa del Rey',
    'football/sweden/division_2_ng': 'Division 2 Norra Götaland',
    'football/switzerland/super_league': 'Super League (Suiza)',
    'football/switzerland/promotion_league': '1. Liga Promotion (Suiza)',
    'football/turkey/1__lig': '1. Lig (Turquía)',
    'football/uruguay/campeonato_uruguayo': 'Primera Division (Uruguay)',
    'football/usa/mls_next_pro': 'MLS Next Pro',
    'football/usa/usl_championship': 'USL Championship',
    'football/usa/usl_league_1': 'USL League One',
    'football/wales/premier_league': 'Premier League (Gales)',
    'football/champions_league': 'Champions League',
    'football/europa_league_qualification': 'Europa League',
    'football/conference_league_qualification': 'Conference League',
    'football/copa_libertadores': 'Copa Libertadores',
    'football/copa_sudamericana': 'Copa Sudamericana',
    'football/uefa_nations_league': 'UEFA Nations League',
    'football/world_cup_2030': 'World Cup',
    'football/euro_2028': 'European Championship',
    'football/fifa_intercontinental_cup': 'FIFA Intercontinental Cup',
    'football/champions_league_qualification': 'Champions League',
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

    # ── Pro League (Arabia Saudí) — 2026-09-03: fix mapeo tras auditoría ──
    # (partido Al Feiha vs Al-Kholood mapeado erróneamente a Al-Fateh vs Al
    # Kholood; fuzzy con threshold 0.65 encontraba 'Al-Fateh' como mejor match
    # incorrecto porque 'Al Feiha' y 'Al-Fayha' solo daban ratio 0.667, casi
    # igual al ratio con 'Al-Fateh'. Kambi usa transliteraciones distintas a
    # las de la BD de Predicta para varios equipos sauditas).
    'Al Feiha': 'Al-Fayha',
    'Al-Kholood': 'Al Kholood',
    'Al Draih': 'Al Diriyah',
    'Al Qadisiya': 'Al-Qadisiyah FC',
    'Neom SC': 'NEOM',
    'Al Hilal': 'Al-Hilal Saudi FC',
    'Al Nassr': 'Al-Nassr',
    'Al Taawon Buraidah': 'Al Taawon',
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