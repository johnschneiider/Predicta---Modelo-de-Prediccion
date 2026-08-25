from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario, LoginAttempt

@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """
    Configuración del admin para el modelo Usuario personalizado
    """
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active', 'fecha_registro')
    list_filter = ('is_staff', 'is_superuser', 'is_active', 'fecha_registro')
    search_fields = ('email', 'first_name', 'last_name', 'username')
    ordering = ('-fecha_registro',)
    
    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Información personal', {'fields': ('first_name', 'last_name', 'email', 'avatar')}),
        ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Fechas importantes', {'fields': ('last_login', 'fecha_registro')}),
    )
    
    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('username', 'email', 'first_name', 'last_name', 'password1', 'password2'),
        }),
    )


@admin.register(LoginAttempt)
class LoginAttemptAdmin(admin.ModelAdmin):
    """Admin para auditar los intentos de login."""
    list_display = ('ip_address', 'username', 'success', 'timestamp')
    list_filter = ('success', 'timestamp')
    search_fields = ('ip_address', 'username')
    ordering = ('-timestamp',)
    readonly_fields = ('ip_address', 'username', 'success', 'timestamp')