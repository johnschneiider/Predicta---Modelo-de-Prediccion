"""
Vistas para basketball_data
"""

from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.core.paginator import Paginator
from django.db.models import Q, Avg, Count
from django.contrib import messages
from django.urls import reverse
from datetime import datetime, timedelta
import json

from .models import NBATeam, NBAPlayer, NBAGame, NBAPrediction
from .services import nba_service
from .forms import PredictionForm
from .predictor import nba_predictor
from .multi_models import nba_multi_model_service

KAMBI_BASE = "https://us.offering-api.kambicdn.com/offering/v2018/betplay"
KAMBI_HEADERS = {"Accept": "application/json",
                 "Origin": "https://betplay.com.co",
                 "Referer": "https://betplay.com.co/"}
KAMBI_PARAMS = {"channel_id": 1, "client_id": 200, "lang": "es_CO", "market": "CO",
                "useCombined": "true", "useCombinedLive": "true"}


def _norm_name(s):
    import unicodedata
    s = unicodedata.normalize('NFKD', str(s or ''))
    return ''.join(c for c in s.lower() if c.isalnum())


def _p_over_from_probs(probs, line):
    """Interpola P(total > line) desde {over_200..over_250} (paso 10)."""
    pts = []
    for t in range(200, 260, 10):
        k = f'over_{t}'
        v = (probs or {}).get(k)
        if v is not None:
            pts.append((t, float(v)))
    if not pts:
        return None
    if line <= pts[0][0]:
        return pts[0][1]
    if line >= pts[-1][0]:
        return pts[-1][1]
    for (t1, p1), (t2, p2) in zip(pts, pts[1:]):
        if t1 <= line <= t2:
            f = (line - t1) / (t2 - t1)
            return p1 + f * (p2 - p1)
    return None


