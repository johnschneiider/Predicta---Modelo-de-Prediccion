"""
Diccionarios estáticos de mapeo.

Fuente única de ligas: (nombre_predicta, api_id, kambi_path, país).
Los nombres `predicta_name` son los valores exactos de `football_data.League.name`
para poder enlazar con la tabla legacy.

Equipos: `TEAM_MAPPING` mapea nombre BetPlay (Kambi) -> nombre API-Football.
Se expande manualmente; `normalize_team_name` da un fallback determinista.
"""

import re
import unicodedata

# ── Ligas: predicta_name -> api_id (API-Football), kambi_path (BetPlay) ──
# Orden = prioridad de backfill (las 44 originales primero).
LEAGUES = [
    # --- Europa ---
    ("Premier League", 39, "football/england/premier_league", "England"),
    ("Championship", 40, "football/england/the_championship", "England"),
    ("League One", 41, "football/england/league_one", "England"),
    ("League Two", 42, "football/england/league_two", "England"),
    ("La Liga", 140, "football/spain/la_liga", "Spain"),
    ("Segunda División", 141, "football/spain/la_liga_2", "Spain"),
    ("Bundesliga", 78, "football/germany/bundesliga", "Germany"),
    ("2. Bundesliga", 79, "football/germany/2__bundesliga", "Germany"),
    ("Serie A", 135, "football/italy/serie_a", "Italy"),
    ("Serie B", 136, "football/italy/serie_b", "Italy"),
    ("Ligue 1", 61, "football/france/ligue_1", "France"),
    ("Ligue 2", 62, "football/france/ligue_2", "France"),
    ("Eredivisie", 88, "football/netherlands/eredivisie", "Netherlands"),
    ("Primeira Liga", 94, "football/portugal/primeira_liga", "Portugal"),
    ("Jupiler Pro League", 144, "football/belgium/jupiler_pro_league", "Belgium"),
    ("Süper Lig", 203, "football/turkey/super_lig", "Turkey"),
    ("Scottish Premiership", 179, "football/scotland/scottish_premiership", "Scotland"),
    ("Scottish Championship", 180, "football/scotland/championship", "Scotland"),
    ("Super Liga (Grecia)", 197, "football/greece/super_league", "Greece"),
    ("Superligaen (Dinamarca)", 119, "football/denmark/superligaen", "Denmark"),
    ("Allsvenskan (Suecia)", 113, "football/sweden/allsvenskan", "Sweden"),
    ("Veikkausliiga (Finlandia)", 244, "football/finland/veikkausliiga", "Finland"),
    ("NB I (Hungria)", 271, "football/hungary/nb_1", "Hungary"),
    ("Super Liga (Serbia)", 286, "football/serbia/super_liga", "Serbia"),
    ("PFL 1 (Bulgaria)", 172, "football/bulgaria/pfl_1", "Bulgaria"),
    ("Liga I (Rumania)", 283, "football/romania/liga_i", "Romania"),
    ("Premijer Liga (Bosnia)", 315, "football/bosnia___herzegovina/premijer_liga", "Bosnia"),
    ("Premier Liga (Azerbaiyan)", 419, "football/azerbaijan/premier_league", "Azerbaijan"),
    ("Urvalsdeild (Islandia)", 164, "football/iceland/urvalsdeild", "Iceland"),
    # --- Américas ---
    ("Serie A (Brasil)", 71, "football/brazil/brasileirao_serie_a", "Brazil"),
    ("Serie B (Brasil)", 72, "football/brazil/brasileirao_serie_b", "Brazil"),
    ("Primera A (Colombia)", 239, "football/colombia/primera_a", "Colombia"),
    ("Primera B (Colombia)", 240, "football/colombia/torneo_betplay_dimayor", "Colombia"),
    ("Primera Division (Argentina)", 128, "football/argentina/liga_profesional_argentina", "Argentina"),
    ("Primera Nacional (Argentina)", 129, "football/argentina/primera_nacional", "Argentina"),
    ("Liga MX (Mexico)", 262, "football/mexico/liga_mx", "Mexico"),
    ("Liga de Expansion MX (Mexico)", 263, "football/mexico/liga_de_expansion_mx", "Mexico"),
    ("US MLS (USA)", 253, "football/usa/mls", "USA"),
    ("Liga Pro (Ecuador)", 242, "football/ecuador/liga_pro", "Ecuador"),
    ("Serie B (Ecuador)", 243, "football/ecuador/serie_b", "Ecuador"),
    ("Primera Division (Chile)", 265, "football/chile/primera_chile", "Chile"),
    ("Primera Division (Costa Rica)", 162, "football/costa_rica/primera_division_costa_rica", "Costa Rica"),
    # --- 25 ligas nuevas BetPlay (2026-08-25) ---
    ("Copa EFL", 48, "football/england/efl_cup", "England"),
    ("FA Cup", 45, "football/england/fa_cup", "England"),
    ("EFL Trophy", 46, "football/england/efl_trophy", "England"),
    ("Northern Premier League (Inglaterra)", 59, "football/england/northern_league_premier_division", "England"),
    ("DBU Pokalen", 121, "football/denmark/dbu_pokalen", "Denmark"),
    ("Primera B Metropolitana (Argentina)", 131, "football/argentina/primera_b_metropolitana", "Argentina"),
    ("PFL 2 (Bulgaria)", 173, "football/bulgaria/pfl_2", "Bulgaria"),
    ("Primera Division (Paraguay)", 250, "football/paraguay/primera_paraguay", "Paraguay"),
    ("PSL (Sudáfrica)", 288, "football/south_africa/psl", "South Africa"),
    ("K-League 1", 292, "football/south_korea/k-league_1", "South Korea"),
    ("Pro League (Arabia Saudí)", 307, "football/saudi_arabia/professional_league", "Saudi Arabia"),
    ("Premier League (Kuwait)", 330, "football/kuwait/premier_league", "Kuwait"),
    ("Liga Profesional (Bolivia)", 344, "football/bolivia/liga_profesional_bolivia", "Bolivia"),
    ("Copa (Rep. Checa)", 347, "football/czech_republic/cup", "Czech Republic"),
    ("1 Lyga (Lituania)", 361, "football/lithuania/1_lyga", "Lithuania"),
    ("Virsliga (Letonia)", 365, "football/latvia/virsliga", "Latvia"),
    ("Copa (Eslovenia)", 375, "football/slovenia/cup", "Slovenia"),
    ("Ligi Kuu Bara (Tanzania)", 567, "football/tanzania/premier_league", "Tanzania"),
    ("Copa de Brasil", 73, "football/brazil/copa_do_brasil", "Brazil"),
    ("Leagues Cup", 772, "football/club_tournaments/leagues_cup", "World"),
    ("Copa Australia", 874, "football/australia/australia_cup", "Australia"),
    ("Copa Uruguay", 930, "football/uruguay/copa_uruguay", "Uruguay"),
    ("Superettan (Suecia)", 114, "football/sweden/superettan", "Sweden"),
    ("Svenska Cupen", 115, "football/sweden/svenska_cupen", "Sweden"),
    ("1. Deild (Islandia)", 165, "football/iceland/1__deild", "Iceland"),
    # --- 74 ligas catálogo completo BetPlay (2026-08-25) ---
    ("Copa Argentina", 130, "football/argentina/copa_argentina", "Argentina"),
    ("A-League (Australia)", 188, "football/australia/a-league", "Australia"),
    ("NPL NSW", 192, "football/australia/npl_nsw", "Australia"),
    ("NPL Queensland", 482, "football/australia/npl_queensland", "Australia"),
    ("NPL South Australia", 194, "football/australia/npl_south_australia", "Australia"),
    ("NPL Victoria", 195, "football/australia/npl_victoria", "Australia"),
    ("Bundesliga (Austria)", 218, "football/austria/bundesliga", "Austria"),
    ("Regionalliga Este (Austria)", 221, "football/austria/regional_league_east", "Austria"),
    ("Challenger Pro League (Bélgica)", 145, "football/belgium/challenger_pro_league", "Belgium"),
    ("Gaúcho 2 (Brasil)", 478, "football/brazil/gaucho_2", "Brazil"),
    ("Canadian Premier League", 479, "football/canada/cpl", "Canada"),
    ("Primera B (Chile)", 266, "football/chile/primera_b", "Chile"),
    ("League One (China)", 170, "football/china/league_one", "China"),
    ("Super League (China)", 169, "football/china/super_league", "China"),
    ("Liga de Ascenso (Costa Rica)", 163, "football/costa_rica/liga_de_ascenso", "Costa Rica"),
    ("CFL (Rep. Checa)", 348, "football/czech_republic/cfl", "Czech Republic"),
    ("Czech Liga", 345, "football/czech_republic/first_league", "Czech Republic"),
    ("1. Division (Dinamarca)", 120, "football/denmark/1st_division", "Denmark"),
    ("2. Division (Dinamarca)", 122, "football/denmark/2nd_division", "Denmark"),
    ("Premier League (Egipto)", 233, "football/egypt/premier_league", "Egypt"),
    ("Primera Division (El Salvador)", 370, "football/el_salvador/primera_el_salvador", "El Salvador"),
    ("National League (Inglaterra)", 43, "football/england/national_league", "England"),
    ("National League North", 50, "football/england/national_league_north", "England"),
    ("National League South", 51, "football/england/national_league_south", "England"),
    ("Isthmian League Division One", 53, "football/england/isthmian_league_division_one", "England"),
    ("Meistriliiga (Estonia)", 329, "football/estonia/premium_liiga", "Estonia"),
    ("Ykkönen (Finlandia)", 245, "football/finland/ykkonen", "Finland"),
    ("Ykkösliiga (Finlandia)", 1087, "football/finland/ykkosliiga", "Finland"),
    ("Coupe de France", 66, "football/france/coupe_de_france", "France"),
    ("Ligue 3", 63, "football/france/ligue_3", "France"),
    ("Liga Nacional (Guatemala)", 339, "football/guatemala/liga_nacional_guatemala", "Guatemala"),
    ("Liga Nacional (Honduras)", 234, "football/honduras/liga_nacional_honduras", "Honduras"),
    ("NB II (Hungria)", 272, "football/hungary/nb_2", "Hungary"),
    ("First Division (Irlanda)", 358, "football/ireland/1st_division", "Ireland"),
    ("Premier Division (Irlanda)", 357, "football/ireland/premier_division", "Ireland"),
    ("Coppa Italia", 137, "football/italy/coppa_italia", "Italy"),
    ("J1 League", 98, "football/japan/j1-league", "Japan"),
    ("J2 League", 99, "football/japan/j2-league", "Japan"),
    ("Premier League (Kazajistán)", 389, "football/kazakhstan/premier_league", "Kazakhstan"),
    ("Eerste Divisie", 89, "football/netherlands/eerste_divisie", "Netherlands"),
    ("KNVB Beker", 90, "football/netherlands/knvb_beker", "Netherlands"),
    ("Primera Division (Nicaragua)", 396, "football/nicaragua/primera_division_nicaragua", "Nicaragua"),
    ("Eliteserien", 103, "football/norway/eliteserien", "Norway"),
    ("OBOS-ligaen", 104, "football/norway/obos-ligaen", "Norway"),
    ("Liga 1 (Perú)", 281, "football/peru/liga_1", "Peru"),
    ("Segunda División (Perú)", 282, "football/peru/segunda_division", "Peru"),
    ("Copa de la Liga (Perú)", 1232, "football/peru/copa_de_la_liga", "Peru"),
    ("Ekstraklasa", 106, "football/poland/ekstraklasa", "Poland"),
    ("I Liga (Polonia)", 107, "football/poland/i_liga", "Poland"),
    ("Segunda Liga (Portugal)", 95, "football/portugal/liga_2", "Portugal"),
    ("FA Cup (Escocia)", 181, "football/scotland/scottish_cup", "Scotland"),
    ("League Cup (Escocia)", 185, "football/scotland/league_cup", "Scotland"),
    ("1. SNL (Eslovenia)", 373, "football/slovenia/prva_liga", "Slovenia"),
    ("K-League 2", 293, "football/south_korea/k-league_2", "South Korea"),
    ("Copa del Rey", 143, "football/spain/copa_del_rey", "Spain"),
    ("Division 2 Norra Götaland", 592, "football/sweden/division_2_ng", "Sweden"),
    ("Super League (Suiza)", 207, "football/switzerland/super_league", "Switzerland"),
    ("1. Liga Promotion (Suiza)", 510, "football/switzerland/promotion_league", "Switzerland"),
    ("1. Lig (Turquía)", 204, "football/turkey/1__lig", "Turkey"),
    ("Primera Division (Uruguay)", 268, "football/uruguay/campeonato_uruguayo", "Uruguay"),
    ("MLS Next Pro", 909, "football/usa/mls_next_pro", "USA"),
    ("USL Championship", 255, "football/usa/usl_championship", "USA"),
    ("USL League One", 489, "football/usa/usl_league_1", "USA"),
    ("Premier League (Gales)", 110, "football/wales/premier_league", "Wales"),
    ("Champions League", 2, "football/champions_league", "Europe"),
    ("Europa League", 3, "football/europa_league_qualification", "Europe"),
    ("Conference League", 848, "football/conference_league_qualification", "Europe"),
    ("Copa Libertadores", 13, "football/copa_libertadores", "South America"),
    ("Copa Sudamericana", 11, "football/copa_sudamericana", "South America"),
    ("UEFA Nations League", 5, "football/uefa_nations_league", "Europe"),
    ("World Cup", 1, "football/world_cup_2030", "World"),
    ("European Championship", 4, "football/euro_2028", "Europe"),
    ("FIFA Intercontinental Cup", 1168, "football/fifa_intercontinental_cup", "World"),
]

