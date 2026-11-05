"""
Vistas de baseball_data (MLB).
"""
import json
import os
import re
from datetime import datetime, timezone

import requests
from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Avg, Q
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect

from .baseline import RollingStats, predict_matchup
from .forms import MLBForm
from .models import BaseballGame, BaseballPrediction, BaseballTeam

KAMBI_BASE = "https://us.offering-api.kambicdn.com/offering/v2018/betplay"
KAMBI_HEADERS = {"Accept": "application/json",
                 "Origin": "https://betplay.com.co",
                 "Referer": "https://betplay.com.co/"}
KAMBI_PARAMS = {"channel_id": 1, "client_id": 200, "lang": "es_CO", "market": "CO",
                "useCombined": "true", "useCombinedLive": "true"}

TOTAL_LINES = (5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5)
FIRST5_LINES = (2.5, 3.5, 4.5, 5.5)


def _full_stats():
    """Stats del baseline sobre TODOS los partidos terminados de la BD."""
    games = BaseballGame.objects.filter(
        home_runs__isnull=False, away_runs__isnull=False,
        status__in=('Game Finished', 'Finished', 'After OT')).order_by('date')
    stats = RollingStats()
    for g in games.iterator():
        stats.update(g)
    return stats


def _kambi_get(path):
    url = f"{KAMBI_BASE}/{path}"
    try:
        r = requests.get(url, params=KAMBI_PARAMS, headers=KAMBI_HEADERS, timeout=20)
        r.raise_for_status()
        return r.json()
    except Exception:
        return None


@login_required
def dashboard(request):
    total_teams = BaseballTeam.objects.count()
    total_games = BaseballGame.objects.count()
    total_predictions = BaseballPrediction.objects.count()
    finished = BaseballGame.objects.filter(home_runs__isnull=False)
    avg_total = finished.aggregate(avg=(Avg('home_runs') + Avg('away_runs')))['avg'] if finished.exists() else None
    recent = BaseballGame.objects.select_related('home_team', 'away_team')[:10]
    backtest = _load_backtest()
    context = {
        'total_teams': total_teams,
        'total_games': total_games,
        'total_predictions': total_predictions,
        'avg_total': round(avg_total, 2) if avg_total else 0,
        'recent_games': recent,
        'backtest': backtest,
    }
    return render(request, 'baseball_data/dashboard.html', context)


@login_required
def games_list(request):
    games = BaseballGame.objects.select_related('home_team', 'away_team')
    season = request.GET.get('season', '')
    team_q = request.GET.get('team', '')
    if season:
        games = games.filter(season=season)
    if team_q:
        games = games.filter(
            Q(home_team__name__icontains=team_q) | Q(away_team__name__icontains=team_q))
    seasons = BaseballGame.objects.values_list('season', flat=True).distinct().order_by('-season')
    paginator = Paginator(games, 25)
    page = paginator.get_page(request.GET.get('page'))
    return render(request, 'baseball_data/games_list.html', {
        'games': page, 'season': season, 'team_q': team_q, 'seasons': seasons,
    })


@login_required
def game_detail(request, game_id):
    game = get_object_or_404(BaseballGame, id=game_id)
    predictions = BaseballPrediction.objects.filter(game=game).order_by('-created_at')
    return render(request, 'baseball_data/game_detail.html', {
        'game': game, 'predictions': predictions,
    })


@login_required
def prediction_form(request):
    if request.method == 'POST':
        form = MLBForm(request.POST)
        if form.is_valid():
            home = form.cleaned_data['home_team']
            away = form.cleaned_data['away_team']
            stats = _full_stats()
            pred = predict_matchup(stats, home.id, away.id, TOTAL_LINES, FIRST5_LINES)
            request.session['mlb_prediction'] = {
                'home': {'id': home.id, 'name': home.name, 'code': home.code},
                'away': {'id': away.id, 'name': away.name, 'code': away.code},
                'prediction': pred,
            }
            return redirect('baseball_data:prediction_result')
        else:
            messages.error(request, "Corrige los errores del formulario.")
    else:
        form = MLBForm()
    return render(request, 'baseball_data/prediction_form.html', {'form': form})


