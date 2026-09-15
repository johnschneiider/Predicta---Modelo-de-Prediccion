"""
Modelos para el sistema de apuestas automáticas de córners en BetPlay.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class AutoBetConfig(models.Model):
    """Configuración del auto-betting (una por usuario)."""

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='auto_bet_config',
        verbose_name="Usuario",
    )
    ticket = models.TextField(verbose_name="Ticket de login BetPlay")
    punter_id = models.CharField(max_length=50, default="", verbose_name="Punter ID")

    # Parámetros de estrategia
    cuota_minima = models.FloatField(default=2.0, verbose_name="Cuota mínima (>)")
    odds_minima = models.FloatField(default=1.5, verbose_name="Odds mínima")
    stake = models.IntegerField(default=500000, verbose_name="Stake (en unidades Kambi, 500000=500 COP)")
    max_apuestas_diarias = models.IntegerField(default=20, verbose_name="Máximo de apuestas por día")
    horas_adelante = models.IntegerField(default=24, verbose_name="Horas hacia adelante para escanear")

    # Control
    activo = models.BooleanField(default=True, verbose_name="Sistema activo")

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    ticket_actualizado = models.DateTimeField(null=True, blank=True, verbose_name="Ticket actualizado el")

    class Meta:
        verbose_name = "Configuración Auto-Betting"
        verbose_name_plural = "Configuración Auto-Betting"

    def __str__(self):
        return f"Auto-Betting Config (cuota>{self.cuota_minima}, stake={self.stake}, max={self.max_apuestas_diarias}/día)"

    def save(self, *args, **kwargs):
        """Track cuándo cambia el ticket para medir TTL y avisar antes de vencer."""
        if self.pk:
            old_ticket = AutoBetConfig.objects.filter(pk=self.pk).values_list('ticket', flat=True).first()
            if old_ticket is not None and old_ticket != self.ticket:
                self.ticket_actualizado = timezone.now()
        elif self.ticket:
            self.ticket_actualizado = timezone.now()
        super().save(*args, **kwargs)



class MarketFilterConfig(models.Model):
    """
    Umbrales de estrategia por SUBMERCADO (mercado + lado over/under/sí/no).

    Configuración GLOBAL (una sola fila, singleton) — aplica igual para todos
    los usuarios/cuentas del auto-betting. Solo un superusuario (admin) puede
    editarla desde /auto-betting/configuracion/ (ver views.configuracion).

    Motivación (auditoría 2026-08-23): dentro de un mismo mercado, el lado
    Over y el lado Under tienen rendimiento muy distinto (ej. córners-over
    +20.5% ROI vs córners-under -55.5% ROI). Antes `MARKET_FILTERS` en
    strategy.py solo distinguía por mercado, no por lado. Este modelo permite
    ajustar cada submercado de forma independiente sin tocar código.

    Valores por defecto = los que ya estaban vigentes en `MARKET_FILTERS`
    (strategy.py) antes de este cambio, para no alterar el comportamiento
    del sistema al desplegar. El admin puede ajustarlos después con datos.
    """

    # Goles totales
    goals_over_min_p = models.FloatField(default=0.50, verbose_name="Goles Over — P mínima")
    goals_over_min_confidence = models.FloatField(default=0.35, verbose_name="Goles Over — Confianza mínima")
    goals_over_enabled = models.BooleanField(default=True, verbose_name="Goles Over — Activo")
    goals_over_min_ev = models.FloatField(default=0.15, verbose_name="Goles Over — EV mínimo")
    goals_over_min_cuota = models.FloatField(default=0.0, verbose_name="Goles Over — Cuota mínima (0=usa global)")
    goals_under_min_p = models.FloatField(default=0.54, verbose_name="Goles Under — P mínima")
    goals_under_min_confidence = models.FloatField(default=0.35, verbose_name="Goles Under — Confianza mínima")
    goals_under_enabled = models.BooleanField(default=True, verbose_name="Goles Under — Activo")
    goals_under_min_ev = models.FloatField(default=0.0, verbose_name="Goles Under — EV mínimo")
    goals_under_min_cuota = models.FloatField(default=0.0, verbose_name="Goles Under — Cuota mínima (0=usa global)")

    # Córners (Total de Tiros de Esquina)
    corners_over_min_p = models.FloatField(default=0.56, verbose_name="Córners Over — P mínima")
    corners_over_min_confidence = models.FloatField(default=0.35, verbose_name="Córners Over — Confianza mínima")
    corners_over_enabled = models.BooleanField(default=True, verbose_name="Córners Over — Activo")
    corners_over_min_ev = models.FloatField(default=0.20, verbose_name="Córners Over — EV mínimo")
    corners_over_min_cuota = models.FloatField(default=0.0, verbose_name="Córners Over — Cuota mínima (0=usa global)")
    corners_under_min_p = models.FloatField(default=0.56, verbose_name="Córners Under — P mínima")
    corners_under_min_confidence = models.FloatField(default=0.35, verbose_name="Córners Under — Confianza mínima")
    corners_under_enabled = models.BooleanField(default=False, verbose_name="Córners Under — Activo")
    corners_under_min_ev = models.FloatField(default=0.0, verbose_name="Córners Under — EV mínimo")
    corners_under_min_cuota = models.FloatField(default=0.0, verbose_name="Córners Under — Cuota mínima (0=usa global)")

    # Tiros a puerta (shots on target)
    shots_on_target_over_min_p = models.FloatField(default=0.56, verbose_name="Tiros a puerta Over — P mínima")
    shots_on_target_over_min_confidence = models.FloatField(default=0.35, verbose_name="Tiros a puerta Over — Confianza mínima")
    shots_on_target_over_enabled = models.BooleanField(default=True, verbose_name="Tiros a puerta Over — Activo")
    shots_on_target_over_min_ev = models.FloatField(default=0.0, verbose_name="Tiros a puerta Over — EV mínimo")
    shots_on_target_over_min_cuota = models.FloatField(default=0.0, verbose_name="Tiros a puerta Over — Cuota mínima (0=usa global)")
    shots_on_target_under_min_p = models.FloatField(default=0.56, verbose_name="Tiros a puerta Under — P mínima")
    shots_on_target_under_min_confidence = models.FloatField(default=0.35, verbose_name="Tiros a puerta Under — Confianza mínima")
    shots_on_target_under_enabled = models.BooleanField(default=True, verbose_name="Tiros a puerta Under — Activo")
    shots_on_target_under_min_ev = models.FloatField(default=0.0, verbose_name="Tiros a puerta Under — EV mínimo")
    shots_on_target_under_min_cuota = models.FloatField(default=0.0, verbose_name="Tiros a puerta Under — Cuota mínima (0=usa global)")
    # Fix 2026-08-31: filtro por línea. Los under de línea baja (7.5/8.5) sangran
    # (WR 27%/40%) porque el modelo subestima ~2 tiros; el under 9.5+ sí rinde (80%).
    # min_line=9.5 por defecto => solo se apuesta Under de línea >= 9.5.
    shots_on_target_under_min_line = models.FloatField(default=9.5, verbose_name="Tiros a puerta Under — Línea mínima")
    shots_on_target_under_max_line = models.FloatField(default=0.0, verbose_name="Tiros a puerta Under — Línea máxima (0=sin tope)")
    shots_on_target_over_min_line = models.FloatField(default=0.0, verbose_name="Tiros a puerta Over — Línea mínima")
    shots_on_target_over_max_line = models.FloatField(default=0.0, verbose_name="Tiros a puerta Over — Línea máxima (0=sin tope)")

    # Remates totales (motor v2.3, integración 2026-09-14 — decisión John)
    remates_over_min_p = models.FloatField(default=0.50, verbose_name="Remates totales Over — P mínima")
    remates_over_min_confidence = models.FloatField(default=0.35, verbose_name="Remates totales Over — Confianza mínima")
    remates_over_enabled = models.BooleanField(default=True, verbose_name="Remates totales Over — Activo")
    remates_over_min_ev = models.FloatField(default=0.0, verbose_name="Remates totales Over — EV mínimo")
    remates_over_min_cuota = models.FloatField(default=0.0, verbose_name="Remates totales Over — Cuota mínima (0=usa global)")
    remates_over_min_line = models.FloatField(default=0.0, verbose_name="Remates totales Over — Línea mínima")
    remates_over_max_line = models.FloatField(default=0.0, verbose_name="Remates totales Over — Línea máxima (0=sin tope)")
    remates_under_min_p = models.FloatField(default=0.50, verbose_name="Remates totales Under — P mínima")
    remates_under_min_confidence = models.FloatField(default=0.35, verbose_name="Remates totales Under — Confianza mínima")
    remates_under_enabled = models.BooleanField(default=True, verbose_name="Remates totales Under — Activo")
    remates_under_min_ev = models.FloatField(default=0.0, verbose_name="Remates totales Under — EV mínimo")
    remates_under_min_cuota = models.FloatField(default=0.0, verbose_name="Remates totales Under — Cuota mínima (0=usa global)")
    remates_under_min_line = models.FloatField(default=0.0, verbose_name="Remates totales Under — Línea mínima")
    remates_under_max_line = models.FloatField(default=0.0, verbose_name="Remates totales Under — Línea máxima (0=sin tope)")

    # Ambos equipos marcan (BTTS)
    btts_si_min_p = models.FloatField(default=0.52, verbose_name="BTTS Sí — P mínima")
    btts_si_min_confidence = models.FloatField(default=0.35, verbose_name="BTTS Sí — Confianza mínima")
    btts_si_enabled = models.BooleanField(default=True, verbose_name="BTTS Sí — Activo")
    btts_si_min_ev = models.FloatField(default=0.0, verbose_name="BTTS Sí — EV mínimo")
    btts_si_min_cuota = models.FloatField(default=0.0, verbose_name="BTTS Sí — Cuota mínima (0=usa global)")
    btts_no_min_p = models.FloatField(default=0.50, verbose_name="BTTS No — P mínima")
    btts_no_min_confidence = models.FloatField(default=0.35, verbose_name="BTTS No — Confianza mínima")
    btts_no_enabled = models.BooleanField(default=False, verbose_name="BTTS No — Activo")
    btts_no_min_ev = models.FloatField(default=0.0, verbose_name="BTTS No — EV mínimo")
    btts_no_min_cuota = models.FloatField(default=0.0, verbose_name="BTTS No — Cuota mínima (0=usa global)")

    # ── Controles globales (auditoría 2026-08-23) ──
    cuota_minima_global = models.FloatField(
        default=2.5, verbose_name="Cuota mínima global",
        help_text="Piso de cuota para TODO el sistema. Reemplaza el 2.0 per-user.")
    stop_loss_diario_cop = models.FloatField(
        default=-30000.0, verbose_name="Stop-loss diario (COP)",
        help_text="Si el P&L del día (solo sistema) baja de esto, se detiene el auto-betting. 0 = desactivado.")
    max_exposicion_evento_cop = models.FloatField(
        default=20000.0, verbose_name="Máx. exposición por evento/mercado (COP)",
        help_text="Tope de stake combinado (todas las cuentas) por evento+mercado. 0 = desactivado.")
    calib_cap = models.FloatField(
        default=0.58, verbose_name="Cap de calibración de probabilidad",
        help_text="Cap duro de probabilidad calibrada. La auditoría muestra anti-señal arriba de 0.60.")

    actualizado = models.DateTimeField(auto_now=True, verbose_name="Última actualización")
    actualizado_por = models.CharField(max_length=200, blank=True, default="", verbose_name="Actualizado por")

    class Meta:
        verbose_name = "Configuración de Umbrales por Submercado"
        verbose_name_plural = "Configuración de Umbrales por Submercado"

    def __str__(self):
        return f"Umbrales por submercado (global) — actualizado {self.actualizado:%Y-%m-%d %H:%M}"

    @classmethod
    def get_solo(cls):
        """Devuelve la única fila de configuración global (la crea si no existe)."""
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def as_market_filters(self):
        """
        Convierte la config a un dict por submercado consumible por
        `strategy.select_bets(market_filters=...)`. Cada submercado incluye:
        min_p, min_confidence, enabled, min_ev, min_cuota.
        """
        return {
            'goals_over': {
                'min_p': self.goals_over_min_p, 'min_confidence': self.goals_over_min_confidence,
                'enabled': self.goals_over_enabled, 'min_ev': self.goals_over_min_ev,
                'min_cuota': self.goals_over_min_cuota,
            },
            'goals_under': {
                'min_p': self.goals_under_min_p, 'min_confidence': self.goals_under_min_confidence,
                'enabled': self.goals_under_enabled, 'min_ev': self.goals_under_min_ev,
                'min_cuota': self.goals_under_min_cuota,
            },
            'corners_over': {
                'min_p': self.corners_over_min_p, 'min_confidence': self.corners_over_min_confidence,
                'enabled': self.corners_over_enabled, 'min_ev': self.corners_over_min_ev,
                'min_cuota': self.corners_over_min_cuota,
            },
            'corners_under': {
                'min_p': self.corners_under_min_p, 'min_confidence': self.corners_under_min_confidence,
                'enabled': self.corners_under_enabled, 'min_ev': self.corners_under_min_ev,
                'min_cuota': self.corners_under_min_cuota,
            },
            'shots_on_target_over': {
                'min_p': self.shots_on_target_over_min_p, 'min_confidence': self.shots_on_target_over_min_confidence,
                'enabled': self.shots_on_target_over_enabled, 'min_ev': self.shots_on_target_over_min_ev,
                'min_cuota': self.shots_on_target_over_min_cuota,
                'min_line': self.shots_on_target_over_min_line, 'max_line': self.shots_on_target_over_max_line,
            },
            'shots_on_target_under': {
                'min_p': self.shots_on_target_under_min_p, 'min_confidence': self.shots_on_target_under_min_confidence,
                'enabled': self.shots_on_target_under_enabled, 'min_ev': self.shots_on_target_under_min_ev,
                'min_cuota': self.shots_on_target_under_min_cuota,
                'min_line': self.shots_on_target_under_min_line, 'max_line': self.shots_on_target_under_max_line,
            },
            'remates_over': {
                'min_p': self.remates_over_min_p, 'min_confidence': self.remates_over_min_confidence,
                'enabled': self.remates_over_enabled, 'min_ev': self.remates_over_min_ev,
                'min_cuota': self.remates_over_min_cuota,
                'min_line': self.remates_over_min_line, 'max_line': self.remates_over_max_line,
            },
            'remates_under': {
                'min_p': self.remates_under_min_p, 'min_confidence': self.remates_under_min_confidence,
                'enabled': self.remates_under_enabled, 'min_ev': self.remates_under_min_ev,
                'min_cuota': self.remates_under_min_cuota,
                'min_line': self.remates_under_min_line, 'max_line': self.remates_under_max_line,
            },
            'btts_si': {
                'min_p': self.btts_si_min_p, 'min_confidence': self.btts_si_min_confidence,
                'enabled': self.btts_si_enabled, 'min_ev': self.btts_si_min_ev,
                'min_cuota': self.btts_si_min_cuota,
            },
            'btts_no': {
                'min_p': self.btts_no_min_p, 'min_confidence': self.btts_no_min_confidence,
                'enabled': self.btts_no_enabled, 'min_ev': self.btts_no_min_ev,
                'min_cuota': self.btts_no_min_cuota,
            },
        }

    def as_globals(self):
        """Controles globales para run_auto_bets / calibración."""
        return {
            'cuota_minima_global': self.cuota_minima_global,
            'stop_loss_diario_cop': self.stop_loss_diario_cop,
            'max_exposicion_evento_cop': self.max_exposicion_evento_cop,
            'calib_cap': self.calib_cap,
        }


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

    # Tenant
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='auto_bets',
        verbose_name="Usuario",
    )

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
    # P cruda del modelo ANTES de calibrate_probability. Persistirla es la base
    # para re-calibrar con datos reales sin depender de logs (2026-08-31).
    predicta_prob_raw = models.FloatField(null=True, blank=True,
                                          verbose_name="Probabilidad cruda (%)")
    confidence = models.FloatField(null=True, blank=True, verbose_name="Confianza (%)")
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
    """Contador diario de apuestas para el límite (por usuario)."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='daily_counters',
        verbose_name="Usuario",
    )
    fecha = models.DateField(verbose_name="Fecha")
    apuestas_colocadas = models.IntegerField(default=0, verbose_name="Apuestas colocadas")

    class Meta:
        verbose_name = "Contador Diario"
        verbose_name_plural = "Contadores Diarios"
        ordering = ['-fecha']
        unique_together = [('usuario', 'fecha')]

    def __str__(self):
        return f"{self.fecha} — {self.apuestas_colocadas} apuestas"


