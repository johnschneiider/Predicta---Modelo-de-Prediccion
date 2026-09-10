"""
today_detail.py — Detalle de las apuestas de HOY (Sep 3): resultado real vs
qué habría apostado el NUEVO esquema (P2a calibración + P3b submercados OFF
+ híbrido xG), apuesta por apuesta.
"""
import os
import sys

sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()

import logging
logging.disable(logging.WARNING)

from django.utils import timezone

from auto_betting.models import AutoBet, AutoBetConfig, HistorialApuesta
from auto_betting.strategy import select_bets, get_market_filters, get_global_config
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
SHORT = {
    'Total de goles': 'goles', 'Total de Tiros de Esquina': 'córners',
    'Total de tiros a puerta': 'tiros', 'Ambos Equipos Marcarán': 'btts',
}


def liga_de(ab):
    return ab.liga if isinstance(ab.liga, League) else League.objects.filter(name=ab.liga).first()


def main():
    hoy = timezone.now().date()
    qs = AutoBet.objects.filter(creado__date=hoy).order_by('usuario', 'creado')
    historial = {h.coupon_ref: h for h in HistorialApuesta.objects.filter(placed_date__date=hoy)}

    gcfg = get_global_config()
    cap = gcfg.get('calib_cap', 0.58)
    mf = {k: {**v, 'min_cuota': 0.0} for k, v in get_market_filters().items()}
    cuota_min = {c.usuario_id: c.cuota_minima for c in AutoBetConfig.objects.all()}

    cache = {}
    def oficial(home, away, liga, web_type):
        from ai_predictions.web_pipeline import build_web_predictions, get_official_prediction
        if not liga:
            return None
        key = (liga.id, home, away)
        if key not in cache:
            try:
                cache[key] = build_web_predictions(home, away, liga,
                                                   prediction_types=list(MERCADO_WEB.values()))
            except Exception:
                cache[key] = {}
        return get_official_prediction(cache[key], web_type)

    def simular(ab):
        key = MERCADO_KEY.get(ab.mercado)
        if not key:
            return None
        sel = ab.seleccion or ''
        side = ('over' if sel.startswith('Over') else 'under' if sel.startswith('Under')
                else 'Sí' if (sel.startswith('Sí') or sel.startswith('Si'))
                else 'No' if sel.startswith('No') else None)
        if not side:
            return None
        off = oficial(ab.home_team, ab.away_team, liga_de(ab), MERCADO_WEB[key])
        if not off or off.get('prediction') is None:
            return False
        conf = off.get('confidence', 0.5)
        cuota = ab.cuota or 0
        if key == 'btts':
            md = {'market': 'btts', 'type': 'btts', 'p_yes': float(off['prediction']),
                  'confidence': conf,
                  'odds': [{'type': 'OT_YES' if side == 'Sí' else 'OT_NO', 'odds_decimal': cuota}]}
        else:
            md = {'market': key, 'type': 'over_under', 'lambda': float(off['prediction']),
                  'confidence': conf,
                  'odds': [{'line': ab.linea,
                            'type': 'OT_OVER' if side == 'over' else 'OT_UNDER',
                            'odds_decimal': cuota}]}
        cands = select_bets([md], cuota_minima=cuota_min.get(ab.usuario_id, 2.0),
                            min_p=0.50, min_confidence=0.35, market_filters=mf, calib_cap=cap)
        return len(cands) > 0

    print(f"APUESTAS DE HOY ({hoy}) — esquema NUEVO vs REAL\n")
    print(f"{'user':22s} {'partido':34s} {'merc':7s} {'sel':9s} {'cuota':>5s} {'res':5s} {'nuevo':6s} {'pnl':>9s}")
    print('-' * 100)
    rows = []
    for ab in qs:
        h = historial.get(ab.coupon_ref)
        status = h.bet_status if h else 'OPEN'
        stake = (h.stake or 0) / 1000.0 if h else 0
        payout = (h.payout or 0) / 1000.0 if h else 0
        would = simular(ab)
        rows.append({'user': ab.usuario.username, 'match': f'{ab.home_team} vs {ab.away_team}',
                     'merc': SHORT.get(ab.mercado, ab.mercado), 'sel': ab.seleccion or '',
                     'cuota': ab.cuota or 0, 'status': status,
                     'pnl': payout - stake if status != 'OPEN' else None,
                     'would': would})
        w = 'SÍ' if would else ('no' if would is False else '—')
        pnl_s = f'{payout - stake:+9,.0f}' if status != 'OPEN' else '   OPEN'
        print(f"{rows[-1]['user'][:22]:22s} {rows[-1]['match'][:34]:34s} {rows[-1]['merc']:7s} "
              f"{rows[-1]['sel'][:9]:9s} {ab.cuota:5.2f} {status:5s} {w:6s} {pnl_s:>9s}")

    def resumen(sub, titulo):
        setts = [r for r in sub if r['status'] in ('WON', 'LOST')]
        won = sum(1 for r in setts if r['status'] == 'WON')
        wr = won / len(setts) * 100 if setts else 0
        pnl = sum(r['pnl'] for r in setts if r['pnl'] is not None)
        opens = sum(1 for r in sub if r['status'] == 'OPEN')
        print(f"\n{titulo}: {len(sub)} apuestas ({len(setts)} asentadas, {opens} OPEN) | "
              f"WR {wr:.1f}% | P&L {pnl:+,.0f} COP")

    resumen(rows, 'HOY REAL      ')
    resumen([r for r in rows if r['would']], 'HOY NUEVO ESQUEMA')

    evitadas = [r for r in rows if r['would'] is False]
    ev_set = [r for r in evitadas if r['status'] in ('WON', 'LOST')]
    ev_w = sum(1 for r in ev_set if r['status'] == 'WON')
    ev_l = sum(1 for r in ev_set if r['status'] == 'LOST')
    ev_open = sum(1 for r in evitadas if r['status'] == 'OPEN')
    ev_pnl = sum(r['pnl'] for r in ev_set if r['pnl'] is not None)
    print(f"\nEvitadas por el esquema nuevo: {len(evitadas)} "
          f"({ev_w} habrían ganado, {ev_l} habrían perdido, {ev_open} OPEN) | "
          f"P&L esquivado: {ev_pnl:+,.0f} COP")


if __name__ == '__main__':
    main()
