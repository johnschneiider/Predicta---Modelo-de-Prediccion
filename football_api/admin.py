from django.contrib import admin

from .models import ApiLeague, ApiTeam, ApiFixture, TeamFixtureStat, ApiOdds, SyncState


@admin.register(ApiLeague)
class ApiLeagueAdmin(admin.ModelAdmin):
    list_display = ("api_id", "name", "country", "type", "current_season", "priority", "backfill_status", "has_statistics", "active")
    list_filter = ("active", "backfill_status", "type", "country", "has_statistics")
    search_fields = ("name", "country", "predicta_name", "kambi_path")
    list_editable = ("priority", "active", "backfill_status")


@admin.register(ApiTeam)
class ApiTeamAdmin(admin.ModelAdmin):
    list_display = ("api_id", "name", "country", "kambi_name")
    search_fields = ("name", "country", "kambi_name", "normalized_name")


@admin.register(ApiFixture)
class ApiFixtureAdmin(admin.ModelAdmin):
    list_display = ("api_id", "league", "home_team", "away_team", "date", "status", "has_statistics", "season")
    list_filter = ("status", "has_statistics", "season", "league")
    search_fields = ("api_id", "home_team__name", "away_team__name")
    date_hierarchy = "date"


@admin.register(TeamFixtureStat)
class TeamFixtureStatAdmin(admin.ModelAdmin):
    list_display = ("fixture", "team", "total_shots", "shots_on_goal", "corner_kicks", "expected_goals")
    search_fields = ("team__name", "fixture__api_id")


@admin.register(ApiOdds)
class ApiOddsAdmin(admin.ModelAdmin):
    list_display = ("fixture", "bookmaker", "market", "outcome", "odds", "line")
    search_fields = ("bookmaker", "market", "outcome")


@admin.register(SyncState)
class SyncStateAdmin(admin.ModelAdmin):
    list_display = ("key", "status", "league_api_id", "season", "phase", "requests_today", "requests_remaining", "quota_date", "last_run_at")
    list_filter = ("key", "status")
