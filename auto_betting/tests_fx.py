# -*- coding: utf-8 -*-
"""Tests del motor fx_deriv (papertrading FX Deriv — MT5 Quant Lab).

Cubren:
  * Indicadores (Bollinger SMA/σ, RSI Wilder, ATR SMA) y hora servidor EET.
  * Fidelidad cruzada: el replay del motor reproduce EXACTAMENTE los agregados
    del backtest independiente (/root/opencode/deriv-backtest) sobre dos
    rebanadas reales congeladas en tests_fx_fixtures.json (sin EOW, planas al
    final): MRGA M5 → 7 ops / 1 win / −348.00 USD; Donchian → 21 ops / 6 wins /
    −259.43 USD.
  * Determinismo: replay partido en dos corridas = replay completo.
  * Mecánica: entrada a la apertura siguiente (con spread), TP/SL, sesión
    9-20 servidor, tope diario, Donchian canal reverso + regla de no
    re-entrada en la misma barra, SL prioritario sobre el canal.
  * Comando: dry-run no escribe; corrida real escribe, es idempotente y
    reanudar en dos corridas da el mismo resultado que una.
  * Modelo: unique (estrategia, t_signal).
  * Página /auto-betting/papertrading/ + enlace desde el paperbet general.
"""
import argparse  # noqa: F401 — usado indirectamente vía --now-ts
import json
import os
import random
from datetime import datetime, timezone as dt_timezone
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone

from auto_betting import fx_deriv as fx
from auto_betting.models import CronSchedule, FxEngineState, FxPaperTrade

FIX = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                  'tests_fx_fixtures.json')))


def _fixture_candles(f):
    return [dict(t=c[0], o=c[1], h=c[2], l=c[3], c=c[4]) for c in f['candles']]


class TestIndicadores(TestCase):
    def test_sma_std(self):
        mid, dev = fx.sma_std([1, 2, 3, 4, 5, 6], 3)
        self.assertIsNone(mid[1])
        self.assertEqual(mid[2], 2.0)
        self.assertAlmostEqual(dev[2], (2.0 / 3.0) ** 0.5, places=12)
        self.assertEqual(mid[5], 5.0)

    def test_rsi_100_en_subida_pura(self):
        out = fx.rsi_wilder([1, 2, 3, 4, 5, 6], 2)
        self.assertEqual(out[2], 100.0)

    def test_rsi_50_serrucho(self):
        out = fx.rsi_wilder([10, 11, 10, 11, 10, 11], 2)
        self.assertAlmostEqual(out[2], 50.0, places=9)  # ventana inicial: ag=al
        self.assertAlmostEqual(out[3], 75.0, places=9)  # Wilder: ag=(0.5+1)/2, al=0.25

    def test_atr_sma(self):
        c = [dict(t=i, o=9 + i, h=10 + i, l=8 + i, c=9 + i) for i in range(6)]
        atr = fx.atr_sma(c, 3)
        self.assertAlmostEqual(atr[3], 2.0, places=12)  # TR constante = h-l = 2

    def test_hora_servidor_dst(self):
        inv = datetime(2026, 1, 15, 10, 0, tzinfo=dt_timezone.utc).timestamp()
        ver = datetime(2026, 7, 15, 10, 0, tzinfo=dt_timezone.utc).timestamp()
        self.assertEqual(fx.server_offset_hours(inv), 2)
        self.assertEqual(fx.server_offset_hours(ver), 3)
        self.assertEqual(fx.server_hour(inv), 12)
        self.assertEqual(fx.server_hour(ver), 13)

    def test_size_lots_eurusd_y_xau(self):
        # EURUSD M5 TP25/SL10: 1% de 10.000 / (10 pips × $10) = 1.0 lote
        self.assertEqual(fx.size_lots('mrga_m5', 10000.0, 10 * fx.PIP), 1.0)
        # XAU: stop de 2.05 USD → riesgo 100 / (2.05 × 100) = 0.4878 → 0.48 (floor)
        self.assertEqual(fx.size_lots('donchian_xau_h4', 10000.0, 2.05), 0.48)


def _serie_mrga(n=40, seed=1):
    """Caminata aleatoria reproducible; la primera señal (i=36, LONG) está
    congelada por contrato en los tests de mecánica."""
    r = random.Random(seed)
    closes = [1.1000]
    for _ in range(n - 1):
        closes.append(round(closes[-1] + r.uniform(-1, 1) * 0.0004, 6))
    return closes


