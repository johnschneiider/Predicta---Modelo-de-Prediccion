"""
URLs para basketball_data
"""

from django.urls import path
from . import views

app_name = 'basketball_data'

urlpatterns = [
    # Dashboard principal
    path('', views.dashboard, name='dashboard'),
    
    # Equipos
    path('teams/', views.teams_list, name='teams_list'),
    path('teams/<int:team_id>/', views.team_detail, name='team_detail'),
    
    # Partidos
    path('games/', views.games_list, name='games_list'),
    path('games/<int:game_id>/', views.game_detail, name='game_detail'),
    
    # Predicciones
    path('predictions/', views.predictions_list, name='predictions_list'),
    path('valor/', views.value_finder, name='value_finder'),
    path('predict/', views.prediction_form, name='prediction_form'),
    path('predict/result/', views.prediction_result, name='prediction_result'),
    
    # Estadísticas
    path('statistics/', views.statistics, name='statistics'),
    
    # API endpoints
    path('api/sync/', views.sync_data, name='sync_data'),
    path('api/train-model/', views.train_model, name='train_model'),
    path('api/predict/', views.predict_points, name='predict_points'),
    path('api/prediction-progress/', views.prediction_progress, name='prediction_progress'),
]