def _kambi_get(path):
    import requests
    try:
        r = requests.get(f"{KAMBI_BASE}/{path}", params=KAMBI_PARAMS,
                         headers=KAMBI_HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


@login_required
def value_finder(request):
    """Valor NBA: modelo (ensemble) vs líneas de Total de Puntos en BetPlay/Kambi."""
    listing = _kambi_get("listView/basketball.json")
    events = []
    if listing:
        for e in listing.get("events", []):
            ev = e.get("event", {})
            keys = [p.get("termKey", "") for p in ev.get("path", [])]
            if ('nba' in keys or 'nba_preseason' in keys) and ev.get("state") == "NOT_STARTED":
                events.append(ev)
    teams = {_norm_name(t.full_name): t for t in NBATeam.objects.all()}

    rows = []
    for ev in events:
        home = teams.get(_norm_name(ev.get("homeName")))
        away = teams.get(_norm_name(ev.get("awayName")))
        if not home or not away:
            continue
        try:
            pred = nba_predictor.predict(home, away)
        except Exception as e:
            pred = {'error': str(e)[:120]}
        if 'error' in pred:
            continue
        mu = pred.get('predicted_total')
        probs = pred.get('probabilities') or {}
        offers = _kambi_get(f"betoffer/event/{ev.get('id')}.json")
        lines = {}
        if offers:
            for bo in offers.get("betOffers", []):
                lab = (bo.get("criterion") or {}).get("label", "")
                if not lab.startswith('Total de puntos'):
                    continue
                line = None
                for o in bo.get("outcomes", []):
                    if o.get('status') != 'OPEN' or o.get('line') is None:
                        continue
                    line = o['line'] / 1000.0
                if line is None:
                    continue
                for o in bo.get("outcomes", []):
                    if o.get('status') != 'OPEN' or o.get('odds') is None:
                        continue
                    side = 'over' if o.get('type') == 'OT_OVER' else ('under' if o.get('type') == 'OT_UNDER' else None)
                    if not side:
                        continue
                    d = lines.setdefault(line, {})
                    d[side] = o['odds'] / 1000.0
        market_rows = []
        for line, d in sorted(lines.items()):
            if 'over' not in d or 'under' not in d:
                continue
            do, du = d['over'], d['under']
            p_over = _p_over_from_probs(probs, line)
            if p_over is None:
                continue
            inv_o, inv_u = 1 / do, 1 / du
            s = inv_o + inv_u
            fair_o, fair_u = inv_o / s, inv_u / s
            market_rows.append({
                'line': line, 'odds_over': do, 'odds_under': du,
                'p_over': p_over, 'p_under': 1 - p_over,
                'fair_over': fair_o, 'fair_under': fair_u,
                'edge_over': p_over - fair_o, 'edge_under': (1 - p_over) - fair_u,
                'ev_over': p_over * do - 1, 'ev_under': (1 - p_over) * du - 1,
            })
        if market_rows:
            best = max(market_rows, key=lambda r: r['edge_over'] + r['edge_under'])
            rows.append({
                'home': home, 'away': away, 'start': ev.get('start'),
                'pred_total': mu, 'confidence': pred.get('confidence'),
                'model': (pred.get('model_info') or {}).get('primary_model', 'Ensemble NBA'),
                'markets': market_rows, 'best': best,
            })

    return render(request, 'basketball_data/value_finder.html', {
        'rows': rows,
        'fetched_at': datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC'),
    })


@login_required
def dashboard(request):
    """Dashboard principal de NBA"""
    
    # Estadísticas generales
    total_teams = NBATeam.objects.count()
    total_players = NBAPlayer.objects.count()
    total_games = NBAGame.objects.count()
    total_predictions = NBAPrediction.objects.count()
    
    # Partidos recientes
    recent_games = NBAGame.objects.select_related('home_team', 'away_team').order_by('-game_date')[:10]
    
    # Estadísticas de puntos
    games_with_points = NBAGame.objects.filter(total_points__isnull=False)
    avg_total_points = games_with_points.aggregate(avg=Avg('total_points'))['avg']
    
    # Distribución de puntos
    point_ranges = {
        'under_200': games_with_points.filter(total_points__lt=200).count(),
        '200_220': games_with_points.filter(total_points__gte=200, total_points__lt=220).count(),
        '220_240': games_with_points.filter(total_points__gte=220, total_points__lt=240).count(),
        'over_240': games_with_points.filter(total_points__gte=240).count(),
    }
    
    context = {
        'total_teams': total_teams,
        'total_players': total_players,
        'total_games': total_games,
        'total_predictions': total_predictions,
        'recent_games': recent_games,
        'avg_total_points': round(avg_total_points, 1) if avg_total_points else 0,
        'point_ranges': point_ranges,
    }
    
    return render(request, 'basketball_data/dashboard.html', context)


@login_required
def teams_list(request):
    """Lista de equipos NBA"""
    
    teams = NBATeam.objects.all().order_by('full_name')
    
    # Búsqueda
    search_query = request.GET.get('search', '')
    if search_query:
        teams = teams.filter(
            Q(full_name__icontains=search_query) |
            Q(abbreviation__icontains=search_query) |
            Q(city__icontains=search_query)
        )
    
    # Paginación
    paginator = Paginator(teams, 20)
    page_number = request.GET.get('page')
    teams_page = paginator.get_page(page_number)
    
    context = {
        'teams': teams_page,
        'search_query': search_query,
    }
    
    return render(request, 'basketball_data/teams_list.html', context)


@login_required
def team_detail(request, team_id):
    """Detalle de un equipo específico"""
    
    team = get_object_or_404(NBATeam, id=team_id)
    
    # Estadísticas del equipo
    home_games = NBAGame.objects.filter(home_team=team)
    away_games = NBAGame.objects.filter(away_team=team)
    all_games = home_games.union(away_games).order_by('-game_date')
    
    # Estadísticas promedio
    team_stats = {
        'total_games': all_games.count(),
        'home_games': home_games.count(),
        'away_games': away_games.count(),
        'avg_points_scored': 0,
        'avg_points_allowed': 0,
        'avg_fg_pct': 0,
        'avg_fg3_pct': 0,
        'avg_ft_pct': 0,
    }
    
    if all_games.exists():
        # Calcular estadísticas promedio
        home_stats = home_games.aggregate(
            avg_points=Avg('home_points'),
            avg_fg_pct=Avg('home_fg_pct'),
            avg_fg3_pct=Avg('home_fg3_pct'),
            avg_ft_pct=Avg('home_ft_pct'),
        )
        
        away_stats = away_games.aggregate(
            avg_points=Avg('away_points'),
            avg_fg_pct=Avg('away_fg_pct'),
            avg_fg3_pct=Avg('away_fg3_pct'),
            avg_ft_pct=Avg('away_ft_pct'),
        )
        
        # Promedio ponderado
        total_games = team_stats['total_games']
        if total_games > 0:
            team_stats['avg_points_scored'] = round(
                (home_stats['avg_points'] * team_stats['home_games'] + 
                 away_stats['avg_points'] * team_stats['away_games']) / total_games, 1
            )
            team_stats['avg_fg_pct'] = round(
                (home_stats['avg_fg_pct'] * team_stats['home_games'] + 
                 away_stats['avg_fg_pct'] * team_stats['away_games']) / total_games, 3
            )
            team_stats['avg_fg3_pct'] = round(
                (home_stats['avg_fg3_pct'] * team_stats['home_games'] + 
                 away_stats['avg_fg3_pct'] * team_stats['away_games']) / total_games, 3
            )
            team_stats['avg_ft_pct'] = round(
                (home_stats['avg_ft_pct'] * team_stats['home_games'] + 
                 away_stats['avg_ft_pct'] * team_stats['away_games']) / total_games, 3
            )
    
    # Partidos recientes
    recent_games = all_games[:10]
    
    context = {
        'team': team,
        'team_stats': team_stats,
        'recent_games': recent_games,
    }
    
    return render(request, 'basketball_data/team_detail.html', context)


@login_required
def games_list(request):
    """Lista de partidos NBA"""
    
    games = NBAGame.objects.select_related('home_team', 'away_team').order_by('-game_date')
    
    # Filtros
    team_filter = request.GET.get('team', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    
    if team_filter:
        games = games.filter(
            Q(home_team__abbreviation__icontains=team_filter) |
            Q(away_team__abbreviation__icontains=team_filter)
        )
    
    if date_from:
        games = games.filter(game_date__gte=date_from)
    
    if date_to:
        games = games.filter(game_date__lte=date_to)
    
    # Paginación
    paginator = Paginator(games, 25)
    page_number = request.GET.get('page')
    games_page = paginator.get_page(page_number)
    
    context = {
        'games': games_page,
        'team_filter': team_filter,
        'date_from': date_from,
        'date_to': date_to,
    }
    
    return render(request, 'basketball_data/games_list.html', context)


@login_required
def game_detail(request, game_id):
    """Detalle de un partido específico"""
    
    game = get_object_or_404(NBAGame, id=game_id)
    
    # Predicciones para este partido
    predictions = NBAPrediction.objects.filter(game=game).order_by('-created_at')
    
    context = {
        'game': game,
        'predictions': predictions,
    }
    
    return render(request, 'basketball_data/game_detail.html', context)


@login_required
def predictions_list(request):
    """Lista de predicciones"""
    
    predictions = NBAPrediction.objects.select_related('game__home_team', 'game__away_team').order_by('-created_at')
    
    # Filtros
    model_filter = request.GET.get('model', '')
    if model_filter:
        predictions = predictions.filter(model_name__icontains=model_filter)
    
    # Paginación
    paginator = Paginator(predictions, 25)
    page_number = request.GET.get('page')
    predictions_page = paginator.get_page(page_number)
    
    context = {
        'predictions': predictions_page,
        'model_filter': model_filter,
    }
    
    return render(request, 'basketball_data/predictions_list.html', context)


@login_required
@require_http_methods(["POST"])
def sync_data(request):
    """Sincronizar datos desde NBA API"""
    
    try:
        data = json.loads(request.body)
        sync_type = data.get('type', 'teams')
        
        if sync_type == 'teams':
            result = nba_service.sync_teams()
        elif sync_type == 'players':
            result = nba_service.sync_players()
        elif sync_type == 'games':
            result = nba_service.sync_current_season_games()
        else:
            return JsonResponse({'error': 'Tipo de sincronización no válido'}, status=400)
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def statistics(request):
    """Página de estadísticas"""
    
    # Estadísticas generales
    total_games = NBAGame.objects.count()
    games_with_points = NBAGame.objects.filter(total_points__isnull=False)
    
    if games_with_points.exists():
        avg_total_points = games_with_points.aggregate(avg=Avg('total_points'))['avg']
        
        # Distribución de puntos
        point_distribution = {
            'under_200': games_with_points.filter(total_points__lt=200).count(),
            '200_220': games_with_points.filter(total_points__gte=200, total_points__lt=220).count(),
            '220_240': games_with_points.filter(total_points__gte=220, total_points__lt=240).count(),
            'over_240': games_with_points.filter(total_points__gte=240).count(),
        }
        
        # Equipos con más puntos promedio
        team_stats = []
        for team in NBATeam.objects.all():
            home_games = NBAGame.objects.filter(home_team=team, home_points__isnull=False)
            away_games = NBAGame.objects.filter(away_team=team, away_points__isnull=False)
            
            if home_games.exists() or away_games.exists():
                home_avg = home_games.aggregate(avg=Avg('home_points'))['avg'] or 0
                away_avg = away_games.aggregate(avg=Avg('away_points'))['avg'] or 0
                total_games = home_games.count() + away_games.count()
                
                if total_games > 0:
                    avg_points = (home_avg * home_games.count() + away_avg * away_games.count()) / total_games
                    team_stats.append({
                        'team': team,
                        'avg_points': round(avg_points, 1),
                        'total_games': total_games
                    })
        
        team_stats.sort(key=lambda x: x['avg_points'], reverse=True)
        top_teams = team_stats[:10]
        
    else:
        avg_total_points = 0
        point_distribution = {}
        top_teams = []
    
    context = {
        'total_games': total_games,
        'avg_total_points': round(avg_total_points, 1) if avg_total_points else 0,
        'point_distribution': point_distribution,
        'top_teams': top_teams,
    }
    
    return render(request, 'basketball_data/statistics.html', context)


@login_required
def prediction_form(request):
    """Formulario de predicción de puntos totales"""
    
    if request.method == 'POST':
        form = PredictionForm(request.POST)
        if form.is_valid():
            home_team = form.cleaned_data['home_team']
            away_team = form.cleaned_data['away_team']
            
            # Inicializar progreso en sesión
            request.session['nba_prediction_progress'] = {
                'current': 0,
                'total': 3,
                'current_type': 'Iniciando análisis...',
                'status': 'processing'
            }
            
            # Para AJAX, solo inicializar progreso y devolver éxito
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # Guardar equipos en sesión para la predicción asíncrona
                request.session['nba_prediction_teams'] = {
                    'home_team_id': home_team.id,
                    'away_team_id': away_team.id,
                    'home_team_name': home_team.full_name,
                    'away_team_name': away_team.full_name,
                    'home_team_abbr': home_team.abbreviation,
                    'away_team_abbr': away_team.abbreviation
                }
                
                return JsonResponse({
                    'success': True,
                    'message': 'Iniciando predicción...'
                })
            
            # Para formulario normal, realizar predicción inmediatamente
            try:
                prediction_result = nba_predictor.predict(home_team, away_team)
                
                if 'error' not in prediction_result:
                    # Guardar resultado en sesión para mostrar en resultado
                    request.session['nba_prediction_result'] = {
                        'home_team': {
                            'id': home_team.id,
                            'full_name': home_team.full_name,
                            'abbreviation': home_team.abbreviation
                        },
                        'away_team': {
                            'id': away_team.id,
                            'full_name': away_team.full_name,
                            'abbreviation': away_team.abbreviation
                        },
                        'prediction': prediction_result
                    }
                    
                    return redirect('basketball_data:prediction_result')
                else:
                    messages.error(request, f"Error en la predicción: {prediction_result['error']}")
            except Exception as e:
                messages.error(request, f"Error procesando predicción: {str(e)}")
        else:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({
                    'success': False,
                    'error': 'Formulario inválido',
                    'form_errors': form.errors
                })
            
            messages.error(request, "Por favor corrige los errores en el formulario")
    else:
        form = PredictionForm()
    
    return render(request, 'basketball_data/prediction_form.html', {
        'form': form
    })


@login_required
def prediction_result(request):
    """Mostrar resultado de la predicción"""
    try:
        # Obtener resultado de la sesión
        prediction_data = request.session.get('nba_prediction_result')
        
        if not prediction_data:
            messages.error(request, "No hay datos de predicción disponibles. Por favor realiza una nueva predicción.")
            return redirect('basketball_data:prediction_form')
        
        # Reconstruir objetos de equipos
        home_team_data = prediction_data['home_team']
        away_team_data = prediction_data['away_team']
        
        # Crear objetos mock para compatibilidad con template
        class MockTeam:
            def __init__(self, data):
                self.id = data['id']
                self.full_name = data['full_name']
                self.abbreviation = data['abbreviation']
        
        home_team = MockTeam(home_team_data)
        away_team = MockTeam(away_team_data)
        prediction = prediction_data['prediction']
        
        # Limpiar datos de sesión después de mostrar
        request.session.pop('nba_prediction_result', None)
        request.session.pop('nba_prediction_progress', None)
        
        return render(request, 'basketball_data/prediction_result.html', {
            'home_team': home_team,
            'away_team': away_team,
            'prediction': prediction
        })
        
    except Exception as e:
        messages.error(request, f"Error mostrando resultado: {str(e)}")
        return redirect('basketball_data:prediction_form')


@login_required
@require_http_methods(["POST"])
def train_model(request):
    """Entrenar modelo de predicción usando múltiples algoritmos"""
    try:
        # Entrenar el predictor principal (ahora usa ensemble)
        train_result = nba_predictor.train()
        
        if train_result['success']:
            # Obtener información adicional de los modelos individuales
            total_games = NBAGame.objects.filter(total_points__isnull=False).count()
            
            result = {
                'success': True,
                'message': 'Modelo ensemble entrenado exitosamente',
                'mae': train_result.get('mae', 'N/A'),
                'rmse': train_result.get('rmse', 'N/A'),
                'training_samples': train_result.get('training_samples', total_games),
                'test_samples': train_result.get('test_samples', 0),
                'models_used': [
                    'Poisson NBA',
                    'Random Forest NBA', 
                    'Ridge Regression NBA',
                    'Ensemble (Promedio Ponderado)'
                ],
                'ensemble_info': train_result.get('message', 'Múltiples algoritmos combinados')
            }
        else:
            result = {
                'success': False,
                'error': train_result.get('error', 'Error desconocido al entrenar el modelo')
            }
        
        return JsonResponse(result)
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': f'Error entrenando modelo: {str(e)}'
        })