def _primer_senal(closes):
    mid, dev = fx.sma_std(closes, fx.BB_PERIOD)
    rsi = fx.rsi_wilder(closes, fx.RSI_PERIOD)
    for i in range(30, len(closes)):
        if mid[i] is None or rsi[i] is None:
            continue
        lo_i = mid[i] - fx.BB_DEV * dev[i]
        lo_p = mid[i - 1] - fx.BB_DEV * dev[i - 1]
        up_i = mid[i] + fx.BB_DEV * dev[i]
        up_p = mid[i - 1] + fx.BB_DEV * dev[i - 1]
        if closes[i - 1] > lo_p and closes[i] <= lo_i and rsi[i] <= fx.RSI_LOW:
            return i, 1
        if closes[i - 1] < up_p and closes[i] >= up_i and rsi[i] >= fx.RSI_HIGH:
            return i, -1
    return None, None


class TestMecanicaMRGA(TestCase):
    CIERRE = 'TP'

    def _candles(self, hora_utc=12):
        closes_full = _serie_mrga()
        i0, direccion = _primer_senal(closes_full)
        self.assertEqual((i0, direccion), (36, 1))  # contrato de la serie
        closes = closes_full[:i0 + 1]              # serie estrictamente ordenada
        fecha = datetime(2026, 7, 15, hora_utc, 0, tzinfo=dt_timezone.utc)
        t0 = int(fecha.timestamp()) - (i0 + 1) * 300
        candles = []
        for i, c in enumerate(closes):
            o = closes[i - 1] if i else c
            candles.append(dict(t=t0 + i * 300, o=o, h=max(o, c) + 0.00015,
                                l=min(o, c) - 0.00015, c=c))
        o_ent = closes[i0]
        candles.append(dict(t=t0 + (i0 + 1) * 300, o=o_ent, h=o_ent + 0.0002,
                            l=o_ent - 0.0002, c=o_ent))
        if self.CIERRE == 'TP':
            candles.append(dict(t=t0 + (i0 + 2) * 300, o=o_ent, h=o_ent + 0.0030,
                                l=o_ent + 0.0005, c=o_ent + 0.0020))
        elif self.CIERRE == 'SL':
            candles.append(dict(t=t0 + (i0 + 2) * 300, o=o_ent, h=o_ent + 0.0010,
                                l=o_ent - 0.0015, c=o_ent - 0.0005))
        else:  # 'NADA': sigue dentro de rango
            candles.append(dict(t=t0 + (i0 + 2) * 300, o=o_ent, h=o_ent + 0.0005,
                                l=o_ent - 0.0005, c=o_ent))
        return candles, i0

    def _replay(self, candles):
        return fx.replay('mrga_m5', candles, candles[0]['t'] - 1, fx.INIT_BALANCE,
                         0, '', None, candles[-1]['t'] + 300)

    def test_entrada_y_tp(self):
        candles, i0 = self._candles()
        ev, st = self._replay(candles)
        entradas = [e for e in ev if e['tipo'] == 'entrada']
        salidas = [e for e in ev if e['tipo'] == 'salida']
        self.assertEqual(len(entradas), 1)
        e = entradas[0]
        self.assertEqual(e['trade_signal_t'], candles[i0]['t'])
        self.assertEqual(e['t_entrada'], candles[i0 + 1]['t'])
        self.assertAlmostEqual(e['precio_entrada'],
                               candles[i0 + 1]['o'] + fx.SPREADS['frxEURUSD'], places=9)
        self.assertAlmostEqual(e['sl'], e['precio_entrada'] - 10 * fx.PIP, places=9)
        self.assertAlmostEqual(e['tp'], e['precio_entrada'] + 25 * fx.PIP, places=9)
        self.assertEqual(e['lots'], 1.0)
        self.assertEqual(len(salidas), 1)
        self.assertEqual(salidas[0]['motivo'], 'TP')
        self.assertAlmostEqual(salidas[0]['pnl'], 250.0, places=2)
        self.assertAlmostEqual(st['balance'], 10250.0, places=2)
        self.assertIsNone(st['posicion'])

    def test_entrada_y_sl(self):
        self.CIERRE = 'SL'
        candles, i0 = self._candles()
        ev, st = self._replay(candles)
        salidas = [e for e in ev if e['tipo'] == 'salida']
        self.assertEqual(len(salidas), 1)
        self.assertEqual(salidas[0]['motivo'], 'SL')
        self.assertAlmostEqual(salidas[0]['pnl'], -100.0, places=2)
        self.assertAlmostEqual(st['balance'], 9900.0, places=2)

    def test_sesion_bloquea_fuera_de_9_20_servidor(self):
        candles, _ = self._candles(hora_utc=3)   # 03:00 UTC = 06:00 EEST → fuera
        ev, _ = self._replay(candles)
        self.assertEqual([e for e in ev if e['tipo'] == 'entrada'], [])
        candles, _ = self._candles(hora_utc=12)  # 12:00 UTC = 15:00 EEST → dentro
        ev, _ = self._replay(candles)
        self.assertEqual(len([e for e in ev if e['tipo'] == 'entrada']), 1)

    def test_tope_diario_bloquea(self):
        candles, i0 = self._candles()
        dia = fx.server_date(candles[i0 + 1]['t'])
        ev, st = fx.replay('mrga_m5', candles, candles[0]['t'] - 1, fx.INIT_BALANCE,
                           10, dia, None, candles[-1]['t'] + 300)
        self.assertEqual([e for e in ev if e['tipo'] == 'entrada'], [])


