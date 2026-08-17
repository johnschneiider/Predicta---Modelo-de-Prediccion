from django.contrib import admin
from .models import AutoBetConfig, AutoBet, DailyCounter, HistorialApuesta


@admin.register(AutoBetConfig)
class AutoBetConfigAdmin(admin.ModelAdmin):
    list_display = ['punter_id', 'cuota_minima', 'odds_minima', 'stake', 'max_apuestas_diarias', 'activo']
    readonly_fields = ['creado', 'actualizado']


@admin.register(AutoBet)
class AutoBetAdmin(admin.ModelAdmin):
    list_display = ['home_team', 'away_team', 'liga', 'mercado', 'seleccion', 'linea', 'cuota', 'edge',
                    'coupon_ref', 'estado', 'creado']
    list_filter = ['estado', 'liga', 'creado']
    search_fields = ['home_team', 'away_team', 'coupon_ref']
    readonly_fields = ['creado', 'actualizado']
    ordering = ['-creado']


@admin.register(DailyCounter)
class DailyCounterAdmin(admin.ModelAdmin):
    list_display = ['fecha', 'apuestas_colocadas']
    ordering = ['-fecha']


@admin.register(HistorialApuesta)
class HistorialApuestaAdmin(admin.ModelAdmin):
    list_display = ['placed_date', 'home_team', 'away_team', 'liga', 'mercado', 'seleccion',
                    'played_odds', 'stake', 'payout', 'bet_status']
    list_filter = ['bet_status', 'sport', 'liga']
    search_fields = ['home_team', 'away_team', 'mercado', 'coupon_ref']
    ordering = ['-placed_date']
    readonly_fields = ['creado', 'actualizado']
