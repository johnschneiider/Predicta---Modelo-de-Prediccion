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

    class Meta:
        verbose_name = "Configuración Auto-Betting"
        verbose_name_plural = "Configuración Auto-Betting"

    def __str__(self):
        return f"Auto-Betting Config (cuota>{self.cuota_minima}, stake={self.stake}, max={self.max_apuestas_diarias}/día)"



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
