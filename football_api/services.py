"""
Lógica de sincronización: seed de ligas, backfill histórico y sync diario.
"""

import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone

from .client import ApiFootballClient, QuotaExceeded, RateLimitError
from .models import ApiLeague, ApiTeam, ApiFixture, TeamFixtureStat, SyncState
from . import mappings

logger = logging.getLogger("football_api")

FINISHED_STATUSES = {"FT", "AET", "PEN", "AWD", "WO"}

# Mapa stat type -> campo del modelo
STAT_FIELD_MAP = {
    "Shots on Goal": "shots_on_goal",
    "Shots off Goal": "shots_off_goal",
    "Total Shots": "total_shots",
    "Blocked Shots": "blocked_shots",
    "Shots insidebox": "shots_insidebox",
    "Shots outsidebox": "shots_outsidebox",
    "Fouls": "fouls",
    "Corner Kicks": "corner_kicks",
    "Offsides": "offsides",
    "Ball Possession": "ball_possession",
    "Yellow Cards": "yellow_cards",
    "Red Cards": "red_cards",
    "Goalkeeper Saves": "goalkeeper_saves",
    "Total passes": "total_passes",
    "Passes accurate": "passes_accurate",
    "Passes %": "passes_pct",
    "expected_goals": "expected_goals",
    "goals_prevented": "goals_prevented",
}


