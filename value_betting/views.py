"""
Vistas del motor de Value Betting
"""

import json
import logging
import threading
from datetime import timedelta
from django.shortcuts import render, get_object_or_404
from django.http import JsonResponse, HttpResponseNotAllowed
from django.views import View
from django.contrib.auth.decorators import login_required
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Avg, Count, Q
from django.utils import timezone

from .models import KambiMatch, KambiBetOffer, ValueOpportunity, ScanRun
from .services import run_scan, check_kambi_api_health
from football_data.models import Match as FootballMatch
import subprocess, os

logger = logging.getLogger('value_betting')

# ── Promedios de remates por liga (página /value-betting/shots/) ──
SHOTS_LEAGUES = [
    (11, 'Francia · Ligue 1'),
    (7, 'Italia · Serie A'),
    (4, 'Inglaterra · Premier League'),
    (5, 'Inglaterra · Championship'),
    (6, 'Alemania · Bundesliga'),
    (8, 'Países Bajos · Eredivisie'),
    (14, 'Escocia · Scottish Premiership'),
    (13, 'Bélgica · Jupiler Pro League'),
    (32, 'Dinamarca · Superligaen'),
    (24, 'Brasil · Serie A'),
    (25, 'Brasil · Serie B'),
    (27, 'Argentina · Primera División'),
    (28, 'México · Liga MX'),
    (29, 'USA · MLS'),
]
SHOTS_WINDOW_DAYS = 365
SHOTS_MIN_MATCHES = 3

# ── Estado del scraper de Flashscore ──
_FS_PID_FILE = '/tmp/flashscore_scrape.pid'
_FS_LOG = '/var/www/predicta.com.co/logs/flashscore_current.log'
_FS_SCRIPT = '/var/www/predicta.com.co/scripts/flashscore_scrape.py'
_FS_VENV = '/var/www/predicta.com.co/venv/bin/python'


@method_decorator(login_required, name='dispatch')
class ValueBettingDashboardView(View):
    """Dashboard principal del motor de value betting"""
    
    template_name = 'value_betting/dashboard.html'
    
    def get(self, request):
        # Último escaneo
        last_scan = ScanRun.objects.order_by('-started_at').first()
        
        # Value bets con probabilidad >= 50%
        value_bets = ValueOpportunity.objects.filter(
            is_value=True, status='pending',
            predicta_probability__gte=0.50
        ).select_related('match').order_by('-edge')[:50]
        
        # Todas las oportunidades (para tabla completa)
        all_opportunities = ValueOpportunity.objects.filter(
            is_value=True
        ).select_related('match').order_by('-edge', '-created_at')[:100]
        
        # Stats
        total_matches = KambiMatch.objects.count()
        total_offers = KambiBetOffer.objects.count()
        total_value = value_bets.count()
        avg_edge = value_bets.aggregate(avg=Avg('edge'))['avg'] or 0
        
        # Escaneos recientes
        recent_scans = ScanRun.objects.order_by('-started_at')[:5]
        
        # Healthcheck de la API de Kambi
        api_health = check_kambi_api_health()
        
        context = {
            'last_scan': last_scan,
            'value_bets': value_bets,
            'all_opportunities': all_opportunities,
            'total_matches': total_matches,
            'total_offers': total_offers,
            'total_value': total_value,
            'avg_edge': round(avg_edge, 2),
            'recent_scans': recent_scans,
            'api_health': api_health,
        }
        
        return render(request, self.template_name, context)


@method_decorator(login_required, name='dispatch')
class RunScanView(View):
    """Ejecuta el escaneo en background"""
    
    def post(self, request):
        # Ejecutar en thread separado para no bloquear
        scan_thread = threading.Thread(target=run_scan, daemon=True)
        scan_thread.start()
        
        return JsonResponse({
            'status': 'started',
            'message': 'Escaneo iniciado en segundo plano. Actualiza la página en ~30 segundos.',
        })


@method_decorator(login_required, name='dispatch')
class ScanStatusView(View):
    """Consulta el estado del escaneo actual"""
    
    def get(self, request):
        scan = ScanRun.objects.order_by('-started_at').first()
        if not scan:
            return JsonResponse({'status': 'none'})
        
        return JsonResponse({
            'status': scan.status,
            'matches_fetched': scan.matches_fetched,
            'matches_mapped': scan.matches_mapped,
            'predictions_generated': scan.predictions_generated,
            'opportunities_found': scan.opportunities_found,
            'value_bets_found': scan.value_bets_found,
            'started_at': scan.started_at.isoformat() if scan.started_at else None,
            'finished_at': scan.finished_at.isoformat() if scan.finished_at else None,
            'errors': scan.errors[:500] if scan.errors else '',
        })


@method_decorator(login_required, name='dispatch')
class OpportunityDetailView(View):
    """Detalle de una oportunidad específica"""
    
    def get(self, request, pk):
        opp = get_object_or_404(ValueOpportunity, pk=pk)
        data = {
            'id': opp.id,
            'match': f"{opp.match.home_team} vs {opp.match.away_team}",
            'league': opp.match.predicta_league.name if opp.match.predicta_league else 'N/A',
            'market': opp.market,
            'selection': opp.selection,
            'betplay_odds': opp.betplay_odds,
            'betplay_implied_prob': round(opp.betplay_implied_prob * 100, 1),
            'predicta_prob': round(opp.predicta_probability * 100, 1),
            'predicta_prediction': opp.predicta_prediction,
            'predicta_confidence': round(opp.predicta_confidence * 100, 1),
            'predicta_model': opp.predicta_model,
            'edge': opp.edge,
            'ev': opp.ev,
            'line': opp.line,
            'status': opp.status,
            'start_time': opp.match.start_time.isoformat(),
        }
        return JsonResponse(data)


