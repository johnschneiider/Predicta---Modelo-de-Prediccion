# -*- coding: utf-8 -*-
"""Sincroniza cupones combinados de BetPlay y liquida el ledger de parleys.

Solo escribe en las tablas de parley_engine. No toca HistorialApuesta,
AutoBet, AutoBetConfig ni el motor real.

Multi-usuario: sincroniza a todos los usuarios con ParleyEngineConfig activa.
Un fallo (ticket vencido, API) no aborta a los demás.
"""
import fcntl
import logging
import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from auto_betting.models import AutoBetConfig
from auto_betting.services import login

from parley_engine.models import ParleyCoupon, ParleyEngineConfig
from parley_engine.services import RateLimitedClient, sync_history

logger = logging.getLogger('parley_engine')
LOCK_PATH = '/var/www/predicta.com.co/logs/real_parleys.lock'


class Command(BaseCommand):
    help = 'Sincroniza cupones combinados y liquida el ledger de parleys.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', type=int, default=0,
                            help='Solo ese usuario (pk). 0 = todos los activos.')

    def handle(self, *args, **opts):
        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        lock = open(LOCK_PATH, 'w')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.stdout.write('parleys sync: ya hay una corrida en curso')
            lock.close()
            return

        try:
            users = self._target_users(opts)
            if not users:
                self.stdout.write('parleys sync: sin usuarios activos')
                return
            for user in users:
                try:
                    self._sync_user(user)
                except Exception as exc:
                    logger.exception('sync parleys falló para %s', user)
                    self.stderr.write(
                        f'parleys sync {user.username}: '
                        f'{type(exc).__name__}: {exc}')
        finally:
            lock.close()

    def _target_users(self, opts):
        User = get_user_model()
        if opts['usuario']:
            user = User.objects.filter(pk=opts['usuario']).first()
            if user is None:
                raise CommandError(f'Usuario {opts["usuario"]} no existe')
            return [user]
        return [cfg.usuario for cfg in (
            ParleyEngineConfig.objects.filter(activo=True)
            .select_related('usuario').order_by('usuario_id'))]

    def _sync_user(self, user):
        config = ParleyEngineConfig.objects.filter(
            usuario=user, activo=True).first()
        if config is None:
            self.stdout.write(
                f'parleys sync {user.username}: motor inactivo/sin config')
            return
        ac = AutoBetConfig.objects.filter(usuario=user).first()
        if not ac or not ac.ticket:
            self.stdout.write(
                f'parleys sync {user.username}: sin AutoBetConfig/ticket')
            return
        token, _ = login(ac.ticket, ac.punter_id)
        if not token:
            self.stdout.write(
                f'parleys sync {user.username}: login BetPlay falló '
                f'(ticket vencido)')
            return
        client = RateLimitedClient(
            requests_per_minute=config.requests_per_minute,
            max_backoff=config.max_backoff_seconds,
            timeout=config.request_timeout)
        n = sync_history(user, client, token, range_size=1000)
        self.stdout.write(
            f'parleys sync {user.username}: {n} cupones actualizados')
        pending = (ParleyCoupon.objects
                   .filter(usuario=user, is_motor=True, status='ERROR')
                   .count())
        if pending:
            self.stdout.write(
                f'parleys sync {user.username}: {pending} cupones ERROR '
                f'pendientes de conciliación (ver manage.py parley_reconcile)')
