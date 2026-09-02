from django.contrib import admin

from .models import NotificacionConfig, NotificacionEstado, NotificacionLog


@admin.register(NotificacionConfig)
class NotificacionConfigAdmin(admin.ModelAdmin):
    list_display = ('activo',)

    def has_add_permission(self, request):
        return not NotificacionConfig.objects.exists()

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(NotificacionEstado)
class NotificacionEstadoAdmin(admin.ModelAdmin):
    list_display = ('usuario', 'evento', 'estado', 'actualizado')
    search_fields = ('usuario__email', 'evento')
    list_filter = ('evento', 'estado')


@admin.register(NotificacionLog)
class NotificacionLogAdmin(admin.ModelAdmin):
    list_display = ('fecha', 'usuario', 'evento', 'destino', 'estado', 'detalle')
    search_fields = ('usuario__email', 'evento', 'destino')
    list_filter = ('estado', 'evento')
