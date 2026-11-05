from django.contrib import admin

from .models import (
    ParleyCoupon, ParleyCouponLeg, ParleyEngineConfig, ParleyLedger, ParleyRun,
)


@admin.register(ParleyEngineConfig)
class ParleyEngineConfigAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'activo', 'dry_run', 'stake', 'capital_inicial',
                    'ev_gate', 'max_legs', 'actualizado')
    list_filter = ('activo', 'dry_run')


@admin.register(ParleyCoupon)
class ParleyCouponAdmin(admin.ModelAdmin):
    list_display = ('coupon_ref', 'usuario', 'is_motor', 'dia', 'n_legs',
                    'status', 'stake', 'payout', 'played_odds', 'placed_date')
    list_filter = ('is_motor', 'status', 'sport')
    search_fields = ('coupon_ref', 'key', 'bet_ref')
    readonly_fields = ('creado', 'actualizado')


@admin.register(ParleyCouponLeg)
class ParleyCouponLegAdmin(admin.ModelAdmin):
    list_display = ('coupon', 'position', 'event_id', 'mercado', 'seleccion',
                    'linea', 'cuota_colocada', 'estado_final')
    list_filter = ('estado_final',)
    search_fields = ('coupon__coupon_ref', 'mercado', 'seleccion')


@admin.register(ParleyLedger)
class ParleyLedgerAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'tipo', 'monto', 'balance_after', 'coupon',
                    'creado')
    list_filter = ('tipo',)


@admin.register(ParleyRun)
class ParleyRunAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'modo', 'dia', 'ok', 'n_picks', 'n_candidates',
                    'n_placed', 'n_skipped', 'n_errors', 'started_at')
    list_filter = ('modo', 'ok')
    readonly_fields = ('started_at', 'finished_at')