LEAGUE_API_IDS = {name: api_id for (name, api_id, _p, _c) in LEAGUES}
KAMBI_PATH_TO_API_ID = {path: api_id for (_n, api_id, path, _c) in LEAGUES}
API_ID_TO_PREDICTA = {api_id: name for (name, api_id, _p, _c) in LEAGUES}

# ── Equipos: mapeo estático BetPlay (Kambi) -> API-Football ──
# Formato: {"nombre_kambi": "nombre_api_football"}
# Se completa con `discover_betplay_leagues` (reporta no-mapeados).
TEAM_MAPPING = {
    # Inglaterra
    "Wolves": "Wolverhampton",
    "Wolverhampton Wanderers": "Wolverhampton",
    "Brighton and Hove Albion": "Brighton",
    "Man United": "Manchester United",
    "Man City": "Manchester City",
    "Newcastle": "Newcastle",
    "Tottenham": "Tottenham",
    "West Ham": "West Ham",
    "Nottm Forest": "Nottingham Forest",
    "Leicester": "Leicester",
    "Ipswich": "Ipswich",
    "Bournemouth": "Bournemouth",
    "Leeds": "Leeds",
    "West Brom": "West Brom",
    "Sheffield Wed": "Sheffield Wednesday",
    "Hull": "Hull City",
    "Preston": "Preston",
    "Oxford Utd": "Oxford United",
    "QPR": "Queens Park Rangers",
    # España
    "Atletico Madrid": "Atletico Madrid",
    "Athletic Bilbao": "Athletic Club",
    "Celta": "Celta Vigo",
    "Alaves": "Alaves",
    "Cordoba": "Cordoba",
    "Cadiz": "Cadiz",
    "La Coruna": "Deportivo La Coruna",
    # Alemania
    "Dortmund": "Borussia Dortmund",
    "Mgladbach": "Borussia Monchengladbach",
    "Koln": "FC Koln",
    "St Pauli": "FC St. Pauli",
    "Hamburgo": "Hamburger SV",
    "Hertha": "Hertha Berlin",
    "Karlsruher": "Karlsruher SC",
    "Düsseldorf": "Fortuna Dusseldorf",
    "Nürnberg": "FC Nurnberg",
    "Schalke 04": "FC Schalke 04",
    "Werder Bremen": "Werder Bremen",
    # Italia
    "Inter": "Inter",
    "Milan": "AC Milan",
    "Roma": "Roma",
    "Lazio": "Lazio",
    "Napoli": "Napoli",
    "Verona": "Verona",
    # Países Bajos
    "PSV": "PSV Eindhoven",
    "Sparta": "Sparta Rotterdam",
    "NEC": "NEC Nijmegen",
    "Zwolle": "PEC Zwolle",
    # Portugal
    "Sporting": "Sporting CP",
    "Vitoria SC": "Vitoria Guimaraes",
    # Bélgica
    "Union SG": "Union Saint-Gilloise",
    "Mechelen": "KV Mechelen",
    "OH Leuven": "OH Leuven",
    # Turquía
    "Fenerbahce": "Fenerbahce",
    "Besiktas": "Besiktas",
    "Basaksehir": "Istanbul Basaksehir",
    # Escocia
    "Hearts": "Heart Of Midlothian",
    "Dundee Utd": "Dundee United",
    "Dundee FC": "Dundee",
    # Grecia
    "AEK Athens": "AEK Athens FC",
    # MLS
    "Atlanta Utd": "Atlanta United",
    "CF Montreal": "Montreal Impact",
    "DC United": "DC United",
    "Los Angeles Galaxy": "Los Angeles Galaxy",
    "Inter Miami": "Inter Miami",
    "St. Louis City": "St. Louis City",
    "Minnesota United": "Minnesota United",
    "New York City": "New York City FC",
    "San Jose Earthquakes": "San Jose Earthquakes",
    # Liga MX
    "Atlas": "Atlas",
    "Toluca": "Toluca",
    "Monterrey": "Monterrey",
    "Juarez": "Juarez",
    "UNAM Pumas": "Pumas UNAM",
    "Queretaro": "Queretaro",
    "Club America": "Club America",
    "Atl. San Luis": "Atletico San Luis",
    "Club Leon": "Leon",
    "Necaxa": "Necaxa",
    "Pachuca": "Pachuca",
    "Puebla": "Puebla",
    # Brasil
    "Atletico-MG": "Atletico Mineiro",
    "Gremio": "Gremio",
    "Sao Paulo": "Sao Paulo",
    "Vitoria": "Vitoria",
    "Botafogo RJ": "Botafogo",
    "Flamengo RJ": "Flamengo",
    "Corinthians": "Corinthians",
    "Cruzeiro": "Cruzeiro",
    "Internacional": "Internacional",
    "Criciuma": "Criciuma",
    "Goias": "Goias",
    "Ceara": "Ceara",
    "Cuiaba": "Cuiaba",
    "Atletico GO": "Atletico Goianiense",
    "Vila Nova FC": "Vila Nova",
    "Juventude": "Juventude",
    "Fortaleza": "Fortaleza",
    "Operario-PR": "Operario-PR",
    "Avai": "Avai",
    "America MG": "America Mineiro",
    "CRB": "CRB",
    "Novorizontino": "Novorizontino",
    "Nautico": "Nautico Recife",
    "Botafogo SP": "Botafogo SP",
    "Sport Recife": "Sport Recife",
    "Sao Bernardo": "Sao Bernardo",
    "Ponte Preta": "Ponte Preta",
    "Londrina": "Londrina",
    # Argentina
    "Union de Santa Fe": "Union Santa Fe",
    "Estudiantes L.P.": "Estudiantes L.P.",
    "Gimnasia L.P.": "Gimnasia La Plata",
    "Gimnasia Mendoza": "Gimnasia Mendoza",
    "Atl. Tucuman": "Atletico Tucuman",
    "Velez Sarsfield": "Velez Sarsfield",
    "Central Cordoba": "Central Cordoba",
    "Huracan": "Huracan",
    "Lanus": "Lanus",
    "Dep. Riestra": "Deportivo Riestra",
}


def normalize_team_name(name: str) -> str:
    """Normaliza un nombre de equipo para comparación determinista."""
    if not name:
        return ""
    name = unicodedata.normalize("NFKD", name)
    name = name.encode("ascii", "ignore").decode("ascii")
    name = name.lower()
    name = re.sub(r"[^a-z0-9 ]", "", name)
    name = re.sub(r"\s+", " ", name).strip()
    return name


def map_team(kambi_name: str):
    """Devuelve el nombre canónico API-Football para un nombre BetPlay.

    Orden: mapeo estático exacto -> normalización -> None (no mapeado).
    """
    if not kambi_name:
        return None
    key = kambi_name.strip()
    if key in TEAM_MAPPING:
        return TEAM_MAPPING[key]
    norm = normalize_team_name(key)
    for k, v in TEAM_MAPPING.items():
        if normalize_team_name(k) == norm or normalize_team_name(v) == norm:
            return v
    return None
