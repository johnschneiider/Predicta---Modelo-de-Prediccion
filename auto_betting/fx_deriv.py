# -*- coding: utf-8 -*-
"""Motor independiente de papertrading FX sobre Deriv — port de los 3 modelos
ganadores de MT5 Quant Lab (MRGA EURUSD H1, MRGA EURUSD M5, Donchian XAUUSD H4).

Validado en `reports/deriv-backtest-2026-10-12.md` (backtest jul-2026 con datos
Deriv). Solo papel, sin dinero real.

Semántica (espejo exacto del backtest de validación):
  * Señal por cierre de barra; entrada a la apertura de la barra siguiente.
  * MRGA: compra cuando el cierre cruza la banda inferior (BB 26/2.3) con
    RSI(15) Wilder <= 27; venta simétrica con 66. TP/SL en pips desde la
    entrada. Sesión 9-20 hora servidor (EET/EEST emulado). Máx 10 entradas/día.
  * Donchian: ruptura del canal 20 sobre cierres (canal excluye la barra de
    señal), stop 2*ATR(20) (media simple, como el backtest y mt5_monitor;
    ojo: el iATR de MT5 usa suavizado Wilder), salida por canal reverso 10.
    No re-entra la misma barra tras salida por canal.
  * 1 posición por estrategia; riesgo 1% del balance virtual (10.000 USD).
  * Spread constante medido en vivo: EURUSD 0.00011 (1.1 pips), XAUUSD 0.60.
    Se cobra completo en la entrada (compra paga ask = mid + s).
  * OHLC de velas Deriv; si una barra toca TP y SL se asume SL primero.
  * Replay determinista e idempotente: cada corrida procesa las barras
    cerradas nuevas desde `last_bar_t`. Primera activación: arranca en la
    última barra cerrada (sin backfill).
"""

import asyncio
import calendar
import datetime as dt
import json

import websockets

MOTOR = 'fx_deriv'
DERIV_WSS = 'wss://api.derivws.com/trading/v1/options/ws/public'

INIT_BALANCE = 10000.0
RISK = 0.01

BB_PERIOD = 26
BB_DEV = 2.3
RSI_PERIOD = 15
RSI_LOW = 27
RSI_HIGH = 66
SESSION_START = 9
SESSION_END = 20
MAX_TRADES_DAY = 10

SPREADS = {
    'frxEURUSD': 0.00011,
    'frxXAUUSD': 0.60,
}

STRATEGIES = {
    'mrga_h1': {
        'nombre': 'MRGA EURUSD H1 (TP35/SL10)',
        'familia': 'mrga',
        'simbolo': 'frxEURUSD',
        'granularidad': 3600,
        'tp_pips': 35,
        'sl_pips': 10,
        'fetch_count': 500,
    },
    'mrga_m5': {
        'nombre': 'MRGA EURUSD M5 (TP25/SL10)',
        'familia': 'mrga',
        'simbolo': 'frxEURUSD',
        'granularidad': 300,
        'tp_pips': 25,
        'sl_pips': 10,
        'fetch_count': 1000,
    },
    'donchian_xau_h4': {
        'nombre': 'Donchian XAUUSD H4 (20/10, 2xATR)',
        'familia': 'donchian',
        'simbolo': 'frxXAUUSD',
        'granularidad': 14400,
        'entry_period': 20,
        'exit_period': 10,
        'atr_period': 20,
        'atr_mult': 2.0,
        'fetch_count': 200,
    },
}

# Depuración 2026-10-24: mrga_m5 3W/11L, -358 USD en 14 cerradas.
# El scheduler ya no la ejecuta; una posición OPEN se deja cerrar sin abrir nuevas.
ESTRATEGIAS_DEPRECADAS = frozenset({'mrga_m5'})

PIP = 0.0001


# ---------------------------------------------------------------------------
# Indicadores (idénticos al backtest de validación)
# ---------------------------------------------------------------------------

def sma_std(closes, period):
    n = len(closes)
    mid = [None] * n
    dev = [None] * n
    s = 0.0
    s2 = 0.0
    for i, c in enumerate(closes):
        s += c
        s2 += c * c
        if i >= period:
            s -= closes[i - period]
            s2 -= closes[i - period] ** 2
        if i >= period - 1:
            m = s / period
            var = max(s2 / period - m * m, 0.0)
            mid[i] = m
            dev[i] = var ** 0.5
    return mid, dev


