"""
Cliente de API-Sports baseball (v1.baseball.api-sports.io) para MLB.
La key se lee de APIFOOTBALL_KEY del .env (misma key multi-deporte de la cuenta).
"""
import logging
import os
import time
import urllib.request
import urllib.error
import json

from django.db import transaction

from .models import BaseballTeam, BaseballGame

logger = logging.getLogger('baseball_data')

BASE = "https://v1.baseball.api-sports.io"
MLB_LEAGUE_ID = 1


def _load_key():
    env_path = "/var/www/predicta.com.co/.env"
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line.startswith("APIFOOTBALL_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise RuntimeError("APIFOOTBALL_KEY no encontrada en .env")


class MLBDataService:
    def __init__(self):
        self.key = _load_key()
        self.delay = 0.7  # segundos entre requests (cuota 7500/día)

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

    # ── Equipos ──────────────────────────────────────────────
    def sync_teams(self, season=2026):
        body = self._get("teams", {"league": MLB_LEAGUE_ID, "season": season})
        created = updated = 0
        for t in body.get("response", []):
            team, was_created = BaseballTeam.objects.get_or_create(
                api_id=t["id"],
                defaults={"name": t.get("name", ""), "code": t.get("code", ""),
                          "logo": t.get("logo", "")},
            )
            if not was_created:
                changed = False
                for field, val in (("name", t.get("name", "")),
                                   ("code", t.get("code", "")),
                                   ("logo", t.get("logo", ""))):
                    if val and getattr(team, field) != val:
                        setattr(team, field, val)
                        changed = True
                if changed:
                    team.save()
                    updated += 1
            else:
                created += 1
        return {"created": created, "updated": updated}

    # ── Partidos ─────────────────────────────────────────────
    def fetch_games(self, season):
        body = self._get("games", {"league": MLB_LEAGUE_ID, "season": season})
        if body.get("errors"):
            return None, body["errors"]
        return body.get("response", []), None

    def sync_games(self, season, quiet=False):
        games, errors = self.fetch_games(season)
        if errors:
            return {"errors": errors}
        created = updated = 0
        teams_cache = {t.api_id: t for t in BaseballTeam.objects.all()}
        missing_teams = []
        for g in games:
            home = g.get("teams", {}).get("home", {})
            away = g.get("teams", {}).get("away", {})
            home_id = home.get("id")
            away_id = away.get("id")
            if not home_id or not away_id:
                missing_teams.append(g["id"])
                continue
            ht = teams_cache.get(home_id)
            at = teams_cache.get(away_id)
            if ht is None or at is None:
                missing_teams.append(g["id"])
                continue
            scores = g.get("scores", {})
            sh = scores.get("home", {})
            sa = scores.get("away", {})
            date_str = g.get("date", "").replace("Z", "+00:00")

            defaults = {
                "season": season,
                "date": date_str,
                "status": g.get("status", {}).get("long", ""),
                "home_team": ht,
                "away_team": at,
                "home_runs": sh.get("total"),
                "away_runs": sa.get("total"),
                "home_hits": sh.get("hits"),
                "away_hits": sa.get("hits"),
                "home_errors": sh.get("errors"),
                "away_errors": sa.get("errors"),
                "innings_home": sh.get("innings") or {},
                "innings_away": sa.get("innings") or {},
            }
            obj, was_created = BaseballGame.objects.get_or_create(
                api_id=g["id"], defaults=defaults)
            if was_created:
                created += 1
            else:
                for f, v in defaults.items():
                    setattr(obj, f, v)
                obj.save()
                updated += 1
        return {"created": created, "updated": updated, "missing_teams": len(missing_teams)}

    # ── Odds (solo juegos recientes/futuros) ──────────────────
    def fetch_odds(self, game_api_id):
        body = self._get("odds", {"game": game_api_id})
        return body.get("response", [])

    # ── Partidos próximos ────────────────────────────────────
    def fetch_games_by_date(self, date_str):
        body = self._get("games", {"date": date_str, "league": MLB_LEAGUE_ID, "season": 2026})
        return body.get("response", [])


mlb_service = MLBDataService()
