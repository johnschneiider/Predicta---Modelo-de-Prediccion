"""
Admin para predicciones de IA
"""

from django.contrib import admin
from .models import PredictionModel, PredictionResult, TeamStats, SavedPrediction, Apuesta


@admin.register(PredictionModel)
class PredictionModelAdmin(admin.ModelAdmin):
    list_display = ['name', 'model_type', 'prediction_type', 'league', 'accuracy', 'r2_score', 'trained_at', 'is_active']
    list_filter = ['model_type', 'prediction_type', 'league', 'is_active']
    search_fields = ['name', 'league__name']
    readonly_fields = ['trained_at', 'last_updated']
    ordering = ['-trained_at']


@admin.register(PredictionResult)
class PredictionResultAdmin(admin.ModelAdmin):
    list_display = ['home_team', 'away_team', 'league', 'predicted_value', 'confidence_score', 'predicted_at']
    list_filter = ['league', 'model__prediction_type', 'predicted_at']
    search_fields = ['home_team', 'away_team', 'league__name']
    readonly_fields = ['predicted_at']
    ordering = ['-predicted_at']


@admin.register(TeamStats)
class TeamStatsAdmin(admin.ModelAdmin):
    list_display = ['team_name', 'league', 'avg_shots_total', 'recent_wins', 'recent_draws', 'recent_losses', 'updated_at']
    list_filter = ['league', 'updated_at']
    search_fields = ['team_name', 'league__name']
    readonly_fields = ['updated_at']
    ordering = ['team_name']


@admin.register(SavedPrediction)
class SavedPredictionAdmin(admin.ModelAdmin):
    list_display = ['home_team', 'away_team', 'league', 'user', 'created_at']
    list_filter = ['league', 'created_at']
    search_fields = ['home_team', 'away_team', 'league__name', 'user__email']
    readonly_fields = ['created_at']
    ordering = ['-created_at']


@admin.register(Apuesta)
class ApuestaAdmin(admin.ModelAdmin):
    list_display = ['user', 'home_team', 'away_team', 'market', 'selection', 'line', 'status', 'created_at']
    list_filter = ['market', 'selection', 'status', 'created_at']
    search_fields = ['home_team', 'away_team', 'league_name', 'user__email']
    readonly_fields = ['created_at']
    ordering = ['-created_at']
