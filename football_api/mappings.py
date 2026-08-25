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
    ("Scottish Premiership", 179, "football/scotland/premier_league", "Scotland"),
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
