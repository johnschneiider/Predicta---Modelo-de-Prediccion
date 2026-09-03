"""
Backfill de xG (Fase 2, 2026-09-03): rellena Match.xg_home / xg_away desde
API-Football (TeamFixtureStat.expected_goals) para partidos que no lo tienen.

Matching seguro (evita falsos emparejamientos):
  1. Liga con NOMBRE IDÉNTICO en ambos sistemas.
  2. Fecha del fixture API dentro de ±1 día del partido.
  3. Fuzzy match de equipos (SequenceMatcher >= 0.80) local-vs-local y
     visitante-vs-visitante.
  4. UN solo fixture candidato por partido.
  5. Verificación de marcador: home_score == fthg y away_score == ftag
     (si la API tiene score y no coincide, se descarta).

Idempotente: solo toca partidos con xg_home IS NULL.
Uso: python scripts/backfill_xg_from_api.py [--year 2026] [--limit 0]
"""
import os
import sys
import argparse

sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()

import datetime
from datetime import timedelta
from difflib import SequenceMatcher

from football_data.models import Match
from football_api.models import ApiFixture, ApiLeague, TeamFixtureStat


def _ratio(a, b):
    a = (a or '').strip().lower()
    b = (b or '').strip().lower()
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--year', type=int, default=2026)
    ap.add_argument('--limit', type=int, default=0, help='0 = sin límite (prueba)')
    args = ap.parse_args()

    qs = Match.objects.filter(
        date__year=args.year, xg_home__isnull=True,
    ).select_related('league')
    if args.limit:
        qs = qs[:args.limit]
    total = qs.count()

    # Índice de fixtures API por liga: {(league_name, date): [fixture, ...]}
    api_leagues = {l.name: l for l in ApiLeague.objects.all()}
    api_league_names = list(api_leagues.keys())
    fixtures = (ApiFixture.objects.filter(date__year=args.year)
                .select_related('home_team', 'away_team', 'league'))
    by_league_date = {}
    for f in fixtures:
        key = (f.league.name, f.date.date())
        by_league_date.setdefault(key, []).append(f)

    # Mapeo fuzzy de ligas (football_data -> API), con caché.
    liga_cache = {}
    def liga_api_para(nombre_fd):
        if nombre_fd in liga_cache:
            return liga_cache[nombre_fd]
        if nombre_fd in api_leagues:
            liga_cache[nombre_fd] = nombre_fd
            return nombre_fd
        # mejor fuzzy único con ratio >= 0.75 y gap con el segundo >= 0.05
        scores = sorted(
            ((_ratio(nombre_fd, n), n) for n in api_league_names),
            reverse=True,
        )[:2]
        if scores and scores[0][0] >= 0.75:
            if len(scores) == 1 or (scores[0][0] - scores[1][0]) >= 0.05:
                liga_cache[nombre_fd] = scores[0][1]
                return scores[0][1]
        liga_cache[nombre_fd] = None
        return None

    # xG por fixture: {fixture_id: {'home': xg, 'away': xg}}
    xg_map = {}
    for ts in TeamFixtureStat.objects.filter(
        fixture__date__year=args.year, expected_goals__isnull=False,
    ).select_related('fixture', 'team'):
        d = xg_map.setdefault(ts.fixture_id, {})
        if ts.team_id == ts.fixture.home_team_id:
            d['home'] = float(ts.expected_goals)
        elif ts.team_id == ts.fixture.away_team_id:
            d['away'] = float(ts.expected_goals)

    rellenados = 0
    sin_fixture = 0
    ambiguos = 0
    score_mismatch = 0
    sin_xg_stats = 0
    for m in qs.iterator():
        liga_nombre_api = liga_api_para(m.league.name)
        if not liga_nombre_api:
            sin_fixture += 1
            continue
        # m.date puede ser DateField (date) o DateTimeField; normalizar a date
        m_date = m.date if isinstance(m.date, datetime.date) else m.date.date()
        candidatos = []
        for delta in (-1, 0, 1):
            candidatos.extend(
                by_league_date.get((liga_nombre_api, m_date + timedelta(days=delta)), [])
            )
        if not candidatos:
            sin_fixture += 1
            continue
        # filtrar por fuzzy de equipos
        buenos = []
        for f in candidatos:
            rh = _ratio(f.home_team.name, m.home_team)
            ra = _ratio(f.away_team.name, m.away_team)
            if rh >= 0.80 and ra >= 0.80:
                buenos.append(f)
        if not buenos:
            sin_fixture += 1
            continue
        if len(buenos) > 1:
            ambiguos += 1
            continue
        f = buenos[0]
        xg = xg_map.get(f.id)
        if not xg or 'home' not in xg or 'away' not in xg:
            sin_xg_stats += 1
            continue
        # verificación de marcador (si la API tiene score)
        if f.home_score is not None and f.away_score is not None:
            if m.fthg is not None and m.ftag is not None:
                if f.home_score != m.fthg or f.away_score != m.ftag:
                    score_mismatch += 1
                    continue
        m.xg_home = xg['home']
        m.xg_away = xg['away']
        m.save(update_fields=['xg_home', 'xg_away'])
        rellenados += 1

    print(f'Backfill xG {args.year}:')
    print(f'  Sin xG al inicio: {total}')
    print(f'  Rellenados:       {rellenados}')
    print(f'  Sin fixture API:  {sin_fixture}')
    print(f'  Ambigüos:         {ambiguos}')
    print(f'  Score mismatch:   {score_mismatch}')
    print(f'  Sin stats xG:     {sin_xg_stats}')


if __name__ == '__main__':
    main()
