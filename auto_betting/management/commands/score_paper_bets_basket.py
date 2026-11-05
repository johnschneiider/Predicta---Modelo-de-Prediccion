# -*- coding: utf-8 -*-
"""Liquida los PaperBet del motor basket_1q2q con resultados de API-Sports.

- Total final oficial (prórroga incluida), emparejando equipos por nombre
  (Jaccard ≥ 0.5 en AMBOS) en el día del partido y vecinos (±1 por husos).
- Push (total == línea) → VOID con stake devuelto.
- Sin resultado tras 40 h desde el inicio → VOID ('sin cobertura API').

Uso: manage.py score_paper_bets_basket [--days-back 10] [--dry-run]
"""
from datetime import timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting import basket_1q2q as bk
from auto_betting.models import PaperBet


class Command(BaseCommand):
    help = 'Liquida apuestas paper de baloncesto (motor basket_1q2q) con API-Sports.'

    def add_arguments(self, parser):
        parser.add_argument('--days-back', type=int, default=10,
                            help='Ventana de búsqueda de resultados en días (default 10).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra las liquidaciones sin escribir.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        abiertas = PaperBet.objects.filter(
            motor__in=(bk.MOTOR, bk.MOTOR_GATED), estado='OPEN')
        if not abiertas.exists():
            self.stdout.write('Sin apuestas OPEN de baloncesto.')
            return

        ahora = timezone.now()
        limite_dias = timedelta(days=opts['days_back'])
        n_won = n_lost = n_void = n_open = 0

        for bet in abiertas.order_by('start_time'):
            if not bet.start_time:
                self.stderr.write(f'id={bet.id}: sin start_time; se deja OPEN')
                n_open += 1
                continue
            edad = ahora - bet.start_time
            fecha = bet.start_time.astimezone(dt_timezone.utc).date()

            total = None
            if edad <= limite_dias:
                total = bk.resultado_oficial(bet.home_team, bet.away_team, fecha)

            if total is None:
                if edad > timedelta(hours=bk.STALE_VOID_HORAS):
                    estado, resultado = 'VOID', 'sin cobertura API'
                    payout = bet.stake
                    n_void += 1
                else:
                    n_open += 1
                    continue
            else:
                estado = bk.liquidar(bet.seleccion, bet.linea, total)
                if estado == 'VOID':
                    resultado = f'{total:g} · push (línea)'
                else:
                    resultado = f'{total:g} (línea {bet.linea:g})'
                payout = (bet.stake * bet.cuota if estado == 'WON'
                          else (bet.stake if estado == 'VOID' else 0.0))
                if estado == 'WON':
                    n_won += 1
                elif estado == 'LOST':
                    n_lost += 1
                else:
                    n_void += 1

            self.stdout.write(
                f"  {'DRY ' if dry else ''}[{estado}] id={bet.id} "
                f"{bet.home_team} vs {bet.away_team} — {bet.seleccion} "
                f"{bet.linea:g} @ {bet.cuota:.2f} → {resultado} "
                f"(payout {payout:.0f})")
            if dry:
                continue
            bet.estado = estado
            bet.resultado_real = resultado
            bet.payout = round(payout, 2)
            bet.settled_at = ahora
            bet.save(update_fields=['estado', 'resultado_real', 'payout',
                                    'settled_at'])

        self.stdout.write(
            f'Liquidadas: {n_won} WON · {n_lost} LOST · {n_void} VOID · '
            f'{n_open} siguen OPEN{" (dry-run, sin escribir)" if dry else ""}')
