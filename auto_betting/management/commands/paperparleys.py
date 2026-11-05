# -*- coding: utf-8 -*-
"""PAPERPARLEYS — genera y liquida los parlays en papel del motor real.

Uso:
  manage.py paperparleys                      # generar HOY + liquidar + reporte
  manage.py paperparleys --backfill 2026-08-16   # backfill ate ayer
  manage.py paperparleys --dias 7             # backfill de los ultimos 7 dias
  manage.py paperparleys --fecha 2026-10-09   # (re)generar un dia puntual
  manage.py paperparleys --solo-settle        # solo liquidar PENDIENTE
  manage.py paperparleys --solo-reporte       # solo imprimir reporte
  manage.py paperparleys --usuario 1          # solo el usuario admin
"""
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting import paper_parleys as pp
from auto_betting.models import PPGenRun, PPParley


class Command(BaseCommand):
    help = 'Paperparleys: generar + liquidar parlays en papel (EV>=1.05)'

    def add_arguments(self, parser):
        parser.add_argument('--backfill', type=str, default='')
        parser.add_argument('--dias', type=int, default=0)
        parser.add_argument('--fecha', type=str, default='')
        parser.add_argument('--solo-settle', action='store_true')
        parser.add_argument('--solo-reporte', action='store_true')
        parser.add_argument('--min-legs', type=int, default=0)
        parser.add_argument('--max-legs', type=int, default=0)
        parser.add_argument('--ev-gate', type=float, default=0)
        parser.add_argument('--max-ev', type=float, default=0)
        parser.add_argument('--max-edge', type=float, default=0)
        parser.add_argument('--no-settle', action='store_true')
        parser.add_argument('--usuario', type=int, action='append',
                            help='Generar solo para este usuario_id (repetible)')

    def handle(self, *args, **opts):
        hoy = timezone.localdate()
        modo = 'LIVE' if not opts['backfill'] and not opts['dias'] else 'BACKFILL'
        min_legs = opts['min_legs'] or None
        max_legs = opts['max_legs'] or None
        ev_gate = opts['ev_gate'] or None
        max_ev = opts['max_ev'] or None
        max_edge = opts['max_edge'] or None
        usuario_ids = opts['usuario'] or None
        if opts['backfill']:
            desde = date.fromisoformat(opts['backfill'])
        elif opts['dias']:
            desde = hoy - timedelta(days=opts['dias'])
        else:
            desde = None

        args_str = ' '.join(
            f'{k}={v}' for k, v in opts.items() if v and v is not True)
        if opts['solo_settle']:
            self._settle(hoy)
            self._report(hoy)
            return
        if opts['solo_reporte']:
            self._report(hoy)
            return

        if desde:
            corriendo = desde
            while corriendo < hoy:
                res = pp.generate_day(corriendo, modo=modo, args=args_str,
                                      min_legs=min_legs, max_legs=max_legs,
                                      ev_gate=ev_gate, max_ev=max_ev,
                                      max_edge=max_edge,
                                      usuario_ids=usuario_ids)
                self.stdout.write(str(res))
                corriendo += timedelta(days=1)
        elif opts['fecha']:
            res = pp.generate_day(date.fromisoformat(opts['fecha']),
                                  modo='MANUAL', args=args_str,
                                  min_legs=min_legs, max_legs=max_legs,
                                  ev_gate=ev_gate, max_ev=max_ev,
                                  max_edge=max_edge,
                                  usuario_ids=usuario_ids)
            self.stdout.write(str(res))
        else:
            res = pp.generate_day(hoy, modo='LIVE', args=args_str,
                                  min_legs=min_legs, max_legs=max_legs,
                                  ev_gate=ev_gate, max_ev=max_ev,
                                  max_edge=max_edge,
                                  usuario_ids=usuario_ids)
            self.stdout.write(str(res))

        if not opts['no_settle']:
            self._settle(hoy)
        self._report(hoy)

    def _settle(self, hoy):
        st = pp.settle(dia_hasta=hoy)
        self.stdout.write(f'settle: {st}')

    def _report(self, hoy):
        desde = hoy - timedelta(days=30)
        qs = PPParley.objects.filter(dia__gte=desde)
        liq = qs.filter(estado__in=('GANADO', 'PERDIDO', 'PUSH'))
        n = liq.count()
        ganados = liq.filter(estado='GANADO').count()
        stake = sum(liq.values_list('stake', flat=True)) or 0
        payout = n and sum(liq.values_list('payout', flat=True)) or 0
        wr = round(100 * ganados / n, 1) if n else None
        roi = round(100 * (payout - stake) / stake, 1) if stake else None
        self.stdout.write(
            f'paperparleys 30d: n={n} wr={wr}% roi={roi}% '
            f'stake={stake:,} payout={payout:,.0f} '
            f'pendientes={qs.filter(estado="PENDIENTE").count()}')