def rsi_wilder(closes, period):
    n = len(closes)
    out = [None] * n
    if n <= period:
        return out
    gains = losses = 0.0
    for i in range(1, period + 1):
        ch = closes[i] - closes[i - 1]
        gains += max(ch, 0.0)
        losses += max(-ch, 0.0)
    ag, al = gains / period, losses / period
    out[period] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    for i in range(period + 1, n):
        ch = closes[i] - closes[i - 1]
        ag = (ag * (period - 1) + max(ch, 0.0)) / period
        al = (al * (period - 1) + max(-ch, 0.0)) / period
        out[i] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def atr_sma(candles, period):
    n = len(candles)
    tr = [None] * n
    for i in range(1, n):
        h, l, pc = candles[i]['h'], candles[i]['l'], candles[i - 1]['c']
        tr[i] = max(h - l, abs(h - pc), abs(l - pc))
    out = [None] * n
    s = 0.0
    for i in range(1, n):
        s += tr[i]
        if i > period:
            s -= tr[i - period]
        if i >= period:
            out[i] = s / period
    return out


# ---------------------------------------------------------------------------
# Hora servidor (EET/EEST como MetaQuotes-Demo) y día servidor
# ---------------------------------------------------------------------------

def _last_sunday(year, month):
    last_day = calendar.monthrange(year, month)[1]
    d = dt.date(year, month, last_day)
    while d.weekday() != 6:
        d -= dt.timedelta(days=1)
    return dt.datetime(d.year, d.month, d.day, 1, 0, tzinfo=dt.timezone.utc)


def server_offset_hours(epoch):
    d = dt.datetime.fromtimestamp(epoch, dt.timezone.utc)
    start = _last_sunday(d.year, 3)
    end = _last_sunday(d.year, 10)
    return 3 if start <= d < end else 2


def server_hour(epoch):
    return int((dt.datetime.fromtimestamp(epoch, dt.timezone.utc).hour + server_offset_hours(epoch)) % 24)


def server_date(epoch):
    return dt.datetime.fromtimestamp(epoch + server_offset_hours(epoch) * 3600, dt.timezone.utc).strftime('%Y-%m-%d')


# ---------------------------------------------------------------------------
# Tamaño de posición y P&L
# ---------------------------------------------------------------------------

def _floor_step(value, step=0.01):
    return int(value / step) * step


def size_lots(key, balance, sl_distance_price):
    cfg = STRATEGIES[key]
    sym = cfg['simbolo']
    if sym == 'frxEURUSD':
        loss_per_lot = sl_distance_price / PIP * 10.0
    else:
        loss_per_lot = sl_distance_price * 100.0
    if loss_per_lot <= 0:
        return 0.01
    lots = _floor_step(balance * RISK / loss_per_lot)
    return max(0.01, round(lots, 2))


def pnl_usd(symbol, direction, entry, exit_price, lots):
    move = (exit_price - entry) if direction == 1 else (entry - exit_price)
    if symbol == 'frxEURUSD':
        return (move / PIP) * 10.0 * lots
    return move * 100.0 * lots


# ---------------------------------------------------------------------------
# Replay determinista
# ---------------------------------------------------------------------------

