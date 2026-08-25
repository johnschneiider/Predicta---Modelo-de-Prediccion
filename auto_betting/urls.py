"""
URLs de la app auto_betting.
"""

from django.urls import path
from . import views

app_name = 'auto_betting'

urlpatterns = [
    path('historial/', views.historial, name='historial'),
    path('historial/sync/', views.historial_sync, name='historial_sync'),
    path('configuracion/', views.configuracion, name='configuracion'),
    path('configuracion/umbrales/', views.configuracion_umbrales, name='configuracion_umbrales'),
]
