"""
URLs para la app value_betting
"""

from django.urls import path
from . import views

app_name = 'value_betting'

urlpatterns = [
    path('', views.ValueBettingDashboardView.as_view(), name='dashboard'),
    path('run/', views.RunScanView.as_view(), name='run_scan'),
    path('status/', views.ScanStatusView.as_view(), name='scan_status'),
    path('opportunity/<int:pk>/', views.OpportunityDetailView.as_view(), name='opportunity_detail'),
    path('matches/', views.MatchListView.as_view(), name='match_list'),
    path('health/', views.ApiHealthView.as_view(), name='api_health'),
    path('flashscore/run/', views.RunFlashscoreScrapeView.as_view(), name='run_flashscore'),
    path('flashscore/status/', views.FlashscoreScrapeStatusView.as_view(), name='flashscore_status'),
]