class TestMecanicaDonchian(TestCase):
    def _candles(self, l34=99.6, c34=99.0):
        base_t = int(datetime(2026, 7, 15, 0, 0, tzinfo=dt_timezone.utc).timestamp())
        base = [dict(t=base_t + i * 14400, o=100.0, h=100.5, l=99.5, c=100.0) for i in range(21)]
        base.append(dict(t=base_t + 21 * 14400, o=100.0, h=101.4, l=99.9, c=101.0))
        base += [dict(t=base_t + (22 + k) * 14400, o=101.0, h=101.3, l=100.4, c=101.0)
                 for k in range(12)]
        base.append(dict(t=base_t + 34 * 14400, o=101.0, h=101.0, l=l34, c=c34))
        base.append(dict(t=base_t + 35 * 14400, o=99.0, h=99.5, l=97.5, c=98.0))
        base.append(dict(t=base_t + 36 * 14400, o=98.0, h=98.2, l=97.0, c=97.5))
        return base

    def _replay(self, candles):
        return fx.replay('donchian_xau_h4', candles, candles[0]['t'] - 1,
                         fx.INIT_BALANCE, 0, '', None, candles[-1]['t'] + 14400)

    def test_canal_reverso_y_no_rentra_misma_barra(self):
        candles = self._candles()
        ev, st = self._replay(candles)
        entradas = [e for e in ev if e['tipo'] == 'entrada']
        salidas = [e for e in ev if e['tipo'] == 'salida']
        self.assertEqual(len(entradas), 2)
        largo, corto = entradas
        self.assertEqual(largo['direccion'], 1)
        self.assertAlmostEqual(largo['precio_entrada'], 101.6, places=6)
        self.assertAlmostEqual(largo['sl'], 99.55, places=6)
        self.assertEqual(largo['lots'], 0.48)
        self.assertEqual(len(salidas), 1)
        self.assertEqual(salidas[0]['motivo'], 'CHANNEL')
        self.assertAlmostEqual(salidas[0]['precio_salida'], 99.0, places=6)
        self.assertAlmostEqual(salidas[0]['pnl'], -124.8, places=2)
        # La salida por canal cierra en t35; la señal bajista de la MISMA barra
        # (t34) se ignora: el corto entra señalado en t35 y ejecutado en t36.
        self.assertEqual(corto['direccion'], -1)
        self.assertEqual(corto['trade_signal_t'], candles[35]['t'])
        self.assertEqual(corto['t_entrada'], candles[36]['t'])
        self.assertAlmostEqual(corto['precio_entrada'], 98.0 - fx.SPREADS['frxXAUUSD'], places=6)
        self.assertIsNotNone(st['posicion'])

    def test_sl_prioritario_sobre_canal(self):
        candles = self._candles(l34=98.9)
        ev, st = self._replay(candles)
        entradas = [e for e in ev if e['tipo'] == 'entrada']
        salidas = [e for e in ev if e['tipo'] == 'salida']
        self.assertEqual(len(salidas), 1)
        self.assertEqual(salidas[0]['motivo'], 'SL')
        self.assertAlmostEqual(salidas[0]['precio_salida'], 99.55, places=6)
        self.assertAlmostEqual(salidas[0]['pnl'], -98.4, places=2)
        # tras SL (cierre dentro de la barra 34) sí se evalúa señal en t34 → corto en t35
        self.assertEqual(len(entradas), 2)
        self.assertEqual(entradas[1]['trade_signal_t'], candles[34]['t'])
        self.assertEqual(entradas[1]['t_entrada'], candles[35]['t'])


