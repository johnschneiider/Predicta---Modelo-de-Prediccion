from django.contrib import admin

from .models import CapitalConfig, CapitalAjuste


@admin.register(CapitalConfig)
class CapitalConfigAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'modo', 'porcentaje', 'balance_inicial', 'ancla',
                    'stake_min_cop', 'stake_max_cop', 'actualizado')
    list_filter = ('modo',)
    search_fields = ('usuario__email',)
    readonly_fields = ('ancla', 'creado', 'actualizado')


@admin.register(CapitalAjuste)
class CapitalAjusteAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'monto_cop', 'motivo', 'fecha')
    search_fields = ('usuario__email', 'motivo')
    list_filter = ('motivo',)