@login_required
def prediction_result(request):
    data = request.session.get('mlb_prediction')
    if not data:
        messages.error(request, "No hay datos de predicción. Haz una nueva predicción.")
        return redirect('baseball_data:prediction_form')
    return render(request, 'baseball_data/prediction_result.html', {
        'home': data['home'], 'away': data['away'], 'prediction': data['prediction'],
    })


@login_required
def value_finder(request):
    """Encuentra valor real por partido: modelo vs líneas Kambi (BetPlay)."""
    listing = _kambi_get("listView/baseball.json")
    events = []
    if listing:
        for e in listing.get("events", []):
            ev = e.get("event", {})
            path = ev.get("path", [])
            keys = [p.get("termKey", "") for p in path]
            if "mlb" not in keys or ev.get("state") != "NOT_STARTED":
                continue
            events.append(ev)

    rows = []
    teams_by_name = {t.name: t for t in BaseballTeam.objects.all()}
    stats = _full_stats()

    for ev in events:
        home_name = ev.get("homeName", "")
        away_name = ev.get("awayName", "")
        ht = teams_by_name.get(home_name)
        at = teams_by_name.get(away_name)
        if not ht or not at:
            continue
        pred = predict_matchup(stats, ht.id, at.id, TOTAL_LINES, FIRST5_LINES)
        offers = _kambi_get(f"betoffer/event/{ev['id']}.json")
        markets = []
        if offers:
            markets = _parse_kambi_markets(offers, pred, home_name, away_name)
        rows.append({
            'home': ht, 'away': at, 'start': ev.get("start"),
            'lam_home': pred['lam_home'], 'lam_away': pred['lam_away'],
            'pred_total': pred['pred_total'],
            'p_home_win': pred['p_home_win'],
            'markets': markets,
            'top_picks': [m for m in markets if m['best']['edge'] >= 0.05][:5],
        })
    return render(request, 'baseball_data/value_finder.html', {
        'rows': rows, 'fetched_at': datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
    })


def _devig(p1, p2):
    s = p1 + p2
    if s <= 0:
        return 0.5, 0.5
    return p1 / s, p2 / s


