#!/usr/bin/env python3
"""
Scraper de datos históricos desde Flashscore (resultados + xG + stats).

Carga partidos terminados en el modelo Match de Predicta (misma tabla que
las ligas europeas), unificando todo en db.sqlite3.

Uso:
  # 1) Descubrir las temporadas disponibles de una liga
  python flashscore_scrape.py --slug football/colombia/primera-a --list-seasons

  # 2) Scrapear una temporada completa (resultados + xG + stats)
  python flashscore_scrape.py --league "Primera A (Colombia)" \
      --slug football/colombia/primera-a --seasons 2025 2024 2023

  # 3) Solo resultados (rápido, sin visitar el detalle)
  python flashscore_scrape.py --league "Primera A (Colombia)" \
      --slug football/colombia/primera-a --seasons 2025 --mode results

Requiere: venv de predicta con playwright + chromium de sistema.
Ejecutar como www-data para no romper ownership de db.sqlite3.
"""

import os
import sys
import re
import time
import random
import argparse
import logging
from datetime import datetime

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
os.environ['DJANGO_ALLOW_ASYNC_UNSAFE'] = 'true'
sys.path.insert(0, '/var/www/predicta.com.co')

import django  # noqa: E402
django.setup()

from django.db import transaction  # noqa: E402
from football_data.models import League, Match  # noqa: E402
from playwright.sync_api import sync_playwright  # noqa: E402

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
log = logging.getLogger('flashscore')

BASE = 'https://www.flashscore.com'

# Chromium de sistema (sin depender del cache de root)
CHROMIUM = '/usr/bin/chromium'

# ── Configuración de ligas: (nombre DB, slug Flashscore) ──
LEAGUE_CONFIG = {
    'sa': [
        ("Primera A (Colombia)", "football/colombia/primera-a"),
        ("Primera Division (Argentina)", "football/argentina/liga-profesional"),
        ("Serie A (Brasil)", "football/brazil/serie-a-betano"),
        ("Serie B (Brasil)", "football/brazil/serie-b"),
        ("Liga MX (Mexico)", "football/mexico/liga-mx"),
        ("US MLS (USA)", "football/usa/mls"),
    ],
    'europe': [
        ("Premier League", "football/england/premier-league"),
        ("Championship", "football/england/championship"),
        ("League One", "football/england/league-one"),
        ("League Two", "football/england/league-two"),
        ("La Liga", "football/spain/laliga"),
        ("Segunda División", "football/spain/laliga2"),
        ("Bundesliga", "football/germany/bundesliga"),
        ("2. Bundesliga", "football/germany/2-bundesliga"),
        ("Serie A", "football/italy/serie-a"),
        ("Serie B", "football/italy/serie-b"),
        ("Ligue 1", "football/france/ligue-1"),
        ("Ligue 2", "football/france/ligue-2"),
        ("Eredivisie", "football/netherlands/eredivisie"),
        ("Primeira Liga", "football/portugal/liga-portugal"),
        ("Süper Lig", "football/turkey/super-lig"),
        ("Jupiler Pro League", "football/belgium/jupiler-pro-league"),
        ("Scottish Premiership", "football/scotland/premiership"),
        ("Scottish Championship", "football/scotland/championship"),
        ("SuperLiga (Grecia)", "football/greece/super-league"),
    ],
    # 14 ligas nuevas (agregadas 2026-08-17 a pedido de John)
    'nuevas': [
        ("Liga Pro (Ecuador)", "football/ecuador/liga-pro"),
        ("Primera Division (Chile)", "football/chile/liga-de-primera"),
        ("Superligaen (Dinamarca)", "football/denmark/superliga"),
        ("Allsvenskan (Suecia)", "football/sweden/allsvenskan"),
        ("Veikkausliiga (Finlandia)", "football/finland/veikkausliiga"),
        ("NB I (Hungria)", "football/hungary/nb-i"),
        ("Super Liga (Serbia)", "football/serbia/mozzart-bet-super-liga"),
        ("PFL 1 (Bulgaria)", "football/bulgaria/efbet-league"),
        ("Liga I (Rumania)", "football/romania/superliga"),
        ("Premijer Liga (Bosnia)", "football/bosnia-and-herzegovina/wwin-liga-bih"),
        ("Premier Liga (Azerbaiyan)", "football/azerbaijan/premier-league"),
        ("Urvalsdeild (Islandia)", "football/iceland/besta-deild-karla"),
        ("Primera Division (Costa Rica)", "football/costa-rica/primera-division"),
        ("Primera Nacional (Argentina)", "football/argentina/primera-nacional"),
    ],
    # 3 segundas divisiones latinoamericanas (agregadas 2026-08-20)
    # NOTA: México usa formato de temporada Apertura/Clausura (YYYY-YYYY),
    #   ej. --seasons 2025-2026 2024-2025. Colombia y Ecuador usan año simple (2025).
    'segunda': [
        ("Primera B (Colombia)", "football/colombia/primera-b"),
        ("Serie B (Ecuador)", "football/ecuador/serie-b"),
        ("Liga de Expansion MX (Mexico)", "football/mexico/liga-de-expansion-mx"),
    ],
}


