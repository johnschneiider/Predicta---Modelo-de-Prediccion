"""
Vistas del auto_betting: historial de apuestas y análisis.
Incluye separación sistema/manual y métricas de CLV.
"""

from django.shortcuts import render, redirect
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Min, Max
import datetime
from .models import HistorialApuesta, OddsSnapshot, AutoBetConfig, MarketFilterConfig
from .services import sync_historial
from .forms import AutoBetConfigForm, MarketFilterConfigForm


def _side_of(seleccion):
    """Clasifica la selección en Over / Under / Sí / No / Otros."""
    s = (seleccion or '').strip().lower()
    if not s:
        return 'Otros'
    if s.startswith('más') or s.startswith('mas'):
        return 'Over'
    if s.startswith('menos'):
        return 'Under'
    if s in ('sí', 'si'):
        return 'Sí'
    if s == 'no':
        return 'No'
    return 'Otros'


_SIDE_CLASS = {'Over': 'over', 'Under': 'under', 'Sí': 'si', 'No': 'no', 'Otros': 'otros'}


def _analisis_grupo(qs):
    """Calcula métricas agregadas para un queryset dado."""
    total = qs.count()
    won = qs.filter(bet_status='WON').count()
    lost = qs.filter(bet_status='LOST').count()
    opened = qs.filter(bet_status='OPEN').count()
    void = qs.exclude(bet_status__in=['WON', 'LOST', 'OPEN']).count()

    settled = won + lost
    win_rate = (won / settled * 100) if settled else 0.0

    stake_total = qs.aggregate(s=Sum('stake'))['s'] or 0
    stake_cop = stake_total / 1000.0

    # Stake desglose: abierto vs asentado
    open_qs = qs.filter(bet_status='OPEN')
    stake_open = open_qs.aggregate(s=Sum('stake'))['s'] or 0
    stake_open_cop = stake_open / 1000.0

    settled_qs = qs.filter(bet_status__in=['WON', 'LOST'])
    settled_stake = settled_qs.aggregate(s=Sum('stake'))['s'] or 0
    settled_payout = settled_qs.aggregate(p=Sum('payout'))['p'] or 0
    realized_pnl = (settled_payout - settled_stake) / 1000.0
    roi = (realized_pnl / (settled_stake / 1000.0) * 100) if settled_stake else 0.0
    pending_stake_cop = stake_open_cop

    # Cuota jugada
    cuota_agg = qs.exclude(played_odds__isnull=True).aggregate(
        avg=Avg('played_odds'), mn=Min('played_odds'), mx=Max('played_odds'))
    cuota_promedio = round(cuota_agg['avg'] or 0, 2)
    cuota_min = round(cuota_agg['mn'] or 0, 2)
    cuota_max = round(cuota_agg['mx'] or 0, 2)

    # CLV
    clv_qs = qs.exclude(clv__isnull=True)
    clv_count = clv_qs.count()
    clv_avg = clv_qs.aggregate(a=Avg('clv'))['a'] if clv_count else None
    clv_pos = clv_qs.filter(clv__gt=0).count()
    clv_pos_pct = round(clv_pos / clv_count * 100, 1) if clv_count else 0.0

    # Por mercado y lado (Over/Under)
    _agg = {}
    for a in qs:
        m = a.mercado or 'Sin mercado'
        lado = _side_of(a.seleccion)
        d = _agg.setdefault((m, lado), {'n': 0, 'won': 0, 'lost': 0, 'st': 0, 'pay': 0})
        d['n'] += 1
        if a.bet_status == 'WON':
            d['won'] += 1
            d['st'] += a.stake or 0
            d['pay'] += a.payout or 0
        elif a.bet_status == 'LOST':
            d['lost'] += 1
            d['st'] += a.stake or 0
            d['pay'] += a.payout or 0

    por_mercado = []
    for (m, lado), d in _agg.items():
        w = d['won']
        l = d['lost']
        s = w + l
        st = d['st']
        pay = d['pay']
        pnl = (pay - st) / 1000.0
        m_roi = (pnl / (st / 1000.0) * 100) if st else 0.0
        por_mercado.append({
            'mercado': m,
            'lado': lado,
            'side_class': _SIDE_CLASS.get(lado, 'otros'),
            'label': f"{m} — {lado}",
            'n': d['n'], 'won': w, 'lost': l,
            'settled': s,
            'win_rate': round((w / s * 100) if s else 0.0, 1),
            'stake_cop': round(st / 1000.0, 0),
            'pnl': round(pnl, 0),
            'roi': round(m_roi, 1),
        })
    por_mercado.sort(key=lambda x: x['pnl'], reverse=True)

    # P&L timeline
    pnl_timeline = []
    cum = 0.0
    for a in settled_qs.order_by('placed_date'):
        cum += a.profit_cop
        pnl_timeline.append({
            'label': a.placed_date.strftime('%d/%m %H:%M'),
            'cum': round(cum, 0),
        })

    # CLV por mercado y lado (Over/Under)
    _clv_agg = {}
    for a in clv_qs:
        m = a.mercado or 'Sin mercado'
        lado = _side_of(a.seleccion)
        d = _clv_agg.setdefault((m, lado), {'n': 0, 'sum': 0.0, 'pos': 0})
        d['n'] += 1
        clv = a.clv or 0
        d['sum'] += clv
        if a.clv and a.clv > 0:
            d['pos'] += 1

    clv_por_mercado = []
    for (m, lado), d in _clv_agg.items():
        clv_por_mercado.append({
            'mercado': m,
            'lado': lado,
            'label': f"{m} — {lado}",
            'n': d['n'],
            'clv_avg': round(d['sum'] / d['n'], 2),
            'clv_pos_pct': round(d['pos'] / d['n'] * 100, 1) if d['n'] else 0,
        })
    clv_por_mercado.sort(key=lambda x: x['clv_avg'], reverse=True)

    return {
        'total': total, 'won': won, 'lost': lost, 'opened': opened, 'void': void,
        'settled': settled, 'win_rate': round(win_rate, 1),
        'stake_cop': round(stake_cop, 2),
        'stake_open_cop': round(stake_open_cop, 2),
        'pending_stake_cop': round(pending_stake_cop, 2),
        'realized_pnl': round(realized_pnl, 2),
        'roi': round(roi, 1),
        'cuota_promedio': cuota_promedio, 'cuota_min': cuota_min, 'cuota_max': cuota_max,
        'clv_count': clv_count,
        'clv_avg': round(clv_avg, 2) if clv_avg is not None else None,
        'clv_pos_pct': clv_pos_pct,
        'por_mercado': por_mercado,
        'pnl_timeline': pnl_timeline,
        'clv_por_mercado': clv_por_mercado,
    }