@method_decorator(login_required, name='dispatch')
class MatchListView(View):
    """Lista de partidos escaneados con sus cuotas"""
    
    def get(self, request):
        matches = KambiMatch.objects.filter(
            mapped_home_team__isnull=False,
            mapped_away_team__isnull=False,
        ).select_related('predicta_league').order_by('start_time')[:100]
        
        data = []
        for m in matches:
            offers_count = m.bet_offers.count()
            value_count = m.opportunities.filter(is_value=True).count()
            data.append({
                'id': m.id,
                'home': m.home_team,
                'away': m.away_team,
                'mapped_home': m.mapped_home_team,
                'mapped_away': m.mapped_away_team,
                'league': m.predicta_league.name if m.predicta_league else 'N/A',
                'start_time': m.start_time.isoformat(),
                'offers_count': offers_count,
                'value_count': value_count,
                'mapping_confidence': round(m.mapping_confidence * 100, 1),
            })
        
        return JsonResponse({'matches': data})


@method_decorator(login_required, name='dispatch')
class ApiHealthView(View):
    """Estado de la API de Kambi (BetPlay)"""
    
    def get(self, request):
        health = check_kambi_api_health()
        return JsonResponse(health)


@method_decorator(login_required, name='dispatch')
class RunFlashscoreScrapeView(View):
    """Lanza el scraper de Flashscore (temporalada actual) en background."""
    
    def post(self, request):
        # ¿Ya está corriendo?
        if os.path.exists(_FS_PID_FILE):
            try:
                pid = int(open(_FS_PID_FILE).read().strip())
                os.kill(pid, 0)  # check si vivo
                return JsonResponse({'status': 'already_running',
                                     'message': 'El scraper ya está corriendo.'})
            except (ProcessLookupError, ValueError):
                pass  # proceso muerto, limpiar

        cmd = [
            _FS_VENV, _FS_SCRIPT,
            '--sa', '--europe', '--current',
            '--mode', 'full', '--delay', '1.5',
        ]
        env = {**os.environ, 'HOME': '/tmp',
               'PLAYWRIGHT_BROWSERS_PATH': '/root/.cache/ms-playwright'}
        proc = subprocess.Popen(
            cmd, stdout=open(_FS_LOG, 'w'), stderr=subprocess.STDOUT,
            cwd='/var/www/predicta.com.co', env=env,
        )
        with open(_FS_PID_FILE, 'w') as f:
            f.write(str(proc.pid))

        return JsonResponse({
            'status': 'started',
            'message': 'Scraper de Flashscore iniciado. Trae partidos actuales con xG.',
            'pid': proc.pid,
        })


@method_decorator(login_required, name='dispatch')
class FlashscoreScrapeStatusView(View):
    """Estado del scraper de Flashscore."""
    
    def get(self, request):
        running = False
        pid = None
        if os.path.exists(_FS_PID_FILE):
            try:
                pid = int(open(_FS_PID_FILE).read().strip())
                os.kill(pid, 0)
                running = True
            except (ProcessLookupError, ValueError):
                running = False

        # Últimas 15 líneas del log
        log_tail = ''
        try:
            lines = open(_FS_LOG).readlines()
            log_tail = ''.join(lines[-15:])
        except Exception:
            pass

        return JsonResponse({
            'running': running,
            'pid': pid,
            'log': log_tail,
        })


@method_decorator(login_required, name='dispatch')
class ShotsAveragesView(View):
    """Promedio de remates totales a favor y en contra, por equipo y condición (local/visitante)."""

    template_name = 'value_betting/shots_averages.html'

    def get(self, request):
        since = timezone.now().date() - timedelta(days=SHOTS_WINDOW_DAYS)
        league_ids = [lid for lid, _ in SHOTS_LEAGUES]

        base = FootballMatch.objects.filter(
            league_id__in=league_ids,
            date__gte=since,
            hs__isnull=False,
            as_field__isnull=False,
        )
        total_matches = base.count()

        # Como local: a favor = hs, en contra = as_field
        home_rows = base.values('league_id', 'home_team').annotate(
            pj=Count('id'), avg_for=Avg('hs'), avg_against=Avg('as_field'),
        )
        # Como visitante: a favor = as_field, en contra = hs
        away_rows = base.values('league_id', 'away_team').annotate(
            pj=Count('id'), avg_for=Avg('as_field'), avg_against=Avg('hs'),
        )

        merged = {}
        for r in home_rows:
            merged.setdefault((r['league_id'], r['home_team']), {})['home'] = r
        for r in away_rows:
            merged.setdefault((r['league_id'], r['away_team']), {})['away'] = r

        leagues_out = []
        for lid, label in SHOTS_LEAGUES:
            teams = []
            for (league_id, team), sides in merged.items():
                if league_id != lid:
                    continue
                h = sides.get('home')
                a = sides.get('away')
                if h and h['pj'] < SHOTS_MIN_MATCHES:
                    h = None
                if a and a['pj'] < SHOTS_MIN_MATCHES:
                    a = None
                if not h and not a:
                    continue
                teams.append({'name': team, 'home': h, 'away': a})
            teams.sort(key=lambda t: t['name'])
            if teams:
                leagues_out.append({
                    'id': lid,
                    'label': label,
                    'teams': teams,
                    'team_count': len(teams),
                })

        context = {
            'since': since,
            'min_matches': SHOTS_MIN_MATCHES,
            'window_days': SHOTS_WINDOW_DAYS,
            'total_matches': total_matches,
            'leagues': leagues_out,
        }
        return render(request, self.template_name, context)