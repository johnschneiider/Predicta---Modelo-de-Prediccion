#!/usr/bin/env python3
"""
Scraper de corners desde adamchoi.co.uk
Uso: python3 scrape_corners.py --country Brazil --league "Serie A" --season 2026
"""

import sqlite3
import argparse
import re
import time
import unicodedata
import json
from datetime import datetime
from playwright.sync_api import sync_playwright


def parse_page_data(page_text: str) -> list:
    """
    Parsea el innerText de la página de adamchoi.co.uk/corners/detailed
    y extrae todos los partidos con corners.

    Estructura esperada:
        TeamName Overall O/U X.X Total Corners X% Y%
        HOME O/U X.X Total Corners X% Y%
        DD-MM-YYYY  HomeTeam  HC - AC  AwayTeam
        ...
        AWAY O/U X.X Total Corners X% Y%
        DD-MM-YYYY  HomeTeam  HC - AC  AwayTeam
        ...
    """
    matches = []
    lines = page_text.split('\n')

    current_team = None
    section = None  # 'home' or 'away'

    for i, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        # Detectar cabecera de equipo
        team_match = re.match(r'^(.+?) Overall O/U', line)
        if team_match:
            current_team = team_match.group(1).strip()
            section = None
            continue

        # Detectar sección HOME
        if line.startswith('HOME O/U'):
            section = 'home'
            continue

        # Detectar sección AWAY
        if line.startswith('AWAY O/U'):
            section = 'away'
            continue

        # Saltar líneas de "Next match" y odds
        if line.startswith('Next match'):
            continue
        if re.match(r'^\d+\.\d+$', line) and i > 0 and 'odds' in lines[i - 1].lower():
            continue

        # Intentar parsear fila de partido
        # Formato: DD-MM-YYYY  HomeTeam  HC - AC  AwayTeam
        match_row = re.match(
            r'^(\d{2}-\d{2}-\d{4})\s+(.+?)\s+(\d+)\s*-\s*(\d+)\s+(.+?)$',
            line
        )
        if match_row:
            date_str = match_row.group(1)
            home_team = match_row.group(2).strip()
            home_corners = int(match_row.group(3))
            away_corners = int(match_row.group(4))
            away_team = match_row.group(5).strip()

            # Validar que no sea una línea espuria
            if len(home_team) < 3 or len(away_team) < 3:
                continue

            matches.append({
                'date': date_str,
                'home_team': home_team,
                'away_team': away_team,
                'home_corners': home_corners,
                'away_corners': away_corners,
                'current_team': current_team,
                'section': section,
            })

    # DEDUP por date + home_team + away_team
    seen = set()
    unique = []
    for m in matches:
        key = f"{m['date']}|{m['home_team']}|{m['away_team']}"
        if key not in seen:
            seen.add(key)
            unique.append(m)

    return unique


def save_to_sqlite(matches: list, db_path: str, country: str, league: str, season: str):
    """Guarda los partidos en SQLite."""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS corners_matches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT NOT NULL,
        home_team TEXT NOT NULL,
        away_team TEXT NOT NULL,
        home_corners INTEGER NOT NULL,
        away_corners INTEGER NOT NULL,
        total_corners INTEGER GENERATED ALWAYS AS (home_corners + away_corners) STORED,
        league TEXT DEFAULT 'Unknown',
        country TEXT DEFAULT 'Unknown',
        season TEXT DEFAULT 'Unknown',
        scraped_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(date, home_team, away_team)
    )
    """)

    inserted = 0
    for m in matches:
        try:
            cursor.execute("""
            INSERT OR IGNORE INTO corners_matches
                (date, home_team, away_team, home_corners, away_corners, league, country, season)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                m['date'], m['home_team'], m['away_team'],
                m['home_corners'], m['away_corners'],
                league, country, season
            ))
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            print(f"  Error inserting {m['date']} {m['home_team']} vs {m['away_team']}: {e}")

    conn.commit()

    # Actualizar estadísticas agregadas por equipo
    cursor.execute("DELETE FROM team_corner_stats WHERE league = ? AND season = ?", (league, season))
    cursor.execute("""
    INSERT INTO team_corner_stats (team_name, league, season, role, avg_corners, matches_count)
    SELECT home_team, league, season, 'home', ROUND(AVG(home_corners), 2), COUNT(*)
    FROM corners_matches WHERE league = ? AND season = ?
    GROUP BY home_team, league, season
    """, (league, season))
    cursor.execute("""
    INSERT INTO team_corner_stats (team_name, league, season, role, avg_corners, matches_count)
    SELECT away_team, league, season, 'away', ROUND(AVG(away_corners), 2), COUNT(*)
    FROM corners_matches WHERE league = ? AND season = ?
    GROUP BY away_team, league, season
    """, (league, season))
    conn.commit()

    total = cursor.execute("SELECT COUNT(*) FROM corners_matches WHERE league=? AND season=?", (league, season)).fetchone()[0]
    conn.close()

    print(f"\n✅ {inserted} nuevos partidos insertados")
    print(f"📊 Total en DB: {total} partidos para {league} {season}")
    return total


