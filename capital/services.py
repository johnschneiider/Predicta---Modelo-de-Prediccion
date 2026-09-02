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

from .models import CapitalConfig, CapitalAjuste

# Estados que cuentan como asentados (WON/LOST). OPEN no cuenta; VOID es
# neutro (Kambi devuelve el stake; no genera P&L).
_ESTADOS_ASENTADOS = ['WON', 'LOST']


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


def bankroll_cop(usuario):
    """
    Balance paralelo (COP) o None si el usuario no ha activado el modo
    compuesto (sin balance declarado / sin ancla).
    """
    cfg = get_config(usuario)
    if cfg.balance_inicial is None or cfg.ancla is None:
        return None
    return int(cfg.balance_inicial) + pnl_asentado_cop(usuario, cfg.ancla) + ajustes_cop(usuario, cfg.ancla)


def resolve_stake(config):
    """
    Resuelve el stake (unidades Kambi, COP × 1000) para una AutoBetConfig.

    Devuelve (stake_kambi, motivo):
      - modo FIJO:         (config.stake, 'fijo')            → sin cambios.
      - modo COMPUESTO:    (stake * 1000, 'compuesto')       → % del balance.
      - sin balance/ancla: (None, 'sin_balance')             → NO apostar.
      - balance ≤ 0:       (None, 'sin_saldo')               → NO apostar.
      - % < stake mínimo:  (None, 'stake_minimo')            → NO apostar.

    `None` SIEMPRE significa "no colocar apuestas para este usuario" —
    protege de apostar sin saldo o con montos que el usuario no eligió.
    """
    cfg = get_config(config.usuario)

    if cfg.modo != CapitalConfig.MODO_COMPUESTO:
        return int(config.stake), 'fijo'

    if cfg.balance_inicial is None or cfg.ancla is None:
        return None, 'sin_balance'

    balance = bankroll_cop(config.usuario)
    if balance is None or balance <= 0:
        return None, 'sin_saldo'

    # % del balance, redondeado hacia ABAJO a múltiplos de 100 COP
    # (conservador: nunca apostar más de lo calculado).
    stake_cop = int(balance * cfg.porcentaje / 100.0)
    stake_cop = (stake_cop // 100) * 100

    if stake_cop < cfg.stake_min_cop:
        return None, 'stake_minimo'
    if stake_cop > cfg.stake_max_cop:
        stake_cop = cfg.stake_max_cop

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
