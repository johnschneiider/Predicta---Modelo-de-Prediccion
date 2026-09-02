from django.urls import path
from . import views

app_name = 'cuentas'

urlpatterns = [
    path('login/', views.VistaLogin.as_view(), name='login'),
    # path('registro/', views.VistaRegistro.as_view(), name='registro'),  # DESHABILITADO - sin registro público
    path('dashboard/', views.VistaDashboard.as_view(), name='dashboard'),
    path('logout/', views.vista_logout, name='logout'),
    
    # Panel de administración de usuarios (solo superusuarios)
    path('admin/usuarios/', views.VistaPanelUsuarios.as_view(), name='panel_usuarios'),
    path('admin/usuarios/crear/', views.VistaCrearUsuario.as_view(), name='crear_usuario'),
    path('admin/usuarios/<int:user_id>/editar/', views.VistaEditarUsuario.as_view(), name='editar_usuario'),
    path('admin/usuarios/<int:user_id>/cambiar-contraseña/', views.VistaCambiarContraseña.as_view(), name='cambiar_contraseña'),
    path('admin/usuarios/<int:user_id>/suspender/', views.vista_suspender_usuario, name='suspender_usuario'),
    path('admin/usuarios/<int:user_id>/eliminar/', views.vista_eliminar_usuario, name='eliminar_usuario'),
]