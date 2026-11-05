# -*- coding: utf-8 -*-
"""Reporte diario por liga del motor OU descanso (spec de ligas §8).

Tabla por liga del `LeagueRegistry` (SOLO LECTURA):

    liga | estado | n_limpios | n_shadow | n_paper | cobertura_línea | mismatch
         | margen_medio_vs_línea | rmse_modelo | rmse_linea | slope_b (IC95)
         | roi_plano | compuerta_siguiente | falta_para_pasar

Uso: manage.py reporte_ligas_ou [--liga X] [--csv]
"""
from django.core.management.base import BaseCommand

from auto_betting import basket_ou as ou
from auto_betting.ligas_ou import stats_liga
from auto_betting.models import LeagueRegistry


def _pct(v, dec=1):
    return 's/d' if v is None else f'{v * 100:.{dec}f}%'


def _num(v, dec=2):
    return 's/d' if v is None else f'{v:+.{dec}f}'


class Command(BaseCommand):
    help = 'Reporte diario de estado/compuertas por liga del motor OU.'

    def add_arguments(self, parser):
        parser.add_argument('--liga', action='append', default=None,
                            help='Filtrar por league_id (repetible).')
        parser.add_argument('--csv', action='store_true',
                            help='Salida CSV en vez de tabla markdown.')

    def handle(self, *args, **opts):
        regs = LeagueRegistry.objects.all()
        if opts['liga']:
            regs = regs.filter(league_id__in=opts['liga'])
        stats = [stats_liga(r) for r in regs]
        if not stats:
            self.stdout.write('reporte_ligas_ou: sin ligas en el registro.')
            return

        if opts['csv']:
            columnas = ['liga', 'estado', 'n_limpios', 'n_shadow', 'n_paper',
                        'cobertura_linea', 'mismatch', 'margen_medio',
                        'rmse_modelo', 'rmse_linea', 'slope_b',
                        'slope_b_lo', 'slope_b_hi', 'roi_plano',
                        'siguiente', 'falta']
            self.stdout.write(','.join(columnas))
            for s in stats:
                g = s['gates']
                sig = ou.siguiente_estado(s['estado'], g)
                falta = g['falta'].get({'DISCOVERY': 'G1', 'SHADOW': 'G2',
                                        'PAPER': 'G3'}.get(s['estado'], 'G1'), '')
                vals = [s['liga'], s['estado'], s['n_partidos_limpios'],
                        s['n_shadow'], s['n_paper'],
                        s['cobertura_linea_descanso'],
                        s['mismatch_reconciliacion'],
                        s['margen_medio_vs_linea'], s['rmse_modelo'],
                        s['rmse_linea'], s['slope_b'], s['slope_b_lo'],
                        s['slope_b_hi'], s['roi_plano'], sig,
                        falta.replace(',', ';')]
                self.stdout.write(','.join('' if v is None else str(v)
                                           for v in vals))
            return

        self.stdout.write('| Liga | Estado | n_limpios | n_shadow | n_paper | '
                          'Cob.línea | Mismatch | Margen/Línea | RMSE mod | '
                          'RMSE línea | slope_b (IC95) | ROI plano | '
                          'Siguiente | Falta para pasar |')
        self.stdout.write('|---|---|---|---|---|---|---|---|---|---|---|---|---|---|')
        for s in stats:
            g = s['gates']
            sig = ou.siguiente_estado(s['estado'], g)
            clave_falta = {'DISCOVERY': 'G1', 'SHADOW': 'G2',
                           'PAPER': 'G3'}.get(s['estado'], '')
            falta = g['falta'].get(clave_falta, '—') if clave_falta else '—'
            slope = 's/d' if s['slope_b'] is None else (
                f'{s["slope_b"]:+.3f} [{_num(s["slope_b_lo"], 3)}, '
                f'{_num(s["slope_b_hi"], 3)}]')
            self.stdout.write(
                f"| {s['liga']} | {s['estado']} | {s['n_partidos_limpios']} | "
                f"{s['n_shadow']} | {s['n_paper']} | "
                f"{_pct(s['cobertura_linea_descanso'])} | "
                f"{_pct(s['mismatch_reconciliacion'])} | "
                f"{_num(s['margen_medio_vs_linea'])} | "
                f"{_num(s['rmse_modelo'])} | {_num(s['rmse_linea'])} | "
                f"{slope} | {_pct(s['roi_plano'], 2)} | {sig} | {falta or '—'} |")