def _analisis(usuario=None, desde=None, hasta=None):
    """Calcula métricas para Todos / Sistema / Manual (scoped por usuario + fechas)."""
    qs_all = HistorialApuesta.objects.all()
    if usuario is not None:
        qs_all = qs_all.filter(usuario=usuario)
    if desde:
        qs_all = qs_all.filter(placed_date__date__gte=desde)
    if hasta:
        qs_all = qs_all.filter(placed_date__date__lte=hasta)
    qs_sys = qs_all.filter(is_system=True)
    qs_man = qs_all.filter(is_system=False)
    return {
        'todos': _analisis_grupo(qs_all),
        'sistema': _analisis_grupo(qs_sys),
        'manual': _analisis_grupo(qs_man),
    }


def _parse_date(s):
    """Parsea YYYY-MM-DD; devuelve None si vacío/inválido."""
    if not s:
        return None
    try:
        return datetime.date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


@login_required
def historial(request):
    filtro = request.GET.get('filtro', 'todos')  # todos / sistema / manual
    desde = _parse_date(request.GET.get('desde'))
    hasta = _parse_date(request.GET.get('hasta'))

    apuestas = HistorialApuesta.objects.filter(usuario=request.user).order_by('-placed_date')
    if desde:
        apuestas = apuestas.filter(placed_date__date__gte=desde)
    if hasta:
        apuestas = apuestas.filter(placed_date__date__lte=hasta)
    if filtro == 'sistema':
        apuestas = apuestas.filter(is_system=True)
    elif filtro == 'manual':
        apuestas = apuestas.filter(is_system=False)

    stats = _analisis(usuario=request.user, desde=desde, hasta=hasta)
    stats_active = stats.get(filtro, stats['todos'])

    return render(request, 'auto_betting/historial.html', {
        'apuestas': apuestas,
        'stats': stats,
        'stats_active': stats_active,
        'filtro': filtro,
        'desde': desde.isoformat() if desde else '',
        'hasta': hasta.isoformat() if hasta else '',
    })


