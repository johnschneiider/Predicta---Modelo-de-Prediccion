"""
URL configuration for betting_bot project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.shortcuts import redirect
from django.views.generic import RedirectView
from django.contrib.auth.decorators import login_required
from . import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('cuentas/', include(('cuentas.urls', 'cuentas'), namespace='cuentas')),
    # Compatibilidad: nombre global 'panel_usuarios' sin depender de namespaces
    path('cuentas/admin/usuarios/compat/', RedirectView.as_view(url='/cuentas/admin/usuarios/', permanent=True), name='panel_usuarios'),
    # Alias adicional directo por compatibilidad extrema
    path('panel_usuarios/', RedirectView.as_view(url='/cuentas/admin/usuarios/', permanent=True), name='panel_usuarios'),
    path('', views.landing_page, name='home'),
    path('odds/', include(('odds.urls', 'odds'), namespace='odds')),
    path('football_data/', include(('football_data.urls', 'football_data'), namespace='football_data')),
    path('ai/', include(('ai_predictions.urls', 'ai_predictions'), namespace='ai_predictions')),
    path('value-betting/', include(('value_betting.urls', 'value_betting'), namespace='value_betting')),
    path('auto-betting/', include(('auto_betting.urls', 'auto_betting'), namespace='auto_betting')),
    path('notificaciones/', include(('notificaciones.urls', 'notificaciones'), namespace='notificaciones')),
    path('inspector/', include(('inspector.urls', 'inspector'), namespace='inspector')),
]

# Eliminado: rutas de basketball_data

# Servir archivos de media en desarrollo
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
