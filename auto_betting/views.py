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
from django.db.models import Sum, Count, Avg, Min, Max, Q
from django.conf import settings
import datetime
import json
import os
import re
import subprocess
from urllib.parse import urlencode
from .models import (HistorialApuesta, OddsSnapshot, AutoBetConfig,
                     MarketFilterConfig, AutoBet, LlmRealConfig)
from .services import sync_historial
from .forms import AutoBetConfigForm, MarketFilterConfigForm, LlmRealConfigForm


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


# Deporte (termKey de Kambi) → (icono, etiqueta en español) para los filtros.
SPORT_DISPLAY = {
    'FOOTBALL': ('⚽', 'Fútbol'),
    'BASKETBALL': ('🏀', 'Baloncesto'),
    'BASEBALL': ('⚾', 'Béisbol'),
    'TENNIS': ('🎾', 'Tenis'),
    'AMERICAN_FOOTBALL': ('🏈', 'Fútbol americano'),
    'ICE_HOCKEY': ('🏒', 'Hockey hielo'),
    'HANDBALL': ('🤾', 'Balonmano'),
    'VOLLEYBALL': ('🏐', 'Voleibol'),
    'BOXING': ('🥊', 'Boxeo'),
    'MOTORSPORT': ('🏎️', 'Automovilismo'),
    'ESPORTS': ('🎮', 'eSports'),
}
_SPORT_ORDER = {k: i for i, k in enumerate(SPORT_DISPLAY)}


def _sport_meta(sport):
    """(icono, etiqueta) de un deporte; soporta términos nuevos sin tocar el código."""
    icon, label = SPORT_DISPLAY.get(sport, ('🎯', (sport or '').replace('_', ' ').title()))
    return icon, label


