"""
URLs para predicciones de IA
"""

from django.urls import path
from . import views

app_name = 'ai_predictions'

urlpatterns = [
    # Dashboard principal
    path('', views.PredictionDashboardView.as_view(), name='dashboard'),
    
    # Predicciones (solo con datos reales)
    path('predict/', views.PredictionFormView.as_view(), name='prediction_form'),
    path('predict/result/', views.PredictionResultView.as_view(), name='prediction_result'),
    path('predict/result/<uuid:prediction_id>/', views.PredictionResultView.as_view(), name='prediction_result_with_id'),
    path('predict/result/<uuid:prediction_id>/apostar/', views.SaveApuestaView.as_view(), name='save_apuesta'),
    path('predict/quick/', views.QuickPredictionView.as_view(), name='quick_prediction'),
    
    # Entrenamiento de modelos
    path('training/', views.TrainingView.as_view(), name='training'),
    
    # Historial y rendimiento
    path('history/', views.PredictionHistoryView.as_view(), name='prediction_history'),
    path('models/', views.ModelPerformanceView.as_view(), name='model_performance'),

    # Apuestas del usuario
    path('apuestas/', views.MisApuestasView.as_view(), name='mis_apuestas'),
    path('apuestas/<int:pk>/resolver/', views.ResolveApuestaView.as_view(), name='resolver_apuesta'),
    
    # APIs
    path('api/teams/<int:league_id>/', views.GetTeamsView.as_view(), name='get_teams'),
    path('api/prediction-progress/', views.PredictionProgressView.as_view(), name='prediction_progress'),
    path('api/league-historical-data/<int:league_id>/', views.LeagueHistoricalDataView.as_view(), name='league_historical_data'),
    path('test-predictions/', views.TestPredictionsView.as_view(), name='test_predictions'),
    # Scraper de corners
    path('scraper/', views.ScraperCornersView.as_view(), name='scraper_corners'),
    path('api/scrape-corners/', views.ScraperCornersAPIView.as_view(), name='api_scrape_corners'),
]
