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

from django.db.models import Sum
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