class HistorialApuesta(models.Model):
    """Historial completo de apuestas (coupons) traído de BetPlay/Kambi."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='historial_apuestas',
        verbose_name="Usuario",
    )
    coupon_ref = models.BigIntegerField(verbose_name="Coupon Ref")
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

    # CLV (Closing Line Value)
    closing_odds = models.FloatField(null=True, blank=True, verbose_name="Cuota de cierre")
    clv = models.FloatField(null=True, blank=True, verbose_name="CLV % (negativo = sin valor)")

    # Clasificación sistema vs manual
    is_system = models.BooleanField(default=False, verbose_name="Apuesta del sistema")

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Historial de Apuesta"
        verbose_name_plural = "Historial de Apuestas"
        ordering = ['-placed_date']
        unique_together = [('usuario', 'coupon_ref')]
        indexes = [
            models.Index(fields=['-placed_date']),
            models.Index(fields=['bet_status']),
            models.Index(fields=['is_system', '-placed_date']),
            models.Index(fields=['outcome_id', '-placed_date']),
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


class OddsSnapshot(models.Model):
    """Snapshot de cuota por outcome, para cálculo de CLV."""

    outcome_id = models.BigIntegerField(db_index=True, verbose_name="Outcome ID")
    event_id = models.BigIntegerField(db_index=True, verbose_name="Event ID")
    market = models.CharField(max_length=250, verbose_name="Mercado")
    seleccion = models.CharField(max_length=200, blank=True, default="", verbose_name="Selección")
    linea = models.FloatField(null=True, blank=True, verbose_name="Línea")
    side = models.CharField(max_length=20, blank=True, default="", verbose_name="Lado (over/under/1/x/2/si/no)")
    odds_decimal = models.FloatField(verbose_name="Cuota decimal")
    captured_at = models.DateTimeField(auto_now_add=True, verbose_name="Capturado")

    class Meta:
        verbose_name = "Snapshot de Cuota"
        verbose_name_plural = "Snapshots de Cuotas"
        ordering = ['-captured_at']
        indexes = [
            models.Index(fields=['outcome_id', '-captured_at']),
            models.Index(fields=['event_id']),
        ]

    def __str__(self):
        return f"outcome={self.outcome_id} | {self.market} | {self.odds_decimal} | {self.captured_at:%Y-%m-%d %H:%M}"


class CronSchedule(models.Model):
    """Horarios del pipeline de auto-betting.

    Una sola fila por tarea (singleton por nombre). El management command
    `run_scheduler` lee esta tabla cada minuto y ejecuta las tareas que
    tocan a su hora. El crontab del VPS solo necesita una entrada:
        * * * * * ... manage.py run_scheduler

    Esto permite gestionar todos los horarios desde la web
    (/auto-betting/configuracion/umbrales/) sin tocar el crontab.
    """

    TAREA_CHOICES = [
        ('api_football_daily', 'Sync diario API-Football (sync_daily + populate_legacy)'),
        ('sync_bet_history', 'Sync de resultados desde Kambi (bet_status)'),
        ('calibration_report', 'Reporte de calibración (WR real vs P declarada)'),
        ('run_auto_bets', 'Auto-betting (colocar apuestas)'),
        ('capture_closing_odds', 'Captura de cuotas de cierre (CLV)'),
        ('sync_bet_history_vespertino', 'Sync vespertino de resultados'),
        ('api_football_backfill', 'Backfill 2 temporadas (reset cuota 00:00 UTC)'),
        ('check_betplay_tokens', 'Verificación de tickets BetPlay'),
    ]

    tarea = models.CharField(max_length=64, unique=True, choices=TAREA_CHOICES, verbose_name="Tarea")
    hora_utc = models.IntegerField(verbose_name="Hora UTC (0-23)")
    minuto_utc = models.IntegerField(default=0, verbose_name="Minuto UTC (0-59)")
    cada_n_minutos = models.IntegerField(default=0, verbose_name="Repetir cada N minutos (0=solo a la hora fija)")
    enabled = models.BooleanField(default=True, verbose_name="Activo")
    descripcion = models.CharField(max_length=300, blank=True, default="", verbose_name="Descripción")
    ultimo_run = models.DateTimeField(null=True, blank=True, verbose_name="Último ejecución")
    actualizado = models.DateTimeField(auto_now=True, verbose_name="Actualizado")
    actualizado_por = models.CharField(max_length=200, blank=True, default="", verbose_name="Actualizado por")

    class Meta:
        verbose_name = "Horario de Cron"
        verbose_name_plural = "Horarios de Cron"
        ordering = ['hora_utc', 'minuto_utc']

    def __str__(self):
        if self.cada_n_minutos > 0:
            return f"{self.tarea} (cada {self.cada_n_minutos}min)"
        return f"{self.tarea} ({self.hora_utc:02d}:{self.minuto_utc:02d} UTC)"

    @classmethod
    def get_or_create_defaults(cls):
        """Crea las filas por defecto si no existen. Idempotente."""
        defaults = [
            ('api_football_backfill', 0, 0, 0, True, 'Reset cuota API + backfill 2 temporadas'),
            ('api_football_daily', 10, 0, 0, True, 'sync_daily + populate_legacy (BD fresca)'),
            ('sync_bet_history', 10, 15, 0, True, 'Sync bet_status desde Kambi (pre-apuestas)'),
            ('calibration_report', 10, 20, 0, True, 'WR real vs P declarada (7 días)'),
            ('run_auto_bets', 10, 30, 0, True, 'Colocar apuestas (BD fresca, mercados abiertos)'),
            ('sync_bet_history_vespertino', 23, 0, 0, True, 'Sync vespertino (resultados tarde/noche)'),
            ('sync_bet_history_pre', 10, 25, 0, True, 'Sync pre-apuestas (balance fresco para stake %)'),
            ('capture_closing_odds', 0, 0, 15, True, 'Snapshots para CLV (cada 15 min)'),
            ('check_betplay_tokens', 3, 0, 0, True, 'Verificación tickets BetPlay (03:00, 11:00, 18:00 UTC)'),
        ]
        for nombre, hora, minuto, cada, enabled, desc in defaults:
            obj, created = cls.objects.get_or_create(
                tarea=nombre,
                defaults={'hora_utc': hora, 'minuto_utc': minuto, 'cada_n_minutos': cada,
                          'enabled': enabled, 'descripcion': desc}
            )
            if created:
                print(f"  + {nombre}: {hora:02d}:{minuto:02d} UTC (cada {cada}min)" if cada else f"  + {nombre}: {hora:02d}:{minuto:02d} UTC")



class ShowcasePick(models.Model):
    """Partido destacado de la portada: vitrina con datos reales del motor.

    Lo genera `manage.py build_showcase_pick` (dispatcher, cada 30 min) y la
    portada muestra la fila más reciente cuyo partido todavía no ha empezado.
    """

    home_team = models.CharField(max_length=200, verbose_name="Equipo local")
    away_team = models.CharField(max_length=200, verbose_name="Equipo visitante")
    liga = models.CharField(max_length=200, verbose_name="Liga")
    start_time = models.DateTimeField(verbose_name="Inicio del partido (UTC)")

    mercado = models.CharField(max_length=100, verbose_name="Mercado")
    seleccion = models.CharField(max_length=120, verbose_name="Selección")
    linea = models.FloatField(null=True, blank=True, verbose_name="Línea")

    cuota = models.FloatField(verbose_name="Cuota de mercado (BetPlay)")
    cuota_justa = models.FloatField(null=True, blank=True, verbose_name="Cuota justa (1/P del modelo)")
    fair_odds = models.FloatField(null=True, blank=True, verbose_name="Cuota justa devig (referencia)")
    prob = models.FloatField(null=True, blank=True, verbose_name="Probabilidad calibrada (%)")
    prob_raw = models.FloatField(null=True, blank=True, verbose_name="Probabilidad sin calibrar (%)")
    prob_mercado = models.FloatField(null=True, blank=True, verbose_name="Probabilidad implícita de mercado (%)")
    edge = models.FloatField(null=True, blank=True, verbose_name="Edge vs cuota de mercado (%)")
    ev = models.FloatField(null=True, blank=True, verbose_name="EV vs cuota justa devig (%)")
    confianza = models.FloatField(null=True, blank=True, verbose_name="Confianza del modelo (0-1)")

    x12_local = models.FloatField(null=True, blank=True, verbose_name="1X2 local (%)")
    x12_empate = models.FloatField(null=True, blank=True, verbose_name="1X2 empate (%)")
    x12_visita = models.FloatField(null=True, blank=True, verbose_name="1X2 visitante (%)")

    evento_id = models.BigIntegerField(null=True, blank=True, verbose_name="Evento Kambi")
    generado = models.DateTimeField(auto_now_add=True, verbose_name="Generado")

    class Meta:
        verbose_name = "Partido destacado de la portada"
        verbose_name_plural = "Partidos destacados de la portada"
        ordering = ['-generado']

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} — {self.seleccion} (@{self.cuota})"

    # ── Presentación (portada) ──
    @property
    def kickoff_short(self):
        """Hora local (Bogotá) del inicio; agrega día cuando no es hoy."""
        loc = timezone.localtime(self.start_time)
        delta = (loc.date() - timezone.localdate()).days
        prefijo = 'HOY ' if delta == 0 else ('MAÑANA ' if delta == 1 else f'{loc:%d/%m} ')
        return f'{prefijo}{loc:%H:%M}'

    @property
    def chat_label(self):
        """Marca temporal del 'mensaje' (momento en que se generó la señal)."""
        loc = timezone.localtime(self.generado)
        delta = (loc.date() - timezone.localdate()).days
        if delta == 0:
            prefijo = 'HOY'
        elif delta == -1:
            prefijo = 'AYER'
        else:
            prefijo = f'{loc:%d/%m}'
        return f'{prefijo} · {loc:%H:%M}'

    @property
    def prob_display(self):
        return f'{self.prob:.1f}%' if self.prob is not None else '—'

    @property
    def cuota_display(self):
        return f'{self.cuota:.2f}' if self.cuota else '—'

    @property
    def cuota_justa_display(self):
        return f'{self.cuota_justa:.2f}' if self.cuota_justa else '—'

    @property
    def edge_str(self):
        return f'{self.edge:+.1f}%' if self.edge is not None else '—'

    @property
    def confianza_10(self):
        return f'{self.confianza * 10:.1f}' if self.confianza is not None else '—'

    @property
    def x12_local_display(self):
        return f'{self.x12_local:.0f}%' if self.x12_local is not None else '—'

    @property
    def x12_empate_display(self):
        return f'{self.x12_empate:.0f}%' if self.x12_empate is not None else '—'

    @property
    def x12_visita_display(self):
        return f'{self.x12_visita:.0f}%' if self.x12_visita is not None else '—'


class PaperBet(models.Model):
    """Apuesta en PAPEL (paperbet): motores independientes, sin dinero real.
    Registra pick, cuota capturada, probabilidad del motor y resultado real.
    """
    ESTADO_CHOICES = [('OPEN', 'Pendiente'), ('WON', 'Ganada'), ('LOST', 'Perdida'), ('VOID', 'Anulada')]

    creado = models.DateTimeField(auto_now_add=True)
    evento_id = models.CharField(max_length=30, blank=True)
    start_time = models.DateTimeField(null=True, blank=True)
    home_team = models.CharField(max_length=120, blank=True)
    away_team = models.CharField(max_length=120, blank=True)
    liga = models.CharField(max_length=120, blank=True)
    mercado = models.CharField(max_length=120)
    motor = models.CharField(max_length=40, blank=True)
    seleccion = models.CharField(max_length=120)
    linea = models.FloatField(null=True, blank=True)
    cuota = models.FloatField(null=True, blank=True)
    prob = models.FloatField(null=True, blank=True)      # probabilidad calibrada del motor
    ev = models.FloatField(null=True, blank=True)        # prob*cuota - 1
    closing_odds = models.FloatField(null=True, blank=True)  # cuota de cierre (CLV)
    stake = models.IntegerField(default=10000)           # COP virtuales
    estado = models.CharField(max_length=8, choices=ESTADO_CHOICES, default='OPEN', db_index=True)
    resultado_real = models.CharField(max_length=20, blank=True)   # ej. '2-1' / 'Sí' / 'Home'
    payout = models.FloatField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Apuesta paper'
        verbose_name_plural = 'Apuestas paper'
        indexes = [models.Index(fields=['estado', 'motor'])]

    def __str__(self):
        return f'[PAPER] {self.home_team} vs {self.away_team} — {self.mercado} {self.seleccion} ({self.estado})'

    @property
    def clv_pct(self):
        if self.closing_odds and self.cuota:
            return round((self.cuota - self.closing_odds) / self.closing_odds * 100, 2)
        return None

    @property
    def net(self):
        if self.estado == 'WON' and self.payout:
            return self.payout - self.stake
        if self.estado == 'LOST':
            return -self.stake
        return 0


class PaperParlay(models.Model):
    """Combinada en PAPEL: 2 picks con edge de los motores, cuota objetivo ~2.0.
    legs = [{'paperbet_id','evento_id','home','away','mercado','seleccion','linea','cuota','prob','motor'}, ...]
    """
    ESTADO_CHOICES = [('OPEN', 'Pendiente'), ('WON', 'Ganada'), ('LOST', 'Perdida'), ('VOID', 'Anulada')]

    creado = models.DateTimeField(auto_now_add=True)
    legs = models.JSONField(default=list)
    cuota = models.FloatField(null=True, blank=True)       # producto de cuotas
    prob = models.FloatField(null=True, blank=True)        # producto de probabilidades
    ev = models.FloatField(null=True, blank=True)          # prob*cuota - 1
    stake = models.IntegerField(default=10000)             # COP virtuales
    estado = models.CharField(max_length=8, choices=ESTADO_CHOICES, default='OPEN', db_index=True)
    resultado_real = models.CharField(max_length=40, blank=True)  # ej. '2/2'
    payout = models.FloatField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Combinada paper'
        verbose_name_plural = 'Combinadas paper'

    def __str__(self):
        evs = [l.get('evento_id', '?') for l in (self.legs or [])]
        return f'[PARLAY] {evs} ({self.estado})'

    @property
    def net(self):
        if self.estado == 'WON' and self.payout:
            return self.payout - self.stake
        if self.estado == 'LOST':
            return -self.stake
        return 0

    @property
    def resumen(self):
        return ' + '.join(f"{l.get('home','?')[:10]} vs {l.get('away','?')[:10]} ({l.get('seleccion','?')})" for l in (self.legs or []))
