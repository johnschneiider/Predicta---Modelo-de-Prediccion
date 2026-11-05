# -*- coding: utf-8 -*-
"""ligas_ou.py — Estadísticas por liga del motor OU descanso (spec de ligas).

Recolecta, SOLO LECTURA, los stats que piden las compuertas G1/G2/G3 para una
liga del `LeagueRegistry`::

    n_partidos_limpios      capturas point-in-time completas (BasketMarketSnapshot)
    cobertura_linea_descanso  limpios / eventos vistos en ventana
    cobertura_periodos      BasketSample con Q1..Q4 completos
    mismatch_reconciliacion eventos con snapshot que no cuadran (Q1/Q2) contra
                            la fuente nocturna (join kambi|<evento_id>)
    n_shadow / n_paper      sombras y apuestas del motor para esa liga
    rmse_modelo / rmse_linea  RMSE(total - proy) vs RMSE(total - línea)
    slope_b (IC95)          regresión (total - línea) ~ (h1 - línea/2)
    margen_medio_vs_linea   puntos a favor del lado elegido (liquidadas)
    roi_plano               ROI del stake plano de las apuestas liquidadas

`stats_liga(registro)` devuelve el dict completo + `gates` (evaluar_compuerta).
"""
import math
import statistics

from auto_betting import basket_ou as ou
from auto_betting.models import (BasketMarketSnapshot, BasketOuShadow,
                                 BasketSample, PaperBet)


def _ultimo_snapshot_por_evento(league_id):
    """{evento_id: snapshot} con el ÚLTIMO snapshot de cada evento (sin filtro de fecha)."""
    ult = {}
    qs = (BasketMarketSnapshot.objects
          .filter(clave_liga=league_id)
          .order_by('capturado_en')
          .only('evento_id', 'linea', 'cuota_over', 'cuota_under', 'q1', 'q2'))
    for r in qs:
        ult[r.evento_id] = r
    return ult


def cobertura_captura(league_id):
    """(n_eventos, n_limpios, cobertura) de la captura en ventana 2Q→3Q.

    'Limpio' = último snapshot del evento con línea, ambas cuotas y q1/q2.
    Acumulado desde el inicio de la captura (no por fecha): la compuerta G1
    pide 30 partidos limpios históricos.
    """
    ult = _ultimo_snapshot_por_evento(league_id)
    n = len(ult)
    lim = sum(1 for r in ult.values()
              if None not in (r.linea, r.cuota_over, r.cuota_under,
                              r.q1, r.q2))
    return n, lim, (lim / n if n else None)


def reconciliacion(league_id):
    """(% mismatch Q1/Q2, n comparables) contra BasketSample (kambi|<id>)."""
    ult = {ev: r for ev, r in _ultimo_snapshot_por_evento(league_id).items()
           if r.q1 is not None and r.q2 is not None}
    if not ult:
        return None, 0
    claves = [f'kambi|{ev}' for ev in ult]
    muestras = {m.evento_clave: m for m in
                BasketSample.objects.filter(evento_clave__in=claves)}
    comparables = malos = 0
    for ev, r in ult.items():
        m = muestras.get(f'kambi|{ev}')
        if m is None or m.q1 is None or m.q2 is None:
            continue
        comparables += 1
        if abs(m.q1 - r.q1) > 0.02 or abs(m.q2 - r.q2) > 0.02:
            malos += 1
    return (malos / comparables if comparables else None), comparables


def cobertura_periodos(league_id):
    """Fracción de BasketSample (liga) con Q1..Q4 completos. None sin datos."""
    qs = BasketSample.objects.filter(liga=league_id)
    n = qs.count()
    if not n:
        return None
    return qs.filter(q3__isnull=False, q4__isnull=False).count() / n


def stats_motor(league_id, nper=4):
    """Sombras/apuestas del motor para la liga + RMSE, regresión y ROI."""
    qs = BasketOuShadow.objects.filter(clave_liga=league_id)
    n_shadow = qs.count()
    eventos = list(qs.values_list('evento_id', flat=True))
    bets = PaperBet.objects.filter(motor=ou.MOTOR, evento_id__in=eventos)

    errs_m, errs_l, xs, ys, margenes = [], [], [], [], []
    for sh in qs.filter(settled_at__isnull=False):
        total = sh.total_reg if sh.total_reg is not None else sh.total_ot
        if total is None or sh.linea is None:
            continue
        if sh.lado in ('OVER', 'UNDER'):
            margenes.append((1 if sh.lado == 'OVER' else -1)
                            * (total - sh.linea))
        if sh.proy is not None:
            errs_m.append(total - sh.proy)
        errs_l.append(total - sh.linea)
        if None not in (sh.q1h, sh.q1a, sh.q2h, sh.q2a):
            h1 = sh.q1h + sh.q1a + ((sh.q2h + sh.q2a) if nper >= 4 else 0.0)
            xs.append(h1 - sh.linea / 2)
            ys.append(total - sh.linea)

    liq = bets.filter(estado__in=['WON', 'LOST'])
    stake = sum(b.stake or 0 for b in liq)
    payout = sum(b.payout or 0 for b in liq)
    reg = ou.regresion_simple(xs, ys)

    def _rmse(errs):
        return math.sqrt(statistics.fmean(e * e for e in errs)) if errs else None

    return {
        'n_shadow': n_shadow,
        'n_paper': liq.count(),
        'rmse_modelo': _rmse(errs_m),
        'rmse_linea': _rmse(errs_l),
        'slope_b': (reg or {}).get('b'),
        'slope_b_lo': (reg or {}).get('lo'),
        'slope_b_hi': (reg or {}).get('hi'),
        'margen_medio_vs_linea': (statistics.fmean(margenes)
                                  if margenes else None),
        'roi_plano': ((payout - stake) / stake if stake else None),
    }


def stats_liga(reg) -> dict:
    """Stats completos + compuertas de una liga del registro."""
    cfg = reg.config_efectiva() or {'estructura': reg.estructura}
    n_ev, n_limpios, cob_linea = cobertura_captura(reg.league_id)
    mism, n_recon = reconciliacion(reg.league_id)
    s = {
        'liga': reg.league_id,
        'nombre': reg.nombre or reg.league_id,
        'estado': reg.estado,
        'n_eventos_ventana': n_ev,
        'n_partidos_limpios': n_limpios,
        'cobertura_linea_descanso': cob_linea,
        'cobertura_periodos': cobertura_periodos(reg.league_id),
        'mismatch_reconciliacion': mism,
        'n_reconciliados': n_recon,
    }
    s.update(stats_motor(reg.league_id, ou.n_periodos_de(cfg)))
    s['gates'] = ou.evaluar_compuerta(s)
    return s