class TestFidelidadCruzada(TestCase):
    """Reproduce los agregados del backtest independiente sobre rebanadas reales."""

    def test_mrga_m5_rebanada_real(self):
        f = FIX['mrga_m5']
        candles = _fixture_candles(f)
        ev, st = fx.replay('mrga_m5', candles, f['t0'] - 1, fx.INIT_BALANCE, 0, '', None,
                           f['t1'] + 300)
        entradas = [e for e in ev if e['tipo'] == 'entrada']
        salidas = [e for e in ev if e['tipo'] == 'salida']
        self.assertEqual(len(entradas), 7)
        self.assertEqual(len(salidas), 7)
        self.assertEqual(sum(1 for e in salidas if e['pnl'] > 0), 1)
        self.assertAlmostEqual(sum(e['pnl'] for e in salidas), -348.0, places=2)
        self.assertAlmostEqual(st['balance'], 9652.0, places=2)
        self.assertIsNone(st['posicion'])

    def test_donchian_rebanada_real(self):
        f = FIX['donchian_xau_h4']
        candles = _fixture_candles(f)
        ev, st = fx.replay('donchian_xau_h4', candles, f['t0'] - 1, fx.INIT_BALANCE, 0, '', None,
                           f['t1'] + 14400)
        entradas = [e for e in ev if e['tipo'] == 'entrada']
        salidas = [e for e in ev if e['tipo'] == 'salida']
        self.assertEqual(len(entradas), 21)
        self.assertEqual(len(salidas), 21)
        self.assertEqual(sum(1 for e in salidas if e['pnl'] > 0), 6)
        self.assertAlmostEqual(sum(e['pnl'] for e in salidas), -259.43, places=2)
        self.assertAlmostEqual(st['balance'], 9740.57, places=2)
        self.assertIsNone(st['posicion'])

    def test_replay_dividido_igual_a_completo(self):
        f = FIX['mrga_m5']
        candles = _fixture_candles(f)
        ev_all, st_all = fx.replay('mrga_m5', candles, f['t0'] - 1, fx.INIT_BALANCE, 0, '', None,
                                   f['t1'] + 300)
        mid = candles[len(candles) // 2]['t']
        ev_a, st_a = fx.replay('mrga_m5', candles, f['t0'] - 1, fx.INIT_BALANCE, 0, '', None, mid)
        ev_b, st_b = fx.replay('mrga_m5', candles, st_a['last_bar_t'], st_a['balance'],
                               st_a['trades_today'], st_a['dia_servidor'], st_a['posicion'],
                               f['t1'] + 300)
        self.assertEqual(ev_a + ev_b, ev_all)
        self.assertEqual(st_b['balance'], st_all['balance'])
        self.assertEqual(st_b['last_bar_t'], st_all['last_bar_t'])
        self.assertEqual(st_b['posicion'], st_all['posicion'])


class TestComando(TestCase):
    def _fetch(self, f):
        return _fixture_candles(f)

    @mock.patch('auto_betting.fx_deriv.fetch_candles')
    def test_dry_run_no_escribe(self, fetch):
        f = FIX['mrga_m5']
        fetch.return_value = self._fetch(f)
        FxEngineState.objects.create(estrategia='mrga_m5', balance=fx.INIT_BALANCE,
                                     last_bar_t=f['t0'] - 1)
        out = StringIO()
        call_command('run_paper_trades_fx', '--estrategia', 'mrga_m5', '--dry-run',
                     '--now-ts', str(f['t1'] + 300), stdout=out)
        self.assertEqual(FxPaperTrade.objects.count(), 0)
        self.assertIn('DRY-RUN', out.getvalue())
        self.assertIn('entradas 7', out.getvalue())
        st = FxEngineState.objects.get(estrategia='mrga_m5')
        self.assertEqual(st.last_bar_t, f['t0'] - 1)  # el dry-run no avanza el cursor

    @mock.patch('auto_betting.fx_deriv.fetch_candles')
    def test_corrida_escribe_y_es_idempotente(self, fetch):
        f = FIX['mrga_m5']
        fetch.return_value = self._fetch(f)
        FxEngineState.objects.create(estrategia='mrga_m5', balance=fx.INIT_BALANCE,
                                     last_bar_t=f['t0'] - 1)
        call_command('run_paper_trades_fx', '--estrategia', 'mrga_m5',
                     '--now-ts', str(f['t1'] + 300), stdout=StringIO())
        st = FxEngineState.objects.get(estrategia='mrga_m5')
        self.assertEqual(FxPaperTrade.objects.count(), 7)
        self.assertEqual(FxPaperTrade.objects.filter(estado='CLOSED').count(), 7)
        self.assertEqual(FxPaperTrade.objects.filter(estado='OPEN').count(), 0)
        self.assertEqual(st.last_bar_t, f['t1'])
        self.assertAlmostEqual(st.balance, 9652.0, places=2)
        call_command('run_paper_trades_fx', '--estrategia', 'mrga_m5',
                     '--now-ts', str(f['t1'] + 600), stdout=StringIO())
        self.assertEqual(FxPaperTrade.objects.count(), 7)
        st.refresh_from_db()
        self.assertAlmostEqual(st.balance, 9652.0, places=2)

    @mock.patch('auto_betting.fx_deriv.fetch_candles')
    def test_reanudar_en_dos_corridas(self, fetch):
        f = FIX['mrga_m5']
        candles = self._fetch(f)
        fetch.return_value = candles
        # motor ya activado: cursor justo antes de la rebanada
        FxEngineState.objects.create(estrategia='mrga_m5', balance=fx.INIT_BALANCE,
                                     last_bar_t=f['t0'] - 1)
        mid = candles[len(candles) // 2]['t']
        call_command('run_paper_trades_fx', '--estrategia', 'mrga_m5',
                     '--now-ts', str(mid), stdout=StringIO())
        call_command('run_paper_trades_fx', '--estrategia', 'mrga_m5',
                     '--now-ts', str(f['t1'] + 300), stdout=StringIO())
        st = FxEngineState.objects.get(estrategia='mrga_m5')
        self.assertEqual(FxPaperTrade.objects.count(), 7)
        self.assertEqual(FxPaperTrade.objects.filter(estado='OPEN').count(), 0)
        self.assertAlmostEqual(st.balance, 9652.0, places=2)
        self.assertEqual(st.last_bar_t, f['t1'])

    def test_unique_estrategia_senal(self):
        ahora = timezone.now()
        FxPaperTrade.objects.create(
            estrategia='mrga_m5', simbolo='frxEURUSD', direccion=1, t_signal=12345,
            t_entrada=ahora, precio_entrada=1.1, sl=1.09, lots=1.0)
        with self.assertRaises(IntegrityError):
            with transaction.atomic():
                FxPaperTrade.objects.create(
                    estrategia='mrga_m5', simbolo='frxEURUSD', direccion=-1, t_signal=12345,
                    t_entrada=ahora, precio_entrada=1.1, sl=1.11, lots=1.0)


class TestPagina(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='fx_t', email='fx_t@test.com', password='x', is_superuser=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_302_sin_login(self):
        r = Client().get(reverse('auto_betting:papertrading'))
        self.assertEqual(r.status_code, 302)

    def test_pagina_responde_y_muestra_estrategias(self):
        FxEngineState.objects.create(estrategia='mrga_h1', balance=10123.45)
        ahora = timezone.now()
        FxPaperTrade.objects.create(
            estrategia='mrga_h1', simbolo='frxEURUSD', direccion=1, t_signal=999,
            t_entrada=ahora, precio_entrada=1.1, sl=1.09, tp=1.125, lots=1.0,
            estado='CLOSED', t_salida=ahora, precio_salida=1.125, motivo='TP',
            pnl=250.0, balance_post=10250.0)
        r = self.client.get(reverse('auto_betting:papertrading'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Papertrading FX', html)
        self.assertIn('MRGA EURUSD H1', html)
        self.assertIn('Donchian XAUUSD H4', html)
        self.assertIn('10123.45', html)
        self.assertIn('2.5%', html)          # ROI sumado 250/10000 = 2.5%

    def test_paperbet_general_enlaza_papertrading(self):
        r = self.client.get(reverse('auto_betting:paperbet'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('/auto-betting/papertrading/', r.content.decode())


class TestScheduler(TestCase):
    def test_mapeos_del_scheduler(self):
        from auto_betting.management.commands.run_scheduler import (
            ANTI_CONCURRENCY, COMANDOS, LOGS)
        self.assertIn('run_paper_trades_fx', COMANDOS)
        self.assertIn('run_paper_trades_fx', LOGS)
        self.assertIn('run_paper_trades_fx', ANTI_CONCURRENCY)
        self.assertIn('run_paper_trades_fx', [c[0] for c in CronSchedule.TAREA_CHOICES])
