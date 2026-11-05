# -*- coding: utf-8 -*-
"""Reporte de cupones del motor pendientes de conciliación (solo lectura).

Uso:
  manage.py parley_reconcile
  manage.py parley_reconcile --usuario 9

Lista, para todos los usuarios (o uno):
- Cupones del motor en ERROR: la colocación fue ambigua (timeout/5xx o
  respuesta SUCCESS sin couponRef). Su ``key`` queda bloqueada a propósito para
  no duplicar; hay que revisar el historial de BetPlay (por requestId o por
  patas) y reconciliar a mano.
- Cupones del motor OPEN sin ``coupon_ref``: placeholder huérfano (el proceso
  murió antes de guardar la respuesta). También bloquea su key.

Este comando NO escribe nada: solo imprime el estado.
"""
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from parley_engine.models import ParleyCoupon


class Command(BaseCommand):
    help = 'Lista cupones del motor pendientes de conciliación (solo lectura).'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', type=int, default=0,
                            help='Solo ese usuario (pk). 0 = todos.')

    def handle(self, *args, **opts):
        qs = ParleyCoupon.objects.filter(is_motor=True)
        if opts['usuario']:
            if not get_user_model().objects.filter(pk=opts['usuario']).exists():
                raise CommandError(f'Usuario {opts["usuario"]} no existe')
            qs = qs.filter(usuario_id=opts['usuario'])

        errors = (qs.filter(status='ERROR')
                  .select_related('usuario').order_by('-creado'))
        stranded = (qs.filter(coupon_ref__isnull=True)
                    .exclude(status='ERROR')
                    .select_related('usuario').order_by('-creado'))

        self.stdout.write(
            f'parleys reconcile · {timezone.localtime():%Y-%m-%d %H:%M} Bogotá')
        self.stdout.write(f'\nERROR ambiguos: {errors.count()}')
        for c in errors:
            legs = ' | '.join(
                f'{l.get("h", "?")} vs {l.get("a", "?")} · {l.get("s", "?")}'
                for l in (c.legs or []))
            self.stdout.write(
                f'  #{c.pk} usuario={c.usuario.username} dia={c.dia} '
                f'key={c.key}\n'
                f'    requestId={c.request_id or "(sin requestId)"} '
                f'creado={c.creado:%Y-%m-%d %H:%M} stake={c.stake}\n'
                f'    patas: {legs or "(sin detalle)"}\n'
                f'    → revisar BetPlay: si la apuesta existe, enlazarla a '
                f'coupon_ref y liquidar a mano; si no existe, borrar el cupón.')

        self.stdout.write(f'\nOPEN sin coupon_ref (placeholder huérfano): '
                          f'{stranded.count()}')
        for c in stranded:
            self.stdout.write(
                f'  #{c.pk} usuario={c.usuario.username} dia={c.dia} '
                f'key={c.key} estado={c.status} '
                f'creado={c.creado:%Y-%m-%d %H:%M}')
            self.stdout.write('    → verificar en BetPlay; si no existe, '
                              'borrar el cupón para liberar la key.')

        if not errors.exists() and not stranded.exists():
            self.stdout.write('\nSin pendientes de conciliación.')
