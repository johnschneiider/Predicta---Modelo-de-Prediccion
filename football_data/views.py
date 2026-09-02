"""
Vistas para mostrar datos históricos de fútbol
"""

import os
from datetime import datetime, timedelta, timezone as tz
import logging
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count, Max, Min, F
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views import View
from django.contrib import messages
from django.conf import settings
from django.utils import timezone
logger = logging.getLogger('football_data')

from .models import League, Match, ExcelFile
from .services import ExcelImportService
from .forms import ExcelUploadForm, LeagueFilterForm, MatchFilterForm
from django.core.paginator import Paginator
import json


@method_decorator(login_required, name='dispatch')
class FootballDataDashboardView(View):
    """Dashboard de estado de sincronización API-Football (fuente de datos)."""

    def get(self, request):
        from football_api.models import ApiLeague, ApiFixture, TeamFixtureStat, ApiTeam, SyncState

        qs = ApiLeague.objects.annotate(
            fixture_count=Count('fixtures', distinct=True),
            stats_count=Count('fixtures__stats', distinct=True),
            finished_count=Count(
                'fixtures',
                filter=Q(fixtures__status__in=('FT', 'AET', 'PEN', 'AWD', 'WO')),
                distinct=True,
            ),
            finished_with_stats=Count(
                'fixtures',
                filter=Q(fixtures__status__in=('FT', 'AET', 'PEN', 'AWD', 'WO'), fixtures__stats__isnull=False),
                distinct=True,
            ),
        ).order_by('priority', 'country', 'name')

        q = request.GET.get('q', '').strip()
        country = request.GET.get('country', '').strip()
        status = request.GET.get('status', '').strip()
        coverage = request.GET.get('coverage', '').strip()

        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(country__icontains=q) | Q(predicta_name__icontains=q))
        if country:
            qs = qs.filter(country=country)
        if status:
            qs = qs.filter(backfill_status=status)
        if coverage == 'yes':
            qs = qs.filter(has_statistics=True)
        elif coverage == 'no':
            qs = qs.filter(has_statistics=False)

        countries = ApiLeague.objects.values_list('country', flat=True).distinct().order_by('country')

        # % de finalizados con al menos una fila de stats (cobertura real por liga)
        for l in qs:
            if l.finished_count:
                l.stats_pct = round(100.0 * l.finished_with_stats / l.finished_count)
            else:
                l.stats_pct = None

        totals = {
            'leagues': ApiLeague.objects.count(),
            'fixtures': ApiFixture.objects.count(),
            'stats': TeamFixtureStat.objects.count(),
            'teams': ApiTeam.objects.count(),
            'done': ApiLeague.objects.filter(backfill_status='done').count(),
            'backfilling': ApiLeague.objects.filter(backfill_status='backfilling').count(),
            'pending': ApiLeague.objects.filter(backfill_status='pending').count(),
            'error': ApiLeague.objects.filter(backfill_status='error').count(),
            'sin_cobertura': ApiLeague.objects.filter(has_statistics=False).count(),
        }

        sync_states = {s.key: s for s in SyncState.objects.all()}

        state_cards = [
            {'label': 'Backfill histórico (2 temporadas)', 'icon': 'fas fa-history', 'st': sync_states.get('backfill')},
            {'label': 'Sync diario (próximos partidos)', 'icon': 'fas fa-calendar-check', 'st': sync_states.get('daily')},
        ]

        context = {
            'totals': totals,
            'leagues': qs,
            'countries': countries,
            'state_cards': state_cards,
            'filters': {'q': q, 'country': country, 'status': status, 'coverage': coverage},
        }
        return render(request, 'football_data/dashboard.html', context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class LeaguesListView(View):
    """Lista de ligas"""
    
    def get(self, request):
        leagues = League.objects.annotate(
            match_count=Count('matches'),
            latest_match=Max('matches__date'),
            avg_goals=Avg('matches__fthg') + Avg('matches__ftag')
        ).order_by('-match_count')
        
        context = {
            'leagues': leagues,
        }
        
        return render(request, 'football_data/leagues_list.html', context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class LeagueDetailView(View):
    """Detalle de una liga específica"""
    
    def get(self, request, league_id):
        league = get_object_or_404(League, id=league_id)
        service = ExcelImportService()
        
        # Obtener estadísticas de la liga
        stats = service.get_league_statistics(league_id)
        
        # Obtener partidos con paginación
        matches = Match.objects.filter(league=league).order_by('-date')
        
        # Filtros
        search = request.GET.get('search', '')
        season_filter = request.GET.get('season', '')
        result_filter = request.GET.get('result', '')
        
        if search:
            matches = matches.filter(
                Q(home_team__icontains=search) | 
                Q(away_team__icontains=search)
            )
        
        if season_filter:
            matches = matches.filter(league__season=season_filter)
        
        if result_filter:
            matches = matches.filter(ftr=result_filter)
        
        # Paginación
        paginator = Paginator(matches, 20)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'league': league,
            'stats': stats,
            'page_obj': page_obj,
            'search_query': search,
            'season_filter': season_filter,
            'result_filter': result_filter,
        }
        
        return render(request, 'football_data/league_detail.html', context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class MatchesListView(View):
    """Lista de partidos"""
    
    def get(self, request):
        matches = Match.objects.select_related('league').order_by('-date')
        
        # Filtros
        league_filter = request.GET.get('league', '')
        search = request.GET.get('search', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        result_filter = request.GET.get('result', '')
        
        if league_filter:
            matches = matches.filter(league_id=league_filter)
        
        if search:
            matches = matches.filter(
                Q(home_team__icontains=search) | 
                Q(away_team__icontains=search)
            )
        
        if date_from:
            matches = matches.filter(date__gte=date_from)
        
        if date_to:
            matches = matches.filter(date__lte=date_to)
        
        if result_filter:
            matches = matches.filter(ftr=result_filter)
        
        # Paginación
        paginator = Paginator(matches, 50)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        # Obtener ligas para el filtro
        leagues = League.objects.annotate(match_count=Count('matches')).order_by('name')
        
        context = {
            'page_obj': page_obj,
            'leagues': leagues,
            'current_league': league_filter,
            'search_query': search,
            'date_from': date_from,
            'date_to': date_to,
            'result_filter': result_filter,
        }
        
        return render(request, 'football_data/matches_list.html', context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class MatchDetailView(View):
    """Detalle de un partido específico"""
    
    def get(self, request, match_id):
        match = get_object_or_404(Match, id=match_id)
        
        # Obtener estadísticas del partido
        match_stats = {
            'total_goals': match.total_goals,
            'is_over_25': match.is_over_25,
            'best_home_odds': match.best_home_odds,
            'best_draw_odds': match.best_draw_odds,
            'best_away_odds': match.best_away_odds,
        }
        
        # Obtener partidos similares (mismo equipo local)
        similar_matches = Match.objects.filter(
            home_team=match.home_team,
            league=match.league
        ).exclude(id=match.id).order_by('-date')[:5]
        
        context = {
            'match': match,
            'match_stats': match_stats,
            'similar_matches': similar_matches,
        }
        
        return render(request, 'football_data/match_detail.html', context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class ImportView(View):
    """Vista para importar archivos Excel"""
    
    def get(self, request):
        form = ExcelUploadForm()
        
        # Obtener información de equipos y fechas por liga
        leagues_data = []
        leagues = League.objects.all().order_by('name')
        
        for league in leagues:
            # Obtener todos los equipos únicos (como local y visitante)
            home_teams = Match.objects.filter(league=league).values_list('home_team', flat=True).distinct()
            away_teams = Match.objects.filter(league=league).values_list('away_team', flat=True).distinct()
            all_teams = sorted(set(list(home_teams)) | set(list(away_teams)))
            
            teams_info = []
            for team_name in all_teams:
                # Obtener fechas de partidos de este equipo
                team_matches = Match.objects.filter(
                    Q(home_team=team_name) | Q(away_team=team_name),
                    league=league
                ).aggregate(
                    first_date=Min('date'),
                    last_date=Max('date'),
                    total_matches=Count('id')
                )
                
                if team_matches['first_date']:
                    teams_info.append({
                        'name': team_name,
                        'first_date': team_matches['first_date'],
                        'last_date': team_matches['last_date'],
                        'total_matches': team_matches['total_matches']
                    })
            
            # Ordenar equipos por fecha más reciente (último partido) de forma descendente
            teams_info.sort(key=lambda x: x['last_date'], reverse=True)
            
            if teams_info:
                leagues_data.append({
                    'league': league,
                    'teams': teams_info
                })
        
        context = {
            'form': form,
            'leagues_data': leagues_data,
        }
        
        return render(request, 'football_data/import.html', context)
    
    def post(self, request):
        form = ExcelUploadForm(request.POST, request.FILES)
        
        if form.is_valid():
            try:
                # Obtener el archivo validado del formulario
                uploaded_file = form.cleaned_data['file']
                league_name = form.cleaned_data['league_name']
                season = form.cleaned_data['season']
                
                # Convertir a lista para mantener compatibilidad con el código existente
                uploaded_files = [uploaded_file]
                
                # Crear directorio de media si no existe
                media_dir = os.path.join(settings.MEDIA_ROOT, 'excel_files')
                os.makedirs(media_dir, exist_ok=True)
                
                # Procesar los archivos
                service = ExcelImportService()
                total_imported = 0
                total_failed = 0
                successful_files = []
                failed_files = []
                
                for uploaded_file in uploaded_files:
                    try:
                        # Guardar archivo temporalmente
                        temp_file_path = os.path.join(media_dir, uploaded_file.name)
                        with open(temp_file_path, 'wb+') as destination:
                            for chunk in uploaded_file.chunks():
                                destination.write(chunk)
                        
                        # Importar archivo
                        result = service.import_data_file(temp_file_path, league_name, season)
                        
                        if result['success']:
                            # Crear registro de ExcelFile
                            league = League.objects.get(name=result['league'])
                            ExcelFile.objects.create(
                                name=uploaded_file.name,
                                file=uploaded_file,
                                file_path=temp_file_path,
                                league=league,
                                total_rows=result['imported_count'] + result['failed_count'],
                                imported_rows=result['imported_count'],
                                failed_rows=result['failed_count'],
                                file_size=uploaded_file.size
                            )
                            
                            total_imported += result['imported_count']
                            total_failed += result['failed_count']
                            successful_files.append(uploaded_file.name)
                        else:
                            failed_files.append(f"{uploaded_file.name}: {result['error']}")
                            # Eliminar archivo temporal si falló
                            if os.path.exists(temp_file_path):
                                os.remove(temp_file_path)
                                
                    except Exception as e:
                        failed_files.append(f"{uploaded_file.name}: {str(e)}")
                        # Eliminar archivo temporal si falló
                        if os.path.exists(temp_file_path):
                            os.remove(temp_file_path)
                
                # Mostrar resultados
                if successful_files:
                    messages.success(
                        request, 
                        f"Archivos importados exitosamente: {len(successful_files)} archivos, "
                        f"{total_imported} partidos importados, {total_failed} fallos"
                    )
                
                if failed_files:
                    for failed_file in failed_files:
                        messages.error(request, f"Error: {failed_file}")
                
            except Exception as e:
                messages.error(request, f"Error procesando archivos: {str(e)}")
        else:
            # Si el formulario no es válido, mostrar errores específicos
            for field, errors in form.errors.items():
                for error in errors:
                    if field == 'file':
                        messages.error(request, f"❌ Archivo: {error}")
                    elif field == 'league':
                        messages.warning(request, f"⚠️ Liga: {error}")
                    elif field == 'league_name':
                        messages.warning(request, f"⚠️ Nombre de liga: {error}")
                    else:
                        messages.error(request, f"❌ {field}: {error}")
        
        # Pasar el formulario con errores para mostrarlos en el template
        # Obtener información de equipos y fechas por liga
        leagues_data = []
        leagues = League.objects.all().order_by('name')
        
        for league in leagues:
            # Obtener todos los equipos únicos (como local y visitante)
            home_teams = Match.objects.filter(league=league).values_list('home_team', flat=True).distinct()
            away_teams = Match.objects.filter(league=league).values_list('away_team', flat=True).distinct()
            all_teams = sorted(set(list(home_teams)) | set(list(away_teams)))
            
            teams_info = []
            for team_name in all_teams:
                # Obtener fechas de partidos de este equipo
                team_matches = Match.objects.filter(
                    Q(home_team=team_name) | Q(away_team=team_name),
                    league=league
                ).aggregate(
                    first_date=Min('date'),
                    last_date=Max('date'),
                    total_matches=Count('id')
                )
                
                if team_matches['first_date']:
                    teams_info.append({
                        'name': team_name,
                        'first_date': team_matches['first_date'],
                        'last_date': team_matches['last_date'],
                        'total_matches': team_matches['total_matches']
                    })
            
            # Ordenar equipos por fecha más reciente (último partido) de forma descendente
            teams_info.sort(key=lambda x: x['last_date'], reverse=True)
            
            if teams_info:
                leagues_data.append({
                    'league': league,
                    'teams': teams_info
                })
        
        context = {
            'form': form,
            'leagues_data': leagues_data,
        }
        
        return render(request, 'football_data/import.html', context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class DeleteFileView(View):
    """Vista para eliminar archivos importados"""
    
    def post(self, request, file_id):
        try:
            # Obtener el archivo
            excel_file = ExcelFile.objects.get(id=file_id)
            
            # Obtener la liga asociada
            league = excel_file.league
            
            # Eliminar solamente los partidos vinculados a este archivo
            matches_qs = Match.objects.filter(source_file=excel_file)
            matches_deleted = matches_qs.count()
            matches_qs.delete()
            
            # Eliminar el archivo físico si existe
            if excel_file.file_path and os.path.exists(excel_file.file_path):
                os.remove(excel_file.file_path)
            
            # Eliminar el registro de la base de datos
            file_name = excel_file.name
            excel_file.delete()
            
            # Verificar si la liga quedó sin partidos y eliminarla si es necesario
            if Match.objects.filter(league=league).count() == 0:
                league.delete()
                league_deleted = True
            else:
                league_deleted = False
            
            messages.success(
                request, 
                f"✅ Archivo '{file_name}' eliminado exitosamente. "
                f"Se eliminaron {matches_deleted} partidos."
                + (f" La liga '{league.name}' también fue eliminada." if league_deleted else "")
            )
            
        except ExcelFile.DoesNotExist:
            messages.error(request, "❌ El archivo no existe.")
        except Exception as e:
            messages.error(request, f"❌ Error al eliminar el archivo: {str(e)}")
        
        return redirect('football_data:import')


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class DeleteAllFilesView(View):
    """Vista para eliminar todos los archivos y datos"""
    
    def post(self, request):
        try:
            # Contar archivos y partidos antes de eliminar
            total_files = ExcelFile.objects.count()
            total_matches = Match.objects.count()
            total_leagues = League.objects.count()
            
            # Eliminar todos los archivos físicos
            for excel_file in ExcelFile.objects.all():
                if excel_file.file_path and os.path.exists(excel_file.file_path):
                    os.remove(excel_file.file_path)
            
            # Eliminar todos los registros de la base de datos
            ExcelFile.objects.all().delete()
            Match.objects.all().delete()
            League.objects.all().delete()
            
            messages.success(
                request, 
                f"🗑️ Todos los datos eliminados exitosamente:\n"
                f"- {total_files} archivos eliminados\n"
                f"- {total_matches} partidos eliminados\n"
                f"- {total_leagues} ligas eliminadas"
            )
            
        except Exception as e:
            messages.error(request, f"❌ Error al eliminar todos los datos: {str(e)}")
        
        return redirect('football_data:import')


@method_decorator(csrf_exempt, name='dispatch')
# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class ImportAjaxView(View):
    """Vista AJAX para importar archivos"""
    
    def post(self, request):
        service = ExcelImportService()
        
        file_name = request.POST.get('file_name')
        league_name = request.POST.get('league_name', '')
        season = request.POST.get('season', '')
        
        if not file_name:
            return JsonResponse({'success': False, 'error': 'Debe seleccionar un archivo'})
        
        file_path = os.path.join(service.data_dir, file_name)
        
        if not os.path.exists(file_path):
            return JsonResponse({'success': False, 'error': 'El archivo seleccionado no existe'})
        
        # Importar archivo
        result = service.import_excel_file(file_path, league_name, season)
        
        return JsonResponse(result)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class StatisticsView(View):
    """Vista de estadísticas"""
    
    def get(self, request):
        # Estadísticas generales
        total_matches = Match.objects.count()
        total_leagues = League.objects.count()
        
        # Análisis de resultados
        result_stats = Match.objects.values('ftr').annotate(
            count=Count('id'),
            percentage=Count('id') * 100.0 / total_matches
        ).exclude(ftr__isnull=True)
        
        # Análisis de goles
        goals_stats = Match.objects.exclude(
            fthg__isnull=True, ftag__isnull=True
        ).aggregate(
            avg_home_goals=Avg('fthg'),
            avg_away_goals=Avg('ftag'),
            avg_total_goals=Avg('fthg') + Avg('ftag'),
            max_goals=Max('fthg') + Max('ftag')
        )
        
        # Análisis de cuotas
        odds_stats = Match.objects.exclude(
            b365h__isnull=True, b365d__isnull=True, b365a__isnull=True
        ).aggregate(
            avg_home_odds=Avg('b365h'),
            avg_draw_odds=Avg('b365d'),
            avg_away_odds=Avg('b365a'),
            max_home_odds=Max('b365h'),
            max_draw_odds=Max('b365d'),
            max_away_odds=Max('b365a')
        )
        
        # Top equipos
        top_home_teams = Match.objects.values('home_team').annotate(
            wins=Count('id', filter=Q(ftr='H')),
            total=Count('id')
        ).order_by('-wins')[:10]
        
        top_away_teams = Match.objects.values('away_team').annotate(
            wins=Count('id', filter=Q(ftr='A')),
            total=Count('id')
        ).order_by('-wins')[:10]
        
        # Estadísticas adicionales
        leagues_stats = League.objects.annotate(
            match_count=Count('matches'),
            avg_goals=Avg('matches__fthg') + Avg('matches__ftag'),
            avg_shots=Avg('matches__hs') + Avg('matches__as_field'),
            latest_match=Max('matches__date')
        ).order_by('-match_count')[:10]
        
        # Estadísticas generales
        stats = {
            'total_matches': total_matches,
            'total_leagues': total_leagues,
            'total_files': ExcelFile.objects.count(),
            'date_range': f"{Match.objects.aggregate(min_date=Min('date'))['min_date']} - {Match.objects.aggregate(max_date=Max('date'))['max_date']}",
            'avg_goals_per_match': goals_stats['avg_total_goals'] or 0,
            'avg_home_goals': goals_stats['avg_home_goals'] or 0,
            'avg_away_goals': goals_stats['avg_away_goals'] or 0,
            'over_25_percentage': 0,  # Se calculará si hay datos
            'avg_shots_per_match': 0,  # Se calculará si hay datos
            'avg_shots_target': 0,  # Se calculará si hay datos
            'shots_effectiveness': 0,  # Se calculará si hay datos
            'avg_corners': 0,  # Se calculará si hay datos
        }
        
        # Calcular estadísticas de remates si hay datos
        shots_data = Match.objects.exclude(hs__isnull=True, as_field__isnull=True, hst__isnull=True, ast__isnull=True)
        if shots_data.exists():
            shots_stats = shots_data.aggregate(
                avg_home_shots=Avg('hs'),
                avg_away_shots=Avg('as_field'),
                avg_home_shots_target=Avg('hst'),
                avg_away_shots_target=Avg('ast')
            )
            stats['avg_shots_per_match'] = (shots_stats['avg_home_shots'] or 0) + (shots_stats['avg_away_shots'] or 0)
            stats['avg_shots_target'] = (shots_stats['avg_home_shots_target'] or 0) + (shots_stats['avg_away_shots_target'] or 0)
            
            if stats['avg_shots_per_match'] > 0:
                stats['shots_effectiveness'] = (stats['avg_shots_target'] / stats['avg_shots_per_match']) * 100
        
        # Calcular estadísticas de corners si hay datos
        corners_data = Match.objects.exclude(hc__isnull=True, ac__isnull=True)
        if corners_data.exists():
            corners_stats = corners_data.aggregate(
                avg_home_corners=Avg('hc'),
                avg_away_corners=Avg('ac')
            )
            stats['avg_corners'] = (corners_stats['avg_home_corners'] or 0) + (corners_stats['avg_away_corners'] or 0)
        
        # Calcular porcentaje Over 2.5 si hay datos
        goals_data = Match.objects.exclude(fthg__isnull=True, ftag__isnull=True)
        if goals_data.exists():
            over_25_count = goals_data.annotate(_tot_goals=F('fthg') + F('ftag')).filter(_tot_goals__gt=2.5).count()
            total_goals_matches = goals_data.count()
            if total_goals_matches > 0:
                stats['over_25_percentage'] = (over_25_count / total_goals_matches) * 100
        
        context = {
            'stats': stats,
            'leagues_stats': leagues_stats,
            'result_stats': result_stats,
            'goals_stats': goals_stats,
            'odds_stats': odds_stats,
            'top_home_teams': top_home_teams,
            'top_away_teams': top_away_teams,
        }
        
        return render(request, 'football_data/statistics.html', context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class LeagueDataTableView(View):
    """Vista para mostrar tabla de datos de una liga específica"""
    
    def get(self, request):
        # Obtener parámetros
        league_id = request.GET.get('league')
        page = request.GET.get('page', 1)
        
        # Obtener todas las ligas para el selector
        leagues = League.objects.annotate(
            match_count=Count('matches')
        ).order_by('name')
        
        matches = None
        selected_league = None
        
        if league_id:
            try:
                selected_league = League.objects.get(id=league_id)
                matches = Match.objects.filter(league=selected_league).order_by('-date', '-time')
                
                # Paginación
                paginator = Paginator(matches, 50)  # 50 partidos por página
                matches = paginator.get_page(page)
                
            except League.DoesNotExist:
                messages.error(request, 'Liga no encontrada')
        
        context = {
            'leagues': leagues,
            'selected_league': selected_league,
            'matches': matches,
            'league_id': league_id,
        }
        
        return render(request, 'football_data/league_data_table.html', context)


# @method_decorator(login_required, name='dispatch')  # Temporalmente deshabilitado
@method_decorator(login_required, name='dispatch')
class MarketsView(View):
    """Vista de análisis de mercados con gráficas"""
    
    def get(self, request):
        # Obtener filtros
        league_filter = request.GET.get('league', '')
        date_from = request.GET.get('date_from', '')
        date_to = request.GET.get('date_to', '')
        
        # Construir consulta base
        matches = Match.objects.exclude(
            b365h__isnull=True, b365d__isnull=True, b365a__isnull=True
        )
        
        if league_filter:
            matches = matches.filter(league_id=league_filter)
        
        if date_from:
            matches = matches.filter(date__gte=date_from)
        
        if date_to:
            matches = matches.filter(date__lte=date_to)
        
        # Obtener ligas para el filtro
        leagues = League.objects.annotate(match_count=Count('matches')).order_by('name')
        
        # Análisis de mercados
        markets_data = self._analyze_markets(matches)
        
        context = {
            'leagues': leagues,
            'current_league': league_filter,
            'date_from': date_from,
            'date_to': date_to,
            'markets_data': json.dumps(markets_data, default=str),
        }
        
        return render(request, 'football_data/markets.html', context)
    
    def _analyze_markets(self, matches):
        """Analiza específicamente el mercado de remates"""
        markets = {}
        
        # Análisis de remates
        markets['shots'] = self._analyze_shots_market(matches)
        
        return markets
    
    def _analyze_shots_market(self, matches):
        """Analiza específicamente el mercado de remates"""
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
    
    def _analyze_over_under_market(self, matches):
        """Analiza el mercado Over/Under 2.5"""
        data = {
            'title': 'Mercado Over/Under 2.5',
            'description': 'Análisis de goles y cuotas Over/Under',
            'charts': {}
        }
        
        # Distribución Over/Under basada en goles reales
        matches_with_goals = matches.exclude(fthg__isnull=True, ftag__isnull=True)
        
        if matches_with_goals.exists():
            over_25_count = matches_with_goals.annotate(_tot=F('fthg') + F('ftag')).filter(_tot__gt=2.5).count()
            under_25_count = matches_with_goals.annotate(_tot=F('fthg') + F('ftag')).filter(_tot__lte=2.5).count()
            
            data['charts']['over_under_distribution'] = {
                'type': 'pie',
                'title': 'Distribución Over/Under 2.5 (Basado en Goles Reales)',
                'data': [
                    {'label': 'Over 2.5', 'value': over_25_count},
                    {'label': 'Under 2.5', 'value': under_25_count},
                ]
            }
            
            # Promedio de goles por partido
            avg_goals = matches_with_goals.aggregate(
                avg_home=Avg('fthg'),
                avg_away=Avg('ftag')
            )
            
            avg_total = (avg_goals['avg_home'] or 0) + (avg_goals['avg_away'] or 0)
            
            data['charts']['goals_average'] = {
                'type': 'bar',
                'title': 'Promedio de Goles por Partido',
                'data': [
                    {'label': 'Local', 'value': round(avg_goals['avg_home'] or 0, 2)},
                    {'label': 'Visitante', 'value': round(avg_goals['avg_away'] or 0, 2)},
                    {'label': 'Total', 'value': round(avg_total, 2)},
                ]
            }
            
            # Distribución de goles por partido
            goals_dist = matches_with_goals.annotate(
                total_goals=F('fthg') + F('ftag')
            ).values('total_goals').annotate(
                count=Count('id')
            ).order_by('total_goals')
            
            data['charts']['goals_distribution'] = {
                'type': 'line',
                'title': 'Distribución de Goles por Partido',
                'data': [{'x': item['total_goals'], 'y': item['count']} for item in goals_dist]
            }
        
        # Análisis de cuotas Over/Under si están disponibles
        matches_with_ou_odds = matches.exclude(
            b365_over_25__isnull=True, b365_under_25__isnull=True
        )
        
        if matches_with_ou_odds.exists():
            ou_odds = matches_with_ou_odds.aggregate(
                b365_over=Avg('b365_over_25'),
                b365_under=Avg('b365_under_25'),
                p_over=Avg('p_over_25'),
                p_under=Avg('p_under_25'),
                max_over=Avg('max_over_25'),
                max_under=Avg('max_under_25'),
                avg_over=Avg('avg_over_25'),
                avg_under=Avg('avg_under_25'),
            )
            
            data['charts']['over_under_odds'] = {
                'type': 'bar',
                'title': 'Promedio de Cuotas Over/Under 2.5',
                'data': [
                    {'label': 'Bet365 Over', 'value': round(ou_odds['b365_over'] or 0, 2)},
                    {'label': 'Bet365 Under', 'value': round(ou_odds['b365_under'] or 0, 2)},
                    {'label': 'Pinnacle Over', 'value': round(ou_odds['p_over'] or 0, 2)},
                    {'label': 'Pinnacle Under', 'value': round(ou_odds['p_under'] or 0, 2)},
                    {'label': 'Max Over', 'value': round(ou_odds['max_over'] or 0, 2)},
                    {'label': 'Max Under', 'value': round(ou_odds['max_under'] or 0, 2)},
                ]
            }
        
        return data
    
    def _analyze_goals_market(self, matches):
        """Analiza el mercado de goles"""
        data = {
            'title': 'Mercado de Goles',
            'description': 'Análisis detallado de goles y estadísticas',
            'charts': {}
        }
        
        # Distribución de goles por partido
        goals_dist = matches.exclude(
            fthg__isnull=True, ftag__isnull=True
        ).annotate(
            total_goals=F('fthg') + F('ftag')
        ).values('total_goals').annotate(
            count=Count('id')
        ).order_by('total_goals')
        
        data['charts']['goals_distribution'] = {
            'type': 'line',
            'title': 'Distribución de Goles por Partido',
            'data': [{'x': item['total_goals'], 'y': item['count']} for item in goals_dist]
        }
        
        return data
    
    def _analyze_corners_market(self, matches):
        """Analiza el mercado de corners"""
        data = {
            'title': 'Mercado de Corners',
            'description': 'Análisis de corners y estadísticas',
            'charts': {}
        }
        
        # Promedio de corners
        corners_stats = matches.exclude(
            hc__isnull=True, ac__isnull=True
        ).aggregate(
            avg_home=Avg('hc'),
            avg_away=Avg('ac')
        )
        
        if corners_stats['avg_home'] is not None:
            avg_total = (corners_stats['avg_home'] or 0) + (corners_stats['avg_away'] or 0)
            
            data['charts']['corners_average'] = {
                'type': 'bar',
                'title': 'Promedio de Corners por Partido',
                'data': [
                    {'label': 'Local', 'value': round(corners_stats['avg_home'] or 0, 2)},
                    {'label': 'Visitante', 'value': round(corners_stats['avg_away'] or 0, 2)},
                    {'label': 'Total', 'value': round(avg_total, 2)},
                ]
            }
            
            # Distribución de corners totales
            corners_dist = matches.exclude(
                hc__isnull=True, ac__isnull=True
            ).annotate(
                total_corners=F('hc') + F('ac')
            ).values('total_corners').annotate(
                count=Count('id')
            ).order_by('total_corners')
            
            data['charts']['corners_distribution'] = {
                'type': 'line',
                'title': 'Distribución de Corners por Partido',
                'data': [{'x': item['total_corners'], 'y': item['count']} for item in corners_dist]
            }
        
        return data
    
    def _analyze_cards_market(self, matches):
        """Analiza el mercado de tarjetas"""
        data = {
            'title': 'Mercado de Tarjetas',
            'description': 'Análisis de tarjetas amarillas y rojas',
            'charts': {}
        }
        
        # Promedio de tarjetas amarillas
        yellow_cards_stats = matches.exclude(
            hy__isnull=True, ay__isnull=True
        ).aggregate(
            avg_home_yellow=Avg('hy'),
            avg_away_yellow=Avg('ay')
        )
        
        # Promedio de tarjetas rojas
        red_cards_stats = matches.exclude(
            hr__isnull=True, ar__isnull=True
        ).aggregate(
            avg_home_red=Avg('hr'),
            avg_away_red=Avg('ar')
        )
        
        if yellow_cards_stats['avg_home_yellow'] is not None:
            data['charts']['yellow_cards_average'] = {
                'type': 'bar',
                'title': 'Promedio de Tarjetas Amarillas',
                'data': [
                    {'label': 'Local', 'value': round(yellow_cards_stats['avg_home_yellow'] or 0, 2)},
                    {'label': 'Visitante', 'value': round(yellow_cards_stats['avg_away_yellow'] or 0, 2)},
                ]
            }
        
        if red_cards_stats['avg_home_red'] is not None:
            data['charts']['red_cards_average'] = {
                'type': 'bar',
                'title': 'Promedio de Tarjetas Rojas',
                'data': [
                    {'label': 'Local', 'value': round(red_cards_stats['avg_home_red'] or 0, 2)},
                    {'label': 'Visitante', 'value': round(red_cards_stats['avg_away_red'] or 0, 2)},
                ]
            }
        
        # Análisis de tiros y tiros a puerta
        shots_stats = matches.exclude(
            hs__isnull=True, as_field__isnull=True, hst__isnull=True, ast__isnull=True
        ).aggregate(
            avg_home_shots=Avg('hs'),
            avg_away_shots=Avg('as_field'),
            avg_home_shots_target=Avg('hst'),
            avg_away_shots_target=Avg('ast')
        )
        
        if shots_stats['avg_home_shots'] is not None:
            data['charts']['shots_average'] = {
                'type': 'bar',
                'title': 'Promedio de Tiros',
                'data': [
                    {'label': 'Tiros Local', 'value': round(shots_stats['avg_home_shots'] or 0, 2)},
                    {'label': 'Tiros Visitante', 'value': round(shots_stats['avg_away_shots'] or 0, 2)},
                    {'label': 'Tiros a Puerta Local', 'value': round(shots_stats['avg_home_shots_target'] or 0, 2)},
                    {'label': 'Tiros a Puerta Visitante', 'value': round(shots_stats['avg_away_shots_target'] or 0, 2)},
                ]
            }
        
        return data
    
    def _analyze_asian_handicap_market(self, matches):
        """Analiza el mercado de handicap asiático"""
        data = {
            'title': 'Mercado Handicap Asiático',
            'description': 'Análisis de handicap asiático',
            'charts': {}
        }
        
        # Promedio de handicap asiático
        handicap_stats = matches.exclude(
            ahh__isnull=True
        ).aggregate(
            avg_handicap=Avg('ahh'),
            b365_ah_home=Avg('b365ahh'),
            b365_ah_away=Avg('b365aha'),
            p_ah_home=Avg('pahh'),
            p_ah_away=Avg('paha'),
            max_ah_home=Avg('maxahh'),
            max_ah_away=Avg('maxaha'),
            avg_ah_home=Avg('avgahh'),
            avg_ah_away=Avg('avgaha'),
        )
        
        if handicap_stats['avg_handicap'] is not None:
            data['charts']['handicap_average'] = {
                'type': 'bar',
                'title': 'Promedio de Handicap Asiático',
                'data': [
                    {'label': 'Handicap Promedio', 'value': round(handicap_stats['avg_handicap'] or 0, 2)},
                    {'label': 'Bet365 AH Home', 'value': round(handicap_stats['b365_ah_home'] or 0, 2)},
                    {'label': 'Bet365 AH Away', 'value': round(handicap_stats['b365_ah_away'] or 0, 2)},
                    {'label': 'Pinnacle AH Home', 'value': round(handicap_stats['p_ah_home'] or 0, 2)},
                    {'label': 'Pinnacle AH Away', 'value': round(handicap_stats['p_ah_away'] or 0, 2)},
                ]
            }
        
        return data


def _get_upcoming_matches_filtered():
    """Obtiene y filtra partidos próximos de todas las ligas disponibles"""
    from odds.services import OddsAPIService
    import logging
    
    logger = logging.getLogger('football_data')
    
    try:
        odds_service = OddsAPIService()
        league_to_sport_key = {
            'premier league': 'soccer_epl',
            'la liga': 'soccer_spain_la_liga',
            'serie a': 'soccer_italy_serie_a',
            'bundesliga': 'soccer_germany_bundesliga',
            'ligue 1': 'soccer_france_ligue_one',
            'ligue one': 'soccer_france_ligue_one',
            'eredivisie': 'soccer_netherlands_eredivisie',
            'primeira liga': 'soccer_portugal_primeira_liga',
            'super lig': 'soccer_turkey_super_league',
            'super league': 'soccer_china_superleague',
            'a-league': 'soccer_australia_aleague',
            'champions league': 'soccer_uefa_champs_league',
        }
        
        sport_keys_to_fetch = set()
        leagues_count = League.objects.count()
        logger.info(f"Buscando partidos para {leagues_count} ligas en la base de datos")
        
        # Mapeo inverso mejorado: mapea nombres de liga comunes a sport_keys
        # Esto incluye variaciones comunes de nombres
        improved_league_mapping = {
            # Premier League
            'premier league': 'soccer_epl',
            'epl': 'soccer_epl',
            'english premier': 'soccer_epl',
            # La Liga
            'la liga': 'soccer_spain_la_liga',
            'liga española': 'soccer_spain_la_liga',
            'spanish la liga': 'soccer_spain_la_liga',
            'primera division': 'soccer_spain_la_liga',
            # Serie A
            'serie a': 'soccer_italy_serie_a',
            'calcio': 'soccer_italy_serie_a',
            'italian serie': 'soccer_italy_serie_a',
            # Bundesliga
            'bundesliga': 'soccer_germany_bundesliga',
            'german bundesliga': 'soccer_germany_bundesliga',
            '1. bundesliga': 'soccer_germany_bundesliga',
            # Ligue 1
            'ligue 1': 'soccer_france_ligue_one',
            'ligue one': 'soccer_france_ligue_one',
            'french ligue': 'soccer_france_ligue_one',
            # Eredivisie
            'eredivisie': 'soccer_netherlands_eredivisie',
            'dutch eredivisie': 'soccer_netherlands_eredivisie',
            # Primeira Liga
            'primeira liga': 'soccer_portugal_primeira_liga',
            'portuguese primeira': 'soccer_portugal_primeira_liga',
            # Super Lig
            'super lig': 'soccer_turkey_super_league',
            'süper lig': 'soccer_turkey_super_league',
            'turkish super': 'soccer_turkey_super_league',
            # Champions League
            'champions league': 'soccer_uefa_champs_league',
            'uefa champions': 'soccer_uefa_champs_league',
        }
        
        for db_league in League.objects.all():
            name_norm = (db_league.name or '').lower().strip()
            matched = False
            
            # Intentar matching mejorado
            for alias, s_key in improved_league_mapping.items():
                if alias in name_norm:
                    sport_keys_to_fetch.add(s_key)
                    logger.info(f"✓ Liga '{db_league.name}' mapeada a '{s_key}' (match: '{alias}')")
                    matched = True
                    break
            
            # Si no se encontró con el mapeo mejorado, intentar el mapeo original
            if not matched:
                for alias, s_key in league_to_sport_key.items():
                    if alias in name_norm:
                        sport_keys_to_fetch.add(s_key)
                        logger.info(f"✓ Liga '{db_league.name}' mapeada a '{s_key}' (match original: '{alias}')")
                        matched = True
                        break
            
            if not matched:
                logger.warning(f"⚠ Liga '{db_league.name}' NO se pudo mapear a ningún sport_key")
        
        if not sport_keys_to_fetch:
            logger.warning("No se encontraron ligas mapeadas, usando 'soccer_epl' por defecto")
            sport_keys_to_fetch.add('soccer_epl')
        
        logger.info(f"Consultando partidos para {len(sport_keys_to_fetch)} deportes: {sport_keys_to_fetch}")
        
        upcoming_matches = []
        for s_key in sport_keys_to_fetch:
            try:
                logger.debug(f"Consultando partidos para {s_key}...")
                matches = odds_service.get_upcoming_matches(sport_key=s_key)
                if matches:
                    logger.info(f"Obtenidos {len(matches)} partidos para {s_key}")
                    upcoming_matches.extend(matches)
                else:
                    logger.warning(f"No se obtuvieron partidos para {s_key}")
            except Exception as e:
                logger.error(f"Error obteniendo partidos para {s_key}: {e}", exc_info=True)
                continue
    except Exception as e:
        logger.error(f"Error en _get_upcoming_matches_filtered: {e}", exc_info=True)
        return []
    
    
    # Filtrar por tiempo
    from datetime import timezone as dt_timezone
    now = timezone.now()
    if now.tzinfo is None:
        now = now.replace(tzinfo=dt_timezone.utc)
    else:
        now = now.astimezone(dt_timezone.utc)
    
    logger.info(f"Total partidos obtenidos de API: {len(upcoming_matches)}")
    logger.info(f"Hora actual (UTC): {now}")
    
    filtered_matches = []
    matches_filtered_out = {
        'no_commence_time': 0,
        'time_out_of_range': 0,
        'missing_teams': 0,
        'parse_error': 0
    }
    
    for match_data in upcoming_matches:
        commence_time_str = match_data.get('commence_time', '')
        if not commence_time_str:
            matches_filtered_out['no_commence_time'] += 1
            continue
        
        try:
            commence_time = datetime.fromisoformat(commence_time_str.replace('Z', '+00:00'))
            if commence_time.tzinfo is None:
                commence_time = commence_time.replace(tzinfo=dt_timezone.utc)
            else:
                commence_time = commence_time.astimezone(dt_timezone.utc)
            
            time_diff = (commence_time - now).total_seconds() / 3600
            
            # Filtrar: partidos entre -2 horas (ya empezaron) y +48 horas (próximos 48 horas)
            if time_diff < -2 or time_diff > 48:
                matches_filtered_out['time_out_of_range'] += 1
                logger.debug(f"Partido fuera de rango: {match_data.get('home_team')} vs {match_data.get('away_team')}, diff={time_diff:.1f}h")
                continue
            
            home_team = match_data.get('home_team', '')
            away_team = match_data.get('away_team', '')
            if not home_team or not away_team:
                matches_filtered_out['missing_teams'] += 1
                continue
            
            filtered_matches.append(match_data)
        except Exception as e:
            matches_filtered_out['parse_error'] += 1
            logger.warning(f"Error parseando partido: {e}, datos: {match_data.get('home_team', 'N/A')} vs {match_data.get('away_team', 'N/A')}")
            continue
    
    logger.info(f"Partidos filtrados - Total: {len(filtered_matches)}, "
                f"Sin hora: {matches_filtered_out['no_commence_time']}, "
                f"Fuera de rango: {matches_filtered_out['time_out_of_range']}, "
                f"Sin equipos: {matches_filtered_out['missing_teams']}, "
                f"Error parseo: {matches_filtered_out['parse_error']}")
    
    return filtered_matches


def _process_match_with_predictions(match_data):
    """Procesa un partido individual y devuelve sus predicciones
    Usa EXACTAMENTE el mismo flujo y funciones que 'result' (process_predictions_background)
    para garantizar consistencia total en los cálculos.
    """
    # Imports necesarios - mismos que process_predictions_background
    from ai_predictions.official_prediction_model import official_prediction_model
    from ai_predictions.shots_prediction_model import shots_prediction_model
    from ai_predictions.xg_shots_model import xg_shots_model
    
    try:
        from datetime import timezone as dt_timezone
        commence_time_str = match_data.get('commence_time', '')
        if not commence_time_str:
            return None
        
        commence_time = datetime.fromisoformat(commence_time_str.replace('Z', '+00:00'))
        if commence_time.tzinfo is None:
            commence_time = commence_time.replace(tzinfo=dt_timezone.utc)
        else:
            commence_time = commence_time.astimezone(dt_timezone.utc)
        
        home_team = match_data.get('home_team', '')
        away_team = match_data.get('away_team', '')
        if not home_team or not away_team:
            return None
        
        colombia_tz = tz(timedelta(hours=-5))
        colombia_time = commence_time.astimezone(colombia_tz)
        
        sport_title = match_data.get('sport_title', '')
        sport_key = match_data.get('sport_key', '')
        
        league_mapping = {
            'soccer_epl': 'Premier League',
            'soccer_spain_la_liga': 'La Liga',
            'soccer_italy_serie_a': 'Serie A',
            'soccer_germany_bundesliga': 'Bundesliga',
            'soccer_france_ligue_one': 'Ligue 1',
            'soccer_netherlands_eredivisie': 'Eredivisie',
            'soccer_portugal_primeira_liga': 'Primeira Liga',
            'soccer_turkey_super_league': 'Super Lig',
            'soccer_argentina_primera_division': 'Primera División',
            'soccer_belgium_first_div': 'Pro League',
            'soccer_china_superleague': 'Super League',
            'soccer_australia_aleague': 'A-League',
            'soccer_uefa_champs_league': 'Champions League',
        }
        
        league = None
        search_names = []
        
        if sport_key and sport_key in league_mapping:
            search_names.append(league_mapping[sport_key])
        if sport_title:
            search_names.append(sport_title)
        
        # Obtener logger para usar en las funciones helper
        import logging
        logger = logging.getLogger('football_data')
        
        # Función helper para normalizar nombres de ligas
        def normalize_league_name(name):
            """Normaliza el nombre de una liga para búsqueda flexible"""
            if not name:
                return ""
            # Convertir a minúsculas y remover caracteres especiales
            normalized = name.lower().strip()
            
            # Remover sufijos de países comunes (ej: "Bundesliga - Germany" -> "Bundesliga")
            country_suffixes = [
                ' - germany', ' - spain', ' - italy', ' - england', ' - france',
                ' - portugal', ' - turkey', ' - netherlands', ' - belgium',
                ' - china', ' - australia', ' - argentina',
                '- germany', '- spain', '- italy', '- england', '- france',
                '- portugal', '- turkey', '- netherlands', '- belgium',
                '- china', '- australia', '- argentina'
            ]
            for suffix in country_suffixes:
                if normalized.endswith(suffix):
                    normalized = normalized[:-len(suffix)].strip()
            
            # Remover prefijos comunes de idiomas/países
            prefixes_to_remove = [
                'english', 'spanish', 'italian', 'german', 'french',
                'portuguese', 'turkish', 'dutch', 'belgian', 'chinese',
                'australian', 'argentine', 'argentinian',
                'eng', 'esp', 'ita', 'ger', 'fra', 'por', 'tur', 'ned', 'bel', 'chn', 'aus', 'arg'
            ]
            for prefix in prefixes_to_remove:
                if normalized.startswith(prefix + ' '):
                    normalized = normalized[len(prefix) + 1:]
                if normalized.endswith(' ' + prefix):
                    normalized = normalized[:-(len(prefix) + 1)]
            
            # Remover espacios extra
            normalized = ' '.join(normalized.split())
            return normalized
        
        # Función helper para buscar liga con matching inteligente
        def find_league_smart(search_name):
            """Busca liga usando matching inteligente"""
            if not search_name:
                return None
            
            normalized_search = normalize_league_name(search_name)
            search_words = set(normalized_search.split())
            
            logger.debug(f"    Buscando liga: '{search_name}' -> normalizado: '{normalized_search}' -> palabras: {search_words}")
            
            # Obtener todas las ligas y hacer matching más inteligente
            all_leagues = League.objects.all()
            best_match = None
            best_score = 0
            
            for candidate_league in all_leagues:
                normalized_candidate = normalize_league_name(candidate_league.name)
                candidate_words = set(normalized_candidate.split())
                
                # Calcular similitud: palabras en común
                common_words = search_words.intersection(candidate_words)
                if not common_words:
                    continue
                
                logger.debug(f"      Comparando con '{candidate_league.name}' (normalizado: '{normalized_candidate}') -> palabras comunes: {common_words}")
                
                # Calcular score de similitud
                # 1. Coincidencia exacta de nombre normalizado
                if normalized_search == normalized_candidate:
                    logger.debug(f"      ✓ Coincidencia EXACTA encontrada!")
                    return candidate_league
                
                # 2. Todas las palabras principales están presentes
                important_words = {w for w in search_words if len(w) > 3}  # Palabras importantes (>3 letras)
                if important_words and important_words.issubset(candidate_words):
                    score = len(common_words) * 2
                    logger.debug(f"      ✓ Todas las palabras importantes presentes, score: {score}")
                    if score > best_score:
                        best_match = candidate_league
                        best_score = score
                    continue
                
                # 3. Coincidencia parcial de palabras clave
                score = len(common_words)
                # Bonus si contiene palabras clave importantes
                key_words = {'league', 'ligue', 'liga', 'serie', 'premier', 'bundesliga', 
                            'eredivisie', 'champions', 'super', 'division', 'primera'}
                matching_keywords = [kw for kw in key_words if kw in normalized_search and kw in normalized_candidate]
                if matching_keywords:
                    score += len(matching_keywords) * 2
                    logger.debug(f"      ✓ Palabras clave coinciden: {matching_keywords}, score: {score}")
                
                if score > best_score:
                    best_match = candidate_league
                    best_score = score
                    logger.debug(f"      Nuevo mejor match con score {score}")
            
            # Si el score es razonable (al menos 1 palabra clave o 2 palabras coinciden), usar ese match
            if best_score >= 1:
                logger.debug(f"    Match encontrado con score {best_score}: '{best_match.name if best_match else None}'")
                return best_match
            
            # Último intento: búsqueda simple con icontains
            logger.debug(f"    Intentando búsqueda simple icontains con: '{search_name}'")
            simple_match = League.objects.filter(name__icontains=search_name).first()
            if simple_match:
                logger.debug(f"    Match simple encontrado: '{simple_match.name}'")
            return simple_match
        
        # Buscar liga usando matching inteligente
        logger.debug(f"Buscando liga para {home_team} vs {away_team}")
        logger.debug(f"  sport_key: {sport_key}")
        logger.debug(f"  sport_title: {sport_title}")
        logger.debug(f"  search_names: {search_names}")
        
        for search_name in search_names:
            league = find_league_smart(search_name)
            if league:
                logger.info(f"✓ Liga encontrada: '{league.name}' (buscado: '{search_name}', sport_key: {sport_key})")
                break
            else:
                logger.debug(f"  No se encontró liga con: '{search_name}'")
        
        if not league:
            # Intentar buscar por equipos en la base de datos
            league_ids = list(
                Match.objects.filter(Q(home_team__iexact=home_team) | Q(away_team__iexact=home_team))
                .values_list('league_id', flat=True)[:1]
            )
            if not league_ids:
                league_ids = list(
                    Match.objects.filter(Q(home_team__iexact=away_team) | Q(away_team__iexact=away_team))
                    .values_list('league_id', flat=True)[:1]
                )
            if league_ids:
                league = League.objects.filter(id=league_ids[0]).first()
        
        # Si aún no se encuentra la liga, NO crear automáticamente - solo buscar
        if not league:
            import logging
            logger = logging.getLogger('football_data')
            
            # Intentar buscar una liga similar usando el mapeo
            league_name = league_mapping.get(sport_key, sport_title or 'Unknown League')
            
            # Buscar si existe una liga similar usando matching inteligente
            league = find_league_smart(league_name)
            
            if league:
                logger.debug(f"Liga encontrada por búsqueda inteligente: {league.name} (buscado: '{league_name}')")
        
        # Si aún no hay liga, retornar None - NO crear liga automáticamente
        if not league:
            import logging
            logger = logging.getLogger('football_data')
            league_name_from_mapping = league_mapping.get(sport_key, sport_title or 'Unknown')
            logger.warning(f"❌ Partido DESCARTADO: No se encontró liga en BD")
            logger.warning(f"   Partido: {home_team} vs {away_team}")
            logger.warning(f"   sport_key: {sport_key}")
            logger.warning(f"   sport_title: {sport_title}")
            logger.warning(f"   Liga buscada: {league_name_from_mapping}")
            logger.warning(f"   Ligas disponibles en BD: {list(League.objects.values_list('name', flat=True))[:10]}")
            logger.warning(f"   Solo se procesan partidos de ligas existentes en la base de datos.")
            return None
        
        # USAR EXACTAMENTE EL MISMO FLUJO QUE "result" (process_predictions_background)
        # Reutilizar la función exacta de ai_predictions/views.py
        # Importar y llamar a una función helper que replicará EXACTAMENTE process_predictions_background
        from ai_predictions.simple_models import SimplePredictionService, ModeloHibridoCorners, ModeloHibridoGeneral
        from ai_predictions.enhanced_both_teams_score import enhanced_both_teams_score_model
        
        prediction_types = [
            'shots_total', 'shots_home', 'shots_away',
            'shots_on_target_total',
            'goals_total', 'goals_home', 'goals_away',
            'corners_total', 'corners_home', 'corners_away',
            'both_teams_score'
        ]
        
        all_predictions_by_type = {}
        simple_service = SimplePredictionService()
        
        # COPIAR EXACTAMENTE la lógica de process_predictions_background (líneas 91-267)
        # Esta es la MISMA lógica que usa "result"
        for pred_type in prediction_types:
            try:
                predictions = []
                
                # MANEJO ESPECIAL PARA REMATES - USAR AMBOS MODELOS (igual que result, líneas 119-170)
                if 'shots' in pred_type or 'remates' in pred_type:
                    try:
                        # Modelo 1: Shots Prediction Model (original) - línea 125-141
                        if pred_type == 'shots_total':
                            pred1 = shots_prediction_model.predict_shots_total(home_team, away_team, league)
                        elif pred_type == 'shots_home':
                            pred1 = shots_prediction_model.predict_shots_home(home_team, away_team, league)
                        elif pred_type == 'shots_away':
                            pred1 = shots_prediction_model.predict_shots_away(home_team, away_team, league)
                        elif pred_type == 'shots_on_target_total':
                            pred1 = shots_prediction_model.predict_shots_on_target_total(home_team, away_team, league)
                        else:
                            pred1 = None
                        
                        if pred1:
                            predictions.append(pred1)
                    except Exception:
                        pass
                    
                    try:
                        # Modelo 2: XG Shots Model (nuevo) - línea 147-164
                        if pred_type == 'shots_total':
                            pred2 = xg_shots_model.predict_shots_total(home_team, away_team, league)
                        elif pred_type == 'shots_home':
                            pred2 = xg_shots_model.predict_shots_home(home_team, away_team, league)
                        elif pred_type == 'shots_away':
                            pred2 = xg_shots_model.predict_shots_away(home_team, away_team, league)
                        elif pred_type == 'shots_on_target_total':
                            pred2 = xg_shots_model.predict_shots_on_target_total(home_team, away_team, league)
                        else:
                            pred2 = None
                        
                        if pred2:
                            predictions.append(pred2)
                    except Exception:
                        pass
                else:
                    # Línea 173: get_all_simple_predictions
                    try:
                        predictions = simple_service.get_all_simple_predictions(home_team, away_team, league, pred_type)
                    except Exception:
                        predictions = []
                
                # Manejo específico para "both_teams_score" con modelo mejorado (líneas 190-216)
                if pred_type == 'both_teams_score':
                    try:
                        enhanced_prob = enhanced_both_teams_score_model.predict(home_team, away_team, league)
                        enhanced_prediction = {
                            'model_name': 'Enhanced Both Teams Score',
                            'prediction': enhanced_prob,
                            'confidence': 0.80,
                            'probabilities': {'both_score': enhanced_prob},
                            'total_matches': 100
                        }
                        predictions.append(enhanced_prediction)
                    except Exception:
                        # Fallback específico para ambos marcan (línea 207-216)
                        fallback_prob = 0.45
                        enhanced_fallback = {
                            'model_name': 'Enhanced Both Teams Score (Fallback)',
                            'prediction': fallback_prob,
                            'confidence': 0.60,
                            'probabilities': {'both_score': fallback_prob},
                            'total_matches': 0
                        }
                        predictions.append(enhanced_fallback)
                
                # Agregar modelo híbrido como modelo adicional (líneas 218-258)
                # CRÍTICO: En process_predictions_background, el elif/else está AL MISMO NIVEL que el if shots
                # Pero en Python, elif se conecta al if más cercano. Sin embargo, los logs muestran que
                # el Modelo Híbrido General SÍ se agrega para both_teams_score. Esto significa que
                # el elif/else debe ejecutarse INDEPENDIENTEMENTE, no como parte del if both_teams_score.
                # SOLUCIÓN: Cambiar elif por if para que sea un bloque independiente, y luego usar else
                if 'corners' in pred_type:
                    try:
                        hybrid_model = ModeloHibridoCorners()
                        hybrid_prediction = hybrid_model.predecir(home_team, away_team, league, pred_type)
                        predictions.append(hybrid_prediction)
                    except Exception:
                        # Fallback híbrido corners (línea 229-237)
                        hybrid_fallback = {
                            'model_name': 'Modelo Híbrido Corners',
                            'prediction': 10.0,
                            'confidence': 0.6,
                            'probabilities': {'over_10': 0.5, 'over_15': 0.3, 'over_20': 0.1},
                            'total_matches': 0,
                            'component_predictions': {}
                        }
                        predictions.append(hybrid_fallback)
                else:
                    # Modelo Híbrido General (línea 240-258)
                    try:
                        hybrid_model = ModeloHibridoGeneral()
                        hybrid_prediction = hybrid_model.predecir(home_team, away_team, league, pred_type)
                        predictions.append(hybrid_prediction)
                    except Exception:
                        # Fallback híbrido general (línea 249-257)
                        hybrid_fallback = {
                            'model_name': 'Modelo Híbrido General',
                            'prediction': 10.0,
                            'confidence': 0.6,
                            'probabilities': {'over_10': 0.5, 'over_15': 0.3, 'over_20': 0.1},
                            'total_matches': 0,
                            'component_predictions': {}
                        }
                        predictions.append(hybrid_fallback)
                
                all_predictions_by_type[pred_type] = predictions
            except Exception:
                all_predictions_by_type[pred_type] = []
        
        # AGREGAR PREDICCIÓN OFICIAL (línea 273 de process_predictions_background)
        all_predictions_by_type = official_prediction_model.add_to_predictions(all_predictions_by_type)
        
        # DEBUG: Log todas las predicciones de both_teams_score
        if 'both_teams_score' in all_predictions_by_type:
            logger.info(f"🔍 ANALYSIS DEBUG - {home_team} vs {away_team}:")
            logger.info(f"   Total predicciones both_teams_score: {len(all_predictions_by_type['both_teams_score'])}")
            for idx, pred in enumerate(all_predictions_by_type['both_teams_score']):
                model_name = pred.get('model_name', 'Unknown')
                prediction_val = pred.get('prediction')
                probabilities = pred.get('probabilities', {})
                both_score_prob = probabilities.get('both_score')
                logger.info(f"   [{idx}] model_name='{model_name}', prediction={prediction_val}, probabilities.both_score={both_score_prob}")
        
        # Extraer el valor de "Predicción Oficial" EXACTAMENTE como lo hace el template "result"
        # El template busca: pred.model_name == "Predicción Oficial" y usa pred.probabilities.both_score
        both_teams_score_value = None
        both_teams_score_pct = None
        
        if 'both_teams_score' in all_predictions_by_type:
            both_teams_score_predictions = all_predictions_by_type['both_teams_score']
            # Buscar la "Predicción Oficial" (igual que el template)
            for pred in both_teams_score_predictions:
                model_name = pred.get('model_name', '')
                if model_name == 'Predicción Oficial':
                    # Usar probabilities.both_score (igual que el template línea 397)
                    probabilities = pred.get('probabilities', {})
                    both_teams_score_value = probabilities.get('both_score')
                    if both_teams_score_value is not None:
                        # Convertir a porcentaje (igual que el template JavaScript línea 464)
                        both_teams_score_pct = both_teams_score_value * 100
                        logger.info(f"✓ ANALYSIS - Encontrado 'Predicción Oficial': both_score={both_teams_score_value} -> {both_teams_score_pct}%")
                        break
                    else:
                        logger.warning(f"⚠ ANALYSIS - 'Predicción Oficial' encontrada pero probabilities.both_score es None")
                else:
                    logger.debug(f"   Saltando modelo: '{model_name}' (no es 'Predicción Oficial')")
        
        # Fallback si no se encontró la predicción oficial
        if both_teams_score_value is None or both_teams_score_pct is None:
            logger.error(f"❌ ANALYSIS - No se encontró 'Predicción Oficial' para both_teams_score!")
            logger.error(f"   Predicciones disponibles: {[p.get('model_name') for p in all_predictions_by_type.get('both_teams_score', [])]}")
            both_teams_score_value = 0.5
            both_teams_score_pct = 50.0
        
        # Construir match_predictions para compatibilidad con el resto del código
        match_predictions = {}
        for pred_type, predictions_list in all_predictions_by_type.items():
            # Buscar la "Predicción Oficial" para cada tipo
            official_pred = None
            for pred in predictions_list:
                if pred.get('model_name') == 'Predicción Oficial':
                    official_pred = pred
                    break
            
            if official_pred and 'prediction' in official_pred:
                match_predictions[pred_type] = {
                    'prediction': official_pred['prediction'],
                    'confidence': official_pred.get('confidence', 0.5),
                    'probabilities': official_pred.get('probabilities', {}),
                    'total_matches': official_pred.get('total_matches', 0),
                }
        
        # VERIFICAR que estamos usando el valor correcto
        if both_teams_score_pct is None:
            logger.error(f"❌ ANALYSIS - both_teams_score_pct es None! Usando fallback")
            both_teams_score_pct = 50.0
            both_teams_score_value = 0.5
        
        logger.info(f"📊 ANALYSIS FINAL - {home_team} vs {away_team}: both_teams_score_pct={both_teams_score_pct}%, both_teams_score_value={both_teams_score_value}")
        
        return {
            'league': league.name,
            'home_team': home_team,
            'away_team': away_team,
            'date': colombia_time.strftime('%d/%m/%Y'),
            'time': colombia_time.strftime('%H:%M'),
            'prediction': both_teams_score_pct,  # Porcentaje (0-100)
            'probability': both_teams_score_value,  # Probabilidad (0.0-1.0)
            'predictions': match_predictions,
        }
    except Exception as e:
        logger.error(f"❌ Error procesando partido: {e}", exc_info=True)
        return None


@method_decorator(login_required, name='dispatch')
class AnalysisView(View):
    """Vista de análisis con predicciones - renderiza template base"""
    
    def get(self, request):
        context = {
            'matches': [],
            'total_matches': 0,
            'updated_at': timezone.now(),
        }
        return render(request, 'football_data/analysis.html', context)


@method_decorator(login_required, name='dispatch')
class AnalysisAjaxView(View):
    """Vista AJAX que procesa partidos en lotes y devuelve JSON"""
    
    def get(self, request):
        import json
        import logging
        import time
        
        logger = logging.getLogger('football_data')
        start_time = time.time()
        
        try:
            offset = int(request.GET.get('offset', 0))
            batch_size = int(request.GET.get('batch_size', 3))  # Procesar 3 partidos por lote
            
            logger.info(f"AnalysisAjaxView: offset={offset}, batch_size={batch_size}")
            
            # Obtener todos los partidos filtrados
            all_matches = _get_upcoming_matches_filtered()
            
            logger.info(f"Total partidos disponibles: {len(all_matches)}")
            
            # Obtener lote actual
            batch_matches = all_matches[offset:offset + batch_size]
            
            logger.info(f"Procesando lote: {len(batch_matches)} partidos (offset={offset})")
            
            processed_matches = []
            discarded_count = 0
            
            for i, match_data in enumerate(batch_matches):
                try:
                    home_team = match_data.get('home_team', 'N/A')
                    away_team = match_data.get('away_team', 'N/A')
                    logger.debug(f"Procesando partido {i+1}/{len(batch_matches)}: {home_team} vs {away_team}")
                    result = _process_match_with_predictions(match_data)
                    if result:
                        processed_matches.append(result)
                        logger.info(f"✓ Partido procesado exitosamente: {home_team} vs {away_team}")
                    else:
                        discarded_count += 1
                        logger.warning(f"✗ Partido descartado (no procesado): {home_team} vs {away_team}")
                except Exception as e:
                    discarded_count += 1
                    logger.error(f"❌ Error procesando partido {i+1}: {e}", exc_info=True)
                    continue
            
            if discarded_count > 0:
                logger.warning(f"⚠ De {len(batch_matches)} partidos, {discarded_count} fueron descartados")
            
            # Calcular el nuevo offset: avanzar según los partidos intentados (no los procesados)
            # Esto es crítico: si descartamos partidos, el offset debe avanzar igualmente
            actual_processed = len(batch_matches)  # Partidos intentados en este batch
            new_offset = offset + actual_processed
            
            # Verificar si hay más partidos
            has_more = new_offset < len(all_matches)
            
            elapsed_time = time.time() - start_time
            logger.info(f"Respuesta: {len(processed_matches)} partidos procesados de {actual_processed} intentados, "
                       f"has_more={has_more}, total={len(all_matches)}, nuevo_offset={new_offset}, tiempo={elapsed_time:.2f}s")
            
            # Verificar que los matches sean serializables antes de enviar
            try:
                import json as json_module
                json_test = json_module.dumps(processed_matches, default=str)
                logger.debug(f"JSON serializable: OK ({len(json_test)} caracteres)")
            except Exception as json_err:
                logger.error(f"❌ Error serializando matches a JSON: {json_err}", exc_info=True)
                # Intentar limpiar los matches de objetos no serializables
                cleaned_matches = []
                for match in processed_matches:
                    cleaned_match = {}
                    for key, value in match.items():
                        try:
                            json_module.dumps(value, default=str)
                            cleaned_match[key] = value
                        except:
                            logger.warning(f"Campo '{key}' no serializable, convirtiendo a string")
                            cleaned_match[key] = str(value) if value is not None else None
                    cleaned_matches.append(cleaned_match)
                processed_matches = cleaned_matches
            
            return JsonResponse({
                'success': True,
                'matches': processed_matches,
                'offset': offset,
                'new_offset': new_offset,  # Nuevo offset para el siguiente batch
                'total': len(all_matches),
                'has_more': has_more,
                'processed_count': len(processed_matches),
                'attempted_count': actual_processed,  # Partidos intentados en este batch
            })
        except Exception as e:
            elapsed_time = time.time() - start_time
            logger.error(f"❌ Error en AnalysisAjaxView (tiempo: {elapsed_time:.2f}s): {e}", exc_info=True)
            current_offset = offset if 'offset' in locals() else 0
            return JsonResponse({
                'success': False,
                'error': str(e),
                'matches': [],
                'offset': current_offset,
                'total': 0,
                'has_more': False,
                'processed_count': 0,
            }, status=500)