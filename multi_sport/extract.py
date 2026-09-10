#!/usr/bin/env python3
"""
Extractor multi-deporte para API-Sports (predicta).

- Lee la key del .env del proyecto (nunca la imprime).
- Cada deporte (menos football) tiene plan Free: 100 req/día.
- Almacena en SQLite separado: multi_sport.db (no toca la BD de producción).
- Throttle conservador: 1 req/1.2s y presupuesto configurable por deporte.
"""
import argparse
import json
import logging
import re
import sqlite3
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

ENV_PATH = "/var/www/predicta.com.co/.env"
DB_PATH = "/var/www/predicta.com.co/multi_sport/multi_sport.db"

SPORTS = {
    "basketball": {
        "base": "https://v1.basketball.api-sports.io",
        "leagues_ep": "/leagues",
        "games_ep": "/games",
        "season_ep_param": "season",
        "league_key": "league",
    },
    "baseball": {
        "base": "https://v1.baseball.api-sports.io",
        "leagues_ep": "/leagues",
        "games_ep": "/games",
        "league_key": "league",
    },
    "volleyball": {
        "base": "https://v1.volleyball.api-sports.io",
        "leagues_ep": "/leagues",
        "games_ep": "/games",
        "league_key": "league",
    },
    "hockey": {
        "base": "https://v1.hockey.api-sports.io",
        "leagues_ep": "/leagues",
        "games_ep": "/games",
        "league_key": "league",
    },
    "handball": {
        "base": "https://v1.handball.api-sports.io",
        "leagues_ep": "/leagues",
        "games_ep": "/games",
        "league_key": "league",
    },
    "rugby": {
        "base": "https://v1.rugby.api-sports.io",
        "leagues_ep": "/leagues",
        "games_ep": "/games",
        "league_key": "league",
    },
    "mma": {
        "base": "https://v1.mma.api-sports.io",
        "leagues_ep": "/leagues",
        "games_ep": "/fights",
        "league_key": "league",
    },
    "formula-1": {
        "base": "https://v1.formula-1.api-sports.io",
        "leagues_ep": "/competitions",
        "games_ep": "/races",
        "league_key": "competition",
    },
    "american-football": {
        "base": "https://v1.american-football.api-sports.io",
        "leagues_ep": "/leagues",
        "games_ep": "/games",
        "league_key": "league",
    },
}

log = logging.getLogger("multi_sport")


def load_key():
    with open(ENV_PATH) as f:
        for line in f:
            line = line.strip()
            if line.startswith("APIFOOTBALL_KEY="):
                return line.split("=", 1)[1].strip().strip("'\"")
    raise SystemExit("APIFOOTBALL_KEY no encontrada en .env")


class SportClient:
    """Cliente HTTP genérico con throttle y presupuesto por deporte."""

    def __init__(self, sport, cfg, api_key, max_requests):
        self.sport = sport
        self.cfg = cfg
        self.api_key = api_key
        self.max_requests = max_requests
        self.used = 0
        self.daily_remaining = None
        self.rate_remaining = None
        self._last_call = 0.0

    def get(self, endpoint, params):
        if self.used >= self.max_requests:
            log.warning("[%s] presupuesto agotado (%d req)", self.sport, self.used)
            return None
        # throttle
        wait = 1.2 - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        url = self.cfg["base"] + endpoint
        if params:
            url += "?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers={"x-apisports-key": self.api_key})
        self._last_call = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                body = json.loads(r.read().decode())
                self.daily_remaining = r.headers.get("x-ratelimit-requests-remaining")
                self.rate_remaining = r.headers.get("x-ratelimit-remaining")
            self.used += 1
            return body
        except urllib.error.HTTPError as e:
            self.used += 1
            if e.code == 429:
                log.warning("[%s] 429 rate-limit en %s", self.sport, endpoint)
                time.sleep(2)
            else:
                log.warning("[%s] HTTP %s en %s", self.sport, e.code, endpoint)
            return None
        except Exception as e:
            self.used += 1
            log.warning("[%s] error en %s: %s", self.sport, endpoint, e)
            return None


