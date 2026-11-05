"""
URLs para baseball_data
"""
from django.urls import path
from . import views

app_name = 'baseball_data'

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('games/', views.games_list, name='games_list'),
    path('games/<int:game_id>/', views.game_detail, name='game_detail'),
    path('predict/', views.prediction_form, name='prediction_form'),
    path('predict/result/', views.prediction_result, name='prediction_result'),
    path('valor/', views.value_finder, name='value_finder'),
    path('backtest/', views.backtest_report, name='backtest_report'),
]
