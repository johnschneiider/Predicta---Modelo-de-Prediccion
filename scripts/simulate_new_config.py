"""
simulate_new_config.py — Contrafactual: ¿qué habría apostado el motor con la
configuración + código de HOY (P2a calibración, submercados OFF, híbrido xG)
sobre los partidos que sí se apostaron ayer (Sep 2) y hoy (Sep 3)?

Método (alta fidelidad):
  - BEFORE: las apuestas reales colocadas (AutoBet) y su resultado real
    (HistorialApuesta por coupon_ref).
  - AFTER: para CADA apuesta real, se reconstruye la misma oferta
    (línea + cuota) y se pasa por `select_bets` con el λ recalculado por el
    pipeline actual (build_web_predictions + blend xG) y la config actual.
    Si la oferta sobrevive el embudo → se habría apostado.

Limitación honesta: solo mide qué apuestas de las REALES se habrían evitado.
No mide apuestas NUEVAS que el motor habría descubierto en otras ofertas
(no hay snapshot completo de ofertas de esa mañana).
"""
import os
import sys

sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()

import logging
logging.disable(logging.WARNING)

from collections import defaultdict
from datetime import timedelta

from django.utils import timezone

from auto_betting.models import AutoBet, AutoBetConfig, HistorialApuesta
from auto_betting.strategy import select_bets, get_market_filters, get_global_config, poisson_over
from football_data.models import League

MERCADO_KEY = {
    'Total de goles': 'goals',
    'Total de Tiros de Esquina': 'corners',
    'Total de tiros a puerta': 'shots_on_target',
    'Ambos Equipos Marcarán': 'btts',
}
MERCADO_WEB = {
    'goals': 'goals_total',
    'corners': 'corners_total',
    'shots_on_target': 'shots_on_target_total',
    'btts': 'both_teams_score',
}


def liga_de(ab):
    if isinstance(ab.liga, League):
        return ab.liga
    return League.objects.filter(name=ab.liga).first()


def resultados_por_coupon():
    out = {}
    for h in HistorialApuesta.objects.filter(bet_status__in=['WON', 'LOST', 'OPEN']):
        out[h.coupon_ref] = h
    return out


