# -*- coding: utf-8 -*-
"""Panel de parleys: cupones combinados (manuales + motor independiente)."""
import re
from datetime import date, timedelta

from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .models import ParleyCoupon

SPORT_META = {
    'FOOTBALL': ('⚽', 'Fútbol'),
    'BASKETBALL': ('🏀', 'Baloncesto'),
    'BASEBALL': ('⚾', 'Béisbol'),
    'MIXED': ('🌐', 'Mixto'),
}

# Excepción puntual pedida por el humano (2026-10-30): el cupón manual que se
# ganó ayer (Memphis +1.5, WON, 2.991,5 COP) sigue visible en el panel; solo
# ese cupón manual, los demás quedan ocultos.
EXCEPCION_MANUAL_VISIBLE = 13291906849


def _sport_meta(key):
    return SPORT_META.get((key or '').upper(), ('🎲', key or 'Sin deporte'))


def _parse_date(s):
    if not s:
        return None
    try:
        return date.fromisoformat(s)
    except (ValueError, TypeError):
        return None


def _max_drawdown(rows):
    """rows: [(fecha, pnl)] ya ordenadas; devuelve COP peak-to-trough."""
    equity = peak = maxdd = 0.0
    for _, pnl in rows:
        equity += float(pnl or 0.0)
        if equity > peak:
            peak = equity
        dd = peak - equity
        if dd > maxdd:
            maxdd = dd
    return maxdd


@login_required
def historial_parleys(request):
    sport = (request.GET.get('sport') or '').strip().upper()
    if not re.fullmatch(r'[A-Z0-9_]{1,32}', sport):
        sport = ''
    desde = _parse_date(request.GET.get('desde'))
    hasta = _parse_date(request.GET.get('hasta'))

    # 2026-10-30: el panel muestra SOLO los cupones que coloca el motor
    # (is_motor=True) desde ayer en adelante. Los manuales (historial
    # importado de BetPlay, pruebas, etc.) se ocultan, salvo la excepción
    # puntual (cupón manual ganado ayer).
    # 2026-11-01: con filtro de fechas explícito se busca en todo el
    # historial y el rango se aplica a la FECHA DEL PARTIDO (la que muestra
    # la columna Fecha), no al día de los picks.
    ayer = timezone.localdate() - timedelta(days=1)
    if desde or hasta:
        filtros = Q(is_motor=True) | Q(coupon_ref=EXCEPCION_MANUAL_VISIBLE)
    else:
        filtros = (
            Q(is_motor=True) & (
                Q(placed_date__date__gte=ayer)
                | Q(placed_date__isnull=True, dia__gte=ayer))
            | Q(coupon_ref=EXCEPCION_MANUAL_VISIBLE)
        )

    qs = (ParleyCoupon.objects
          .filter(filtros, usuario=request.user, coupon_ref__isnull=False)
          .prefetch_related('leg_rows__autobet')
          .order_by('-placed_date', '-id'))

    base = list(qs)
    if desde or hasta:
        base = [
            c for c in base
            if any((desde is None or f >= desde)
                   and (hasta is None or f <= hasta)
                   for f in c.fechas_encuentro)
        ]
    sport_counts = {}
    for c in base:
        sport_counts[c.sport] = sport_counts.get(c.sport, 0) + 1
    coupons = [c for c in base if not sport or c.sport == sport]
    settled_states = ('WON', 'LOST', 'VOID', 'CASHOUT', 'PUSH')
    settled = [c for c in coupons if c.status in settled_states]
    won = sum(1 for c in settled if c.status == 'WON')
    lost = sum(1 for c in settled if c.status == 'LOST')
    opened = sum(1 for c in coupons if c.status == 'OPEN')
    stake = sum(float(c.stake or 0) for c in settled)
    payout = sum(float(c.payout or 0) for c in settled)
    pnl = payout - stake
    roi = (100 * pnl / stake) if stake else 0.0
    wr = (100 * won / (won + lost)) if (won + lost) else 0.0

    ordered = sorted(
        settled,
        key=lambda c: (c.placed_date.timestamp() if c.placed_date else 0.0, c.id))
    maxdd = _max_drawdown([(c.dia, float(c.payout or 0) - float(c.stake or 0))
                           for c in ordered])

    def _url(sport_value):
        params = []
        if sport_value:
            params.append(f'sport={sport_value}')
        if desde:
            params.append(f'desde={desde.isoformat()}')
        if hasta:
            params.append(f'hasta={hasta.isoformat()}')
        return '?' + '&'.join(params) if params else '?'

    sport_options = []
    for key in sorted(sport_counts, key=lambda s: (s != '', s)):
        icon, label = _sport_meta(key)
        sport_options.append({
            'value': key, 'icon': icon, 'label': label,
            'count': sport_counts[key],
            'active': key == sport,
            'url': _url(key),
        })

    return render(request, 'parley_engine/historial.html', {
        'coupons': coupons,
        'stats': {
            'total': len(coupons),
            'settled': len(settled),
            'won': won,
            'lost': lost,
            'opened': opened,
            'stake': stake,
            'payout': payout,
            'pnl': pnl,
            'roi': roi,
            'wr': wr,
            'maxdd': maxdd,
            'motor': sum(1 for c in coupons if c.is_motor),
        },
        'sport': sport,
        'sport_options': sport_options,
        'sport_todos': {'count': sum(sport_counts.values()), 'url': _url('')},
        'desde': desde.isoformat() if desde else '',
        'hasta': hasta.isoformat() if hasta else '',
        'sport_active_label': _sport_meta(sport)[1] if sport else '',
        'now': timezone.now(),
    })


@login_required
@require_POST
def sync_parleys(request):
    """Actualiza y liquida los cupones del usuario desde BetPlay."""
    from .services import sync_user_history

    return JsonResponse(sync_user_history(request.user))