@csrf_exempt
@require_POST
@login_required
def historial_sync(request):
    """Dispara la sincronización del historial desde BetPlay (botón actualizar)."""
    result = sync_historial('2026-08-01', usuario=request.user)
    if result.get('error'):
        msg = result['error']
        if msg == 'No hay AutoBetConfig':
            msg = 'Aún no has configurado tus credenciales de BetPlay. Ve a ⚙️ Config BetPlay en el menú.'
        return JsonResponse({'ok': False, 'error': msg}, status=200)
    return JsonResponse({'ok': True, **result})


@login_required
def configuracion(request):
    """Cada usuario ve/edita SU propia configuración de auto-apuestas (BetPlay)."""
    config, created = AutoBetConfig.objects.get_or_create(usuario=request.user)

    if request.method == 'POST':
        form = AutoBetConfigForm(request.POST, instance=config)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Configuración de BetPlay guardada.')
            return redirect('auto_betting:configuracion')
    else:
        form = AutoBetConfigForm(instance=config)

    return render(request, 'auto_betting/configuracion.html', {
        'form': form,
        'config': config,
    })


def _es_admin_principal(user):
    """Solo el usuario admin@predicta.com.co (superusuario) puede tocar los
    umbrales globales por submercado. admin2 y cualquier otro usuario NO."""
    return user.is_authenticated and user.is_superuser


@login_required
@user_passes_test(_es_admin_principal, login_url='auto_betting:configuracion')
def configuracion_umbrales(request):
    """Config GLOBAL de umbrales por submercado (P mínima/confianza por
    mercado+lado). Una sola fila para todo el sistema; solo el admin la edita.
    """
    cfg = MarketFilterConfig.get_solo()

    if request.method == 'POST':
        form = MarketFilterConfigForm(request.POST, instance=cfg)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.actualizado_por = request.user.email
            obj.save()
            messages.success(request, '✅ Umbrales por submercado actualizados (aplican a todos los usuarios).')
            return redirect('auto_betting:configuracion_umbrales')
    else:
        form = MarketFilterConfigForm(instance=cfg)

    # (titulo, prefijo_submercado, etiqueta_lado)
    grupos = [
        ('Goles', [('goals_over', 'Over'), ('goals_under', 'Under')]),
        ('Córners', [('corners_over', 'Over'), ('corners_under', 'Under')]),
        ('Tiros a puerta', [('shots_on_target_over', 'Over'), ('shots_on_target_under', 'Under')]),
        ('Ambos marcan (BTTS)', [('btts_si', 'Sí'), ('btts_no', 'No')]),
    ]
    filas = []
    for titulo, campos in grupos:
        subfilas = []
        for pref, lado in campos:
            subfilas.append({
                'lado': lado,
                'enabled': form[f'{pref}_enabled'],
                'p': form[f'{pref}_min_p'],
                'conf': form[f'{pref}_min_confidence'],
                'ev': form[f'{pref}_min_ev'],
                'cuota': form[f'{pref}_min_cuota'],
            })
        filas.append({'titulo': titulo, 'subfilas': subfilas})

    globales = [
        {'field': form['cuota_minima_global'], 'label': 'Cuota mínima global',
         'help': '⚠️ Ya no se aplica (25-Ago-2026): la cuota mínima la define cada usuario en su propia config. Campo conservado por compatibilidad.'},
        {'field': form['stop_loss_diario_cop'], 'label': 'Stop-loss diario (COP)',
         'help': 'Si el P&L del día (solo sistema) baja de esto, se detiene el auto-betting. 0 = off.'},
        {'field': form['max_exposicion_evento_cop'], 'label': 'Máx. exposición por evento (COP)',
         'help': 'Tope de stake combinado (todas las cuentas) por evento+mercado. 0 = off.'},
        {'field': form['calib_cap'], 'label': 'Cap de calibración',
         'help': 'Cap duro de probabilidad calibrada. Auditoría: anti-señal arriba de 0.60.'},
    ]

    return render(request, 'auto_betting/configuracion_umbrales.html', {
        'form': form,
        'cfg': cfg,
        'filas': filas,
        'globales': globales,
    })