@login_required
@require_http_methods(["GET"])
def prediction_progress(request):
    """API endpoint para obtener el progreso de la predicción"""
    try:
        # Simular progreso de predicción NBA
        # En una implementación real, esto vendría de la sesión o base de datos
        
        # Obtener progreso de la sesión
        progress_data = request.session.get('nba_prediction_progress', {
            'current': 0,
            'total': 3,  # 3 modelos: Poisson, Random Forest, Ridge
            'current_type': 'Iniciando análisis...',
            'status': 'processing'
        })
        
        # Simular progreso incremental
        if progress_data['current'] < progress_data['total']:
            progress_data['current'] += 1
            
            if progress_data['current'] == 1:
                progress_data['current_type'] = 'Modelo Poisson NBA'
            elif progress_data['current'] == 2:
                progress_data['current_type'] = 'Modelo Random Forest NBA'
            elif progress_data['current'] == 3:
                progress_data['current_type'] = 'Modelo Ridge Regression NBA'
                progress_data['status'] = 'completed'
                
                # Cuando se complete el progreso, realizar la predicción real
                teams_data = request.session.get('nba_prediction_teams')
                if teams_data:
                    try:
                        home_team = NBATeam.objects.get(id=teams_data['home_team_id'])
                        away_team = NBATeam.objects.get(id=teams_data['away_team_id'])
                        
                        prediction_result = nba_predictor.predict(home_team, away_team)
                        
                        if 'error' not in prediction_result:
                            # Guardar resultado en sesión
                            request.session['nba_prediction_result'] = {
                                'home_team': {
                                    'id': home_team.id,
                                    'full_name': home_team.full_name,
                                    'abbreviation': home_team.abbreviation
                                },
                                'away_team': {
                                    'id': away_team.id,
                                    'full_name': away_team.full_name,
                                    'abbreviation': away_team.abbreviation
                                },
                                'prediction': prediction_result
                            }
                            
                            # Limpiar datos temporales
                            request.session.pop('nba_prediction_teams', None)
                        else:
                            progress_data['status'] = 'error'
                            progress_data['current_type'] = f'Error: {prediction_result["error"]}'
                    except Exception as e:
                        progress_data['status'] = 'error'
                        progress_data['current_type'] = f'Error: {str(e)}'
            
            # Guardar en sesión
            request.session['nba_prediction_progress'] = progress_data
        else:
            progress_data['status'] = 'completed'
            progress_data['current_type'] = 'Predicciones completadas'
        
        return JsonResponse(progress_data)
        
    except Exception as e:
        return JsonResponse({
            'current': 0,
            'total': 3,
            'current_type': 'Error',
            'status': 'error',
            'error': str(e)
        })


