# -*- coding: utf-8 -*-
"""Liquida (respaldo) las apuestas y sombras del motor basket_ou con API-Sports.

El bot liquida con el propio feed cuando el partido termina; este comando cubre
los casos en que el feed ya no traiga el partido (nombre Jaccard >= 0.5 en
AMBOS equipos, día del partido ±1).

- Push (total == línea) → VOID con stake devuelto (apuestas) / ganancia 0 (sombras).
- Sin resultado tras 40 h desde el inicio → VOID ('sin cobertura API').

Uso: manage.py score_paper_bets_ou [--days-back 10] [--dry-run]
"""
from datetime import timedelta, timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting import basket_1q2q as bk
from auto_betting import basket_ou as ou
from auto_betting.models import BasketOuShadow, PaperBet


class Command(BaseCommand):
    help = 'Liquida apuestas paper OU descanso (motor basket_ou) con API-Sports.'

    def add_arguments(self, parser):
        parser.add_argument('--days-back', type=int, default=10,
                            help='Ventana de búsqueda de resultados (días).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Muestra las liquidaciones sin escribir.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        ahora = timezone.now()
        limite = timedelta(days=opts['days_back'])
        n_won = n_lost = n_void = n_open = 0

        for bet in (PaperBet.objects.filter(motor=ou.MOTOR, estado='OPEN')
                    .order_by('start_time')):
            if not bet.start_time:
                self.stderr.write(f'id={bet.id}: sin start_time; se deja OPEN')
                n_open += 1
                continue
            edad = ahora - bet.start_time
            fecha = bet.start_time.astimezone(dt_timezone.utc).date()
            total = (bk.resultado_oficial(bet.home_team, bet.away_team, fecha)
                     if edad <= limite else None)
            if total is None:
                if edad > timedelta(hours=bk.STALE_VOID_HORAS):
                    estado, resultado = 'VOID', 'sin cobertura API'
                    payout = float(bet.stake)
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
                if estado == 'WON':
                    payout = bet.stake * bet.cuota
                    n_won += 1
                elif estado == 'LOST':
                    payout = 0.0
                    n_lost += 1
                else:
                    payout = float(bet.stake)
                    n_void += 1
            self.stdout.write(
                f"  {'DRY ' if dry else ''}[{estado}] id={bet.id} "
                f'{bet.home_team} vs {bet.away_team} — {bet.seleccion} '
                f'{bet.linea:g} @ {bet.cuota:.2f} → {resultado}')
            if dry:
                continue
            bet.estado = estado
            bet.resultado_real = resultado
            bet.payout = round(payout, 2)
            bet.settled_at = ahora
            bet.save(update_fields=['estado', 'resultado_real', 'payout',
                                    'settled_at'])

        # Sombras (decisión registrada aunque no fuera apuesta) — resultado real
        n_sh = 0
        sombras = (BasketOuShadow.objects.filter(settled_at__isnull=True)
                   .exclude(lado='').order_by('start_time'))
        for sh in sombras:
            if not sh.start_time:
                continue
            edad = ahora - sh.start_time
            fecha = sh.start_time.astimezone(dt_timezone.utc).date()
            total = (bk.resultado_oficial(sh.home_team, sh.away_team, fecha)
                     if edad <= limite else None)
            if total is None:
                if edad > timedelta(hours=bk.STALE_VOID_HORAS):
                    res, gan = 'VOID', None
                else:
                    continue
            else:
                res, gan = ou.liquidar_apuesta(sh.lado, sh.linea, total,
                                               sh.odds_side)
            self.stdout.write(
                f"  {'DRY ' if dry else ''}[shadow {res}] id={sh.id} "
                f'{sh.home_team} vs {sh.away_team} — {sh.lado} {sh.linea:g} '
                f'→ total {total if total is not None else "s/d"}')
            if dry:
                continue
            BasketOuShadow.objects.filter(pk=sh.pk,
                                          settled_at__isnull=True).update(
                total_ot=total, resultado=res,
                ganancia_u=(None if gan is None else round(gan, 4)),
                settled_at=ahora)
            n_sh += 1

        self.stdout.write(
            f'Liquidadas: {n_won} WON · {n_lost} LOST · {n_void} VOID · '
            f'{n_open} siguen OPEN · sombras: {n_sh}'
            f'{" (dry-run, sin escribir)" if dry else ""}')
