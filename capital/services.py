"""
Servicios del gestor de capital.

Fuente de verdad del P&L: `auto_betting.HistorialApuesta` (sincronizada a
diario desde BetPlay). El balance paralelo se calcula al vuelo con una única
query de agregación — no hay cron ni snapshot intermedio para la corrección
del stake (solo para visualización, si se decide añadirla luego).

IMPORTANTE: se incluyen TODAS las apuestas asentadas (de sistema y manuales)
colocadas desde `ancla`, porque el balance paralelo debe reflejar el
movimiento REAL de la cuenta BetPlay. Las apuestas OPEN no cuentan hasta
que se asientan (el balance puede quedar temporalmente optimista; los
circuit breakers del auto_betting acotan la exposición).
"""

from datetime import datetime, time, timedelta

from django.db.models import Q, Sum
from django.utils import timezone

from auto_betting.models import HistorialApuesta

from .models import CapitalConfig, CapitalAjuste, CapitalLegada

# Estados que cuentan como asentados (WON/LOST). OPEN no cuenta; VOID es
# neutro (Kambi devuelve el stake; no genera P&L).
_ESTADOS_ASENTADOS = ['WON', 'LOST']

# Política anti-bloqueo (John, 2026-09-02): ningún stake por debajo de 500 COP
# y siempre números "redondos" según su magnitud, para que las apuestas no
# parezcan calculadas (surebets) ante la casa de apuestas.
_STAKE_MIN_COP = 500


def _step_cop(valor_cop):
    """
    Escalón de redondeo según la magnitud del stake (COP):
      < 10.000     → 100      (500, 600, ..., 9.900)
      < 100.000    → 1.000    (10.000, 11.000, ...)
      < 1.000.000  → 10.000   (y así sucesivamente: 10^(n−2) con n dígitos).
    """
    return 10 ** max(len(str(int(valor_cop))) - 2, 2)


