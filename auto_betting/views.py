"""
Vistas del auto_betting: historial de apuestas y análisis.
"""

from django.shortcuts import render
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST
from django.db.models import Sum, Count, Q
from .models import HistorialApuesta
from .services import sync_historial


def _analisis():
    """Calcula métricas agregadas del historial."""
    qs = HistorialApuesta.objects.all()
    total = qs.count()
    won = qs.filter(bet_status='WON').count()
    lost = qs.filter(bet_status='LOST').count()
    opened = qs.filter(bet_status='OPEN').count()
    void = qs.exclude(bet_status__in=['WON', 'LOST', 'OPEN']).count()

    settled = won + lost
    win_rate = (won / settled * 100) if settled else 0.0

    # Totales en unidades Kambi (÷1000 = COP)
    stake_total = qs.aggregate(s=Sum('stake'))['s'] or 0
    payout_total = qs.aggregate(p=Sum('payout'))['p'] or 0
    potential_total = qs.aggregate(p=Sum('potential_payout'))['p'] or 0

    stake_cop = stake_total / 1000.0
    payout_cop = payout_total / 1000.0
    pnl = (payout_total - stake_total) / 1000.0

    # Solo asentadas (WON+LOST): P&L realizado
    settled_qs = qs.filter(bet_status__in=['WON', 'LOST'])
    settled_stake = settled_qs.aggregate(s=Sum('stake'))['s'] or 0
    settled_payout = settled_qs.aggregate(p=Sum('payout'))['p'] or 0
    realized_pnl = (settled_payout - settled_stake) / 1000.0
    # ROI sobre lo asentado (consistente con P&L realizado)
    roi = (realized_pnl / (settled_stake / 1000.0) * 100) if settled_stake else 0.0

    # Por mercado (con P&L, ROI y volumen)
    por_mercado = []
    for row in qs.values('mercado').annotate(
        n=Count('id'),
        won=Count('id', filter=Q(bet_status='WON')),
        lost=Count('id', filter=Q(bet_status='LOST')),
        st=Sum('stake', filter=Q(bet_status__in=['WON', 'LOST'])),
        pay=Sum('payout', filter=Q(bet_status__in=['WON', 'LOST'])),
    ):
        m = row['mercado'] or 'Sin mercado'
        w = row['won']
        l = row['lost']
        s = w + l
        st = row['st'] or 0
        pay = row['pay'] or 0
        pnl = (pay - st) / 1000.0
        roi = (pnl / (st / 1000.0) * 100) if st else 0.0
        por_mercado.append({
            'mercado': m,
            'n': row['n'],
            'won': w,
            'lost': l,
            'settled': s,
            'win_rate': round((w / s * 100) if s else 0.0, 1),
            'stake_cop': round(st / 1000.0, 0),
            'pnl': round(pnl, 0),
            'roi': round(roi, 1),
        })
    # Ordenar por P&L descendente (mejor primero)
    por_mercado.sort(key=lambda x: x['pnl'], reverse=True)

    # Línea temporal de P&L acumulado (solo asentadas, en orden cronológico)
    pnl_timeline = []
    cum = 0.0
    for a in qs.filter(bet_status__in=['WON', 'LOST']).order_by('placed_date'):
        cum += a.profit_cop
        pnl_timeline.append({
            'label': a.placed_date.strftime('%d/%m %H:%M'),
            'cum': round(cum, 0),
        })

    return {
        'total': total,
        'won': won,
        'lost': lost,
        'opened': opened,
        'void': void,
        'settled': settled,
        'win_rate': round(win_rate, 1),
        'stake_cop': round(stake_cop, 2),
        'payout_cop': round(payout_cop, 2),
        'potential_cop': round(potential_total / 1000.0, 2),
        'pnl': round(pnl, 2),
        'realized_pnl': round(realized_pnl, 2),
        'roi': round(roi, 1),
        'por_mercado': por_mercado,
        'pnl_timeline': pnl_timeline,
    }


def historial(request):
    apuestas = HistorialApuesta.objects.all().order_by('-placed_date')
    stats = _analisis()
    return render(request, 'auto_betting/historial.html', {
        'apuestas': apuestas,
        'stats': stats,
    })


@csrf_exempt
@require_POST
def historial_sync(request):
    """Dispara la sincronización del historial desde BetPlay (botón actualizar)."""
    result = sync_historial('2026-08-01')
    if result.get('error'):
        return JsonResponse({'ok': False, 'error': result['error']}, status=500)
    return JsonResponse({'ok': True, **result})