# ─────────────────────────────────────────────────────────────────────────
#  UTILIDADES DE PARSEO
# ─────────────────────────────────────────────────────────────────────────

def _num(s):
    """Convierte '13' o '13.5' o '38%' a float/int, o None."""
    if s is None:
        return None
    s = str(s).strip().replace('%', '').replace(',', '.')
    if not s:
        return None
    try:
        f = float(s)
        return int(f) if f == int(f) else f
    except ValueError:
        return None


def _extract_stat(text, label):
    """
    Extrae (home_val, away_val) de un bloque de stats con formato:
        {home_val}
        {label}
        {away_val}
    Devuelve (None, None) si no encuentra el label.
    """
    lines = text.split('\n')
    for i, line in enumerate(lines):
        if line.strip() == label and i > 0 and i + 1 < len(lines):
            return _num(lines[i - 1].strip()), _num(lines[i + 1].strip())
    return None, None


def parse_match_detail(text):
    """
    Parsea el innerText de la página de detalle de un partido terminado.
    Devuelve dict con campos del modelo Match.
    """
    d = {}

    # ── Título: "Home v Away DD/MM/YYYY [Stats]" ──
    m = re.search(r'^([^\n]+?)\s+v\s+([^\n]+?)\s+(\d{1,2}/\d{1,2}/\d{4})', text.strip(), re.M)
    if m:
        d['home_team'] = m.group(1).strip()
        d['away_team'] = m.group(2).strip()
        try:
            d['date'] = datetime.strptime(m.group(3), '%d/%m/%Y').date()
        except ValueError:
            d['date'] = None
    else:
        return None

    # ── Marcador final (bloque "...FINISHED") ──
    # Patrón: HomeName\nH\n-\nA\nFINISHED\nAwayName\nH\n-\nA\nFINISHED
    fin = re.search(r'\n(\d+)\s*\n\s*-\s*\n\s*(\d+)\s*\n\s*FINISHED', text)
    if fin:
        d['fthg'] = int(fin.group(1))
        d['ftag'] = int(fin.group(2))
        if d['fthg'] > d['ftag']:
            d['ftr'] = 'H'
        elif d['fthg'] < d['ftag']:
            d['ftr'] = 'A'
        else:
            d['ftr'] = 'D'
    else:
        # Partido no terminado o marcador no parseable
        return None

    # ── Marcador 1er tiempo / 2do tiempo ──
    ht = re.search(r'1ST HALF\s*\n\s*(\d+)\s*-\s*(\d+)', text)
    if ht:
        d['hthg'] = int(ht.group(1))
        d['htag'] = int(ht.group(2))
    hth = re.search(r'HALF TIME\s*\n\s*(\d+)\s*-\s*(\d+)', text)
    if hth:
        d['hthg'] = int(hth.group(1))
        d['htag'] = int(hth.group(2))

    # ── Stats (xG, tiros, córners, tarjetas, posesión) ──
    d['xg_home'], d['xg_away'] = _extract_stat(text, 'Expected goals (xG)')
    d['hs'], d['as_field'] = _extract_stat(text, 'Total shots')
    d['hst'], d['ast'] = _extract_stat(text, 'Shots on target')
    if d['hst'] is None:
        d['hst'], d['ast'] = _extract_stat(text, 'Shots on goal')
    d['hc'], d['ac'] = _extract_stat(text, 'Corner kicks')
    d['hf'], d['af'] = _extract_stat(text, 'Fouls')
    d['hy'], d['ay'] = _extract_stat(text, 'Yellow cards')
    d['hr'], d['ar'] = _extract_stat(text, 'Red cards')

    # BTTS derivado
    if d.get('fthg') is not None and d.get('ftag') is not None:
        d['both_teams_score'] = (d['fthg'] > 0 and d['ftag'] > 0)

    # Córners totales
    if d.get('hc') is not None and d.get('ac') is not None:
        d['corners_total'] = d['hc'] + d['ac']

    return d