def normalizar_stake_cop(stake_cop, hacia='cercano'):
    """
    Normaliza un stake en COP a la política de números redondos:
      - piso global: 500 COP.
      - múltiplos de 100 / 1.000 / 10.000 / ... según la magnitud.
    Nunca produce valores "raros" (525, 10.850) que delaten automatización.

    `hacia`: 'cercano' (default, empate hacia arriba), 'abajo' o 'arriba'.
    """
    stake_cop = int(stake_cop)
    if stake_cop < _STAKE_MIN_COP:
        return _STAKE_MIN_COP
    step = _step_cop(stake_cop)
    if hacia == 'abajo':
        return (stake_cop // step) * step
    if hacia == 'arriba':
        return ((stake_cop + step - 1) // step) * step
    return (stake_cop + step // 2) // step * step


def get_config(usuario):
    """Devuelve (creando si no existe) la CapitalConfig del usuario."""
    cfg, _ = CapitalConfig.objects.get_or_create(usuario=usuario)
    return cfg


def pnl_asentado_cop(usuario, desde=None):
    """P&L neto (COP) de las apuestas asentadas del usuario desde `desde`."""
    qs = HistorialApuesta.objects.filter(
        usuario=usuario, bet_status__in=_ESTADOS_ASENTADOS,
    )
    if desde is not None:
        qs = qs.filter(placed_date__gte=desde)
    agg = qs.aggregate(st=Sum('stake'), pay=Sum('payout'))
    return int(((agg['pay'] or 0) - (agg['st'] or 0)) / 1000.0)


def ajustes_cop(usuario, desde=None):
    """Suma de ajustes manuales del usuario desde `desde`."""
    qs = CapitalAjuste.objects.filter(usuario=usuario)
    if desde is not None:
        qs = qs.filter(fecha__gte=desde)
    return int(qs.aggregate(s=Sum('monto_cop'))['s'] or 0)


def snapshot_legadas(usuario):
    """
    Registra las apuestas OPEN del usuario en el momento de activar el modo
    compuesto. Idempotente por (usuario, coupon_ref).
    """
    refs = list(
        HistorialApuesta.objects.filter(usuario=usuario, bet_status='OPEN')
        .values_list('coupon_ref', flat=True)
    )
    if refs:
        CapitalLegada.objects.bulk_create(
            [CapitalLegada(usuario=usuario, coupon_ref=r) for r in refs],
            ignore_conflicts=True,
        )
    return len(refs)


def payout_legadas_cop(usuario, desde=None):
    """
    Crédito de las apuestas legadas (OPEN al activar) que ya asentaron.

    Se suma el `payout` COMPLETO (no profit): el stake ya estaba descontado
    del balance declarado, así que al asentar la cuenta real recibe el payout
    entero (WON) o nada (LOST); VOID devuelve el stake (= payout).
    """
    qs_leg = CapitalLegada.objects.filter(usuario=usuario)
    if desde is not None:
        qs_leg = qs_leg.filter(creado__gte=desde)
    refs = list(qs_leg.values_list('coupon_ref', flat=True))
    if not refs:
        return 0
    pay = HistorialApuesta.objects.filter(
        usuario=usuario,
        coupon_ref__in=refs,
        bet_status__in=['WON', 'LOST', 'VOID'],
    ).aggregate(s=Sum('payout'))['s'] or 0
    return int(pay / 1000.0)


def _stakes_pendientes_autobet(usuario, ancla):
    """
    Stake (unidades Kambi) de apuestas del sistema colocadas DESDE el ancla
    que aún NO están en HistorialApuesta (todavía no sincronizadas).

    Evita doble conteo: si el cupón ya fue importado por el sync, el stake
    se descuenta vía HistorialApuesta; aquí solo entran las pendientes de
    sincronizar (recién colocadas).
    """
    from auto_betting.models import AutoBet

    refs_hist = set(
        HistorialApuesta.objects.filter(usuario=usuario, placed_date__gte=ancla)
        .values_list('coupon_ref', flat=True)
    )
    qs = AutoBet.objects.filter(usuario=usuario, estado='OPEN', creado__gte=ancla)
    if refs_hist:
        qs = qs.exclude(coupon_ref__in=refs_hist)
    return int(qs.aggregate(s=Sum('stake'))['s'] or 0)


def bankroll_cop(usuario):
    """
    Balance paralelo en TIEMPO REAL (COP) o None si el usuario no ha activado
    el modo compuesto.

    = balance_inicial
      + payout de apuestas colocadas desde el ancla YA asentadas
      − stake de TODAS las apuestas colocadas desde el ancla (asentadas y
        pendientes: el stake se descuenta al colocar, como en la cuenta real)
      − stake de apuestas del sistema recién colocadas aún sin sincronizar
      + payout completo de apuestas legadas (OPEN al ancla) asentadas
      + ajustes manuales.

    Efecto: al colocar una apuesta el balance BAJA (stake); al asentar WON
    SUBE el payout completo (stake + ganancia) → el movimiento neto es la
    ganancia real.
    """
    cfg = get_config(usuario)
    if cfg.balance_inicial is None or cfg.ancla is None:
        return None

    qs = HistorialApuesta.objects.filter(usuario=usuario, placed_date__gte=cfg.ancla)
    agg = qs.aggregate(st=Sum('stake'), pay=Sum('payout'))
    movimiento_cop = int(((agg['pay'] or 0) - (agg['st'] or 0)) / 1000.0)
    pendientes_cop = int(_stakes_pendientes_autobet(usuario, cfg.ancla) / 1000.0)

    return (
        int(cfg.balance_inicial)
        + movimiento_cop
        - pendientes_cop
        + payout_legadas_cop(usuario, cfg.ancla)
        + ajustes_cop(usuario, cfg.ancla)
    )


def resolve_stake(config):
    """
    Resuelve el stake (unidades Kambi, COP × 1000) para una AutoBetConfig.

    Política anti-bloqueo (2026-09-02): TODO stake de salida pasa por
    `normalizar_stake_cop` — mínimo 500 COP y múltiplos redondos por
    magnitud (100 / 1.000 / 10.000 / ...).

    Devuelve (stake_kambi, motivo):
      - modo FIJO:         (stake normalizado, 'fijo')        → piso 500 COP.
      - modo COMPUESTO:    (stake * 1000, 'compuesto')        → % del balance.
      - % < stake mínimo:  se usa el stake mínimo (2026-09-02: el piso es un
                           suelo operativo, no un freno).
      - sin balance/ancla: (None, 'sin_balance')              → NO apostar.
      - balance ≤ 0:       (None, 'sin_saldo')                → NO apostar.

    `None` SIEMPRE significa "no colocar apuestas para este usuario" —
    protege de apostar sin saldo o con montos que el usuario no eligió.
    """
    cfg = get_config(config.usuario)

    if cfg.modo != CapitalConfig.MODO_COMPUESTO:
        stake_cop = int(config.stake) / 1000.0
        if stake_cop <= 0:
            return None, 'sin_saldo'
        return int(normalizar_stake_cop(stake_cop) * 1000), 'fijo'

    if cfg.balance_inicial is None or cfg.ancla is None:
        return None, 'sin_balance'

    balance = bankroll_cop(config.usuario)
    if balance is None or balance <= 0:
        return None, 'sin_saldo'

    # % del balance. Si queda por debajo del mínimo configurado, se usa el
    # MÍNIMO como stake (2026-09-02, pedido de John): el piso es un suelo
    # operativo — apostar el mínimo — no un freno que pause la cuenta.
    stake_cop = int(balance * cfg.porcentaje / 100.0)
    if stake_cop < cfg.stake_min_cop:
        stake_cop = cfg.stake_min_cop
    if stake_cop > cfg.stake_max_cop:
        stake_cop = cfg.stake_max_cop
    stake_cop = normalizar_stake_cop(stake_cop)
    # Si el techo configurado no era redondo, el redondeo pudo pasarse:
    # techo duro al múltiplo inferior del máximo.
    if stake_cop > cfg.stake_max_cop:
        stake_cop = normalizar_stake_cop(cfg.stake_max_cop, hacia='abajo')

    return int(stake_cop * 1000), 'compuesto'


def format_cop(valor):
    """Formatea COP con signo $ y separador de miles colombiano (punto)."""
    signo = '-' if valor < 0 else ''
    return f"{signo}${abs(valor):,.0f}".replace(',', '.')


def registrar_ajuste(usuario, monto_cop, motivo='Ajuste manual'):
    """Crea un CapitalAjuste auditado (monto firmado, en COP)."""
    return CapitalAjuste.objects.create(
        usuario=usuario, monto_cop=int(monto_cop), motivo=motivo,
    )


def balance_timeline(usuario, desde=None, hasta=None):
    """Serie temporal para el gráfico "Movimiento del balance real" (COP).

    Dos modos:

    - SIN filtro de fechas: balance paralelo real de la CUENTA en el tiempo
      (fórmula idéntica a `bankroll_cop()` repartida por eventos):
      balance_inicial al ancla, −stake al colocar cada apuesta, +payout al
      asentarse (`event_start_date + 3h`), +payout completo de legadas,
      +ajustes manuales, −stakes del sistema pendientes de sincronizar.
      Cada punto lleva `bal` (depósito), `en_juego` y `total` = bal + en_juego.

    - CON `desde`/`hasta` (fechas de PARTIDO, TZ local): la serie muestra el
      dinero de SOLO los partidos del rango, para ser coherente con el filtro
      del resto de la página: `en_juego` (stakes vivos de esos partidos),
      `realizado` (P&L acumulado de los que ya asentaron) y
      `total` = en_juego + realizado. Los ajustes manuales no entran (no son de
      partidos). La ventana va del inicio del rango (o el primer evento) al
      cierre del rango (o ahora).

    Devuelve None si el usuario no tiene ancla/balance declarado.
    """
    cfg = get_config(usuario)
    if cfg.balance_inicial is None or cfg.ancla is None:
        return None
    if desde or hasta:
        return _timeline_partidos(usuario, desde, hasta)

    from auto_betting.models import HistorialApuesta, AutoBet

    # (timestamp, delta_balance, delta_en_juego)
    events = []

    qs = HistorialApuesta.objects.filter(usuario=usuario, placed_date__gte=cfg.ancla)
    for h in qs.only('placed_date', 'stake', 'payout', 'bet_status', 'actualizado',
                     'event_start_date'):
        stake_cop = (h.stake or 0) / 1000.0
        if h.placed_date:
            events.append((h.placed_date, -stake_cop, stake_cop))
        asentada = h.bet_status in ('WON', 'LOST', 'VOID')
        if (h.payout or 0) > 0 or asentada:
            # Asentamiento ≈ fin del partido (+3h). NO usar `actualizado`: es
            # auto_now y el sync lo re-fecha en cada corrida → todos los payouts
            # caían en el último sync y el gráfico mostraba un falso desplome.
            base = h.event_start_date or h.placed_date or h.actualizado
            t_settle = base + timedelta(hours=3)
            if h.placed_date:
                # El stake solo puede salir de "en juego" después de entrar.
                t_settle = max(t_settle, h.placed_date)
            events.append((
                t_settle,
                (h.payout or 0) / 1000.0 if (h.payout or 0) > 0 else 0.0,
                -stake_cop if asentada else 0.0,
            ))

    legadas = set(CapitalLegada.objects.filter(usuario=usuario)
                  .values_list('coupon_ref', flat=True))
    if legadas:
        for h in HistorialApuesta.objects.filter(
                usuario=usuario, coupon_ref__in=legadas):
            stake_cop = (h.stake or 0) / 1000.0
            asentada = h.bet_status in ('WON', 'LOST', 'VOID')
            base = h.event_start_date or h.placed_date or h.actualizado
            t_settle = max(base + timedelta(hours=3), cfg.ancla)
            # Su stake ya salió del balance declarado → estaba en juego al
            # anclar. Si ya había asentado al ancla, no entra en la serie; si
            # sigue viva, permanece en juego hasta que asiente.
            if asentada:
                if t_settle > cfg.ancla and stake_cop:
                    events.append((cfg.ancla, 0.0, stake_cop))
                    events.append((t_settle, 0.0, -stake_cop))
            elif stake_cop:
                events.append((cfg.ancla, 0.0, stake_cop))
            if (h.payout or 0) > 0:
                events.append((t_settle, (h.payout or 0) / 1000.0, 0.0))

    refs_hist = set(qs.values_list('coupon_ref', flat=True))
    pend = AutoBet.objects.filter(usuario=usuario, estado='OPEN', creado__gte=cfg.ancla)
    if refs_hist:
        pend = pend.exclude(coupon_ref__in=refs_hist)
    for b in pend.only('creado', 'stake'):
        stake_cop = (b.stake or 0) / 1000.0
        events.append((b.creado, -stake_cop, stake_cop))

    for a in CapitalAjuste.objects.filter(usuario=usuario, fecha__gte=cfg.ancla):
        events.append((a.fecha, float(a.monto_cop or 0), 0.0))

    events.sort(key=lambda e: e[0])

    bal = float(cfg.balance_inicial)
    en_juego = 0.0
    inicio = cfg.ancla

    def _punto(t):
        return {
            't': t.isoformat(),
            'bal': round(bal, 2),
            'en_juego': round(en_juego, 2),
            'total': round(bal + en_juego, 2),
        }

    points = [_punto(inicio)]
    for t, dbal, dopen in events:
        bal += dbal
        en_juego += dopen
        points.append(_punto(t))

    return {
        'points': points,
        'inicial': int(round(float(cfg.balance_inicial))),
        'ancla': inicio.isoformat(),
        'final': int(round(bal)),
        'en_juego': int(round(en_juego)),
        'total': int(round(bal + en_juego)),
        'bankroll': bankroll_cop(usuario),
        'filtrado': False,
    }


def _timeline_partidos(usuario, desde, hasta):
    """Serie del dinero de los PARTIDOS del rango (modo filtrado del gráfico).

    `en_juego` = stakes vivos de los partidos del rango; `realizado` = P&L
    acumulado de los que asentaron (fechado en `event_start_date + 3h`, igual
    que `balance_timeline`); `total` = en_juego + realizado. Los ajustes
    manuales quedan fuera (no pertenecen a ningún partido).
    """
    from auto_betting.models import HistorialApuesta, AutoBet

    # (timestamp, delta_en_juego, delta_realizado)
    events = []

    qs = HistorialApuesta.objects.filter(usuario=usuario)
    if desde:
        qs = qs.filter(
            Q(event_start_date__date__gte=desde)
            | Q(event_start_date__isnull=True, placed_date__date__gte=desde)
        )
    if hasta:
        qs = qs.filter(
            Q(event_start_date__date__lte=hasta)
            | Q(event_start_date__isnull=True, placed_date__date__lte=hasta)
        )
    for h in qs.only('placed_date', 'stake', 'payout', 'bet_status', 'actualizado',
                     'event_start_date'):
        stake_cop = (h.stake or 0) / 1000.0
        if h.placed_date and stake_cop:
            events.append((h.placed_date, stake_cop, 0.0))
        if h.bet_status in ('WON', 'LOST', 'VOID'):
            base = h.event_start_date or h.placed_date or h.actualizado
            t_settle = base + timedelta(hours=3)
            if h.placed_date:
                t_settle = max(t_settle, h.placed_date)
            profit_cop = ((h.payout or 0) - (h.stake or 0)) / 1000.0
            events.append((t_settle, -stake_cop, profit_cop))

    # Apuestas del sistema recién colocadas y aún sin sincronizar: su stake
    # está en juego, pero no están en el historial.
    refs = {r for r in HistorialApuesta.objects.filter(usuario=usuario)
            .values_list('coupon_ref', flat=True) if r is not None}
    pend = AutoBet.objects.filter(usuario=usuario, estado='OPEN')
    if desde:
        pend = pend.filter(start_time__date__gte=desde)
    if hasta:
        pend = pend.filter(start_time__date__lte=hasta)
    if refs:
        pend = pend.exclude(coupon_ref__in=refs)
    for b in pend.only('creado', 'stake'):
        stake_cop = (b.stake or 0) / 1000.0
        if b.creado and stake_cop:
            events.append((b.creado, stake_cop, 0.0))

    events.sort(key=lambda e: e[0])

    inicio = timezone.make_aware(datetime.combine(desde, time.min)) if desde else None
    if inicio is None:
        inicio = events[0][0] if events else timezone.now()
    fin = timezone.make_aware(datetime.combine(hasta, time.max)) if hasta else timezone.now()

    en_juego = 0.0
    realizado = 0.0
    for t, de, dr in events:
        if t < inicio:
            # Ya estaba colocado (o asentado) al abrir la ventana: entra como
            # estado inicial, no como movimiento.
            en_juego += de
            realizado += dr

    def _punto(t):
        return {
            't': t.isoformat(),
            'en_juego': round(en_juego, 2),
            'realizado': round(realizado, 2),
            'total': round(en_juego + realizado, 2),
        }

    points = [_punto(inicio)]
    last_t = inicio
    for t, de, dr in events:
        if t < inicio:
            continue
        if t > fin:
            break
        en_juego += de
        realizado += dr
        last_t = t
        points.append(_punto(t))
    if last_t < fin:
        points.append(_punto(fin))

    return {
        'points': points,
        'ancla': inicio.isoformat(),
        'en_juego': int(round(en_juego)),
        'realizado': int(round(realizado)),
        'total': int(round(en_juego + realizado)),
        'bankroll': bankroll_cop(usuario),
        'filtrado': True,
    }


def crecimiento_capital(usuario, desde=None, hasta=None):
    """Crecimiento del capital de la CUENTA entre el inicio y el fin de un rango.

    Es la métrica "ROI de capital" del rango filtrado: compara el capital TOTAL
    (libre + en juego, la línea "Total" del gráfico del balance) en los dos
    extremos. Se usa el total para que el % no se distorsione por apuestas
    abiertas justo en el borde del rango (su stake ya salió del balance libre,
    pero sigue siendo dinero).

    - Sin fechas: todo el periodo con capital registrado (ancla → ahora).
    - Inicio: capital al comenzar el día `desde` (00:00 local). Si el rango
      arranca antes del ancla, se usa el primer punto disponible (ancla).
    - Fin: capital al terminar el día `hasta` (23:59:59 local); sin `hasta`,
      el último movimiento (ahora).

    Devuelve None solo si el usuario no tiene capital paralelo. Si el rango
    cae entero antes del ancla (o después del último movimiento) devuelve
    `sin_datos=True` con `pct=None`: la tarjeta se muestra igual, indicando
    que no hay capital registrado en ese rango (antes desaparecía sin más).
    """
    tl = balance_timeline(usuario)
    if not tl or not tl.get('points'):
        return None

    puntos = tl['points']
    t_primer = datetime.fromisoformat(puntos[0]['t'])
    t_ultimo = datetime.fromisoformat(puntos[-1]['t'])
    ancla_local = timezone.localtime(t_primer).date()

    def _snapshot(limite):
        """Último punto con t <= limite (los puntos van ordenados por tiempo)."""
        elegido = None
        for p in puntos:
            if datetime.fromisoformat(p['t']) <= limite:
                elegido = p
            else:
                break
        return elegido

    borde_inicio = timezone.make_aware(datetime.combine(desde, time.min)) if desde else None
    borde_fin = timezone.make_aware(datetime.combine(hasta, time.max)) if hasta else None

    # Fechas del rango efectivo (coinciden con el filtro de la UI; el capital
    # comparado es el vigente en cada borde).
    fecha_inicio = max(desde, ancla_local) if desde else ancla_local
    fecha_fin = hasta or timezone.localdate()

    def _rango_fmt():
        """Texto del rango pedido, sin invertir fechas en rangos abiertos."""
        if desde and hasta:
            return f"{desde.strftime('%d/%m')} → {hasta.strftime('%d/%m')}"
        if desde:
            return f"desde {desde.strftime('%d/%m')}"
        if hasta:
            return f"hasta {hasta.strftime('%d/%m')}"
        return f"{fecha_inicio.strftime('%d/%m')} → {fecha_fin.strftime('%d/%m')}"

    def _sin_datos(motivo):
        return {
            'sin_datos': True,
            'motivo': motivo,
            'pct': None, 'delta': None, 'inicio': None, 'fin': None,
            'fecha_inicio': fecha_inicio.strftime('%d/%m'),
            'fecha_fin': fecha_fin.strftime('%d/%m'),
            'rango_fmt': _rango_fmt(),
            'ancla_fmt': ancla_local.strftime('%d/%m'),
            'inicio_fmt': '', 'fin_fmt': '',
        }

    # El rango termina antes de que exista capital registrado (ancla posterior).
    if borde_fin is not None and borde_fin < t_primer:
        return _sin_datos('antes_ancla')
    # El rango empieza después del último movimiento (p. ej. fechas futuras).
    if borde_inicio is not None and borde_inicio > t_ultimo:
        return _sin_datos('sin_movimientos')

    inicio = _snapshot(borde_inicio) if borde_inicio else None
    fin = _snapshot(borde_fin) if borde_fin else None

    if inicio is None:
        inicio = puntos[0]          # el rango arranca antes del ancla
    if fin is None:
        fin = puntos[-1]            # sin `hasta`: hasta el último movimiento

    cap_inicio = float(inicio['total'])
    cap_fin = float(fin['total'])
    pct = round((cap_fin - cap_inicio) / cap_inicio * 100, 1) if cap_inicio > 0 else None
    return {
        'sin_datos': False,
        'motivo': '',
        'inicio': int(round(cap_inicio)),
        'fin': int(round(cap_fin)),
        'delta': int(round(cap_fin - cap_inicio)),
        'pct': pct,
        'fecha_inicio': fecha_inicio.strftime('%d/%m'),
        'fecha_fin': fecha_fin.strftime('%d/%m'),
        'inicio_fmt': format_cop(cap_inicio),
        'fin_fmt': format_cop(cap_fin),
        'ancla_fmt': ancla_local.strftime('%d/%m'),
    }


def balance_filtrado(usuario, desde=None, hasta=None, sport='', tipo='todos'):
    """Serie de balance de la cuenta acotada a los filtros del historial.

    Devuelve una serie de puntos `{'t', 'bal'}` (COP) con el saldo libre de la
    cuenta, no el dinero "en juego". Tres comportamientos:

    - Sin filtros (sin fechas, `sport=''` y `tipo='todos'`): la serie real
      completa de `balance_timeline(usuario)`, añadiendo `modo='real'` y
      `parcial=False`.
    - Solo fechas: la MISMA curva real recortada a [inicio, fin]. El primer
      punto es el saldo real vigente al inicio de la ventana (no el
      `balance_inicial` del ancla) y el último queda fijado en `fin`.
      `modo='real'`, `parcial=False`.
    - Con deporte y/o tipo: la curva es el APORTE de esas apuestas al balance.
      Parte del saldo real al inicio y aplica únicamente los stakes colocados
      dentro de la ventana y los payouts que asientan dentro. Las apuestas
      colocadas antes del inicio ya están reflejadas en la base (no se les
      vuelve a restar el stake); los ajustes manuales y los AutoBet pendientes
      no se incluyen porque no son atribuibles a deporte/tipo.
      `modo='filtrado'`, `parcial=True`.

    La ventana empieza en `desde` a las 00:00 local (nunca antes del ancla) o
    en el ancla si no hay `desde`, y termina en `hasta` a las 23:59:59.999
    local o en `now` si no hay `hasta`. Devuelve `None` si el usuario no tiene
    balance/ancla declarados o si el rango termina antes de empezar.
    """
    cfg = get_config(usuario)
    if cfg.balance_inicial is None or cfg.ancla is None:
        return None

    sport = (sport or '').strip().upper()
    tipo = (tipo or 'todos').strip().lower()
    hay_fechas = bool(desde or hasta)
    filtra_apuestas = bool(sport) or tipo in ('sistema', 'manual')

    # Sin ningún filtro: la serie real completa, tal cual la usa el gráfico
    # histórico. Solo se añade la metadata que consume la tarjeta nueva.
    if not hay_fechas and not filtra_apuestas:
        serie = balance_timeline(usuario)
        if serie is None:
            return None
        serie = dict(serie)
        serie['modo'] = 'real'
        serie['parcial'] = False
        return serie

    inicio = (timezone.make_aware(datetime.combine(desde, time.min))
              if desde else cfg.ancla)
    if inicio < cfg.ancla:
        inicio = cfg.ancla
    fin = (timezone.make_aware(datetime.combine(hasta, time.max))
           if hasta else timezone.now())
    if fin < inicio:
        return None

    serie_real = balance_timeline(usuario)
    if serie_real is None or not serie_real.get('points'):
        return None
    puntos_reales = [
        (datetime.fromisoformat(p['t']), float(p['bal']))
        for p in serie_real['points']
    ]

    def _saldo_real_en(limite):
        """Último saldo real registrado en/antes de `limite` (serie ordenada)."""
        saldo = float(cfg.balance_inicial)
        for t, bal in puntos_reales:
            if t <= limite:
                saldo = bal
            else:
                break
        return saldo

    saldo_inicial = _saldo_real_en(inicio)
    saldo = saldo_inicial
    ultimo_t = inicio
    points = [{'t': inicio.isoformat(), 'bal': round(saldo, 2)}]

    if not filtra_apuestas:
        # Solo fechas: recortar la curva real, conservando todos sus eventos
        # (stakes, payouts, legadas y ajustes) dentro de la ventana.
        for t, bal in puntos_reales:
            if t <= inicio:
                continue
            if t > fin:
                break
            points.append({'t': t.isoformat(), 'bal': round(bal, 2)})
            ultimo_t = t
            saldo = bal
        modo = 'real'
        parcial = False
    else:
        # Deporte y/o tipo: aporte de esas apuestas sobre el saldo real.
        qs = HistorialApuesta.objects.filter(usuario=usuario)
        if sport:
            qs = qs.filter(sport=sport)
        if tipo == 'sistema':
            qs = qs.filter(is_system=True)
        elif tipo == 'manual':
            qs = qs.filter(is_system=False)

        eventos = []
        for h in qs.only('placed_date', 'stake', 'payout', 'bet_status',
                         'actualizado', 'event_start_date'):
            # Stake: solo si la apuesta se colocó DENTRO de la ventana. Las
            # anteriores ya están descontadas en el saldo real de partida.
            if h.placed_date and inicio < h.placed_date <= fin:
                eventos.append((h.placed_date, -(h.stake or 0) / 1000.0))
            # Payout: se acredita al asentar (fin del partido + 3h), igual que
            # `balance_timeline`; una apuesta previa al inicio solo aporta su
            # payout si asienta dentro de la ventana.
            asentada = h.bet_status in ('WON', 'LOST', 'VOID')
            if (h.payout or 0) > 0 or asentada:
                base_t = h.event_start_date or h.placed_date or h.actualizado
                t_settle = base_t + timedelta(hours=3)
                if h.placed_date:
                    t_settle = max(t_settle, h.placed_date)
                if inicio < t_settle <= fin:
                    eventos.append((t_settle, (h.payout or 0) / 1000.0))

        eventos.sort(key=lambda e: e[0])
        for t, delta in eventos:
            saldo += delta
            ultimo_t = t
            points.append({'t': t.isoformat(), 'bal': round(saldo, 2)})
        modo = 'filtrado'
        parcial = True

    # Cierre explícito en `fin`, aunque no haya eventos (dos puntos planos).
    if ultimo_t < fin:
        points.append({'t': fin.isoformat(), 'bal': round(saldo, 2)})

    return {
        'points': points,
        'inicial': int(round(saldo_inicial)),
        'final': int(round(saldo)),
        'ancla': inicio.isoformat(),
        'filtrado': True,
        'modo': modo,
        'parcial': parcial,
    }