def _int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _float(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def get_sync_state(key="backfill"):
    obj, _ = SyncState.objects.get_or_create(key=key)
    return obj


def persist_quota(state, client):
    """Guarda el estado de cuota actual para reanudar al día siguiente."""
    state.requests_remaining = client.daily_remaining if client.daily_remaining is not None else state.requests_remaining
    state.limit_day = client.daily_limit or state.limit_day
    state.requests_today = client.requests_made
    state.quota_date = timezone.localdate()
    state.save(update_fields=["requests_remaining", "limit_day", "requests_today", "quota_date", "updated_at"])


def seed_leagues(client=None):
    """Crea/actualiza las ligas de `mappings.LEAGUES` con cobertura y temporadas."""
    client = client or ApiFootballClient()
    created = updated = 0
    for idx, (predicta_name, api_id, kambi_path, country) in enumerate(mappings.LEAGUES):
        data = client.leagues(id=api_id)
        client.check_quota()
        resp = data.get("response", [])
        if not resp:
            logger.warning("Sin datos para liga %s (%s)", predicta_name, api_id)
            continue
        item = resp[0]
        league = item["league"]
        seasons = item.get("seasons", [])
        current = None
        # Cobertura real: miramos las últimas 3 temporadas (no solo la actual,
        # que al inicio de temporada puede no estar marcada aún).
        year_cov = {}
        for s in seasons:
            year = s["year"]
            c = s.get("coverage", {})
            fixtures_cov = c.get("fixtures", {})
            year_cov[year] = {
                "statistics": fixtures_cov.get("statistics_fixtures", False),
                "odds": c.get("odds", False),
                "predictions": c.get("predictions", False),
            }
            if s.get("current"):
                current = year

        target_years = sorted([current - i for i in range(3)])
        cov = {"statistics": False, "odds": False, "predictions": False}
        for y in target_years:
            yc = year_cov.get(y, {})
            cov["statistics"] = cov["statistics"] or yc.get("statistics", False)
            cov["odds"] = cov["odds"] or yc.get("odds", False)
            cov["predictions"] = cov["predictions"] or yc.get("predictions", False)

        defaults = {
            "name": league.get("name", predicta_name),
            "country": item.get("country", {}).get("name", country),
            "type": league.get("type", "League"),
            "logo": league.get("logo", ""),
            "kambi_path": kambi_path,
            "predicta_name": predicta_name,
            "current_season": current,
            "seasons": sorted([s["year"] for s in seasons]),
            "has_statistics": cov["statistics"],
            "has_odds": cov["odds"],
            "has_predictions": cov["predictions"],
            "priority": 0 if cov["statistics"] else 1,
            "active": True,
        }
        obj, was_created = ApiLeague.objects.update_or_create(api_id=api_id, defaults=defaults)
        if was_created:
            created += 1
        else:
            updated += 1
    logger.info("seed_leagues: %d creadas, %d actualizadas", created, updated)
    return created, updated


def target_seasons(league, num_previous=2):
    """Devuelve [actual, -1, -2] (ordenadas) para una liga."""
    current = league.current_season
    if not current:
        return []
    return sorted([current - i for i in range(num_previous + 1)])


def get_or_create_team(t):
    obj, _ = ApiTeam.objects.get_or_create(
        api_id=t["id"],
        defaults={
            "name": t.get("name", ""),
            "country": t.get("country", ""),
            "logo": t.get("logo", ""),
            "normalized_name": mappings.normalize_team_name(t.get("name", "")),
        },
    )
    return obj


def _save_fixture(league, season, fx):
    """Guarda un fixture (y sus equipos) desde el payload de /fixtures."""
    teams = fx.get("teams", {})
    home = teams.get("home", {})
    away = teams.get("away", {})
    home_team = get_or_create_team(home)
    away_team = get_or_create_team(away)

    fixture = fx.get("fixture", {})
    goals = fx.get("goals", {})
    score = fx.get("score", {})
    ht = score.get("halftime", {})
    ft = score.get("fulltime", {})
    et = score.get("extratime", {})
    pen = score.get("penalty", {})
    status = fixture.get("status", {})

    defaults = {
        "league": league,
        "season": season,
        "round": (fx.get("league", {}) or {}).get("round") or "",
        "home_team": home_team,
        "away_team": away_team,
        "date": fixture.get("date"),
        "status": status.get("short") or "",
        "status_long": status.get("long") or "",
        "home_score": _int(goals.get("home")),
        "away_score": _int(goals.get("away")),
        "ht_home": _int(ht.get("home")),
        "ht_away": _int(ht.get("away")),
        "ft_home": _int(ft.get("home")),
        "ft_away": _int(ft.get("away")),
        "et_home": _int(et.get("home")),
        "et_away": _int(et.get("away")),
        "pen_home": _int(pen.get("home")),
        "pen_away": _int(pen.get("away")),
        "venue": ((fixture.get("venue") or {}).get("name") or ""),
        "referee": (fixture.get("referee") or ""),
        "raw_json": fx,
    }
    obj, _ = ApiFixture.objects.update_or_create(api_id=fixture["id"], defaults=defaults)
    return obj


def save_statistics(fixture_obj, client):
    """Trae y guarda estadísticas de un fixture finalizado."""
    data = client.fixtures_statistics(fixture_obj.api_id)
    client.check_quota()
    stats_by_team = data.get("response", [])
    for entry in stats_by_team:
        team = entry.get("team", {})
        stats = entry.get("statistics", [])
        team_obj = get_or_create_team(team)
        fields = {"raw_json": entry}
        for s in stats:
            stype = s.get("type")
            field = STAT_FIELD_MAP.get(stype)
            if field:
                value = s.get("value")
                if value is None:
                    continue
                if field in ("ball_possession", "passes_pct"):
                    fields[field] = str(value)
                elif field in ("expected_goals", "goals_prevented"):
                    fields[field] = _float(value)
                else:
                    fields[field] = _int(value)
        TeamFixtureStat.objects.update_or_create(
            fixture=fixture_obj, team=team_obj, defaults=fields
        )
    fixture_obj.has_statistics = True
    fixture_obj.save(update_fields=["has_statistics"])


def fetch_fixtures(client, league, season, date_from=None, date_to=None, status=None):
    """Devuelve TODOS los fixtures de una liga/temporada (el endpoint no pagina)."""
    params = {"league": league.api_id, "season": season}
    if date_from:
        params["from"] = date_from
    if date_to:
        params["to"] = date_to
    if status:
        params["status"] = status
    data = client.fixtures(**params)
    client.check_quota()
    return data.get("response", [])


def backfill_league_season(client, league, season, state, fetch_stats=True):
    """Backfill de fixtures + stats de una liga/temporada. Resiste rate-limit."""
    fixtures = fetch_fixtures(client, league, season)
    total_fixtures = len(fixtures)
    stats_fetched = 0
    for fx in fixtures:
        obj = _save_fixture(league, season, fx)
        if fetch_stats and obj.status in FINISHED_STATUSES and not obj.has_statistics:
            save_statistics(obj, client)
            stats_fetched += 1
    return total_fixtures, stats_fetched


def run_backfill(fetch_stats=True, max_leagues=None):
    """Backfill completo (2 temporadas + actual) de todas las ligas activas.

    Avanza liga por liga. Ante QuotaExceeded pausa y guarda checkpoint.
    """
    client = ApiFootballClient()
    state = get_sync_state("backfill")
    state.status = "running"
    state.save(update_fields=["status", "updated_at"])

    leagues = ApiLeague.objects.filter(active=True).exclude(backfill_status="done").order_by("priority", "id")
    if max_leagues:
        leagues = leagues[:max_leagues]

    try:
        for league in leagues:
            try:
                seasons = target_seasons(league)
                if not seasons:
                    logger.warning("Liga %s sin temporadas; salto", league)
                    continue
                league.backfill_status = "backfilling"
                league.save(update_fields=["backfill_status"])
                for season in seasons:
                    state.league_api_id = league.api_id
                    state.season = season
                    state.phase = "fixtures"
                    state.save(update_fields=["league_api_id", "season", "phase", "updated_at"])
                    n_fx, n_st = backfill_league_season(client, league, season, state, fetch_stats=fetch_stats)
                    logger.info("Backfill %s (%s) s%s: %d fixtures, %d stats", league.name, league.api_id, season, n_fx, n_st)
                league.backfill_status = "done"
                league.last_backfill_at = timezone.now()
                league.save(update_fields=["backfill_status", "last_backfill_at"])
                try:
                    populate_legacy_matches(league_api_id=league.api_id, clear_first=True)
                except Exception:
                    logger.exception("Error poblando Match legacy para %s", league.name)
            except QuotaExceeded:
                raise  # pausa todo el run
            except RateLimitError as e:
                # Rate-limit por minuto: no es error fatal, deja la liga pendiente para reintentar
                league.backfill_status = "pending"
                league.save(update_fields=["backfill_status"])
                logger.warning("Rate-limit en %s (%s): %s — queda pendiente", league.name, league.api_id, e)
            except Exception as e:
                league.backfill_status = "error"
                league.save(update_fields=["backfill_status"])
                logger.exception("Error en liga %s (%s)", league.name, league.api_id)
        state.status = "done"
    except QuotaExceeded as e:
        state.status = "paused"
        state.error_log = str(e)
        persist_quota(state, client)
        logger.warning("Backfill pausado por cuota: %s", e)
    except Exception as e:
        state.status = "error"
        state.error_log = str(e)
        persist_quota(state, client)
        logger.exception("Error en backfill")
        raise
    finally:
        state.save(update_fields=["status", "error_log", "updated_at"])
    return state.status


def run_daily_sync(days_ahead=7, days_back=3):
    """Sync diario: fixtures próximos + stats de finalizados recientes.

    - Trae fixtures de las próximas `days_ahead` jornadas.
    - Actualiza stats de partidos finalizados en los últimos `days_back` días
      que aún no tengan estadísticas.
    """
    client = ApiFootballClient()
    state = get_sync_state("daily")
    state.status = "running"
    state.save(update_fields=["status", "updated_at"])

    now = timezone.now()
    date_from = (now - timedelta(days=days_back)).strftime("%Y-%m-%d")
    date_to = (now + timedelta(days=days_ahead)).strftime("%Y-%m-%d")

    total_fx = 0
    total_st = 0
    try:
        for league in ApiLeague.objects.filter(active=True).order_by("priority", "id"):
            if not league.current_season:
                continue
            state.league_api_id = league.api_id
            state.season = league.current_season
            state.phase = "daily"
            state.save(update_fields=["league_api_id", "season", "phase", "updated_at"])

            # 1) Fixtures en la ventana (próximos + recientes)
            fixtures = fetch_fixtures(
                client, league, league.current_season,
                date_from=date_from, date_to=date_to,
            )
            for fx in fixtures:
                _save_fixture(league, league.current_season, fx)
                total_fx += 1

            # 2) Stats de finalizados recientes sin stats
            pending = ApiFixture.objects.filter(
                league=league, status__in=FINISHED_STATUSES, has_statistics=False,
                date__gte=now - timedelta(days=days_back),
            )
            for fx in pending:
                save_statistics(fx, client)
                total_st += 1

        state.status = "done"
    except QuotaExceeded as e:
        state.status = "paused"
        state.error_log = str(e)
        persist_quota(state, client)
        logger.warning("Daily sync pausado por cuota: %s", e)
    except Exception as e:
        state.status = "error"
        state.error_log = str(e)
        persist_quota(state, client)
        logger.exception("Error en daily sync")
        raise
    finally:
        state.save(update_fields=["status", "error_log", "updated_at"])
    return state.status, total_fx, total_st


# ── ETL: poblar la tabla legacy `football_data.Match` desde API-Football ──
# Los motores (corners_model, xg_shots, DixonColes) leen `Match`; esto cambia
# SOLO el origen de datos (API-Football en vez de Excel/Flashscore), sin
# reentrenar ni tocar la lógica de los motores.


def _legacy_league_map():
    """ApiLeague.api_id -> football_data.League.id (cache)."""
    from football_data.models import League as LegacyLeague
    m = {}
    for al in ApiLeague.objects.all():
        if al.predicta_league_id:
            m[al.api_id] = al.predicta_league_id
            continue
        lg = LegacyLeague.objects.filter(name=al.predicta_name).first()
        if lg:
            m[al.api_id] = lg.id
            al.predicta_league_id = lg.id
            al.save(update_fields=["predicta_league_id"])
    return m


def _dec(value):
    if value is None:
        return None
    try:
        return Decimal(str(round(float(value), 3)))
    except (TypeError, ValueError):
        return None


def _ftr(h, a):
    if h is None or a is None:
        return None
    return "H" if h > a else ("A" if a > h else "D")


def populate_legacy_matches(league_api_id=None, clear_first=False):
    """Mapea ApiFixture (con stats) -> football_data.Match.

    - league_api_id: si se indica, solo procesa esa liga (ApiLeague.api_id).
    - clear_first: borra los Match legacy de la liga antes de insertar los nuevos
      (evita duplicados por nombres de equipos distintos entre fuentes).

    Devuelve (creados, actualizados, borrados).
    """
    from football_data.models import Match as LegacyMatch

    league_map = _legacy_league_map()
    leagues = ApiLeague.objects.all()
    if league_api_id:
        leagues = leagues.filter(api_id=league_api_id)

    created = updated = deleted = 0
    for al in leagues:
        lid = league_map.get(al.api_id)
        if not lid:
            continue
        if clear_first:
            n, _ = LegacyMatch.objects.filter(league_id=lid).delete()
            deleted += n

        qs = ApiFixture.objects.filter(league=al, has_statistics=True).select_related("home_team", "away_team")
        for fx in qs.iterator():
            stats = {s.team_id: s for s in fx.stats.all()}
            hs = stats.get(fx.home_team_id)
            aws = stats.get(fx.away_team_id)

            fthg = fx.home_score
            ftag = fx.away_score
            hc = hs.corner_kicks if hs else None
            ac = aws.corner_kicks if aws else None

            defaults = {
                "date": fx.date.date(),
                "time": fx.date.time(),
                "home_team": fx.home_team.name,
                "away_team": fx.away_team.name,
                "fthg": fthg,
                "ftag": ftag,
                "ftr": _ftr(fthg, ftag),
                "hthg": fx.ht_home,
                "htag": fx.ht_away,
                "htr": _ftr(fx.ht_home, fx.ht_away),
                "hs": hs.total_shots if hs else None,
                "as_field": aws.total_shots if aws else None,
                "hst": hs.shots_on_goal if hs else None,
                "ast": aws.shots_on_goal if aws else None,
                "hf": hs.fouls if hs else None,
                "af": aws.fouls if aws else None,
                "hc": hc,
                "ac": ac,
                "hy": hs.yellow_cards if hs else None,
                "ay": aws.yellow_cards if aws else None,
                "hr": hs.red_cards if hs else None,
                "ar": aws.red_cards if aws else None,
                "xg_home": _dec(hs.expected_goals if hs else None),
                "xg_away": _dec(aws.expected_goals if aws else None),
                "corners_total": (hc + ac) if (hc is not None and ac is not None) else None,
                "corners_home": hc,
                "corners_away": ac,
                "both_teams_score": (fthg > 0 and ftag > 0) if (fthg is not None and ftag is not None) else None,
            }
            obj, was_created = LegacyMatch.objects.update_or_create(
                league_id=lid,
                date=defaults["date"],
                home_team=defaults["home_team"],
                away_team=defaults["away_team"],
                defaults=defaults,
            )
            if was_created:
                created += 1
            else:
                updated += 1
    return created, updated, deleted