def replay(key, candles, last_bar_t, balance, trades_today, dia_servidor,
           posicion, now_epoch):
    """Procesa las barras cerradas nuevas desde `last_bar_t`.

    `posicion` = dict(dir, entry, sl, tp, lots, t_entrada) o None (se
    reconstruye desde la fila OPEN en DB antes de llamar).
    Devuelve (eventos, estado_nuevo). Los eventos son dicts:
      {'tipo':'entrada'|'salida', ...} — la capa de DB los persiste.
    """
    cfg = STRATEGIES[key]
    gran = cfg['granularidad']
    sym = cfg['simbolo']
    spread = SPREADS[sym]
    closes = [c['c'] for c in candles]
    tiempos = [c['t'] for c in candles]
    n = len(candles)

    familia = cfg['familia']
    if familia == 'mrga':
        bb_mid, bb_dev = sma_std(closes, BB_PERIOD)
        rsi = rsi_wilder(closes, RSI_PERIOD)
    else:
        atr = atr_sma(candles, cfg['atr_period'])

    eventos = []
    nuevas_barras = 0

    if last_bar_t <= 0:
        cerradas = [i for i in range(n) if tiempos[i] + gran <= now_epoch]
        nuevo_last = tiempos[cerradas[-1]] if cerradas else 0
        return eventos, dict(balance=balance, last_bar_t=nuevo_last,
                             trades_today=trades_today, dia_servidor=dia_servidor,
                             posicion=posicion)

    start = None
    for i in range(n):
        if tiempos[i] > last_bar_t:
            start = i
            break
    if start is None:
        return eventos, dict(balance=balance, last_bar_t=last_bar_t,
                             trades_today=trades_today, dia_servidor=dia_servidor,
                             posicion=posicion)
    if start > 0 and tiempos[start - 1] > last_bar_t:
        return eventos, dict(balance=balance, last_bar_t=last_bar_t,
                             trades_today=trades_today, dia_servidor=dia_servidor,
                             posicion=posicion)

    i = start
    while i < n and tiempos[i] + gran <= now_epoch:
        bar = candles[i]
        cerrado_ok = False
        salida_por_canal = False

        if posicion is not None and tiempos[i] >= posicion['t_entrada']:
            hit = None
            if posicion['dir'] == 1:
                if bar['o'] <= posicion['sl']:
                    hit = ('SL_GAP', bar['o'])
                elif posicion.get('tp') and bar['o'] >= posicion['tp']:
                    hit = ('TP_GAP', bar['o'])
                elif posicion['tp'] and bar['l'] <= posicion['sl'] and bar['h'] >= posicion['tp']:
                    hit = ('SL', posicion['sl'])
                elif bar['l'] <= posicion['sl']:
                    hit = ('SL', posicion['sl'])
                elif posicion['tp'] and bar['h'] >= posicion['tp']:
                    hit = ('TP', posicion['tp'])
            else:
                if bar['o'] >= posicion['sl']:
                    hit = ('SL_GAP', bar['o'])
                elif posicion.get('tp') and bar['o'] <= posicion['tp']:
                    hit = ('TP_GAP', bar['o'])
                elif posicion['tp'] and bar['h'] >= posicion['sl'] and bar['l'] <= posicion['tp']:
                    hit = ('SL', posicion['sl'])
                elif bar['h'] >= posicion['sl']:
                    hit = ('SL', posicion['sl'])
                elif posicion['tp'] and bar['l'] <= posicion['tp']:
                    hit = ('TP', posicion['tp'])

            if hit is not None:
                pnl = round(pnl_usd(sym, posicion['dir'], posicion['entry'], hit[1], posicion['lots']), 2)
                balance = round(balance + pnl, 2)
                eventos.append(dict(tipo='salida', trade_signal_t=posicion['t_signal'],
                                    t_salida=tiempos[i], precio_salida=hit[1],
                                    motivo=hit[0], pnl=pnl, balance_post=balance))
                posicion = None
            elif familia == 'donchian':
                ex_hi = max(c['h'] for c in candles[i - cfg['exit_period']:i]) if i >= cfg['exit_period'] else None
                ex_lo = min(c['l'] for c in candles[i - cfg['exit_period']:i]) if i >= cfg['exit_period'] else None
                if ex_hi is not None:
                    salida = (posicion['dir'] == 1 and bar['c'] < ex_lo) or (posicion['dir'] == -1 and bar['c'] > ex_hi)
                    if salida:
                        if i + 1 >= n:
                            # sin barra siguiente aún: se pospone al próximo run
                            break
                        px = candles[i + 1]['o']
                        pnl = round(pnl_usd(sym, posicion['dir'], posicion['entry'], px, posicion['lots']), 2)
                        balance = round(balance + pnl, 2)
                        eventos.append(dict(tipo='salida', trade_signal_t=posicion['t_signal'],
                                            t_salida=tiempos[i + 1], precio_salida=px,
                                            motivo='CHANNEL', pnl=pnl, balance_post=balance))
                        posicion = None
                        salida_por_canal = True

        if posicion is None and not salida_por_canal and i + 1 < n:
            if familia == 'mrga':
                if i >= BB_PERIOD + 1 and bb_mid[i] is not None and bb_mid[i - 1] is not None and rsi[i] is not None:
                    lo_i = bb_mid[i] - BB_DEV * bb_dev[i]
                    lo_prev = bb_mid[i - 1] - BB_DEV * bb_dev[i - 1]
                    up_i = bb_mid[i] + BB_DEV * bb_dev[i]
                    up_prev = bb_mid[i - 1] + BB_DEV * bb_dev[i - 1]
                    direction = 0
                    if closes[i - 1] > lo_prev and closes[i] <= lo_i and rsi[i] <= RSI_LOW:
                        direction = 1
                    elif closes[i - 1] < up_prev and closes[i] >= up_i and rsi[i] >= RSI_HIGH:
                        direction = -1
                    if direction:
                        hora = server_hour(tiempos[i + 1])
                        if SESSION_START <= hora < SESSION_END:
                            day = server_date(tiempos[i + 1])
                            if day != dia_servidor:
                                dia_servidor = day
                                trades_today = 0
                            if trades_today < MAX_TRADES_DAY:
                                entry = candles[i + 1]['o'] + spread if direction == 1 else candles[i + 1]['o'] - spread
                                sl = entry - cfg['sl_pips'] * PIP if direction == 1 else entry + cfg['sl_pips'] * PIP
                                tp = entry + cfg['tp_pips'] * PIP if direction == 1 else entry - cfg['tp_pips'] * PIP
                                lots = size_lots(key, balance, cfg['sl_pips'] * PIP)
                                posicion = dict(dir=direction, entry=entry, sl=sl, tp=tp,
                                                lots=lots, t_signal=tiempos[i], t_entrada=tiempos[i + 1])
                                trades_today += 1
                                eventos.append(dict(tipo='entrada', trade_signal_t=tiempos[i],
                                                    t_entrada=tiempos[i + 1], direccion=direction,
                                                    precio_entrada=entry, sl=sl, tp=tp, lots=lots,
                                                    balance_pre=balance))
            else:
                if i >= cfg['entry_period'] + 1 and atr[i] is not None:
                    hi = max(c['h'] for c in candles[i - cfg['entry_period']:i])
                    lo = min(c['l'] for c in candles[i - cfg['entry_period']:i])
                    direction = 0
                    if closes[i] > hi:
                        direction = 1
                    elif closes[i] < lo:
                        direction = -1
                    if direction:
                        entry = candles[i + 1]['o'] + spread if direction == 1 else candles[i + 1]['o'] - spread
                        sl_dist = cfg['atr_mult'] * atr[i]
                        sl = entry - sl_dist if direction == 1 else entry + sl_dist
                        lots = size_lots(key, balance, sl_dist)
                        posicion = dict(dir=direction, entry=entry, sl=sl, tp=None,
                                        lots=lots, t_signal=tiempos[i], t_entrada=tiempos[i + 1])
                        eventos.append(dict(tipo='entrada', trade_signal_t=tiempos[i],
                                            t_entrada=tiempos[i + 1], direccion=direction,
                                            precio_entrada=entry, sl=sl, tp=None, lots=lots,
                                            balance_pre=balance))

        last_bar_t = tiempos[i]
        nuevas_barras += 1
        i += 1

    return eventos, dict(balance=balance, last_bar_t=last_bar_t,
                         trades_today=trades_today, dia_servidor=dia_servidor,
                         posicion=posicion)


