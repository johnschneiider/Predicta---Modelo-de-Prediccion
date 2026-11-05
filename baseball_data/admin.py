from django.contrib import admin
from .models import BaseballTeam, BaseballGame, BaseballPrediction


@admin.register(BaseballTeam)
class BaseballTeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'api_id')
    search_fields = ('name', 'code')


@admin.register(BaseballGame)
class BaseballGameAdmin(admin.ModelAdmin):
    list_display = ('date', 'away_team', 'home_team', 'away_runs', 'home_runs', 'season', 'status')
    list_filter = ('season', 'status')
    search_fields = ('home_team__name', 'away_team__name')
    date_hierarchy = 'date'


@admin.register(BaseballPrediction)
class BaseballPredictionAdmin(admin.ModelAdmin):
    list_display = ('created_at', 'game', 'model_name', 'pred_home_runs', 'pred_away_runs', 'p_home_win')
    list_filter = ('model_name',)
