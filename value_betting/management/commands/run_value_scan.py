# -*- coding: utf-8 -*-
"""Escaneo de value betting (Kambi/BetPlay → predicciones → oportunidades).

Uso: manage.py run_value_scan
Programable desde el dispatcher (CronSchedule, tarea `run_value_scan`).
"""

from django.core.management.base import BaseCommand

from value_betting.services import run_scan


class Command(BaseCommand):
    help = 'Ejecuta el escaneo de value betting (refresca oportunidades del dashboard)'

    def handle(self, *args, **options):
        scan = run_scan()
        self.stdout.write(
            f'Scan #{scan.id} [{scan.status}] — {scan.matches_fetched} partidos, '
            f'{scan.matches_mapped} mapeados, {scan.predictions_generated} predicciones, '
            f'{scan.opportunities_found} oportunidades, {scan.value_bets_found} value bets'
            + (f' | errores: {scan.errors[:300]}' if scan.errors else '')
        )