def init_db():
    con = sqlite3.connect(DB_PATH)
    con.executescript(
        """
        CREATE TABLE IF NOT EXISTS sport_leagues (
            id INTEGER PRIMARY KEY,
            sport TEXT NOT NULL,
            api_id INTEGER NOT NULL,
            name TEXT,
            type TEXT,
            country TEXT,
            logo TEXT,
            seasons TEXT,
            raw_json TEXT,
            first_seen TEXT,
            last_seen TEXT,
            UNIQUE(sport, api_id)
        );
        CREATE TABLE IF NOT EXISTS sport_teams (
            id INTEGER PRIMARY KEY,
            sport TEXT NOT NULL,
            api_id INTEGER NOT NULL,
            name TEXT,
            country TEXT,
            logo TEXT,
            raw_json TEXT,
            UNIQUE(sport, api_id)
        );
        CREATE TABLE IF NOT EXISTS sport_fixtures (
            id INTEGER PRIMARY KEY,
            sport TEXT NOT NULL,
            api_id INTEGER NOT NULL,
            league_api_id INTEGER,
            season TEXT,
            date_utc TEXT,
            status TEXT,
            home_team_api_id INTEGER,
            away_team_api_id INTEGER,
            home_score INTEGER,
            away_score INTEGER,
            raw_json TEXT,
            updated_at TEXT,
            UNIQUE(sport, api_id)
        );
        CREATE INDEX IF NOT EXISTS idx_fx_sport_league ON sport_fixtures(sport, league_api_id);
        """
    )
    con.commit()
    return con


def _j(v):
    return json.dumps(v, ensure_ascii=False) if v is not None else None


def _s(v):
    """Normaliza valores que a veces vienen como dict {name: ...}."""
    if isinstance(v, dict):
        return v.get("name")
    return v


def _now():
    return time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime())


def upsert_league(con, sport, lg):
    keys = ("id", "name", "type", "country", "logo", "seasons")
    if not isinstance(lg, dict):
        return
    api_id = lg.get("id")
    if api_id is None:
        return
    now = _now()
    con.execute(
        """INSERT INTO sport_leagues(sport,api_id,name,type,country,logo,seasons,raw_json,first_seen,last_seen)
           VALUES(?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(sport,api_id) DO UPDATE SET
             name=excluded.name, type=excluded.type, country=excluded.country,
             logo=excluded.logo, seasons=excluded.seasons, raw_json=excluded.raw_json,
             last_seen=excluded.last_seen""",
        (
            sport, api_id, _s(lg.get("name")), _s(lg.get("type")), _s(lg.get("country")),
            _s(lg.get("logo")), _j(lg.get("seasons")), _j(lg), now, now,
        ),
    )


def upsert_team(con, sport, tm):
    if not isinstance(tm, dict):
        return
    api_id = tm.get("id")
    if api_id is None:
        return
    con.execute(
        """INSERT INTO sport_teams(sport,api_id,name,country,logo,raw_json)
           VALUES(?,?,?,?,?,?)
           ON CONFLICT(sport,api_id) DO UPDATE SET
             name=excluded.name, country=excluded.country, logo=excluded.logo,
             raw_json=excluded.raw_json""",
        (sport, api_id, _s(tm.get("name")), _s(tm.get("country")), _s(tm.get("logo")), _j(tm)),
    )


def upsert_fixture(con, sport, fx, league_api_id, season):
    if not isinstance(fx, dict):
        return
    api_id = fx.get("id")
    if api_id is None:
        return
    teams = fx.get("teams") or {}
    home = teams.get("home") or {}
    away = teams.get("away") or {}
    if isinstance(home, dict):
        upsert_team(con, sport, home)
    if isinstance(away, dict):
        upsert_team(con, sport, away)
    scores = fx.get("scores") or {}
    hs = (scores.get("home") or {}).get("total")
    as_ = (scores.get("away") or {}).get("total")
    con.execute(
        """INSERT INTO sport_fixtures(sport,api_id,league_api_id,season,date_utc,status,
             home_team_api_id,away_team_api_id,home_score,away_score,raw_json,updated_at)
           VALUES(?,?,?,?,?,?,?,?,?,?,?,?)
           ON CONFLICT(sport,api_id) DO UPDATE SET
             status=excluded.status, home_score=excluded.home_score,
             away_score=excluded.away_score, raw_json=excluded.raw_json,
             updated_at=excluded.updated_at""",
        (
            sport, api_id, league_api_id, season, fx.get("date"),
            (fx.get("status") or {}).get("long"),
            home.get("id"), away.get("id"), hs, as_, _j(fx), _now(),
        ),
    )