def parse_results_listing(text, season=None):
    """
    Extrae resultados (marcadores) directamente del listado /results/.
    
    El formato de fecha en el listado puede ser:
      - Temporada actual (sin año): 'DD.MM.YYYY' (ej. 22.12.2024)
      - Temporada histórica (con año): 'DD.MM. HH:MM' (ej. 24.05. 15:00)
    
    Para el formato corto (sin año), el año se infiere del season
    ('YYYY-YYYY' → año inicio si mes>=8, año fin si mes<8).
    
    Devuelve lista de dicts compatibles con save_match (solo fthg/ftag/ftr).
    """
    results = []
    lines = text.split('\n')
    i = 0
    n = len(lines)
    date_full_re = re.compile(r'^(\d{2})\.(\d{2})\.(\d{4})$')
    date_short_re = re.compile(r'^(\d{2})\.(\d{2})\.\s+\d{2}:\d{2}$')

    # Inferir año inicio/fin de la temporada (para fechas cortas sin año)
    year_start = year_end = None
    if season:
        m = re.match(r'^(\d{4})-(\d{4})$', str(season))
        if m:
            year_start, year_end = int(m.group(1)), int(m.group(2))
        else:
            m = re.match(r'^(\d{4})$', str(season))
            if m:
                year_start = int(m.group(1))
                year_end = year_start + 1

    while i < n - 4:
        line = lines[i].strip()
        fecha_str = None
        m = date_full_re.match(line)
        if m:
            fecha_str = line
        else:
            m = date_short_re.match(line)
            if m and year_start:
                day, month = int(m.group(1)), int(m.group(2))
                year = year_start if month >= 8 else year_end
                fecha_str = f'{day:02d}.{month:02d}.{year}'
        if fecha_str:
            home = lines[i + 1].strip()
            away = lines[i + 2].strip()
            hg = lines[i + 3].strip()
            ag = lines[i + 4].strip()
            # Validar: home/away son nombres (no fechas, no vacíos), hg/ag son dígitos
            if (home and away
                    and not date_full_re.match(home) and not date_full_re.match(away)
                    and not date_short_re.match(home) and not date_short_re.match(away)
                    and hg.isdigit() and ag.isdigit()
                    and not home.isdigit() and not away.isdigit()):
                try:
                    d = datetime.strptime(fecha_str, '%d.%m.%Y').date()
                except ValueError:
                    d = None
                fthg, ftag = int(hg), int(ag)
                if fthg > ftag:
                    ftr = 'H'
                elif fthg < ftag:
                    ftr = 'A'
                else:
                    ftr = 'D'
                results.append({
                    'date': d,
                    'home_team': home,
                    'away_team': away,
                    'fthg': fthg,
                    'ftag': ftag,
                    'ftr': ftr,
                })
                i += 5
                continue
        i += 1
    return results


