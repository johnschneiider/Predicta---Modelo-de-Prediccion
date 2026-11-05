# -*- coding: utf-8 -*-
"""Papertrading FX (Deriv) — motor `fx_deriv` con los 3 modelos de MT5 Quant Lab.

Revisa las velas del endpoint público de Deriv, reprocesa deterministicamente
las barras cerradas nuevas (desde FxEngineState.last_bar_t) y persiste
entradas/salidas en FxPaperTrade. Solo papel, sin dinero real.

Uso: manage.py run_paper_trades_fx [--dry-run] [--estrategia CLAVE]
"""
import argparse
import datetime as dt
import logging

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from auto_betting import fx_deriv as fx
from auto_betting.models import FxEngineState, FxPaperTrade

logger = logging.getLogger('auto_betting')


class Command(BaseCommand):
    help = 'Papertrading FX Deriv (MRGA H1/M5 + Donchian XAU H4) — solo papel.'

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Simula y muestra; no escribe nada.')
        parser.add_argument('--estrategia', default='',
                            help='Procesa solo esta clave (mrga_h1, mrga_m5, donchian_xau_h4).')
        parser.add_argument('--now-ts', type=float, default=0.0,
                            help=argparse.SUPPRESS)  # determinismo en tests

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        explicita = bool(opts['estrategia'])
        claves = [opts['estrategia']] if explicita else list(fx.STRATEGIES)
        for clave in claves:
            if clave not in fx.STRATEGIES:
                self.stderr.write(f'estrategia desconocida: {clave}')
                return
        now = opts['now_ts'] or timezone.now().timestamp()
        for clave in claves:
            abiertas = FxPaperTrade.objects.filter(
                estrategia=clave, estado='OPEN').exists()
            if (not explicita and clave in fx.ESTRATEGIAS_DEPRECADAS
                    and not abiertas):
                self.stdout.write(
                    f'fx {clave}: deprecada; sin posiciones abiertas, se omite')
                continue
            permitir_entradas = (explicita
                                 or clave not in fx.ESTRATEGIAS_DEPRECADAS)
            if clave in fx.ESTRATEGIAS_DEPRECADAS:
                self.stdout.write(
                    f'fx {clave}: deprecada; entradas '
                    + ('permitidas por --estrategia (manual)'
                       if explicita else 'suprimidas'))
            try:
                self._procesar(clave, now, dry,
                               permitir_entradas=permitir_entradas)
            except Exception as exc:  # noqa: BLE001 — una estrategia no tumba a las demás
                logger.exception('fx %s: error en la corrida', clave)
                self.stderr.write(f'fx {clave}: ERROR {exc.__class__.__name__}: {exc}')

    def _procesar(self, clave, now, dry, permitir_entradas=True):
        cfg = fx.STRATEGIES[clave]
        state = FxEngineState.objects.filter(estrategia=clave).first()
        if state is None:
            state = FxEngineState(estrategia=clave)

        abiertas = list(FxPaperTrade.objects.filter(estrategia=clave, estado='OPEN').order_by('-creado'))
        if len(abiertas) > 1:
            logger.warning('fx %s: %d posiciones OPEN; se usa la más reciente', clave, len(abiertas))
        posicion = None
        if abiertas:
            p = abiertas[0]
            posicion = dict(dir=p.direccion, entry=p.precio_entrada, sl=p.sl, tp=p.tp,
                            lots=p.lots, t_signal=p.t_signal,
                            t_entrada=int(p.t_entrada.timestamp()))

        candles = fx.fetch_candles(cfg['simbolo'], cfg['granularidad'], cfg['fetch_count'])
        if not candles:
            raise RuntimeError('Deriv devolvió 0 velas')
        if state.last_bar_t and candles[0]['t'] - state.last_bar_t > 2 * cfg['granularidad']:
            logger.warning('fx %s: hueco de datos (la ventana arranca en %s, cursor en %s)',
                           clave, candles[0]['t'], state.last_bar_t)

        eventos, nuevo = fx.replay(clave, candles, state.last_bar_t, state.balance,
                                   state.trades_today, state.dia_servidor, posicion, now)

        entradas = [e for e in eventos if e['tipo'] == 'entrada']
        salidas = [e for e in eventos if e['tipo'] == 'salida']
        if not permitir_entradas and entradas:
            self.stdout.write(
                f'fx {clave}: {len(entradas)} entrada(s) suprimida(s) '
                '(estrategia deprecada)')
            entradas = []
        prefijo = 'DRY-RUN ' if dry else ''
        self.stdout.write(
            f'{prefijo}fx {clave}: cursor {state.last_bar_t} → {nuevo["last_bar_t"]} · '
            f'entradas {len(entradas)} · salidas {len(salidas)} · balance {nuevo["balance"]:.2f}')
        for e in entradas:
            d = 'LONG' if e['direccion'] == 1 else 'SHORT'
            self.stdout.write(
                f'  {prefijo}ENTRADA {d} {cfg["simbolo"]} @ {e["precio_entrada"]:.5f} '
                f'SL {e["sl"]:.5f}{" TP %.5f" % e["tp"] if e["tp"] else ""} lots {e["lots"]} '
                f'({dt.datetime.fromtimestamp(e["t_entrada"], dt.timezone.utc):%Y-%m-%d %H:%M} UTC)')
        for e in salidas:
            self.stdout.write(
                f'  {prefijo}SALIDA {e["motivo"]} @ {e["precio_salida"]:.5f} '
                f'pnl {e["pnl"]:+.2f} · balance {e["balance_post"]:.2f} '
                f'({dt.datetime.fromtimestamp(e["t_salida"], dt.timezone.utc):%Y-%m-%d %H:%M} UTC)')

        if dry:
            return

        with transaction.atomic():
            for e in entradas:
                FxPaperTrade.objects.create(
                    estrategia=clave, simbolo=cfg['simbolo'], direccion=e['direccion'],
                    t_signal=e['trade_signal_t'],
                    t_entrada=dt.datetime.fromtimestamp(e['t_entrada'], dt.timezone.utc),
                    precio_entrada=e['precio_entrada'], sl=e['sl'], tp=e['tp'],
                    lots=e['lots'], estado='OPEN')
            for e in salidas:
                trade = (FxPaperTrade.objects
                         .filter(estrategia=clave, t_signal=e['trade_signal_t'])
                         .first())
                if trade is None:
                    logger.error('fx %s: salida sin operación para la señal %s',
                                 clave, e['trade_signal_t'])
                    continue
                trade.estado = 'CLOSED'
                trade.t_salida = dt.datetime.fromtimestamp(e['t_salida'], dt.timezone.utc)
                trade.precio_salida = e['precio_salida']
                trade.motivo = e['motivo']
                trade.pnl = e['pnl']
                trade.balance_post = e['balance_post']
                trade.save(update_fields=['estado', 't_salida', 'precio_salida',
                                          'motivo', 'pnl', 'balance_post'])
            if state.pk:
                FxEngineState.objects.filter(pk=state.pk).update(
                    balance=nuevo['balance'], last_bar_t=nuevo['last_bar_t'],
                    trades_today=nuevo['trades_today'], dia_servidor=nuevo['dia_servidor'],
                    ultimo_run=timezone.now())
            else:
                FxEngineState.objects.create(
                    estrategia=clave, balance=nuevo['balance'], last_bar_t=nuevo['last_bar_t'],
                    trades_today=nuevo['trades_today'], dia_servidor=nuevo['dia_servidor'],
                    ultimo_run=timezone.now())
