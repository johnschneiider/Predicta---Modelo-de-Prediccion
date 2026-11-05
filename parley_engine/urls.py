from django.urls import path

from . import views

app_name = 'parley_engine'

urlpatterns = [
    path('', views.historial_parleys, name='historial'),
    path('sync/', views.sync_parleys, name='sync'),
]