def main():
    hoy = timezone.now().date()
    desde = hoy - timedelta(days=1)
    qs = AutoBet.objects.filter(creado__date__gte=desde).order_by('creado')
    historial = resultados_por_coupon()

    # precómputo λ por (liga_id, home, away) → official por mercado
    cache = {}
    def oficial(home, away, liga, web_type):
        from ai_predictions.web_pipeline import build_web_predictions, get_official_prediction
        if not liga:
            return None
        key = (liga.id, home, away)
        if key not in cache:
            tipos = set()
            for m in (MERCADO_WEB['goals'], MERCADO_WEB['corners'],
                      MERCADO_WEB['shots_on_target'], MERCADO_WEB['btts']):
                tipos.add(m)
            try:
                cache[key] = build_web_predictions(home, away, liga, prediction_types=list(tipos))
            except Exception:
                cache[key] = {}
        return get_official_prediction(cache[key], web_type)

    gcfg = get_global_config()
    cap = gcfg.get('calib_cap', 0.58)
    # Fiel a run_auto_bets.py (2026-08-25): los min_cuota por submercado se
    # neutralizan (0) — la cuota mínima efectiva es SOLO la per-user.
    mf = {k: {**v, 'min_cuota': 0.0} for k, v in get_market_filters().items()}
    cuota_min_por_user = {
        c.usuario_id: c.cuota_minima
        for c in AutoBetConfig.objects.all()
    }

    def simular(ab):
        """Devuelve True si la oferta real sobreviviría el embudo de hoy."""
        key = MERCADO_KEY.get(ab.mercado)
        if not key:
            return None
        sel = (ab.seleccion or '')
        if sel.startswith('Over'):
            side = 'over'
        elif sel.startswith('Under'):
            side = 'under'
        elif sel.startswith('Sí') or sel.startswith('Si'):
            side = 'Sí'
        elif sel.startswith('No'):
            side = 'No'
        else:
            return None
        liga = liga_de(ab)
        off = oficial(ab.home_team, ab.away_team, liga, MERCADO_WEB[key])
        if not off or off.get('prediction') is None:
            return False  # sin predicción oficial → el motor omite el mercado
        conf = off.get('confidence', 0.5)
        cuota = ab.cuota or 0
        linea = ab.linea
        cuota_min = cuota_min_por_user.get(ab.usuario_id, 2.0)

        if key == 'btts':
            p_yes = float(off['prediction'])
            otype = 'OT_YES' if side in ('Sí',) else 'OT_NO'
            md = {'market': 'btts', 'type': 'btts', 'p_yes': p_yes,
                  'confidence': conf, 'odds': [{'type': otype, 'odds_decimal': cuota}]}
        else:
            lam = float(off['prediction'])
            otype = 'OT_OVER' if side == 'over' else 'OT_UNDER'
            md = {'market': key, 'type': 'over_under', 'lambda': lam,
                  'confidence': conf, 'odds': [{'line': linea, 'type': otype, 'odds_decimal': cuota}]}

        cands = select_bets([md], cuota_minima=cuota_min, min_p=0.50,
                            min_confidence=0.35, market_filters=mf, calib_cap=cap)
        return len(cands) > 0

    rows = []
    for ab in qs:
        h = historial.get(ab.coupon_ref)
        status = h.bet_status if h else 'OPEN'
        stake = (h.stake or 0) / 1000.0 if h else 0
        payout = (h.payout or 0) / 1000.0 if h else 0
        rows.append({
            'dia': ab.creado.date(),
            'user': ab.usuario.username if ab.usuario else '?',
            'mercado': ab.mercado,
            'match': f'{ab.home_team} vs {ab.away_team}',
            'status': status,
            'stake': stake,
            'payout': payout,
            'would': simular(ab),
        })

    def reporte(sub, titulo):
        n = len(sub)
        settled = [r for r in sub if r['status'] in ('WON', 'LOST')]
        won = sum(1 for r in settled if r['status'] == 'WON')
        wr = won / len(settled) * 100 if settled else 0
        pnl = sum(r['payout'] - r['stake'] for r in settled)
        print(f'{titulo}: n={n} (asentadas {len(settled)}) WR={wr:.1f}% P&L={pnl:+,.0f} COP')

    print('=' * 78)
    for dia in sorted({r['dia'] for r in rows}):
        print(f'\n── {dia} ──')
        sub = [r for r in rows if r['dia'] == dia]
        antes = sub
        despues = [r for r in sub if r['would']]
        evitadas = [r for r in sub if not r['would']]
        reporte(antes, '  ANTES  (real)   ')
        reporte(despues, '  DESPUÉS (simulado)')
        ev_set = [r for r in evitadas if r['status'] in ('WON', 'LOST')]
        ev_loss = sum(1 for r in ev_set if r['status'] == 'LOST')
        ev_win = sum(1 for r in ev_set if r['status'] == 'WON')
        ev_pnl = sum(r['payout'] - r['stake'] for r in ev_set)
        print(f'  Evitadas: {len(evitadas)} ({ev_loss} perdidas, {ev_win} ganadas, '
              f'{len(evitadas)-len(ev_set)} OPEN) → P&L que se habría evitado: {ev_pnl:+,.0f} COP')

    # total
    print('\n' + '=' * 78)
    reporte([r for r in rows], 'TOTAL ANTES   ')
    reporte([r for r in rows if r['would']], 'TOTAL DESPUÉS ')

    # por usuario (hoy)
    print('\n── Por usuario (ambos días) ──')
    for u in sorted({r['user'] for r in rows}):
        sub = [r for r in rows if r['user'] == u]
        antes = sub
        despues = [r for r in sub if r['would']]
        a_set = [r for r in antes if r['status'] in ('WON', 'LOST')]
        d_set = [r for r in despues if r['status'] in ('WON', 'LOST')]
        a_wr = sum(1 for r in a_set if r['status'] == 'WON') / len(a_set) * 100 if a_set else 0
        d_wr = sum(1 for r in d_set if r['status'] == 'WON') / len(d_set) * 100 if d_set else 0
        a_pnl = sum(r['payout'] - r['stake'] for r in a_set)
        d_pnl = sum(r['payout'] - r['stake'] for r in d_set)
        print(f'  {u:22s} ANTES n={len(antes)} WR={a_wr:4.1f}% P&L={a_pnl:+9,.0f} | '
              f'DESPUÉS n={len(despues)} WR={d_wr:4.1f}% P&L={d_pnl:+9,.0f}')

    # por mercado (ambos días)
    print('\n── Por mercado (ambos días) ──')
    for m in sorted({r['mercado'] for r in rows}):
        sub = [r for r in rows if r['mercado'] == m]
        despues = [r for r in sub if r['would']]
        a_set = [r for r in sub if r['status'] in ('WON', 'LOST')]
        d_set = [r for r in despues if r['status'] in ('WON', 'LOST')]
        a_wr = sum(1 for r in a_set if r['status'] == 'WON') / len(a_set) * 100 if a_set else 0
        d_wr = sum(1 for r in d_set if r['status'] == 'WON') / len(d_set) * 100 if d_set else 0
        a_pnl = sum(r['payout'] - r['stake'] for r in a_set)
        d_pnl = sum(r['payout'] - r['stake'] for r in d_set)
        print(f'  {m:32s} ANTES n={len(sub):3d} WR={a_wr:4.1f}% P&L={a_pnl:+9,.0f} | '
              f'DESPUÉS n={len(despues):3d} WR={d_wr:4.1f}% P&L={d_pnl:+9,.0f}')

    # top pérdidas evitadas
    ev_todas = [r for r in rows if not r['would'] and r['status'] == 'LOST']
    ev_todas.sort(key=lambda r: r['payout'] - r['stake'])
    print('\n── Top 8 pérdidas evitadas por la nueva config ──')
    for r in ev_todas[:8]:
        print(f"  {r['dia']} {r['match'][:40]:40s} {r['mercado'][:28]:28s} "
              f"{r['stake']:,.0f} COP")

    print('\nNota: contrafactual limitado a las ofertas realmente apostadas '
          '(no hay snapshot de TODAS las ofertas de esa mañana).')


if __name__ == '__main__':
    main()
