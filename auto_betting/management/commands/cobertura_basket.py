# -*- coding: utf-8 -*-
"""Cobertura del paperbet de baloncesto (solo lectura).

Mide qué porcentaje de los partidos vistos EN VENTANA 2Q→3Q (snapshots
point-in-time) terminó con una apuesta registrada del motor basket_1q2q.
Objetivo operativo: 100 % de los partidos con mercado publicado.

Uso: manage.py cobertura_basket [--horas 24]
"""
from collections import defaultdict
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting import basket_1q2q as bk
from auto_betting.models import BasketMarketSnapshot, PaperBet


class Command(BaseCommand):
    help = ('Cobertura de apuestas sobre partidos en ventana (snapshots vs '
            'PaperBet). Solo lectura.')

    def add_arguments(self, parser):
        parser.add_argument('--horas', type=int, default=24,
                            help='Ventana de análisis en horas (default 24).')

    def handle(self, *args, **opts):
        desde = timezone.now() - timedelta(hours=opts['horas'])
        por_evento = {}
        for ev, liga in (BasketMarketSnapshot.objects
                         .filter(capturado_en__gte=desde)
                         .values_list('evento_id', 'clave_liga')
                         .distinct()):
            por_evento[ev] = liga or '?'
        if not por_evento:
            self.stdout.write(f'Cobertura {opts["horas"]}h: sin snapshots en ventana.')
            return

        con_apuesta = set(PaperBet.objects
                          .filter(motor=bk.MOTOR,
                                  evento_id__in=list(por_evento))
                          .values_list('evento_id', flat=True).distinct())
        total = len(por_evento)
        cubiertos = len(con_apuesta)
        pct = cubiertos / total * 100 if total else 0.0
        self.stdout.write(
            f'Cobertura {opts["horas"]}h: {cubiertos}/{total} partidos en '
            f'ventana con apuesta ({pct:.1f} %).')

        ligas = defaultdict(lambda: [0, 0])
        for ev, liga in por_evento.items():
            ligas[liga][0] += 1
            if ev in con_apuesta:
                ligas[liga][1] += 1
        for liga in sorted(ligas, key=lambda l: -ligas[l][0]):
            n, c = ligas[liga]
            self.stdout.write(f'  · {liga}: {c}/{n}')