def _analisis_grupo(qs, fecha_partido=False):
    """Calcula métricas agregadas para un queryset dado.

    `fecha_partido=True` (hay filtro de fechas activo): el P&L acumulado se
    ordena y etiqueta por fecha del PARTIDO, coherente con el resto del filtro.
    """
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
    clv_qs = qs.filter(closing_odds__isnull=False)
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
    if fecha_partido:
        ordenados = settled_qs.order_by('event_start_date', 'placed_date')
    else:
        ordenados = settled_qs.order_by('placed_date')
    for a in ordenados:
        cum += a.profit_cop
        base = (a.event_start_date or a.placed_date) if fecha_partido else a.placed_date
        pnl_timeline.append({
            'label': base.strftime('%d/%m %H:%M'),
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


def _filtrar_por_fecha_partido(qs, desde=None, hasta=None):
    """Filtra apuestas por la FECHA DEL PARTIDO (event_start_date).

    El rango de fechas de la UI es el del partido, no el de colocación. Si una
    apuesta no tiene fecha de partido se usa placed_date como respaldo.
    """
    if desde:
        qs = qs.filter(
            Q(event_start_date__date__gte=desde)
            | Q(event_start_date__isnull=True, placed_date__date__gte=desde)
        )
    if hasta:
        qs = qs.filter(
            Q(event_start_date__date__lte=hasta)
            | Q(event_start_date__isnull=True, placed_date__date__lte=hasta)
        )
    return qs


def _analisis(usuario=None, desde=None, hasta=None, sport=None):
    """Calcula métricas para Todos / Sistema / Manual (usuario + fecha del partido + deporte)."""
    qs_all = HistorialApuesta.objects.all()
    if usuario is not None:
        qs_all = qs_all.filter(usuario=usuario)
    # 2026-10-31: los parleys (combinadas, coupon_legs>1) se excluyen de esta
    # página; viven en /parleys/. Así las tarjetas cuentan solo apuestas simples.
    qs_all = qs_all.exclude(coupon_legs__gt=1)
    qs_all = _filtrar_por_fecha_partido(qs_all, desde, hasta)
    if sport:
        qs_all = qs_all.filter(sport=sport)
    qs_sys = qs_all.filter(is_system=True)
    qs_man = qs_all.filter(is_system=False)
    por_fecha_partido = bool(desde or hasta)
    return {
        'todos': _analisis_grupo(qs_all, fecha_partido=por_fecha_partido),
        'sistema': _analisis_grupo(qs_sys, fecha_partido=por_fecha_partido),
        'manual': _analisis_grupo(qs_man, fecha_partido=por_fecha_partido),
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
    if filtro not in ('todos', 'sistema', 'manual'):
        filtro = 'todos'
    desde = _parse_date(request.GET.get('desde'))
    hasta = _parse_date(request.GET.get('hasta'))
    # Un rango abierto ("desde" sin "hasta") se cierra HOY: las fechas filtran
    # por fecha de PARTIDO y un "desde" abierto colaba partidos futuros
    # (p. ej. NBA del 21-oct al filtrar "hoy"). Si el "desde" es futuro se
    # mantiene abierto para poder mirar días por venir.
    if desde and hasta is None:
        from django.utils import timezone as _tz_hoy
        hoy_local = _tz_hoy.localdate()
        if desde <= hoy_local:
            hasta = hoy_local
    # Deporte (sport = termKey de Kambi, ej. FOOTBALL/BASKETBALL/BASEBALL).
    # Se acepta cualquier término válido —los chips se generan desde los datos—
    # y se descarta cualquier valor con formato inesperado.
    sport = (request.GET.get('sport') or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9_]{1,50}', sport):
        sport = ''

    apuestas = HistorialApuesta.objects.filter(usuario=request.user).order_by('-placed_date')
    # 2026-10-31: sin parleys aquí (viven en /parleys/); solo apuestas simples.
    apuestas = apuestas.exclude(coupon_legs__gt=1)
    apuestas = _filtrar_por_fecha_partido(apuestas, desde, hasta)
    if sport:
        apuestas = apuestas.filter(sport=sport)
    if filtro == 'sistema':
        apuestas = apuestas.filter(is_system=True)
    elif filtro == 'manual':
        apuestas = apuestas.filter(is_system=False)

    # Anotar probabilidad, confianza e IA (AutoBet) por coupon_ref
    from django.db.models import OuterRef, Subquery
    prob_sub = AutoBet.objects.filter(
        usuario=OuterRef('usuario'), coupon_ref=OuterRef('coupon_ref')
    ).values('predicta_prob')[:1]
    conf_sub = AutoBet.objects.filter(
        usuario=OuterRef('usuario'), coupon_ref=OuterRef('coupon_ref')
    ).values('confidence')[:1]
    ia_sub = AutoBet.objects.filter(
        usuario=OuterRef('usuario'), coupon_ref=OuterRef('coupon_ref')
    ).values('llm_verdict')[:1]
    ia_conf_sub = AutoBet.objects.filter(
        usuario=OuterRef('usuario'), coupon_ref=OuterRef('coupon_ref')
    ).values('llm_confidence')[:1]
    ia_reason_sub = AutoBet.objects.filter(
        usuario=OuterRef('usuario'), coupon_ref=OuterRef('coupon_ref')
    ).values('llm_reason')[:1]
    ia_model_sub = AutoBet.objects.filter(
        usuario=OuterRef('usuario'), coupon_ref=OuterRef('coupon_ref')
    ).values('llm_model')[:1]
    apuestas = apuestas.annotate(
        pred_prob=Subquery(prob_sub),
        pred_conf=Subquery(conf_sub),
        ia_verdict=Subquery(ia_sub),
        ia_conf=Subquery(ia_conf_sub),
        ia_reason=Subquery(ia_reason_sub),
        ia_model=Subquery(ia_model_sub),
    )

    # Orden del listado:
    #  - Sin filtro de fechas: "próximos primero" (el más cercano a jugarse
    #    arriba), luego el resto de futuros por cercanía; después los ya
    #    jugados del más reciente al más antiguo. Sin fecha de partido → al final.
    #  - Con filtro de fechas (desde/hasta): cronológico ascendente por fecha
    #    de partido, para que los partidos del rango se vean juntos y en orden.
    from django.utils import timezone as _tz
    _now = _tz.now()

    def _orden_partido(a):
        if not a.event_start_date:
            return (2, 0.0)
        ts = a.event_start_date.timestamp()
        if a.event_start_date > _now:
            return (0, ts)
        return (1, -ts)

    def _orden_cronologico(a):
        base = a.event_start_date or a.placed_date
        if not base:
            return (1, 0.0)
        return (0, base.timestamp())

    apuestas = sorted(apuestas, key=_orden_cronologico if (desde or hasta) else _orden_partido)

    stats = _analisis(usuario=request.user, desde=desde, hasta=hasta, sport=sport)
    stats_active = stats.get(filtro, stats['todos'])

    # ── Filtros: URLs construidas en la vista para preservar todo el estado ──
    # (tipo + deporte + fechas) y que el template solo pinte opciones.
    desde_iso = desde.isoformat() if desde else ''
    hasta_iso = hasta.isoformat() if hasta else ''

    def _url(**overrides):
        params = {'filtro': filtro, 'sport': sport, 'desde': desde_iso, 'hasta': hasta_iso}
        params.update(overrides)
        return '?' + urlencode([(k, v) for k, v in params.items() if v])

    tipo_tabs = [{
        'key': key, 'icon': icon, 'label': label,
        'count': stats[key]['total'], 'url': _url(filtro=key),
    } for key, icon, label in (
        ('todos', '📊', 'Todos'), ('sistema', '🤖', 'Sistema'), ('manual', '✋', 'Manual'),
    )]

    # Conteos por deporte dentro del tipo + fechas activos (cross-filter), para
    # que cada chip muestre exactamente lo que verías al pulsarlo.
    sport_qs = HistorialApuesta.objects.filter(usuario=request.user)
    sport_qs = sport_qs.exclude(coupon_legs__gt=1)
    sport_qs = _filtrar_por_fecha_partido(sport_qs, desde, hasta)
    if filtro == 'sistema':
        sport_qs = sport_qs.filter(is_system=True)
    elif filtro == 'manual':
        sport_qs = sport_qs.filter(is_system=False)
    conteos = {r['sport']: r['n'] for r in
               sport_qs.exclude(sport='').values('sport').annotate(n=Count('id'))}
    sport_options = []
    for value in sorted(conteos, key=lambda s: (_SPORT_ORDER.get(s, 99), s)):
        icon, label = _sport_meta(value)
        sport_options.append({
            'value': value, 'icon': icon, 'label': label, 'count': conteos[value],
            'url': _url(sport=value), 'active': value == sport,
        })

    # Movimiento del balance real (capital paralelo) para el gráfico superior.
    from capital.services import (
        balance_filtrado, balance_timeline, crecimiento_capital,
    )
    balance_tl = balance_timeline(request.user, desde=desde, hasta=hasta)

    # Balance de la CUENTA acotado a los filtros activos (tipo, deporte y
    # fechas): alimenta el gráfico "Evolución del balance de la cuenta".
    balance_cuenta = balance_filtrado(
        request.user, desde=desde, hasta=hasta, sport=sport, tipo=filtro,
    )

    # Crecimiento del capital (libre + en juego) dentro del rango del filtro:
    # "ROI de capital" del rango, adicional al ROI sobre lo apostado.
    crec_capital = crecimiento_capital(request.user, desde=desde, hasta=hasta)

    return render(request, 'auto_betting/historial.html', {
        'apuestas': apuestas,
        'stats': stats,
        'stats_active': stats_active,
        'balance_timeline': balance_tl,
        'balance_cuenta': balance_cuenta,
        'crecimiento_capital': crec_capital,
        'filtro': filtro,
        'desde': desde_iso,
        'hasta': hasta_iso,
        'sport': sport,
        'sport_active_label': _sport_meta(sport)[1] if sport else '',
        'tipo_tabs': tipo_tabs,
        'sport_options': sport_options,
        'sport_todos': {'count': sport_qs.count(), 'url': _url(sport=None),
                        'active': not sport},
        'hay_filtros': bool(sport or desde or hasta or filtro != 'todos'),
        'clear_url': _url(filtro='todos', sport=None, desde=None, hasta=None),
        'clear_dates_url': _url(desde=None, hasta=None),
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
    # El mismo botón liquida también los parleys del usuario (motor aparte).
    try:
        from parley_engine.services import sync_user_history
        result['parleys'] = sync_user_history(request.user)
    except Exception as exc:
        result['parleys_error'] = f'{type(exc).__name__}: {exc}'
    return JsonResponse({'ok': True, **result})


@login_required
def configuracion(request):
    """Cada usuario ve/edita SU propia configuración de auto-apuestas (BetPlay)
    y su modo de gestión de capital (stake fijo vs % compuesto)."""
    from capital.forms import CapitalConfigForm
    from capital.models import CapitalAjuste
    from capital.services import bankroll_cop, get_config, resolve_stake
    from django.utils import timezone

    config, created = AutoBetConfig.objects.get_or_create(usuario=request.user)
    cap_config = get_config(request.user)

    if request.method == 'POST':
        form = AutoBetConfigForm(request.POST, instance=config)
        cap_form = CapitalConfigForm(request.POST, instance=cap_config)
        if form.is_valid() and cap_form.is_valid():
            form.save()
            _guardar_capital(request, cap_form)
            _avisar_ajustes_antiblqueo(request, form, cap_form)
            messages.success(request, '✅ Configuración de BetPlay y de capital guardada.')
            return redirect('auto_betting:configuracion')
    else:
        form = AutoBetConfigForm(instance=config)
        cap_form = CapitalConfigForm(instance=cap_config)
        # El stake se muestra en COP (la BD guarda unidades Kambi ×1000).
        form.initial['stake'] = (
            config.stake // 1000 if config.stake % 1000 == 0
            else round(config.stake / 1000, 2)
        )
        # El campo de balance muestra el balance paralelo actual (referencia),
        # no el ancla original: así el usuario ve el número "vivo".
        actual = bankroll_cop(request.user)
        if actual is not None:
            cap_form.initial['balance_inicial'] = actual

    balance = bankroll_cop(request.user)
    stake_kambi, motivo = resolve_stake(config)

    return render(request, 'auto_betting/configuracion.html', {
        'form': form,
        'cap_form': cap_form,
        'config': config,
        'cap_config': cap_config,
        'balance': balance,
        'stake_resuelto_cop': (stake_kambi // 1000) if stake_kambi else None,
        'stake_motivo': motivo,
    })


def _avisar_ajustes_antiblqueo(request, form, cap_form):
    """
    Política anti-bloqueo (2026-09-02): si el sistema normalizó un valor a
    número redondo, se lo informa al usuario (transparencia sobre el stake
    que realmente se usará).
    """
    def _fmt(v):
        return f'{v:,}'.replace(',', '.')

    ajustes = []
    aj = getattr(form, '_stake_ajustado', None)
    if aj:
        ajustes.append(f'stake fijo {_fmt(aj[0])} → {_fmt(aj[1])} COP')
    aj = getattr(cap_form, '_min_ajustado', None)
    if aj:
        ajustes.append(f'stake mínimo {_fmt(aj[0])} → {_fmt(aj[1])} COP')
    aj = getattr(cap_form, '_max_ajustado', None)
    if aj:
        ajustes.append(f'stake máximo {_fmt(aj[0])} → {_fmt(aj[1])} COP')
    if ajustes:
        messages.info(
            request,
            '💡 Ajustado a números redondos (política anti-bloqueo): '
            + '; '.join(ajustes) + '.',
        )


def _guardar_capital(request, cap_form):
    """
    Persiste la CapitalConfig gestionando balance_inicial/ancla manualmente:
    - Alta del modo compuesto: fija el balance declarado y el ancla (momento
      exacto desde el que cuenta el histórico para el balance paralelo).
    - Re-declaración de balance (compuesto ya activo): se toma como
      RECONCILIACIÓN → CapitalAjuste por la diferencia, sin tocar el ancla.
    - Modo fijo: conserva ancla/balance existentes (el balance paralelo sigue
      vivo aunque el stake vuelva a ser fijo).
    """
    from django.utils import timezone
    from capital.models import CapitalAjuste, CapitalConfig
    from capital.services import bankroll_cop

    prev = CapitalConfig.objects.filter(pk=cap_form.instance.pk).first()
    old_ancla = prev.ancla if prev else None
    old_balance = prev.balance_inicial if prev else None

    cap = cap_form.save(commit=False)
    modo = cap_form.cleaned_data.get('modo')
    balance_input = cap_form.cleaned_data.get('balance_inicial')

    if modo == CapitalConfig.MODO_COMPUESTO:
        if old_ancla is None:
            # Primera activación: anclar balance + momento.
            cap.ancla = timezone.now()
            cap.balance_inicial = int(balance_input)
            # Snapshot de apuestas OPEN: su payout completo se acreditará al
            # asentar (su stake ya estaba descontado del balance declarado).
            from capital.services import snapshot_legadas
            snapshot_legadas(request.user)
        else:
            # Ya activo: el ancla/balance declarado son inmutables.
            cap.ancla = old_ancla
            cap.balance_inicial = old_balance
            if balance_input and balance_input > 0:
                actual = bankroll_cop(request.user)
                diff = int(balance_input) - (actual or 0)
                if diff != 0:
                    CapitalAjuste.objects.create(
                        usuario=request.user,
                        monto_cop=diff,
                        motivo='Reconciliación desde configuración',
                    )
                    messages.info(
                        request,
                        f'💰 Balance reconciliado: ajuste de {diff:+,} COP registrado.',
                    )
    else:
        # FIJO: conservar el ancla/balance declarado (si existía).
        cap.balance_inicial = old_balance
        cap.ancla = old_ancla

    cap.save()


def _es_admin_principal(user):
    """Solo el usuario admin@predicta.com.co (superusuario) puede tocar los
    umbrales globales por submercado. admin2 y cualquier otro usuario NO."""
    return user.is_authenticated and user.is_superuser


@login_required
@user_passes_test(_es_admin_principal, login_url='auto_betting:configuracion')
def configuracion_v2(request):
    """Filtro V2: regla de apuestas en dinero real (liga × mercado × día).
    Solo deja pasar combinaciones con ROI positivo observado. Editable por admin.
    """
    from auto_betting.v2_filter import parse_rules, DEFAULT_RULES
    from auto_betting.models import BettingFilterV2

    obj = BettingFilterV2.get_solo()
    preview = None
    errores = []

    if request.method == 'POST':
        activo = request.POST.get('activo') == 'on'
        reglas = request.POST.get('reglas', '')
        parsed, errores = parse_rules(reglas)
        if not errores:
            obj.activo = activo
            obj.reglas = reglas
            obj.actualizado_por = request.user.email
            obj.save()
            messages.success(
                request,
                f'✅ Filtro V2 guardado: {"ON" if activo else "OFF"} · '
                f'{len(parsed)} reglas activas.')
            return redirect('auto_betting:configuracion_v2')
        else:
            messages.error(request, f'⚠️ {len(errores)} error(es) en las reglas; no se guardó.')
            preview = parsed
    else:
        reglas = obj.reglas or DEFAULT_RULES

    parsed, errores2 = parse_rules(reglas)
    return render(request, 'auto_betting/configuracion_v2.html', {
        'obj': obj,
        'reglas': reglas,
        'n_reglas': len(parsed),
        'errores': errores or errores2,
    })


@login_required
@user_passes_test(_es_admin_principal, login_url='auto_betting:configuracion')
def configuracion_umbrales(request):
    """Config GLOBAL de umbrales por submercado (P mínima/confianza por
    mercado+lado). Una sola fila para todo el sistema; solo el admin la edita.
    """
    cfg = MarketFilterConfig.get_solo()
    llm_cfg = LlmRealConfig.get_solo()

    if request.method == 'POST' and 'guardar_llm' in request.POST:
        # Formulario de la OPINIÓN IA de apuestas reales.
        llm_form = LlmRealConfigForm(request.POST, instance=llm_cfg)
        if llm_form.is_valid():
            obj = llm_form.save(commit=False)
            obj.actualizado_por = request.user.email
            obj.save()
            key = llm_form.cleaned_data.get('api_key') or ''
            if key:
                from auto_betting.llm_validator import guardar_api_key
                guardar_api_key(key)
                messages.success(request, '✅ Config IA guardada y API key actualizada.')
            else:
                messages.success(request, '✅ Config IA de apuestas reales guardada.')
            return redirect('auto_betting:configuracion_umbrales')
        form = MarketFilterConfigForm(instance=cfg)
    elif request.method == 'POST':
        form = MarketFilterConfigForm(request.POST, instance=cfg)
        llm_form = LlmRealConfigForm(instance=llm_cfg)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.actualizado_por = request.user.email
            obj.save()
            messages.success(request, '✅ Umbrales por submercado actualizados (aplican a todos los usuarios).')
            return redirect('auto_betting:configuracion_umbrales')
    else:
        form = MarketFilterConfigForm(instance=cfg)
        llm_form = LlmRealConfigForm(instance=llm_cfg)

    from auto_betting.llm_validator import api_key_real
    llm_ctx = {
        'llm_form': llm_form,
        'llm_cfg': llm_cfg,
        'llm_api_key_configurada': bool(api_key_real()),
        'llm_modelo_efectivo': llm_cfg.modelo or getattr(settings, 'LLM_MODEL_REAL', ''),
    }

    # (titulo, prefijo_submercado, etiqueta_lado)
    grupos = [
        ('Goles', [('goals_over', 'Over'), ('goals_under', 'Under')]),
        ('Córners', [('corners_over', 'Over'), ('corners_under', 'Under')]),
        ('Tiros a puerta', [('shots_on_target_over', 'Over'), ('shots_on_target_under', 'Under')]),
        ('Remates totales', [('remates_over', 'Over'), ('remates_under', 'Under')]),
        ('Ambos marcan (BTTS)', [('btts_si', 'Sí'), ('btts_no', 'No')]),
        ('Resultado Final — x12_v2 (migrado del paper, 03-Oct-2026)', [('x12', '1X2')]),
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

    # Filtro por línea (Fix 2026-08-31): solo tiros a puerta over/under.
    # 0 = sin tope en ese lado.
    line_filters = [
        {'field': form['shots_on_target_under_min_line'], 'label': 'Tiros Under — línea mínima',
         'help': 'Bloquea Under de línea menor a este valor. 9.5 elimina el sangrador de under 7.5/8.5 (WR 27%/40%). 0 = sin filtro.'},
        {'field': form['shots_on_target_under_max_line'], 'label': 'Tiros Under — línea máxima',
         'help': 'Tope superior para Under. 0 = sin tope.'},
        {'field': form['shots_on_target_over_min_line'], 'label': 'Tiros Over — línea mínima',
         'help': 'Bloquea Over de línea menor a este valor. 0 = sin filtro.'},
        {'field': form['shots_on_target_over_max_line'], 'label': 'Tiros Over — línea máxima',
         'help': 'Tope superior para Over. 0 = sin tope.'},
        {'field': form['remates_under_min_line'], 'label': 'Remates Under — línea mínima',
         'help': 'Bloquea Under de línea menor a este valor. 0 = sin filtro.'},
        {'field': form['remates_under_max_line'], 'label': 'Remates Under — línea máxima',
         'help': 'Tope superior para Under. 0 = sin tope.'},
        {'field': form['remates_over_min_line'], 'label': 'Remates Over — línea mínima',
         'help': 'Bloquea Over de línea menor a este valor. 0 = sin filtro.'},
        {'field': form['remates_over_max_line'], 'label': 'Remates Over — línea máxima',
         'help': 'Tope superior para Over. 0 = sin tope.'},
    ]

    ctx = {
        'form': form,
        'cfg': cfg,
        'filas': filas,
        'globales': globales,
        'line_filters': line_filters,
    }
    ctx.update(llm_ctx)
    return render(request, 'auto_betting/configuracion_umbrales.html', ctx)


@login_required
@user_passes_test(_es_admin_principal, login_url='auto_betting:configuracion')
def llm_modelos(request):
    """Lista en vivo de modelos del proveedor LLM (para el selector de umbrales).

    Usa la API key del .env (nunca se expone al navegador) y el base_url de la
    configuración. Devuelve {'ok', 'modelos', 'error', 'actual'} — con el error
    del proveedor tal cual para mostrarlo en la página.
    """
    from auto_betting.llm_validator import api_key_real, listar_modelos
    cfg = LlmRealConfig.get_solo()
    modelos, error = listar_modelos(cfg.base_url, api_key=api_key_real())
    return JsonResponse({
        'ok': error is None,
        'modelos': modelos,
        'error': error,
        'actual': cfg.modelo or getattr(settings, 'LLM_MODEL_REAL', ''),
    })


@login_required
@user_passes_test(_es_admin_principal, login_url='auto_betting:configuracion')
@require_POST
def run_manual(request):
    """
    Botón del panel superusuario (2026-08-29): ejecuta el auto-betting
    manualmente EN SEGUNDO PLANO para TODAS las cuentas activas
    (todas las AutoBetConfig con activo=True), igual que el cron.

    - Usa el mismo comando y settings del cron (`run_auto_bets` sin --email,
      DJANGO_SETTINGS_MODULE=betting_bot.settings).
    - La salida se anexa a logs/auto_betting.log.
    - Guard anti-concurrencia: si ya hay una corrida en curso (cron o manual),
      no lanza otra (SQLite es mono-escritor).

    Semántica: NO repite apuestas ya hechas (dedup por usuario+evento+mercado
    en run_auto_bets); SÍ coloca nuevas apuestas que pasen filtros para cada
    usuario, hasta su límite diario (max_apuestas_diarias - ya colocadas hoy).
    """
    try:
        check = subprocess.run(
            ['pgrep', '-f', 'manage.py run_auto_bets'],
            capture_output=True, text=True, timeout=10,
        )
        if check.returncode == 0:
            return JsonResponse({
                'ok': False,
                'error': 'Ya hay una ejecución de auto_betting en curso (cron o manual). Espera a que termine e inténtalo de nuevo.',
            })
    except Exception:
        pass  # pgrep no disponible: seguimos (riesgo bajo, dedup protege)

    cmd = [
        str(settings.BASE_DIR / 'venv' / 'bin' / 'python'),
        'manage.py', 'run_auto_bets',
        # Sin --email: ejecuta TODAS las AutoBetConfig activas (igual que el cron).
    ]
    env = dict(os.environ)
    # Mismo settings del cron: evita heredar config.settings.production
    # de /etc/environment (fix documentado en SOUL.md §10).
    env['DJANGO_SETTINGS_MODULE'] = 'betting_bot.settings'

    log_path = settings.BASE_DIR / 'logs' / 'auto_betting.log'
    try:
        with open(log_path, 'a', encoding='utf-8') as log_f:
            subprocess.Popen(
                cmd,
                cwd=str(settings.BASE_DIR),
                env=env,
                stdout=log_f,
                stderr=subprocess.STDOUT,
                start_new_session=True,  # sobrevive aunque gunicorn se reinicie
            )
    except Exception as e:
        return JsonResponse({'ok': False, 'error': f'No se pudo lanzar el proceso: {e}'})

    return JsonResponse({
        'ok': True,
        'msg': 'Auto-betting lanzado en segundo plano para TODAS las cuentas '
               'activas (admin, admin2, carlos…). Tarda ~3-8 min. Revisa el '
               'resultado en el historial de apuestas BetPlay o en '
               'logs/auto_betting.log.',
    })


# ─────────────────────────────────────────────────────────────────────────────
# Horarios de Cron — gestión desde la web
# ─────────────────────────────────────────────────────────────────────────────

from .models import CronSchedule


@login_required
@user_passes_test(_es_admin_principal, login_url='auto_betting:configuracion')
def cron_schedules(request):
    """Lista y edita los horarios del pipeline de auto-betting.

    GET  → muestra la tabla con todos los CronSchedule.
    POST → actualiza hora/minuto/enabled de cada tarea.
    """
    if request.method == 'POST':
        # Solo actualizar campos que vienen en el POST
        updated = 0
        for sched in CronSchedule.objects.all():
            prefix = f'task_{sched.id}_'
            hora_key = prefix + 'hora'
            minuto_key = prefix + 'minuto'
            cada_key = prefix + 'cada'
            enabled_key = prefix + 'enabled'

            changed = False
            if hora_key in request.POST:
                try:
                    new_hora = int(request.POST[hora_key])
                    if 0 <= new_hora <= 23 and new_hora != sched.hora_utc:
                        sched.hora_utc = new_hora
                        changed = True
                except (ValueError, TypeError):
                    pass
            if minuto_key in request.POST:
                try:
                    new_minuto = int(request.POST[minuto_key])
                    if 0 <= new_minuto <= 59 and new_minuto != sched.minuto_utc:
                        sched.minuto_utc = new_minuto
                        changed = True
                except (ValueError, TypeError):
                    pass
            if cada_key in request.POST:
                try:
                    new_cada = int(request.POST[cada_key])
                    if new_cada >= 0 and new_cada != sched.cada_n_minutos:
                        sched.cada_n_minutos = new_cada
                        changed = True
                except (ValueError, TypeError):
                    pass
            # enabled: checkbox → viene "on" si está activo, ausente si no
            new_enabled = enabled_key in request.POST
            if new_enabled != sched.enabled:
                sched.enabled = new_enabled
                changed = True

            if changed:
                sched.actualizado_por = request.user.email
                sched.save()
                updated += 1

        if updated > 0:
            messages.success(request, f'✅ {updated} horario(s) actualizados. El próximo minuto el dispatcher los tomará.')
        else:
            messages.info(request, 'Sin cambios en los horarios.')
        return redirect('auto_betting:cron_schedules')

    schedules = CronSchedule.objects.all().order_by('hora_utc', 'minuto_utc')
    return render(request, 'auto_betting/cron_schedules.html', {
        'schedules': schedules,
    })

@login_required
def paperbet_dashboard(request):
    """Panel PAPERBET: apuestas en papel de los motores independientes (sin dinero real)."""
    from django.db.models import Sum, Count, Q
    from .models import PaperBet

    bets = PaperBet.objects.all()

    def agg(qs):
        """qs = apuestas del grupo (OPEN incluidas). Liquidadas = WON/LOST.

        Los VOID (reembolso: payout == stake) quedan fuera de n, stake, ROI y
        WR: meterlos no cambiaba el neto pero sí diluía el ROI y los contaba
        como derrotas. Se reportan aparte en 'void'.
        """
        liq = qs.filter(estado__in=['WON', 'LOST'])
        n = liq.count()
        won = liq.filter(estado='WON').count()
        stake = liq.aggregate(s=Sum('stake'))['s'] or 0
        payout = liq.aggregate(p=Sum('payout'))['p'] or 0
        return {
            'n': n, 'won': won, 'lost': n - won,
            'void': qs.filter(estado='VOID').count(),
            'wr': round(won / n * 100, 1) if n else None,
            'stake': stake, 'net': payout - stake,
            'roi': round((payout - stake) / stake * 100, 1) if stake else None,
        }

    global_stats = agg(bets)
    open_count = bets.filter(estado='OPEN').count()

    por_motor = []
    for motor in bets.values_list('motor', flat=True).distinct():
        if not motor:
            continue
        st = agg(bets.filter(motor=motor))
        st['motor'] = motor
        st['open'] = bets.filter(motor=motor, estado='OPEN').count()
        por_motor.append(st)
    por_motor.sort(key=lambda x: -(x['net']))

    por_mercado = []
    for mercado in bets.values_list('mercado', flat=True).distinct():
        st = agg(bets.filter(mercado=mercado))
        st['mercado'] = mercado
        st['open'] = bets.filter(mercado=mercado, estado='OPEN').count()
        por_mercado.append(st)
    por_mercado.sort(key=lambda x: -(x['net']))

    recientes = bets.order_by('-creado')[:120]

    # Winrate de la opinión de la IA (SI/NO) por mercado × motor.
    # Solo liquidados (WON/LOST); VOID se excluye del denominador.
    def _wr(won, n):
        return round(won / n * 100, 1) if n else None

    _llm_agg = {}
    for b in bets.filter(estado__in=['WON', 'LOST']):
        key = (b.mercado or '—', b.motor or '—')
        d = _llm_agg.setdefault(key, {
            'n': 0, 'won': 0,
            'si': {'n': 0, 'won': 0},
            'no': {'n': 0, 'won': 0},
        })
        d['n'] += 1
        if b.estado == 'WON':
            d['won'] += 1
        if b.llm_verdict is True:
            d['si']['n'] += 1
            if b.estado == 'WON':
                d['si']['won'] += 1
        elif b.llm_verdict is False:
            d['no']['n'] += 1
            if b.estado == 'WON':
                d['no']['won'] += 1

    llm_resumen = []
    for (mercado, motor), d in _llm_agg.items():
        llm_resumen.append({
            'mercado': mercado,
            'motor': motor,
            'n': d['n'],
            'wr': _wr(d['won'], d['n']),
            'si_n': d['si']['n'], 'si_won': d['si']['won'],
            'si_lost': d['si']['n'] - d['si']['won'],
            'si_wr': _wr(d['si']['won'], d['si']['n']),
            'no_n': d['no']['n'], 'no_won': d['no']['won'],
            'no_lost': d['no']['n'] - d['no']['won'],
            'no_wr': _wr(d['no']['won'], d['no']['n']),
        })
    llm_resumen.sort(key=lambda x: -(x['n']))

    arb_monitors = None
    try:
        with open(os.path.join(settings.BASE_DIR, 'data', 'arb_monitors.json'), encoding='utf-8') as fh:
            arb_monitors = json.load(fh)
    except (OSError, ValueError):
        arb_monitors = None
    arb_paper_total = 0.0
    if arb_monitors:
        for key in ('depeg', 'p2p'):
            block = (arb_monitors.get(key) or {}).get('data') or {}
            try:
                arb_paper_total += float(block.get('paper_total') or 0.0)
            except (TypeError, ValueError):
                pass

    return render(request, 'auto_betting/paperbet.html', {
        'global_stats': global_stats,
        'open_count': open_count,
        'por_motor': por_motor,
        'por_mercado': por_mercado,
        'llm_resumen': llm_resumen,
        'recientes': recientes,
        'arb_monitors': arb_monitors,
        'arb_paper_total': arb_paper_total,
    })


@login_required
def paperbet_basket(request):
    """Página dedicada: paperbet de baloncesto 1Q+2Q (motor basket_1q2q).

    Portado de la app de escritorio "App de Baloncesto": modelo MCO por liga
    TOTAL = b0 + b1·1Q + b2·2Q, apuesta en el descanso 2Q→3Q con cuota viva
    de Kambi/BetPlay. Solo papel (sin dinero real).
    """
    from django.db.models import Count, Sum, Q

    from . import basket_1q2q as bk
    from .management.commands.run_paper_bets_basket import (
        cargar_filtro_ligadia, ZONA_BOG)
    from .models import (BasketMarketSnapshot, BasketModel, BasketSample,
                         PaperBet, PinnacleCallLog, PinnacleSnapshot)

    ver_gated = request.GET.get('gated') == '1'
    motor = bk.MOTOR_GATED if ver_gated else bk.MOTOR
    bets = PaperBet.objects.filter(motor=motor)
    ver_todas = request.GET.get('todas') == '1'
    # Modos: ligadia (default del motor principal, filtro liga x dia
    # pre-registrado 31-oct), ganadoras (comportamiento previo), todas.
    if ver_gated:
        modo = 'todas' if ver_todas else 'ganadoras'
    else:
        modo = 'todas' if ver_todas else request.GET.get('filtro', 'ligadia')
        if modo not in ('ligadia', 'ganadoras', 'todas'):
            modo = 'ligadia'
    whitelist = (cargar_filtro_ligadia() if modo == 'ligadia' else None)

    def cumple_celda(b):
        if whitelist is None:
            return True
        dia = b.creado.astimezone(ZONA_BOG).weekday()
        return (b.liga, dia) in whitelist

    def agg_list(lst):
        liq = [b for b in lst if b.estado in ['WON', 'LOST']]
        n = len(liq)
        won = sum(1 for b in liq if b.estado == 'WON')
        stake = sum(b.stake or 0 for b in liq)
        payout = sum(b.payout or 0 for b in liq)
        clv_rows = [b for b in liq if b.closing_odds and b.cuota]
        clv = (round(sum(b.closing_odds / b.cuota - 1 for b in clv_rows)
                     / len(clv_rows) * 100, 2) if clv_rows else None)
        return {
            'n': n, 'won': won, 'lost': n - won,
            'void': sum(1 for b in lst if b.estado == 'VOID'),
            'wr': round(won / n * 100, 1) if n else None,
            'stake': stake, 'net': payout - stake,
            'roi': round((payout - stake) / stake * 100, 1) if stake else None,
            'clv': clv,
        }

    bets_all = list(bets)
    por_liga_todas = []
    base_por_liga = [b for b in bets_all if cumple_celda(b)]
    for liga in {b.liga for b in base_por_liga if b.liga}:
        st = agg_list([b for b in base_por_liga if b.liga == liga])
        st['liga'] = liga
        st['open'] = sum(1 for b in base_por_liga
                         if b.liga == liga and b.estado == 'OPEN')
        por_liga_todas.append(st)
    por_liga_todas.sort(key=lambda x: -(x['net']))

    # Vista "ganadoras" (comportamiento previo): excluye ligas con neto
    # histórico negativo. Selección in-sample; no es ROI esperado.
    ligas_ganadoras = {r['liga'] for r in por_liga_todas
                       if (r['net'] or 0) > 0}
    if modo == 'todas':
        por_liga = por_liga_todas
        bets_calc = bets_all
    elif modo == 'ganadoras':
        por_liga = [r for r in por_liga_todas
                    if r['liga'] in ligas_ganadoras]
        bets_calc = [b for b in bets_all
                     if b.liga in ligas_ganadoras]
    else:  # ligadia
        por_liga = por_liga_todas
        bets_calc = [b for b in bets_all if cumple_celda(b)]

    global_stats = agg_list(bets_calc)
    global_stats_todas = agg_list(bets_all) if modo != 'todas' else global_stats
    open_count = bets.filter(estado='OPEN').count()
    recientes = sorted(
        (b for b in bets_all
         if modo == 'todas'
         or (modo == 'ganadoras'
             and (b.liga in ligas_ganadoras or b.estado == 'OPEN'))
         or (modo == 'ligadia'
             and (cumple_celda(b) or b.estado == 'OPEN'))),
        key=lambda b: b.creado, reverse=True)[:120]

    # Pinnacle (solo datos): precios para las columnas P. PRE / P. 2Q→3Q.
    pins = {}
    for s in PinnacleSnapshot.objects.filter(
            kambi_event_id__in=[b.evento_id for b in recientes]):
        pins.setdefault(s.kambi_event_id, {})[s.tipo] = s
    for b in recientes:
        b.pin_pre = pins.get(b.evento_id, {}).get('pregame')
        b.pin_break = pins.get(b.evento_id, {}).get('break')
    pin_total = PinnacleSnapshot.objects.count()
    pin_ultima = PinnacleCallLog.objects.order_by('-capturado_en').first()

    modelos = list(BasketModel.objects.all())
    con_modelo = {m.liga for m in modelos}
    muestras = {r['liga']: r['n'] for r in
                BasketSample.objects.values('liga').annotate(n=Count('id'))}
    pendientes = [(clave, muestras.get(clave, 0))
                  for clave in sorted(bk.LIGAS_API_SPORTS)
                  if clave not in con_modelo]

    snap_total = BasketMarketSnapshot.objects.count()
    snap_ultimo = BasketMarketSnapshot.objects.order_by('-capturado_en').first()

    return render(request, 'auto_betting/paperbet_basket.html', {
        'global_stats': global_stats,
        'global_stats_todas': global_stats_todas,
        'ver_todas': ver_todas,
        'modo': modo,
        'n_celdas': len(whitelist) if whitelist else 0,
        'descartadas': (len(bets_all) - len([b for b in bets_all
                                             if cumple_celda(b)])
                        if whitelist else 0),
        'ligas_totales': len(por_liga_todas),
        'ligas_excluidas': len(por_liga_todas) - len(por_liga),
        'open_count': open_count,
        'por_liga': por_liga,
        'recientes': recientes,
        'modelos': modelos,
        'pendientes': pendientes,
        'snap_total': snap_total,
        'snap_ultimo': snap_ultimo,
        'pin_total': pin_total,
        'pin_ultima': pin_ultima,
        'motor': motor,
        'ver_gated': ver_gated,
        'delta_min': bk.GATE_DELTA_MIN if ver_gated else bk.DELTA_MINIMO,
        'delta_max': bk.GATE_DELTA_MAX if ver_gated else bk.DELTA_MAXIMO,
        'ev_min': (bk.GATE_EV_MIN if ver_gated else bk.EV_MINIMA) * 100,
        'factor_rmse': bk.FACTOR_RMSE,
    })


@login_required
def paperbet_basket_ou(request):
    """Página hija: motor Over/Under al descanso (basket_ou) — EUROPA/NBA.

    Modelo de los libros EUROPA.xlsx/NBA.xlsx (spec): patrón por cuartos +
    línea viva del descanso, sombras por partido y apuestas paper a 1 u.
    Solo papel (sin dinero real).
    """
    from django.db.models import Count, Sum

    from . import basket_ou as bou
    from .models import BasketOuCalib, BasketOuShadow, BasketOuSharp, PaperBet

    def agg(qs):
        liq = qs.filter(estado__in=['WON', 'LOST'])
        n = liq.count()
        won = liq.filter(estado='WON').count()
        stake = liq.aggregate(s=Sum('stake'))['s'] or 0
        payout = liq.aggregate(p=Sum('payout'))['p'] or 0
        return {
            'n': n, 'won': won, 'lost': n - won,
            'void': qs.filter(estado='VOID').count(),
            'open': qs.filter(estado='OPEN').count(),
            'wr': round(won / n * 100, 1) if n else None,
            'stake': stake, 'net': payout - stake,
            'roi': round((payout - stake) / stake * 100, 1) if stake else None,
        }

    def con_txt(m):
        m = dict(m)
        m['wr_txt'] = (f"{m['acierto'] * 100:.1f}%"
                       if m['acierto'] is not None else '—')
        m['roi_txt'] = (f"{m['roi'] * 100:+.2f}%"
                        if m['roi'] is not None else '—')
        m['wilson_txt'] = (f"{m['wilson_low'] * 100:.1f}–"
                           f"{m['wilson_high'] * 100:.1f}%"
                           if m['wilson_low'] is not None else '—')
        m['margen_txt'] = (f"{m['margen_medio']:+.2f}"
                           if m['margen_medio'] is not None else '—')
        return m

    sombras = BasketOuShadow.objects.all()
    liquidadas = [{'apostar': s.decision.startswith('APOSTAR'), 'side': s.lado,
                   'resultado': s.resultado or None,
                   'ganancia_u': s.ganancia_u, 'total': s.total_ot,
                   'linea': s.linea, 'cfg': s.cfg, 'liga': s.clave_liga}
                  for s in sombras.filter(settled_at__isnull=False)]
    global_m = con_txt(bou.metricas(liquidadas, bou.CFG['EUROPA']))

    por_cfg = []
    for cfg_key in sorted(bou.CFG):
        m = con_txt(bou.metricas([f for f in liquidadas if f['cfg'] == cfg_key],
                                 bou.CFG[cfg_key]))
        m['cfg'] = cfg_key
        por_cfg.append(m)

    por_liga = []
    for liga in sorted({f['liga'] for f in liquidadas if f['liga']}):
        m = con_txt(bou.metricas([f for f in liquidadas if f['liga'] == liga],
                                 bou.CFG['EUROPA']))
        m['liga'] = liga
        por_liga.append(m)

    recientes_sombras = []
    for s in sombras.order_by('-actualizado')[:60]:
        descanso = '—'
        if None not in (s.q1h, s.q1a, s.q2h, s.q2a):
            descanso = f'{s.q1h:.0f}-{s.q1a:.0f} / {s.q2h:.0f}-{s.q2a:.0f}'
        recientes_sombras.append({
            'ts': s.actualizado, 'liga': s.liga or s.clave_liga,
            'partido': f'{s.home_team} vs {s.away_team}',
            'descanso': descanso, 'linea': s.linea, 'odds_side': s.odds_side,
            'proy': s.proy, 'diff': s.diff, 'lado': s.lado,
            'p_pct': (f'{s.p_side * 100:.1f}%'
                      if s.p_side is not None else '—'),
            'ev_pct': (f'{s.ev_side * 100:+.1f}%'
                       if s.ev_side is not None else '—'),
            'decision': s.decision, 'stake_kelly': s.stake_kelly,
            'resultado': s.resultado, 'ganancia_u': s.ganancia_u,
        })

    bets = PaperBet.objects.filter(motor=bou.MOTOR)
    recientes_bets = []
    for b in bets.order_by('-creado')[:60]:
        recientes_bets.append({
            'ts': b.creado, 'liga': b.liga,
            'partido': f'{b.home_team} vs {b.away_team}',
            'seleccion': b.seleccion, 'linea': b.linea, 'cuota': b.cuota,
            'prob': b.prob, 'ev': b.ev, 'stake': b.stake,
            'kelly': b.stake_kelly, 'estado': b.estado,
            'resultado': b.resultado_real,
        })

    calibs = [{'cfg': k,
               'row': (BasketOuCalib.objects.filter(cfg=k)
                       .order_by('-calculada_en').first())}
              for k in sorted(bou.CFG)]
    sharp_por_liga = list(BasketOuSharp.objects.values('clave_liga')
                          .annotate(n=Count('id')).order_by('-n'))

    return render(request, 'auto_betting/paperbet_basket_ou.html', {
        'motor': bou.MOTOR,
        'mercado': bou.MERCADO,
        'global_m': global_m,
        'por_cfg': por_cfg,
        'por_liga': por_liga,
        'bets_stats': agg(bets),
        'n_sombras': sombras.count(),
        'n_pendientes': sombras.filter(settled_at__isnull=True).count(),
        'recientes_sombras': recientes_sombras,
        'recientes_bets': recientes_bets,
        'calibs': calibs,
        'sharp_por_liga': sharp_por_liga,
        'sharp_total': BasketOuSharp.objects.count(),
        'sharp_ultimo': BasketOuSharp.objects.order_by('-capturado_en').first(),
    })


@login_required
def papertrading(request):
    """Página dedicada: papertrading FX con Deriv (motor fx_deriv, MT5 Quant Lab).

    Independiente del paperbet de fútbol/baloncesto: opera 3 modelos de trading
    (MRGA EURUSD H1/M5 + Donchian XAUUSD H4) sobre velas del endpoint público
    de Deriv, en USD virtuales. Solo papel, sin dinero real.
    """
    from django.db.models import Sum
    from django.utils import timezone as tz

    from . import fx_deriv as fx
    from .models import FxEngineState, FxPaperTrade

    def stats(qs):
        cer = qs.filter(estado='CLOSED')
        n = cer.count()
        won = cer.filter(pnl__gt=0).count()
        net = cer.aggregate(s=Sum('pnl'))['s'] or 0.0
        gw = cer.filter(pnl__gt=0).aggregate(s=Sum('pnl'))['s'] or 0.0
        gl = -((cer.filter(pnl__lte=0).aggregate(s=Sum('pnl'))['s']) or 0.0)
        return {
            'n': n, 'won': won, 'lost': n - won,
            'wr': round(won / n * 100, 1) if n else None,
            'net': round(net, 2),
            'roi': round(net / fx.INIT_BALANCE * 100, 2) if n else None,
            'pf': round(gw / gl, 3) if gl > 0 else None,
        }

    def max_dd(cerradas):
        peak = float(fx.INIT_BALANCE)
        dd = 0.0
        for b in cerradas.order_by('t_salida').values_list('balance_post', flat=True):
            if not b:
                continue
            peak = max(peak, b)
            dd = max(dd, (peak - b) / peak * 100.0)
        return round(dd, 1)

    estrategias = []
    total = {'n': 0, 'wins': 0, 'net': 0.0, 'open': 0}
    for clave, cfg in fx.STRATEGIES.items():
        if clave in fx.ESTRATEGIAS_DEPRECADAS:
            continue
        qs = FxPaperTrade.objects.filter(estrategia=clave)
        st = stats(qs)
        st['clave'] = clave
        st['nombre'] = cfg['nombre']
        st['simbolo'] = cfg['simbolo']
        st['dd'] = max_dd(qs.filter(estado='CLOSED'))
        estado = FxEngineState.objects.filter(estrategia=clave).first()
        st['balance'] = round(estado.balance, 2) if estado else fx.INIT_BALANCE
        st['ultimo_run'] = estado.ultimo_run if estado else None
        primera = qs.order_by('t_entrada').values_list('t_entrada', flat=True).first()
        if primera:
            semanas = max((tz.now() - primera).total_seconds() / (7 * 86400), 0.2)
            st['ops_sem'] = round(st['n'] / semanas, 1)
        else:
            st['ops_sem'] = None
        st['abierta'] = qs.filter(estado='OPEN').order_by('-creado').first()
        estrategias.append(st)
        total['n'] += st['n']
        total['wins'] += st['won']
        total['net'] += st['net']
        total['open'] += 1 if st['abierta'] else 0

    roi_sum = round(sum(s['roi'] or 0 for s in estrategias), 2)
    total.update({
        'wr': round(total['wins'] / total['n'] * 100, 1) if total['n'] else None,
        'net': round(total['net'], 2),
        'roi_sum': roi_sum,
        'roi_mean': round(roi_sum / len(estrategias), 2),
    })
    recientes = FxPaperTrade.objects.order_by('-t_signal')[:100]

    return render(request, 'auto_betting/papertrading.html', {
        'estrategias': estrategias,
        'total': total,
        'recientes': recientes,
        'init_balance': fx.INIT_BALANCE,
        'motor': fx.MOTOR,
    })



@login_required
def paperparleys(request):
    """Panel PAPERPARLEYS: parlays en papel generados con los picks del
    motor real (AutoBet), recalibrados por deciles y filtrados por EV."""
    from django.utils import timezone
    from django.db.models import Q
    from .models import PPGenRun, PPParley, PPParleyLeg
    from auto_betting import paper_parleys as pp

    cfg = pp.get_cfg()
    hoy = timezone.localdate()
    desde = hoy - datetime.timedelta(days=30)
    qs = PPParley.objects.filter(dia__gte=desde)

    liq = qs.filter(estado__in=('GANADO', 'PERDIDO', 'PUSH'))
    n_liq = liq.count()
    ganados = liq.filter(estado='GANADO').count()
    aggs = liq.aggregate(stake=Sum('stake'), payout=Sum('payout'))
    stake = aggs['stake'] or 0
    payout = aggs['payout'] or 0
    global_stats = {
        'n': n_liq, 'ganados': ganados, 'perdidos': n_liq - ganados,
        'wr': round(100 * ganados / n_liq, 1) if n_liq else None,
        'stake': stake, 'net': payout - stake,
        'roi': round(100 * (payout - stake) / stake, 1) if stake else None,
        'pendientes': qs.filter(estado='PENDIENTE').count(),
        'n_total': qs.count(),
    }

    por_patas = []
    for r in liq.values('n_legs').annotate(
            n=Count('id'), sum_p=Sum('payout'), sum_s=Sum('stake'),
            won=Count('id', filter=Q(estado='GANADO'))):
        neto = (r['sum_p'] or 0) - (r['sum_s'] or 0)
        r['neto'] = neto
        r['wr'] = round(100 * r['won'] / r['n'], 1) if r['n'] else None
        por_patas.append(r)
    por_patas.sort(key=lambda x: x['n_legs'])

    por_dia = list(qs.values('dia').annotate(n=Count('id'))
                   .order_by('-dia')[:30])
    net_dia = {r['dia']: r for r in liq.values('dia')
               .annotate(sum_p=Sum('payout'), sum_s=Sum('stake'),
                         won=Count('id', filter=Q(estado='GANADO')))}
    for f in por_dia:
        r = net_dia.get(f['dia']) or {}
        f['won'] = r.get('won', 0)
        f['neto'] = (r.get('sum_p') or 0) - (r.get('sum_s') or 0)

    ultimos = qs.order_by('-creado', '-id')[:25]
    runs = (PPGenRun.objects.filter(parlays__isnull=False)
            .distinct().order_by('-id')[:12])

    top_ev = list(PPParleyLeg.objects
                  .filter(parley__dia__gte=desde, parley__estado='GANADO')
                  .values('parley__dia', 'parley__cuota_producto',
                          'parley__payout', 'parley__n_legs')
                  .order_by('-parley__cuota_producto')[:10])
    ligas_top = list(PPParleyLeg.objects
                     .filter(parley__dia__gte=desde,
                             parley__estado__in=('GANADO', 'PERDIDO'))
                     .values('liga')
                     .annotate(n=Count('id'),
                               won=Count('id', filter=Q(parley__estado='GANADO')))
                     .order_by('-n')[:12])

    ctx = {
        'cfg': cfg, 'global_stats': global_stats, 'por_patas': por_patas,
        'por_dia': por_dia, 'ultimos': ultimos, 'runs': runs,
        'top_ev': top_ev, 'ligas_top': ligas_top,
        'desde': desde, 'hoy': hoy,
    }
    if request.method == 'POST':
        if not request.user.is_superuser:
            return HttpResponseForbidden()
        res = pp.generate_day(hoy, modo='MANUAL', args='web-generar')
        st = pp.settle(dia_hasta=hoy)
        messages.success(request,
                         f'Paperparleys hoy: {res["generados"]} nuevos, '
                         f'{res["existentes"]} ya existían; settle {st}')
        return redirect('auto_betting:paperparleys')
    return render(request, 'auto_betting/paperparleys.html', ctx)
