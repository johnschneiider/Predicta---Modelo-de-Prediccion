# -*- coding: utf-8 -*-
"""
Cliente API-Sports basketball (v1.basketball.api-sports.io) para NBA.

Plan Pro activo (7.500 req/día). Da calendario y resultados de 2025-26 y 2026-27.
NO incluye /games/statistics (box-scores) ni /odds → esos siguen por nba_api
(stats) y Kambi/BetPlay (cuotas).

Usa la misma key del .env (APIFOOTBALL_KEY — el plan basketball está en esa key).
"""
import json
import logging
import time
import urllib.request
import urllib.error

from .models import NBATeam, NBAGame

logger = logging.getLogger('basketball_data')

BASE = "https://v1.basketball.api-sports.io"
NBA_LEAGUE_ID = 12


def _load_key():
    with open('/var/www/predicta.com.co/.env') as f:
        for line in f:
            if line.strip().startswith('APIFOOTBALL_KEY='):
                return line.split('=', 1)[1].strip().strip("'\"")
    raise RuntimeError("APIFOOTBALL_KEY no encontrada en .env")


def _norm(s):
    import unicodedata
    s = unicodedata.normalize('NFKD', str(s or ''))
    return ''.join(c for c in s.lower() if c.isalnum())


class BasketballAPIService:
    def __init__(self):
        self.key = _load_key()
        self.delay = 0.4

    def _get(self, path, params=None):
        url = f"{BASE}/{path}"
        if params:
            url += "?" + "&".join(f"{k}={v}" for k, v in params.items())
        req = urllib.request.Request(url, headers={"x-apisports-key": self.key})
        for attempt in (1, 2, 3):
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    return json.loads(r.read().decode())
            except urllib.error.HTTPError as e:
                body = json.loads(e.read().decode())
                if e.code == 429 and attempt < 3:
                    time.sleep(2 * attempt)
                    continue
                return {"errors": body.get("errors", {"http": e.code})}
            except Exception as e:
                if attempt < 3:
                    time.sleep(2 * attempt)
                    continue
                return {"errors": {"exception": str(e)[:200]}}

    def fetch_games(self, season):
        body = self._get('games', {'league': NBA_LEAGUE_ID, 'season': season})
        if body.get('errors'):
            return None, body['errors']
        return body.get('response', []), None

    def sync_games(self, season):
        """Upsert de partidos de una temporada API ('2026-2027')."""
        games, errors = self.fetch_games(season)
        if errors:
            return {'errors': errors}
        teams_by_name = {_norm(t.full_name): t for t in NBATeam.objects.all()}
        teams_by_abbr = {t.abbreviation: t for t in NBATeam.objects.all()}
        created = updated = skipped = 0
        start_year = int(season.split('-')[0])
        preseason_cutoff = f"{start_year}-10-20"
        for g in games:
            ht = g.get('teams', {}).get('home', {})
            at = g.get('teams', {}).get('away', {})
            home = teams_by_name.get(_norm(ht.get('name')))
            away = teams_by_name.get(_norm(at.get('name')))
            if not home or not away:
                skipped += 1
                continue
            date_str = (g.get('date') or '').replace('Z', '+00:00')
            game_date = date_str[:10]
            season_type = 'Preseason' if game_date < preseason_cutoff else 'Regular Season'
            sh = (g.get('scores') or {}).get('home') or {}
            sa = (g.get('scores') or {}).get('away') or {}
            defaults = {
                'season_id': f'API-{season}',
                'game_date': game_date,
                'season_type': season_type,
                'home_team': home,
                'away_team': away,
                'home_points': sh.get('total'),
                'away_points': sa.get('total'),
                'home_win': (sh.get('total') > sa.get('total')) if (sh.get('total') is not None and sa.get('total') is not None) else None,
            }
            obj, was_created = NBAGame.objects.get_or_create(
                nba_game_id=f"api-{g.get('id')}", defaults=defaults)
            if was_created:
                created += 1
            else:
                for f, v in defaults.items():
                    setattr(obj, f, v)
                obj.save()
                updated += 1
        return {'created': created, 'updated': updated, 'skipped_no_team': skipped}


basketball_api_service = BasketballAPIService()
