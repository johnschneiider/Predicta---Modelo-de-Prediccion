from django.contrib import admin

from .models import InspeccionApuesta


@admin.register(InspeccionApuesta)
class InspeccionApuestaAdmin(admin.ModelAdmin):
    list_display = ('creado', 'veredicto', 'direccion', 'apuesta_resumen', 'estado_kambi',
                    'estado_esperado', 'confianza', 'aviso_usuario')
    list_filter = ('veredicto', 'direccion', 'confianza', 'aviso_usuario')
    search_fields = ('apuesta__home_team', 'apuesta__away_team', 'apuesta__usuario__email',
                     'apuesta__coupon_ref')
    readonly_fields = ('creado', 'actualizado')
    date_hierarchy = 'creado'

    @admin.display(description='Apuesta')
    def apuesta_resumen(self, obj):
        a = obj.apuesta
        return f'{a.home_team} vs {a.away_team} — {a.seleccion}'
