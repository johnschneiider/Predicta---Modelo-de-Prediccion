# -*- coding: utf-8 -*-
"""Motor independiente de parleys reales.

No toca AutoBet, AutoBetConfig, DailyCounter ni el motor real:
- Lee picks ya colocados por el motor real (AutoBet) en modo lectura.
- Lleva su propio capital/ledger y sus propias tablas de cupones.
- Liquida desde el historial de cupones de BetPlay, no desde AutoBet.
"""
from django.conf import settings
from django.db import models
from django.utils import timezone

JUNK_DEFAULT = "descanso\nprimera parte\ncuotas del partido\nganador\nesquina"


class ParleyEngineConfig(models.Model):
    """Configuración singleton por usuario (multi-usuario desde 2026-10-31)."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='parley_engine_config', verbose_name='Usuario')
    activo = models.BooleanField(default=False, verbose_name='Motor activo')
    dry_run = models.BooleanField(default=True, verbose_name='Dry-run (no coloca)')
    stake = models.IntegerField(default=500, verbose_name='Stake COP por parley')
    capital_inicial = models.IntegerField(default=100000, verbose_name='Capital inicial COP')
    ev_gate = models.FloatField(default=0.80, verbose_name='EV mínimo')
    max_legs = models.IntegerField(default=2, verbose_name='Patas máximas')
    min_fit = models.IntegerField(default=50, verbose_name='Mínimo de bets para el fit')
    junk_mercados = models.TextField(
        default=JUNK_DEFAULT,
        verbose_name='Filtros de mercado (una frase por línea)')
    requests_per_minute = models.IntegerField(
        default=30, verbose_name='Requests por minuto (rate limit)')
    max_backoff_seconds = models.IntegerField(
        default=300, verbose_name='Backoff máximo (segundos)')
    request_timeout = models.IntegerField(
        default=20, verbose_name='Timeout HTTP (segundos)')
    max_placements_per_run = models.IntegerField(
        default=5,
        verbose_name='Máximo de colocaciones por corrida',
        help_text='Tope duro para no saturar la API ni el saldo. 0 = sin tope.')
    place_interval_seconds = models.IntegerField(
        default=30,
        verbose_name='Pausa entre colocaciones (segundos)',
        help_text='Coloca poco a poco: espera este tiempo entre apuestas.')
    notas = models.TextField(blank=True, default='')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Config motor parleys'
        verbose_name_plural = 'Config motor parleys'

    def __str__(self):
        return (f'Parleys {self.usuario} · EV>={self.ev_gate} · '
                f'{self.stake} COP · {"DRY" if self.dry_run else "REAL"}')


class ParleyRun(models.Model):
    """Auditoría de cada corrida del motor."""

    MODO_CHOICES = [('DRY', 'Dry-run'), ('LIVE', 'Real')]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='parley_runs')
    modo = models.CharField(max_length=5, choices=MODO_CHOICES, default='DRY')
    dia = models.DateField(null=True, blank=True)
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=True)
    error = models.TextField(blank=True, default='')
    args = models.CharField(max_length=300, blank=True, default='')

    n_picks = models.IntegerField(default=0)
    n_eventos = models.IntegerField(default=0)
    n_candidates = models.IntegerField(default=0)
    n_would_place = models.IntegerField(default=0)
    n_placed = models.IntegerField(default=0)
    n_skipped = models.IntegerField(default=0)
    n_pending = models.IntegerField(default=0)
    n_errors = models.IntegerField(default=0)
    n_rate_limits = models.IntegerField(default=0)
    ledger_start = models.FloatField(null=True, blank=True)
    ledger_end = models.FloatField(null=True, blank=True)
    elapsed_ms = models.IntegerField(default=0)

    class Meta:
        verbose_name = 'Corrida motor parleys'
        verbose_name_plural = 'Corridas motor parleys'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.modo} {self.dia} · {self.n_placed} colocados'


class ParleyCoupon(models.Model):
    """Cupón combinado (manual o del motor) con todas sus patas.

    `coupon_ref` es único y viene de BetPlay. `key` solo existe para cupones
    del motor y es la llave de idempotencia `dia|ids`.
    """

    ESTADO_CHOICES = [
        ('OPEN', 'Abierta'),
        ('WON', 'Ganada'),
        ('LOST', 'Perdida'),
        ('VOID', 'Anulada'),
        ('CASHOUT', 'Cashout'),
        ('PUSH', 'Push'),
        ('ERROR', 'Error'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='parley_coupons')
    coupon_ref = models.BigIntegerField(unique=True, null=True, blank=True)
    bet_ref = models.BigIntegerField(null=True, blank=True)
    is_motor = models.BooleanField(default=False, db_index=True)
    key = models.CharField(max_length=300, unique=True, null=True, blank=True)
    dia = models.DateField(null=True, blank=True, db_index=True,
                           verbose_name='Día (Bogotá) de los picks')
    placed_date = models.DateTimeField(null=True, blank=True, db_index=True)
    stake = models.IntegerField(default=500, verbose_name='Stake COP')
    payout = models.FloatField(null=True, blank=True, verbose_name='Payout COP')
    potential_payout = models.FloatField(null=True, blank=True,
                                         verbose_name='Payout potencial COP')
    played_odds = models.FloatField(null=True, blank=True)
    n_legs = models.IntegerField(default=2)
    status = models.CharField(max_length=10, choices=ESTADO_CHOICES,
                              default='OPEN', db_index=True)
    sport = models.CharField(max_length=32, blank=True, default='', db_index=True)
    legs = models.JSONField(default=list, blank=True)
    request_id = models.CharField(max_length=64, blank=True, default='')
    engine_run = models.ForeignKey(
        ParleyRun, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='coupons')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Cupón parley'
        verbose_name_plural = 'Cupones parley'
        ordering = ['-placed_date', '-id']
        indexes = [
            models.Index(fields=['usuario', '-placed_date']),
            models.Index(fields=['usuario', 'status']),
            models.Index(fields=['is_motor', 'status']),
        ]

    @property
    def pnl(self):
        if self.payout is None or self.status == 'OPEN':
            return None
        return float(self.payout) - float(self.stake or 0)

    @property
    def fechas_encuentro(self):
        """Fechas (Bogotá) de los partidos del cupón, sin duplicados."""
        fechas = set()
        for leg in self.leg_rows.all():
            ab = leg.autobet if leg.autobet_id else None
            if ab and ab.start_time:
                fechas.add(timezone.localtime(ab.start_time).date())
        if not fechas:
            if self.dia:
                fechas.add(self.dia)
            elif self.placed_date:
                fechas.add(timezone.localtime(self.placed_date).date())
        return sorted(fechas)

    def __str__(self):
        return f'{self.coupon_ref or self.key} · {self.n_legs} patas · {self.status}'


class ParleyCouponLeg(models.Model):
    """Pata normalizada de un cupón parley (manual o del motor)."""

    coupon = models.ForeignKey(
        ParleyCoupon, on_delete=models.CASCADE, related_name='leg_rows')
    autobet = models.ForeignKey(
        'auto_betting.AutoBet', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='parley_engine_legs')
    position = models.IntegerField(default=0)
    event_id = models.BigIntegerField(null=True, blank=True)
    home_team = models.CharField(max_length=200, blank=True, default='')
    away_team = models.CharField(max_length=200, blank=True, default='')
    liga = models.CharField(max_length=200, blank=True, default='')
    sport = models.CharField(max_length=32, blank=True, default='')
    mercado = models.CharField(max_length=160, blank=True, default='')
    seleccion = models.CharField(max_length=160, blank=True, default='')
    linea = models.FloatField(null=True, blank=True)
    cuota_original = models.FloatField(null=True, blank=True)
    cuota_colocada = models.FloatField(null=True, blank=True)
    prob = models.FloatField(null=True, blank=True,
                             verbose_name='Prob modelo (%)')
    p_rec = models.FloatField(null=True, blank=True)
    q = models.FloatField(null=True, blank=True)
    outcome_id = models.BigIntegerField(null=True, blank=True)
    betoffer_id = models.BigIntegerField(null=True, blank=True)
    estado_final = models.CharField(max_length=10, blank=True, default='')

    class Meta:
        verbose_name = 'Pata cupón parley'
        verbose_name_plural = 'Patas cupón parley'
        ordering = ['position']
        indexes = [models.Index(fields=['coupon', 'position'])]

    def __str__(self):
        return f'{self.coupon_id} #{self.position} {self.seleccion}'


class ParleyLedger(models.Model):
    """Ledger interno del capital dedicado a parleys (misma cuenta BetPlay)."""

    TIPO_CHOICES = [
        ('PLACEMENT', 'Colocación'),
        ('SETTLEMENT', 'Liquidación'),
        ('ADJUSTMENT', 'Ajuste'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='parley_ledger')
    coupon = models.ForeignKey(
        ParleyCoupon, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='ledger_entries')
    tipo = models.CharField(max_length=12, choices=TIPO_CHOICES)
    monto = models.FloatField(verbose_name='Monto COP (con signo)')
    balance_after = models.FloatField()
    nota = models.CharField(max_length=300, blank=True, default='')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Movimiento ledger parleys'
        verbose_name_plural = 'Movimientos ledger parleys'
        ordering = ['-creado', '-id']
        indexes = [
            models.Index(fields=['usuario', '-creado']),
            models.Index(fields=['coupon', 'tipo']),
        ]

    def __str__(self):
        return f'{self.tipo} {self.monto:+.2f} → {self.balance_after:.2f}'
