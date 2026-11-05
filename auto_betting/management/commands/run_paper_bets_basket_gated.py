# -*- coding: utf-8 -*-
"""PAPER GATED: copia los picks del paper completo que pasan la compuerta.

No evalúa el feed ni crea picks propios: toma los PaperBet OPEN del motor
basket_1q2q creados en los últimos 30 minutos y clona solo los que cumplen
|Δ| en [3, 5] y EV >= 2%. El motor gated queda separado para comparar su ROI
forward contra el paper completo sin filtro.

Uso: manage.py run_paper_bets_basket_gated
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting import basket_1q2q as bk
from auto_betting.models import PaperBet

VENTANA_MINUTOS = 30


class Command(BaseCommand):
    help = ('PAPER GATED: clona los picks del paper basket_1q2q que pasan '
            '|Δ| 3-5 + EV>=2%, con motor basket_1q2q_gated.')

    def handle(self, *args, **options):
        ahora = timezone.now()
        raw = (PaperBet.objects
               .filter(motor=bk.MOTOR, estado='OPEN',
                       creado__gte=ahora - timedelta(minutes=VENTANA_MINUTOS))
               .order_by('creado'))

        nuevas = 0
        revisadas = 0
        for b in raw:
            revisadas += 1
            if b.diferencia is None or b.ev is None:
                continue
            delta = abs(float(b.diferencia))
            if delta < bk.GATE_DELTA_MIN or delta > bk.GATE_DELTA_MAX:
                continue
            if float(b.ev) < bk.GATE_EV_MIN:
                continue
            _, created = PaperBet.objects.get_or_create(
                motor=bk.MOTOR_GATED,
                evento_id=b.evento_id,
                defaults={
                    'start_time': b.start_time,
                    'home_team': b.home_team,
                    'away_team': b.away_team,
                    'liga': b.liga,
                    'mercado': b.mercado,
                    'seleccion': b.seleccion,
                    'linea': b.linea,
                    'diferencia': b.diferencia,
                    'cuota': b.cuota,
                    'prob': b.prob,
                    'ev': b.ev,
                    'stake': b.stake,
                    'pin_pregame_linea': b.pin_pregame_linea,
                    'pin_break_linea': b.pin_break_linea,
                    'pin_break_at': b.pin_break_at,
                },
            )
            if created:
                nuevas += 1

        self.stdout.write(
            f'Paper gated: {nuevas} nuevas de {revisadas} revisadas '
            f'(ventana {VENTANA_MINUTOS} min).')