# ─────────────────────────────────────────────────────────────────────────
#  NAVEGACIÓN
# ─────────────────────────────────────────────────────────────────────────

def dismiss_popups(page):
    """Cierra cookie consent y age gate si aparecen."""
    for label in ['Reject All', 'Reject all', "I'm 18 and older"]:
        try:
            b = page.locator(f"button:has-text('{label}')")
            if b.count() > 0:
                b.first.click(timeout=2000)
                page.wait_for_timeout(500)
        except Exception:
            pass


def get_season_match_links(page, slug_year):
    """
    Navega a /football/.../SLUG-YEAR/results/ y extrae los matchId.
    Hace scroll + click en "Show more matches" hasta agotar.
    """
    url = f"{BASE}/{slug_year}/results/"
    log.info(f"  → {url}")
    page.goto(url, wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(3000)
    dismiss_popups(page)

    # Scroll y "Show more" hasta que no queden más
    for _ in range(60):
        try:
            btn = page.locator("button:has-text('Show more matches'), a:has-text('Show more matches')")
            if btn.count() > 0:
                btn.first.scroll_into_view_if_needed(timeout=3000)
                btn.first.click(timeout=3000)
                page.wait_for_timeout(1500)
            else:
                break
        except Exception:
            break
        # scroll al fondo para lazy-load
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)

    links = page.eval_on_selector_all(
        "a[href*='/match/']",
        "els => els.map(e => e.href).filter(h => h.includes('mid='))"
    )
    # dedup manteniendo orden (devolvemos URL completa)
    seen, urls = set(), []
    for h in links:
        mid = re.search(r'mid=([A-Za-z0-9]+)', h)
        if mid and mid.group(1) not in seen:
            seen.add(mid.group(1))
            urls.append(h)
    return urls


def get_results_listing_text(page, slug_year):
    """
    Navega a /results/ y devuelve el innerText completo del body
    (tras scroll + 'Show more matches'). Útil para extraer marcadores
    sin visitar el detalle de cada partido.
    """
    url = f"{BASE}/{slug_year}/results/"
    log.info(f"  → {url}")
    page.goto(url, wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(3000)
    dismiss_popups(page)

    for _ in range(60):
        try:
            btn = page.locator("button:has-text('Show more matches'), a:has-text('Show more matches')")
            if btn.count() > 0:
                btn.first.scroll_into_view_if_needed(timeout=3000)
                btn.first.click(timeout=3000)
                page.wait_for_timeout(1500)
            else:
                break
        except Exception:
            break
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)

    return page.inner_text('body')


