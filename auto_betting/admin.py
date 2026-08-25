from django.contrib import admin
from .models import AutoBetConfig, AutoBet, DailyCounter, HistorialApuesta, OddsSnapshot, MarketFilterConfig


@admin.register(AutoBetConfig)
class AutoBetConfigAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'punter_id', 'cuota_minima', 'stake', 'max_apuestas_diarias', 'activo']
    list_filter = ['activo']
    search_fields = ['usuario__email', 'punter_id']
    readonly_fields = ['creado', 'actualizado']


@admin.register(AutoBet)
class AutoBetAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'home_team', 'away_team', 'liga', 'mercado', 'seleccion', 'linea', 'cuota', 'edge',
                    'coupon_ref', 'estado', 'creado']
    list_filter = ['usuario', 'estado', 'liga', 'creado']
    search_fields = ['home_team', 'away_team', 'coupon_ref']
    readonly_fields = ['creado', 'actualizado']
    ordering = ['-creado']


@admin.register(DailyCounter)
class DailyCounterAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'fecha', 'apuestas_colocadas']
    list_filter = ['usuario']
    ordering = ['-fecha']


@admin.register(HistorialApuesta)
class HistorialApuestaAdmin(admin.ModelAdmin):
    list_display = ['usuario', 'placed_date', 'home_team', 'away_team', 'liga', 'mercado', 'seleccion',
                    'played_odds', 'stake', 'payout', 'bet_status']
    list_filter = ['usuario', 'bet_status', 'sport', 'liga']
    search_fields = ['home_team', 'away_team', 'mercado', 'coupon_ref']
    ordering = ['-placed_date']
    readonly_fields = ['creado', 'actualizado']


@admin.register(MarketFilterConfig)
class MarketFilterConfigAdmin(admin.ModelAdmin):
    list_display = ['id', 'actualizado', 'actualizado_por']
    readonly_fields = ['actualizado']


@admin.register(OddsSnapshot)
class OddsSnapshotAdmin(admin.ModelAdmin):
    list_display = ['outcome_id', 'event_id', 'market', 'seleccion', 'linea', 'odds_decimal', 'captured_at']
    list_filter = ['market']
    search_fields = ['outcome_id', 'event_id', 'market']
    ordering = ['-captured_at']
    readonly_fields = ['captured_at']