def pick_season(seasons, max_year):
    """Elige la temporada más reciente permitida por el plan Free (<= max_year).

    Los elementos de `seasons` son dicts {season, start, end} en basketball,
    o strings en otros deportes.
    """
    cands = []
    for s in seasons or []:
        if isinstance(s, dict):
            val, start = s.get("season"), s.get("start")
        else:
            val, start = s, None
        if val is None:
            continue
        m = re.match(r"(\d{4})", str(val))
        if not m:
            continue
        year = int(m.group(1))
        if year <= max_year:
            cands.append((year, start or "", str(val)))
    if not cands:
        return None
    cands.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return cands[0][2]


def extract_sport(con, sport, cfg, client, min_season=None, max_year=2024):
    log.info("[%s] === inicio (presupuesto %d req) ===", sport, client.max_requests)
    # 1) ligas
    body = client.get(cfg["leagues_ep"], {})
    leagues = []
    if body and isinstance(body.get("response"), list):
        leagues = body["response"]
    else:
        log.warning("[%s] no se pudieron listar ligas", sport)
        return 0
    for lg in leagues:
        upsert_league(con, sport, lg)
    con.commit()
    log.info("[%s] ligas obtenidas: %d", sport, len(leagues))

    # 2) partidos por liga (temporada más reciente disponible)
    n_fixtures = 0
    leagues_done = 0
    for lg in leagues:
        if client.used >= client.max_requests - 2:
            break
        api_id = lg.get("id")
        season = pick_season(lg.get("seasons"), max_year)
        if not season:
            continue
        if min_season and season < str(min_season):
            continue
        # no re-fetchear ligas ya extraídas para esa temporada
        done = con.execute(
            "SELECT 1 FROM sport_fixtures WHERE sport=? AND league_api_id=? AND season=? LIMIT 1",
            (sport, api_id, season),
        ).fetchone()
        if done:
            continue
        params = {cfg["league_key"]: api_id, "season": season}
        body = client.get(cfg["games_ep"], params)
        if not body:
            continue
        items = body.get("response") or []
        if not items and (body.get("errors") or {}):
            # plan Free rechazó la temporada -> probar una más atrás
            prev = pick_season(
                [s for s in (lg.get("seasons") or []) if str(s.get("season") if isinstance(s, dict) else s) != season],
                max_year,
            )
            if prev:
                params["season"] = prev
                body = client.get(cfg["games_ep"], params)
                items = body.get("response") or [] if body else []
                season = prev
        for fx in items:
            upsert_fixture(con, sport, fx, api_id, str(season))
        n_fixtures += len(items)
        leagues_done += 1
        con.commit()
        if len(items) >= 100:
            log.info("[%s] liga %s: %d partidos (posible truncado)", sport, api_id, len(items))
    log.info(
        "[%s] === fin: %d ligas procesadas, %d partidos, %d req usados, "
        "daily_remaining=%s ===",
        sport, leagues_done, n_fixtures, client.used, client.daily_remaining,
    )
    return n_fixtures


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sport", default="all", help="Deporte o 'all'")
    ap.add_argument("--max-req", type=int, default=60, help="Presupuesto por deporte (default 60, deja margen del plan Free de 100)")
    ap.add_argument("--min-season", default=None, help="Solo temporadas >= este valor")
    ap.add_argument("--max-year", type=int, default=2024, help="Año máximo de temporada permitido por el plan Free (default 2024)")
    args = ap.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    key = load_key()
    con = init_db()

    sports = SPORTS if args.sport == "all" else {args.sport: SPORTS[args.sport]}
    total = 0
    for sport, cfg in sports.items():
        client = SportClient(sport, cfg, key, args.max_req)
        total += extract_sport(con, sport, cfg, client, args.min_season, args.max_year)
    con.close()
    log.info("TOTAL partidos extraídos en esta corrida: %d", total)
    print(f"DONE total_fixtures={total}")


if __name__ == "__main__":
    main()
