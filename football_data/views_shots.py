"""
Vista simplificada para análisis de remates
"""

from django.shortcuts import render
from django.views.generic import View
from django.db.models import Avg, Count, F
from django.http import JsonResponse
import json

from .models import League, Match


class ShotsAnalysisView(View):
    """Vista para análisis específico de remates"""
    
    def get(self, request):
        # Obtener filtros
        league_filter = request.GET.get('league', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        # Obtener ligas para el filtro
        leagues = League.objects.annotate(match_count=Count('matches')).order_by('name')
        
        # Filtrar partidos
        matches = Match.objects.all()
        
        if league_filter:
            matches = matches.filter(league_id=league_filter)
        
        if date_from:
            matches = matches.filter(date__gte=date_from)
        
        if date_to:
            matches = matches.filter(date__lte=date_to)
        
        context = {
            'leagues': leagues,
            'current_league': league_filter,
            'date_from': date_from,
            'date_to': date_to,
            'matches_count': matches.count(),
        }
        
        return render(request, 'football_data/shots_analysis.html', context)
    
    def _analyze_shots(self, matches):
        """Analiza específicamente los remates"""
        data = {
            'title': 'Análisis de Remates',
            'description': 'Análisis detallado de tiros y tiros a puerta',
            'charts': {}
        }
        
        # Filtrar partidos que tengan datos de remates
        matches_with_shots = matches.exclude(
            hs__isnull=True, as_field__isnull=True, hst__isnull=True, ast__isnull=True
        )
        
        if not matches_with_shots.exists():
            data['charts']['no_data'] = {
                'type': 'info',
                'title': 'Sin Datos',
                'message': 'No hay datos de remates disponibles para el filtro seleccionado'
            }
            return data
        
        # Promedio de remates por partido
        shots_stats = matches_with_shots.aggregate(
            avg_home_shots=Avg('hs'),
            avg_away_shots=Avg('as_field'),
            avg_home_shots_target=Avg('hst'),
            avg_away_shots_target=Avg('ast')
        )
        
        # Gráfica 1: Promedio de remates totales
        data['charts']['shots_average'] = {
            'type': 'bar',
            'title': 'Promedio de Remates por Partido',
            'data': [
                {'label': 'Remates Local', 'value': round(shots_stats['avg_home_shots'] or 0, 2)},
                {'label': 'Remates Visitante', 'value': round(shots_stats['avg_away_shots'] or 0, 2)},
                {'label': 'Remates a Puerta Local', 'value': round(shots_stats['avg_home_shots_target'] or 0, 2)},
                {'label': 'Remates a Puerta Visitante', 'value': round(shots_stats['avg_away_shots_target'] or 0, 2)},
            ]
        }
        
        # Gráfica adicional: Comparación detallada de remates
        data['charts']['detailed_shots_comparison'] = {
            'type': 'bar',
            'title': 'Comparación Detallada de Remates',
            'data': [
                {'label': 'Local - Totales', 'value': round(shots_stats['avg_home_shots'] or 0, 2)},
                {'label': 'Local - A Puerta', 'value': round(shots_stats['avg_home_shots_target'] or 0, 2)},
                {'label': 'Visitante - Totales', 'value': round(shots_stats['avg_away_shots'] or 0, 2)},
                {'label': 'Visitante - A Puerta', 'value': round(shots_stats['avg_away_shots_target'] or 0, 2)},
            ]
        }
        
        # Gráfica 2: Efectividad de remates (porcentaje de acierto)
        home_effectiveness = 0
        away_effectiveness = 0
        
        if shots_stats['avg_home_shots'] and shots_stats['avg_home_shots'] > 0:
            home_effectiveness = round((shots_stats['avg_home_shots_target'] or 0) / shots_stats['avg_home_shots'] * 100, 2)
        
        if shots_stats['avg_away_shots'] and shots_stats['avg_away_shots'] > 0:
            away_effectiveness = round((shots_stats['avg_away_shots_target'] or 0) / shots_stats['avg_away_shots'] * 100, 2)
        
        data['charts']['shots_effectiveness'] = {
            'type': 'bar',
            'title': 'Efectividad de Remates (%)',
            'data': [
                {'label': 'Local', 'value': home_effectiveness},
                {'label': 'Visitante', 'value': away_effectiveness},
            ]
        }
        
        # Gráfica 3: Distribución de remates totales por partido
        total_shots_dist = matches_with_shots.annotate(
            total_shots=F('hs') + F('as_field')
        ).values('total_shots').annotate(
            count=Count('id')
        ).order_by('total_shots')
        
        data['charts']['total_shots_distribution'] = {
            'type': 'line',
            'title': 'Distribución de Remates Totales por Partido',
            'data': [{'x': item['total_shots'], 'y': item['count']} for item in total_shots_dist]
        }
        
        # Gráfica 4: Distribución de remates a puerta por partido
        shots_target_dist = matches_with_shots.annotate(
            total_shots_target=F('hst') + F('ast')
        ).values('total_shots_target').annotate(
            count=Count('id')
        ).order_by('total_shots_target')
        
        data['charts']['shots_target_distribution'] = {
            'type': 'line',
            'title': 'Distribución de Remates a Puerta por Partido',
            'data': [{'x': item['total_shots_target'], 'y': item['count']} for item in shots_target_dist]
        }
        
        # Gráfica 5: Comparación Local vs Visitante (remates totales)
        data['charts']['home_vs_away_shots'] = {
            'type': 'pie',
            'title': 'Distribución de Remates: Local vs Visitante',
            'data': [
                {'label': 'Local', 'value': round(shots_stats['avg_home_shots'] or 0, 2)},
                {'label': 'Visitante', 'value': round(shots_stats['avg_away_shots'] or 0, 2)},
            ]
        }
        
        # Gráfica 6: Comparación Local vs Visitante (remates a puerta)
        data['charts']['home_vs_away_shots_target'] = {
            'type': 'pie',
            'title': 'Distribución de Remates a Puerta: Local vs Visitante',
            'data': [
                {'label': 'Local', 'value': round(shots_stats['avg_home_shots_target'] or 0, 2)},
                {'label': 'Visitante', 'value': round(shots_stats['avg_away_shots_target'] or 0, 2)},
            ]
        }
        
        return data