@login_required
@require_http_methods(["POST"])
def predict_points(request):
    """API endpoint para predicción de puntos usando ensemble de modelos"""
    
    try:
        data = json.loads(request.body)
        home_team_id = data.get('home_team_id')
        away_team_id = data.get('away_team_id')
        
        if not home_team_id or not away_team_id:
            return JsonResponse({'error': 'IDs de equipos requeridos'}, status=400)
        
        home_team = get_object_or_404(NBATeam, id=home_team_id)
        away_team = get_object_or_404(NBATeam, id=away_team_id)
        
        # Entrenar modelo si no está entrenado
        if not nba_predictor.is_trained:
            training_result = nba_predictor.train()
            if not training_result['success']:
                return JsonResponse({'error': training_result['error']}, status=500)
        
        # Realizar predicción usando ensemble
        prediction_result = nba_predictor.predict(home_team, away_team)
        
        if 'error' in prediction_result:
            return JsonResponse({'error': prediction_result['error']}, status=500)
        
        # Agregar información sobre los modelos utilizados
        enhanced_result = {
            **prediction_result,
            'models_info': {
                'primary_model': prediction_result.get('model_info', {}).get('primary_model', 'Ensemble NBA'),
                'component_models': prediction_result.get('model_info', {}).get('component_models', {}),
                'total_matches_analyzed': prediction_result.get('model_info', {}).get('total_matches', 0),
                'ensemble_method': 'Promedio ponderado de múltiples algoritmos'
            }
        }
        
        return JsonResponse(enhanced_result)
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)