def get_results_listing_dom(page, slug_year, season=None):
    """
    Extrae resultados del DOM estructurado de la página /results/.
    Más robusto que el innerText plano (maneja marcadores 0-0 correctamente).
    
    Usa los selectores WCL de Flashscore:
      .event__homeParticipant span, .event__awayParticipant span,
      .event__score--home, .event__score--away, .event__stageTime
    
    Devuelve lista de dicts compatibles con save_match_result.
    """
    url = f"{BASE}/{slug_year}/results/"
    log.info(f"  → {url}")
    page.goto(url, wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(3000)
    dismiss_popups(page)

    for _ in range(60):
        try:
            btn = page.locator("button:has-text('Show more matches'), a:has-text('Show more matches')")
            if btn.count() > 0:
                btn.first.scroll_into_view_if_needed(timeout=3000)
                btn.first.click(timeout=3000)
                page.wait_for_timeout(1500)
            else:
                break
        except Exception:
            break
        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        page.wait_for_timeout(1000)

    events = page.eval_on_selector_all('div.event__match', '''els => els.map(e => {
        const h = e.querySelector('.event__homeParticipant span')?.innerText || '';
        const a = e.querySelector('.event__awayParticipant span')?.innerText || '';
        const sh = e.querySelector('.event__score--home')?.innerText || '';
        const sa = e.querySelector('.event__score--away')?.innerText || '';
        const t = e.querySelector('.event__stageTime')?.innerText || '';
        const link = e.querySelector('a[href*="mid="]')?.href || '';
        return {time: t, home: h, away: a, sh: sh, sa: sa, link: link};
    })''')

    # Inferir año inicio/fin de la temporada (para fechas sin año)
    year_start = year_end = None
    if season:
        m = re.match(r'^(\d{4})-(\d{4})$', str(season))
        if m:
            year_start, year_end = int(m.group(1)), int(m.group(2))
        else:
            m = re.match(r'^(\d{4})$', str(season))
            if m:
                year_start = int(m.group(1))
                year_end = year_start + 1

    results = []
    for ev in events:
        t = (ev.get('time') or '').strip()
        home = (ev.get('home') or '').strip()
        away = (ev.get('away') or '').strip()
        sh = (ev.get('sh') or '').strip()
        sa = (ev.get('sa') or '').strip()
        if not home or not away or not sh.isdigit() or not sa.isdigit():
            continue
        # Parsear fecha: 'DD.MM. HH:MM' o 'DD.MM.YYYY'
        m = re.match(r'^(\d{2})\.(\d{2})\.\s+\d{2}:\d{2}$', t)
        if m:
            day, month = int(m.group(1)), int(m.group(2))
            if year_start:
                year = year_start if month >= 8 else year_end
            else:
                year = datetime.now().year
            fecha = datetime(year, month, day).date()
        else:
            m = re.match(r'^(\d{2})\.(\d{2})\.(\d{4})$', t)
            if not m:
                continue
            fecha = datetime(int(m.group(3)), int(m.group(2)), int(m.group(1))).date()
        fthg, ftag = int(sh), int(sa)
        if fthg > ftag:
            ftr = 'H'
        elif fthg < ftag:
            ftr = 'A'
        else:
            ftr = 'D'
        results.append({
            'date': fecha,
            'home_team': home,
            'away_team': away,
            'fthg': fthg,
            'ftag': ftag,
            'ftr': ftr,
            'link': ev.get('link', ''),
        })
    return results


def scrape_match(page, url, retries=1):
    """Visita la pestaña de stats de un partido y devuelve el dict parseado."""
    stats_url = url.replace('/?mid=', '/summary/stats/?mid=')
    mid = re.search(r'mid=([A-Za-z0-9]+)', url)
    mid = mid.group(1) if mid else '?'
    for attempt in range(retries + 1):
        try:
            page.goto(stats_url, wait_until='domcontentloaded', timeout=45000)
            page.wait_for_timeout(2500)
            dismiss_popups(page)
            text = page.inner_text('body')
            d = parse_match_detail(text)
            if d:
                return d
            log.warning(f"    ✗ {mid}: parseo sin datos (intento {attempt+1})")
        except Exception as e:
            log.warning(f"    ✗ {mid}: {str(e)[:80]} (intento {attempt+1})")
        if attempt < retries:
            time.sleep(3)
    return None


# ─────────────────────────────────────────────────────────────────────────
#  PERSISTENCIA
# ─────────────────────────────────────────────────────────────────────────

def _normalize_team_name(name):
    """Normaliza nombres de equipos para matching."""
    if not name:
        return name
    n = name.strip()
    # Mapeo de nombres cortos a largos
    replacements = {
        'Atl. ': 'Atletico ',
        'Athletico ': 'Atletico ',
        'Atl ': 'Atletico ',
    }
    for short, long in replacements.items():
        if n.startswith(short):
            n = long + n[len(short):]
    return n


def _find_existing_match(league, date, home_team, away_team, prefer_no_stats=False):
    """Busca un partido existente por fecha y nombres fuzzy.
    Si prefer_no_stats=True, prefiere el registro sin córners."""
    # Búsqueda exacta primero
    qs = Match.objects.filter(
        league=league, date=date,
        home_team=home_team, away_team=away_team
    )
    if prefer_no_stats:
        m = qs.filter(hc__isnull=True).first()
        if m:
            return m
    m = qs.first()
    if m:
        return m
    # Probar nombre normalizado
    home_norm = _normalize_team_name(home_team)
    qs2 = Match.objects.filter(
        league=league, date=date,
        home_team=home_norm, away_team=away_team
    )
    if prefer_no_stats:
        m = qs2.filter(hc__isnull=True).first()
        if m:
            return m
    m = qs2.first()
    if m:
        return m
    # Búsqueda fuzzy: mismo league, fecha, away_team similar
    from difflib import SequenceMatcher
    candidates = list(Match.objects.filter(league=league, date=date))
    # Si prefer_no_stats, ordenar: sin stats primero
    if prefer_no_stats:
        candidates.sort(key=lambda x: (x.hc is not None))
    for c in candidates:
        ratio_home = SequenceMatcher(None, home_team.lower(), c.home_team.lower()).ratio()
        ratio_away = SequenceMatcher(None, away_team.lower(), c.away_team.lower()).ratio()
        if ratio_home > 0.6 and ratio_away > 0.6:
            return c
    return None


def save_match(league, d, skip_existing_stats=False):
    """Inserta o actualiza el partido respetando unique_together.
    Si skip_existing_stats=True, no actualiza si el partido ya tiene córners."""
    if not d or not d.get('date') or not d.get('home_team') or not d.get('away_team'):
        return False
    if skip_existing_stats:
        existing = _find_existing_match(
            league, d['date'], d['home_team'], d['away_team']
        )
        if existing and existing.hc is not None:
            return False  # ya tiene stats, saltar
    fields = {
        'fthg': d.get('fthg'), 'ftag': d.get('ftag'), 'ftr': d.get('ftr'),
        'hthg': d.get('hthg'), 'htag': d.get('htag'),
        'hs': d.get('hs'), 'as_field': d.get('as_field'),
        'hst': d.get('hst'), 'ast': d.get('ast'),
        'hf': d.get('hf'), 'af': d.get('af'),
        'hc': d.get('hc'), 'ac': d.get('ac'),
        'hy': d.get('hy'), 'ay': d.get('ay'),
        'hr': d.get('hr'), 'ar': d.get('ar'),
        'xg_home': d.get('xg_home'), 'xg_away': d.get('xg_away'),
        'corners_total': d.get('corners_total'),
        'both_teams_score': d.get('both_teams_score'),
    }
    # Buscar partido existente (fuzzy match)
    existing = _find_existing_match(league, d['date'], d['home_team'], d['away_team'], prefer_no_stats=True)
    if existing:
        # Actualizar el registro existente
        for k, v in fields.items():
            if v is not None:
                setattr(existing, k, v)
        existing.save()
        return False  # no fue creado nuevo
    # Crear nuevo registro
    Match.objects.create(league=league, date=d['date'],
                         home_team=d['home_team'], away_team=d['away_team'], **fields)
    return True


def save_match_result(league, d):
    """
    Inserta o actualiza SOLO el resultado (fthg/ftag/ftr), sin tocar stats.
    Usado por el modo 'results' para backfill rápido de marcadores.
    """
    if not d or not d.get('date') or not d.get('home_team') or not d.get('away_team'):
        return False
    if d.get('fthg') is None or d.get('ftag') is None:
        return False
    obj, created = Match.objects.update_or_create(
        league=league,
        date=d['date'],
        home_team=d['home_team'],
        away_team=d['away_team'],
        defaults={'fthg': d['fthg'], 'ftag': d['ftag'], 'ftr': d.get('ftr')},
    )
    return created


# ─────────────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────────────

def list_seasons_with_page(page, slug):
    """Descubre temporadas disponibles de una liga usando una página ya abierta."""
    page.goto(f"{BASE}/{slug}/archive/", wait_until='domcontentloaded', timeout=45000)
    page.wait_for_timeout(3000)
    dismiss_popups(page)
    years = []
    for h in page.eval_on_selector_all("a[href*='-20'], a[href*='-19']", "els => els.map(e=>e.href)"):
        m = re.search(r'/([a-z0-9-]+-(\d{4}))/?$', h)
        if m and m.group(1).startswith(slug.split('/')[-1] + '-'):
            y = m.group(2)
            if y not in years:
                years.append(y)
    return sorted(years, reverse=True)


def list_seasons(slug):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=CHROMIUM, args=['--no-sandbox'])
        page = browser.new_page()
        r = list_seasons_with_page(page, slug)
        browser.close()
        return r