def normalize_text(text: str) -> str:
    """Elimina acentos y normaliza Unicode (NFD -> quitar combining chars)."""
    return unicodedata.normalize('NFD', text).encode('ascii', 'ignore').decode('ascii')


def _select_option_with_fallback(page, selector_nth: int, label: str, field_name: str = "opción"):
    """
    Intenta seleccionar con label exacto, luego normalizado (sin acentos).
    Si falla, lista las opciones disponibles y lanza error descriptivo.
    """
    label_normalized = normalize_text(label)
    select = page.locator('select').nth(selector_nth)

    # Intentar exact match primero
    try:
        select.select_option(label=label, timeout=5000)
        return
    except Exception:
        pass

    # Intentar match normalizado (sin acentos)
    options = select.locator('option').all()
    for opt in options:
        opt_text = opt.inner_text().strip()
        if normalize_text(opt_text) == label_normalized:
            select.select_option(label=opt_text, timeout=5000)
            print(f"   ✅ Match normalizado: '{opt_text}' (recibido: '{label}')")
            return

    # Fallback: listar opciones disponibles
    available = [opt.inner_text().strip() for opt in options]
    raise ValueError(
        f"No se encontró '{field_name}: {label}' en las opciones.\n"
        f"   Opciones disponibles: {available[:15]}"
    )


def scrape_country_league_season(country: str, league: str, season: str,
                                 db_path: str = "corners.db",
                                 headless: bool = True):
    """
    Scrapea corners de una liga/país/temporada específica desde adamchoi.co.uk.
    """
    # Normalizar nombres para consistencia en DB
    league = normalize_text(league)
    country = normalize_text(country)
    url = "https://www.adamchoi.co.uk/corners/detailed"

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=headless)
        page = browser.new_page()
        page.set_default_timeout(30000)

        print(f"🌐 Navegando a {url}...")
        page.goto(url, wait_until='domcontentloaded')
        page.wait_for_timeout(2000)

        # Seleccionar país
        print(f"🔽 Seleccionando país: {country}")
        _select_option_with_fallback(page, 0, country, "país")
        page.wait_for_timeout(1500)

        # Seleccionar liga
        print(f"🔽 Seleccionando liga: {league}")
        _select_option_with_fallback(page, 1, league, "liga")
        page.wait_for_timeout(1500)

        # Seleccionar temporada
        print(f"🔽 Seleccionando temporada: {season}")
        _select_option_with_fallback(page, 2, str(season), "temporada")
        page.wait_for_timeout(2000)

        # Esperar que los datos carguen
        try:
            page.wait_for_selector('text=Overall O/U', timeout=15000)
        except:
            page.wait_for_timeout(3000)
        time.sleep(1)

        # Extraer texto completo de la página
        page_text = page.inner_text('body')
        browser.close()

    # Parsear datos
    print(f"📝 Parseando datos...")
    matches = parse_page_data(page_text)
    print(f"   {len(matches)} partidos extraídos del texto")

    if not matches:
        print("❌ No se encontraron partidos. Verifica los parámetros.")
        return 0

    # Guardar
    total = save_to_sqlite(matches, db_path, country, league, season)

    # Resumen
    teams = set()
    for m in matches:
        teams.add(m['home_team'])
        teams.add(m['away_team'])
    print(f"\n📋 Resumen:")
    print(f"   Equipos: {len(teams)}")
    print(f"   Rango fechas: {matches[-1]['date']} → {matches[0]['date']}")
    print(f"   DB: {db_path}")

    return total


def main():
    parser = argparse.ArgumentParser(description='Scraper de corners desde adamchoi.co.uk')
    parser.add_argument('--country', default='Brazil', help='País (default: Brazil)')
    parser.add_argument('--league', default='Serie A', help='Liga (default: Serie A)')
    parser.add_argument('--season', default='2026', help='Temporada (default: 2026)')
    parser.add_argument('--db', default='corners.db', help='Ruta DB SQLite')
    parser.add_argument('--no-headless', action='store_true', help='Mostrar navegador')
    args = parser.parse_args()

    print("=" * 60)
    print(f"🔍 SCRAPER DE CORNERS - adamchoi.co.uk")
    print(f"   País: {args.country}")
    print(f"   Liga: {args.league}")
    print(f"   Temp: {args.season}")
    print("=" * 60)

    scrape_country_league_season(
        country=args.country,
        league=args.league,
        season=args.season,
        db_path=args.db,
        headless=not args.no_headless
    )


if __name__ == '__main__':
    main()