# ---------------------------------------------------------------------------
# Cliente Deriv (endpoint público 2026, sin token)
# ---------------------------------------------------------------------------

async def _fetch(symbol, granularity, count):
    async with websockets.connect(DERIV_WSS, max_size=64 * 1024 * 1024, open_timeout=25) as ws:
        req = {'ticks_history': symbol, 'count': count, 'end': 'latest',
               'style': 'candles', 'granularity': granularity, 'req_id': 1}
        await ws.send(json.dumps(req))
        while True:
            msg = json.loads(await asyncio.wait_for(ws.recv(), 45))
            if msg.get('req_id') != 1:
                continue
            if 'error' in msg:
                raise RuntimeError(f"Deriv {symbol}/{granularity}: {msg['error'].get('message')}")
            return [dict(t=int(c['epoch']), o=float(c['open']), h=float(c['high']),
                         l=float(c['low']), c=float(c['close']))
                    for c in (msg.get('candles') or [])]


def fetch_candles(symbol, granularity, count, tries=3):
    last_err = None
    for attempt in range(tries):
        try:
            return asyncio.run(_fetch(symbol, granularity, count))
        except Exception as e:  # noqa: BLE001 — se reporta y se reintenta
            last_err = e
            if attempt + 1 < tries:
                import time
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Deriv no respondió para {symbol}/{granularity}: {last_err}")
