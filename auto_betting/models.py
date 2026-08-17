"""
Modelos para el sistema de apuestas automáticas de córners en BetPlay.
"""

from django.db import models
from django.utils import timezone


class AutoBetConfig(models.Model):
    """Configuración global del auto-betting (singleton)."""

    ticket = models.TextField(verbose_name="Ticket de login BetPlay")
    punter_id = models.CharField(max_length=50, default="2585240", verbose_name="Punter ID")

    # Parámetros de estrategia
    cuota_minima = models.FloatField(default=2.0, verbose_name="Cuota mínima (>)")
    odds_minima = models.FloatField(default=1.5, verbose_name="Odds mínima")
    stake = models.IntegerField(default=500000, verbose_name="Stake (en unidades Kambi, 500000=500 COP)")
    max_apuestas_diarias = models.IntegerField(default=5, verbose_name="Máximo de apuestas por día")
    horas_adelante = models.IntegerField(default=24, verbose_name="Horas hacia adelante para escanear")

    # Control
    activo = models.BooleanField(default=True, verbose_name="Sistema activo")

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración Auto-Betting"
        verbose_name_plural = "Configuración Auto-Betting"

    def __str__(self):
        return f"Auto-Betting Config (cuota>{self.cuota_minima}, stake={self.stake}, max={self.max_apuestas_diarias}/día)"

    def save(self, *args, **kwargs):
        """Singleton: solo puede haber una configuración."""
        if not self.pk and AutoBetConfig.objects.exists():
            self.pk = AutoBetConfig.objects.first().pk
        super().save(*args, **kwargs)


class AutoBet(models.Model):
    """Apuesta colocada automáticamente por el sistema."""

    ESTADO_CHOICES = [
        ('OPEN', 'Abierta'),
        ('WIN', 'Ganada'),
        ('LOSE', 'Perdida'),
        ('VOID', 'Anulada'),
        ('CASHOUT', 'Cashout'),
        ('ERROR', 'Error'),
    ]

    # Datos del partido
    evento_id = models.BigIntegerField(verbose_name="Event ID (Kambi)")
    home_team = models.CharField(max_length=200, verbose_name="Equipo Local")
    away_team = models.CharField(max_length=200, verbose_name="Equipo Visitante")
    liga = models.CharField(max_length=200, verbose_name="Liga")
    start_time = models.DateTimeField(verbose_name="Inicio del partido")

    # Datos de la apuesta
    mercado = models.CharField(max_length=100, verbose_name="Mercado")
    seleccion = models.CharField(max_length=100, verbose_name="Selección")
    linea = models.FloatField(null=True, blank=True, verbose_name="Línea")
    cuota = models.FloatField(verbose_name="Cuota jugada")

    # Datos de la predicción
    corners_predichos = models.FloatField(verbose_name="Córners predichos")
    predicta_prob = models.FloatField(verbose_name="Probabilidad Predicta (%)")
    edge = models.FloatField(verbose_name="Edge (%)")
    ev = models.FloatField(verbose_name="EV")

    # Resultado de la apuesta en BetPlay
    coupon_ref = models.BigIntegerField(null=True, blank=True, verbose_name="Coupon Ref")
    bet_ref = models.BigIntegerField(null=True, blank=True, verbose_name="Bet Ref")
    stake = models.IntegerField(default=500000, verbose_name="Stake (Kambi)")
    potential_payout = models.BigIntegerField(null=True, blank=True, verbose_name="Pago potencial")

    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='OPEN', verbose_name="Estado")
    error_msg = models.TextField(blank=True, default="", verbose_name="Mensaje de error")

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Apuesta Automática"
        verbose_name_plural = "Apuestas Automáticas"
        ordering = ['-creado']
        indexes = [
            models.Index(fields=['-creado']),
            models.Index(fields=['evento_id', 'mercado']),
        ]

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} | {self.mercado} {self.seleccion} @ {self.cuota} | {self.estado}"


class DailyCounter(models.Model):
    """Contador diario de apuestas para el límite."""

    fecha = models.DateField(unique=True, verbose_name="Fecha")
    apuestas_colocadas = models.IntegerField(default=0, verbose_name="Apuestas colocadas")

    class Meta:
        verbose_name = "Contador Diario"
        verbose_name_plural = "Contadores Diarios"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.fecha} — {self.apuestas_colocadas} apuestas"


class HistorialApuesta(models.Model):
    """Historial completo de apuestas (coupons) traído de BetPlay/Kambi."""

    coupon_ref = models.BigIntegerField(unique=True, verbose_name="Coupon Ref")
    coupon_external_ref = models.CharField(max_length=100, blank=True, default="", verbose_name="External Ref")
    placed_date = models.DateTimeField(null=True, blank=True, verbose_name="Fecha colocada")
    bet_ref = models.BigIntegerField(null=True, blank=True, verbose_name="Bet Ref")
    bet_odds = models.FloatField(null=True, blank=True, verbose_name="Cuota (decimal)")
    played_odds = models.FloatField(null=True, blank=True, verbose_name="Cuota jugada (decimal)")
    bet_status = models.CharField(max_length=10, default="OPEN", verbose_name="Estado (Kambi)")
    stake = models.IntegerField(default=0, verbose_name="Stake (unidades Kambi)")
    payout = models.BigIntegerField(default=0, verbose_name="Payout (unidades Kambi)")
    potential_payout = models.BigIntegerField(default=0, verbose_name="Payout potencial")

    outcome_id = models.BigIntegerField(null=True, blank=True, verbose_name="Outcome ID")
    event_id = models.BigIntegerField(null=True, blank=True, verbose_name="Event ID")
    home_team = models.CharField(max_length=200, blank=True, default="", verbose_name="Local")
    away_team = models.CharField(max_length=200, blank=True, default="", verbose_name="Visitante")
    event_start_date = models.DateTimeField(null=True, blank=True, verbose_name="Inicio del partido")
    seleccion = models.CharField(max_length=200, blank=True, default="", verbose_name="Selección")
    mercado = models.CharField(max_length=250, blank=True, default="", verbose_name="Mercado")
    linea = models.FloatField(null=True, blank=True, verbose_name="Línea")
    sport = models.CharField(max_length=50, blank=True, default="", verbose_name="Deporte")
    liga = models.CharField(max_length=200, blank=True, default="", verbose_name="Liga")

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Historial de Apuesta"
        verbose_name_plural = "Historial de Apuestas"
        ordering = ['-placed_date']
        indexes = [
            models.Index(fields=['-placed_date']),
            models.Index(fields=['bet_status']),
        ]

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} | {self.seleccion} | {self.bet_status}"

    # ── Propiedades en COP (÷1000) ──
    @property
    def stake_cop(self):
        return self.stake / 1000.0

    @property
    def payout_cop(self):
        return self.payout / 1000.0

    @property
    def potential_cop(self):
        return self.potential_payout / 1000.0

    @property
    def profit_cop(self):
        """Beneficio neto en COP (payout - stake)."""
        return (self.payout - self.stake) / 1000.0