def _parse_kambi_markets(offers, pred, home_name, away_name):
    """Extrae los mercados principales de un evento Kambi y calcula EV/edge."""
    markets = []
    seen = set()
    for bo in offers.get("betOffers", []):
        crit = bo.get("criterion", {})
        label = crit.get("label", "")
        outcomes = [o for o in bo.get("outcomes", []) if o.get("status") == "OPEN"]
        if not outcomes:
            continue

        if label == "Cuotas del partido" and len(outcomes) == 2:
            if ('ml',) in seen:
                continue
            seen.add(('ml',))
            by_name = {o.get("label"): o for o in outcomes}
            oh = by_name.get(home_name)
            oa = by_name.get(away_name)
            if oh and oa:
                ph, pa = _devig(1 / (oh["odds"] / 1000), 1 / (oa["odds"] / 1000))
                row = {'market': 'Ganador', 'line': None,
                       'outcomes': [
                           {'side': home_name, 'odds': oh["odds"] / 1000,
                            'p_model': pred['p_home_win'], 'edge': round(pred['p_home_win'] - ph, 4),
                            'ev': round(pred['p_home_win'] * (oh["odds"] / 1000) - 1, 4)},
                           {'side': away_name, 'odds': oa["odds"] / 1000,
                            'p_model': pred['p_away_win'], 'edge': round(pred['p_away_win'] - pa, 4),
                            'ev': round(pred['p_away_win'] * (oa["odds"] / 1000) - 1, 4)},
                       ]}
                row['best'] = max(row['outcomes'], key=lambda x: x['edge'])
                markets.append(row)

        elif label == "Hándicap" and len(outcomes) == 2:
            by_line = {o.get("line") / 1000: o for o in outcomes}
            if -1.5 in by_line and 1.5 in by_line and ('rl',) not in seen:
                seen.add(('rl',))
                o_minus = by_line[-1.5]
                o_plus = by_line[1.5]
                p_home_cover = pred['runline_probs']['1.5']['home']
                ph, pa = _devig(1 / (o_minus["odds"] / 1000), 1 / (o_plus["odds"] / 1000))
                side_minus = 'home' if o_minus.get("label") == home_name else 'away'
                p_minus = p_home_cover if side_minus == 'home' else 1 - p_home_cover
                p_plus = 1 - p_minus
                row = {'market': 'Run line ±1.5', 'line': '-1.5/+1.5',
                       'outcomes': [
                           {'side': f"{home_name if side_minus=='home' else away_name} -1.5",
                            'odds': o_minus["odds"] / 1000, 'p_model': round(p_minus, 4),
                            'edge': round(p_minus - ph, 4),
                            'ev': round(p_minus * (o_minus["odds"] / 1000) - 1, 4)},
                           {'side': f"{home_name if side_minus!='home' else away_name} +1.5",
                            'odds': o_plus["odds"] / 1000, 'p_model': round(p_plus, 4),
                            'edge': round(p_plus - pa, 4),
                            'ev': round(p_plus * (o_plus["odds"] / 1000) - 1, 4)},
                       ]}
                row['best'] = max(row['outcomes'], key=lambda x: x['edge'])
                markets.append(row)

        elif label == "Total de carreras" and len(outcomes) == 2:
            line = outcomes[0].get("line") / 1000
            key = f"{line:.1f}"
            if key not in pred['total_line_probs'] or ('total', line) in seen:
                continue
            seen.add(('total', line))
            probs = pred['total_line_probs'][key]
            by_type = {o.get("type"): o for o in outcomes}
            o_over = by_type.get("OT_OVER")
            o_under = by_type.get("OT_UNDER")
            if o_over and o_under:
                ph, pa = _devig(1 / (o_over["odds"] / 1000), 1 / (o_under["odds"] / 1000))
                row = {'market': f'Total carreras {line}', 'line': line,
                       'outcomes': [
                           {'side': 'Más de', 'odds': o_over["odds"] / 1000,
                            'p_model': probs['over'], 'edge': round(probs['over'] - ph, 4),
                            'ev': round(probs['over'] * (o_over["odds"] / 1000) - 1, 4)},
                           {'side': 'Menos de', 'odds': o_under["odds"] / 1000,
                            'p_model': probs['under'], 'edge': round(probs['under'] - pa, 4),
                            'ev': round(probs['under'] * (o_under["odds"] / 1000) - 1, 4)},
                       ]}
                row['best'] = max(row['outcomes'], key=lambda x: x['edge'])
                markets.append(row)

        elif label == "Total de carreras - 1.ª 5 entradas" and len(outcomes) == 2:
            line = outcomes[0].get("line") / 1000
            key = f"{line:.1f}"
            if key not in pred['first5_probs'] or ('f5', line) in seen:
                continue
            seen.add(('f5', line))
            probs = pred['first5_probs'][key]
            by_type = {o.get("type"): o for o in outcomes}
            o_over = by_type.get("OT_OVER")
            o_under = by_type.get("OT_UNDER")
            if o_over and o_under:
                ph, pa = _devig(1 / (o_over["odds"] / 1000), 1 / (o_under["odds"] / 1000))
                row = {'market': f'Total 1.ª 5 entradas {line}', 'line': line,
                       'outcomes': [
                           {'side': 'Más de', 'odds': o_over["odds"] / 1000,
                            'p_model': probs['over'], 'edge': round(probs['over'] - ph, 4),
                            'ev': round(probs['over'] * (o_over["odds"] / 1000) - 1, 4)},
                           {'side': 'Menos de', 'odds': o_under["odds"] / 1000,
                            'p_model': probs['under'], 'edge': round(probs['under'] - pa, 4),
                            'ev': round(probs['under'] * (o_under["odds"] / 1000) - 1, 4)},
                       ]}
                row['best'] = max(row['outcomes'], key=lambda x: x['edge'])
                markets.append(row)
    return markets


def _load_backtest():
    path = os.path.join(settings.BASE_DIR, 'baseball_data', 'reports', 'backtest_latest.json')
    if os.path.exists(path):
        try:
            with open(path) as f:
                return json.load(f)
        except Exception:
            return None
    return None


@login_required
def backtest_report(request):
    report = _load_backtest()
    return render(request, 'baseball_data/backtest_report.html', {'report': report})