def scrape_league(page, league_name, slug, seasons, mode, max_matches, delay, skip_existing_stats=False):
    """Scrapea las temporadas de una liga. Devuelve (creados, existentes, errores)."""
    league = League.objects.filter(name=league_name).first()
    if not league:
        log.error(f"Liga no encontrada en DB: {league_name}")
        return 0, 0, 0

    if not seasons:
        seasons = list_seasons_with_page(page, slug)
        log.info(f"[{league_name}] {len(seasons)} temporadas: {seasons}")

    tot_c = tot_s = tot_e = 0
    for season in seasons:
        if season in ('', 'current'):
            slug_year = slug  # temporada actual (sin año)
        else:
            slug_year = f"{slug}-{season}" if not slug.endswith(f"-{season}") else slug
        log.info(f"=== {league_name} / {season} ===")

        # ── MODO RESULTS: extraer marcadores del DOM (rápido) ──
        if mode == 'results':
            results = get_results_listing_dom(page, slug_year, season)
            log.info(f"  {len(results)} resultados encontrados en el listado")
            created = skipped = 0
            for i, r in enumerate(results):
                if max_matches and i >= max_matches:
                    break
                try:
                    if save_match_result(league, r):
                        created += 1
                    else:
                        skipped += 1
                except Exception as e:
                    log.warning(f"    ✗ guardar {r.get('home_team')} vs {r.get('away_team')}: {str(e)[:80]}")
            log.info(f"  → {season}: {created} nuevos, {skipped} existentes")
            tot_c += created; tot_s += skipped
            continue

        # ── MODO FULL con skip_existing_stats: pre-filtrar del DOM ──
        if skip_existing_stats:
            # Usar get_results_listing_dom para obtener team names + fechas + links
            results = get_results_listing_dom(page, slug_year, season)
            log.info(f"  {len(results)} partidos en el listado DOM")
            # Pre-filtrar: solo visitar partidos que no tienen stats
            to_scrape = []
            for r in results:
                if not r.get('link'):
                    continue
                existing = Match.objects.filter(
                    league=league, date=r['date'],
                    home_team=r['home_team'], away_team=r['away_team'],
                    hc__isnull=False
                ).exists()
                if not existing:
                    to_scrape.append(r)
            log.info(f"  {len(to_scrape)} partidos necesitan stats (de {len(results)} totales)")

            created = skipped = errors = consec_err = 0
            for i, r in enumerate(to_scrape):
                if max_matches and i >= max_matches:
                    break
                url = r['link']
                d = scrape_match(page, url)
                if not d:
                    errors += 1
                    consec_err += 1
                    if consec_err >= 5:
                        log.error(f"    5 errores consecutivos. Saltando {league_name}/{season}.")
                        break
                    continue
                consec_err = 0
                if save_match(league, d, skip_existing_stats=True):
                    created += 1
                else:
                    skipped += 1
                if (i + 1) % 10 == 0:
                    log.info(f"    {i+1}/{len(to_scrape)} | nuevos={created} existentes={skipped} errores={errors}")
                time.sleep(delay + random.uniform(0, 1.5))

            log.info(f"  → {season}: {created} nuevos, {skipped} existentes, {errors} errores")
            tot_c += created; tot_s += skipped; tot_e += errors
            continue

        # ── MODO FULL normal (sin pre-filtro) ──
        mids = get_season_match_links(page, slug_year)
        log.info(f"  {len(mids)} partidos encontrados")

        created = skipped = errors = consec_err = 0
        for i, url in enumerate(mids):
            if max_matches and i >= max_matches:
                break
            d = scrape_match(page, url)
            if not d:
                errors += 1
                consec_err += 1
                if consec_err >= 5:
                    log.error(f"    5 errores consecutivos. Saltando {league_name}/{season}.")
                    break
                continue
            consec_err = 0
            if save_match(league, d, skip_existing_stats=skip_existing_stats):
                created += 1
            else:
                skipped += 1
            if (i + 1) % 10 == 0:
                log.info(f"    {i+1}/{len(mids)} | nuevos={created} existentes={skipped} errores={errors}")
            time.sleep(delay + random.uniform(0, 1.5))

        log.info(f"  → {season}: {created} nuevos, {skipped} existentes, {errors} errores")
        tot_c += created; tot_s += skipped; tot_e += errors
    return tot_c, tot_s, tot_e


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--slug', default=None)
    ap.add_argument('--league', default=None, help='Nombre exacto de la liga en DB')
    ap.add_argument('--seasons', nargs='*', type=str, default=[], help='Años a scrapear (vacío = autodetectar)')
    ap.add_argument('--list-seasons', action='store_true')
    ap.add_argument('--mode', choices=['full', 'results'], default='full')
    ap.add_argument('--max', type=int, default=0, help='Límite de partidos por temporada (0=sin límite)')
    ap.add_argument('--delay', type=float, default=2.5, help='Delay entre partidos')
    ap.add_argument('--sa', action='store_true', help='Scrapear todas las ligas de Suramérica')
    ap.add_argument('--europe', action='store_true', help='Scrapear todas las ligas de Europa')
    ap.add_argument('--nuevas', action='store_true', help='Scrapear las 14 ligas nuevas (2026-08-17)')
    ap.add_argument('--segunda', action='store_true', help='Scrapear las 3 segundas divisiones latinoamericanas (2026-08-20)')
    ap.add_argument('--skip-existing-stats', action='store_true',
                   help='Saltar partidos que ya tienen córners en DB (backfill eficiente)')
    ap.add_argument('--current', action='store_true', help='Solo temporada actual (sin año)')
    args = ap.parse_args()

    if args.list_seasons:
        if not args.slug:
            log.error('--list-seasons requiere --slug')
            sys.exit(1)
        print(list_seasons(args.slug))
        return

    if args.current:
        args.seasons = ['current']

    # Determinar la lista de (league, slug) a procesar
    jobs = []
    if args.sa:
        jobs += LEAGUE_CONFIG['sa']
    if args.europe:
        jobs += LEAGUE_CONFIG['europe']
    if args.nuevas:
        jobs += LEAGUE_CONFIG['nuevas']
    if args.segunda:
        jobs += LEAGUE_CONFIG['segunda']
    if args.slug:
        jobs.append((args.league, args.slug))
    if not jobs:
        ap.print_help()
        sys.exit(1)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, executable_path=CHROMIUM, args=['--no-sandbox'])
        page = browser.new_page()
        page.set_default_timeout(40000)

        for league_name, slug in jobs:
            if not league_name:
                log.error(f'Falta --league para el slug {slug}')
                continue
            c, s, e = scrape_league(page, league_name, slug, args.seasons, args.mode, args.max, args.delay,
                                   skip_existing_stats=args.skip_existing_stats)
            log.info(f"[{league_name}] TOTAL: {c} nuevos, {s} existentes, {e} errores")

        browser.close()

    log.info("Listo.")


if __name__ == '__main__':
    main()
