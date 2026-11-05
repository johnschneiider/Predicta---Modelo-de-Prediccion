"""
Modelos para el sistema de apuestas automáticas de córners en BetPlay.
"""

from django.conf import settings
from django.db import models
from django.utils import timezone


class BettingFilterV2(models.Model):
    """
    Filtro V2 (2026-10-03): regla de apuestas en dinero real.

    Solo deja pasar combinaciones liga × mercado × día con ROI positivo
    observado (backtest walk-forward motores de producción + sistema real).
    Texto editable (una regla por línea: `liga | mercado | días`) desde
    /auto-betting/configuracion/v2/. Singleton (pk=1).
    """

    activo = models.BooleanField(default=True, verbose_name="Filtro V2 activo")
    reglas = models.TextField(blank=True, default="", verbose_name="Reglas (liga | mercado | días)")
    actualizado = models.DateTimeField(auto_now=True)
    actualizado_por = models.CharField(max_length=120, blank=True, default="")

    class Meta:
        verbose_name = "Filtro V2 (liga × mercado × día)"
        verbose_name_plural = "Filtro V2"

    def __str__(self):
        return f"Filtro V2 {'ON' if self.activo else 'OFF'} ({len((self.reglas or '').splitlines())} líneas)"

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1, defaults={'activo': True})
        return obj


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
    # 2026-10-01 (ROI admin): tope de línea para Goles Over. Evidencia real admin:
    # línea 2.5 ROI +16.7% (n=60), línea 3.5 −12.2% (n=43). P3b descalibró
    # goals_over por la brecha de 3.5 (+17.9pp); con tope 2.5 la brecha es +5.1pp.
    goals_over_min_line = models.FloatField(default=0.0, verbose_name="Goles Over — Línea mínima")
    goals_over_max_line = models.FloatField(default=0.0, verbose_name="Goles Over — Línea máxima (0=sin tope)")
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

    # Resultado Final 1X2 — motor x12_v2 migrado del paperbet (2026-10-03).
    # La compuerta por defecto replica EXACTAMENTE la del ROI en papel:
    # P >= 0.45, edge >= 5pp vs fair devig (constante MIN_EDGE_VS_MARKET) y
    # cuota >= 1.80. La cuota mínima de este submercado es parte de la
    # estrategia: reemplaza el piso per-user SOLO para x12.
    x12_min_p = models.FloatField(default=0.45, verbose_name="Resultado Final (x12) — P mínima")
    x12_min_confidence = models.FloatField(default=0.35, verbose_name="Resultado Final (x12) — Confianza mínima")
    x12_enabled = models.BooleanField(default=True, verbose_name="Resultado Final (x12) — Activo")
    x12_min_ev = models.FloatField(default=0.0, verbose_name="Resultado Final (x12) — EV mínimo")
    x12_min_cuota = models.FloatField(default=1.80, verbose_name="Resultado Final (x12) — Cuota mínima")

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
                'min_line': self.goals_over_min_line, 'max_line': self.goals_over_max_line,
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
            'x12': {
                'min_p': self.x12_min_p, 'min_confidence': self.x12_min_confidence,
                'enabled': self.x12_enabled, 'min_ev': self.x12_min_ev,
                'min_cuota': self.x12_min_cuota,
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

    # Opinión IA INFORMATIVA sobre apuestas reales (2026-10-07): se registra
    # después de colocar en BetPlay (LLM_MODEL_REAL, default gpt-5.6-luna) y
    # NUNCA bloquea ni filtra. NULL = sin opinión (deshabilitada o fallo).
    llm_verdict = models.BooleanField(null=True, blank=True, verbose_name="Veredicto IA")
    llm_confidence = models.IntegerField(null=True, blank=True, verbose_name="Confianza IA (%)")
    llm_reason = models.TextField(blank=True, default="", verbose_name="Motivo IA")
    llm_model = models.CharField(max_length=60, blank=True, default="", verbose_name="Modelo IA")
    llm_asked_at = models.DateTimeField(null=True, blank=True, verbose_name="IA consultada el")

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

    # Estructura del cupón: 1 = simple, >1 = combinada (n.º de patas).
    # NULL = aún sin verificar (p. ej. ticket vencido en el momento del sync).
    # El inspector NUNCA alerta sobre cupones combinados: el estado global
    # (LOST/WON) no es atribuible a la pata almacenada (solo se guarda la 1ª).
    coupon_legs = models.IntegerField(null=True, blank=True, verbose_name="Patas del cupón (1=simple)")

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
        ('inspect_bets', 'Inspector de apuestas (verificación de liquidaciones)'),
        ('run_paper_bets_basket', 'Paperbet baloncesto 1Q+2Q (recolectar picks)'),
        ('run_paper_bets_basket_gated', 'Paperbet gated basket 1Q+2Q (solo compuerta)'),
        ('run_basket_1q2q_bets', 'Basket 1Q+2Q real (dinero real, ligas whitelist)'),
        ('score_paper_bets_basket', 'Paperbet baloncesto 1Q+2Q (liquidar)'),
        ('train_basket_models', 'Entrenar modelos MCO de baloncesto (API-Sports)'),
        ('run_paper_trades_fx', 'Papertrading FX Deriv (MT5 Quant Lab)'),
        ('run_paper_bets_ou', 'Paperbet OU al descanso (modelo EUROPA/NBA — picks)'),
        ('score_paper_bets_ou', 'Paperbet OU al descanso (liquidación respaldo)'),
        ('calibrar_ou', 'Calibración motor OU descanso (hoja Patron)'),
        ('backfill_ou_sharp', 'Backfill líneas OU del descanso (OddsPapi)'),
        ('reporte_ligas_ou', 'Reporte diario de ligas/compuertas OU descanso'),
        ('ask_llm_real_ventana', 'Opinión IA apuestas reales (ventana T-X antes del inicio)'),
        ('paperparleys', 'Paperparleys (generar+liquidar EV>=1.05, papel)'),
        ('real_parleys', 'Parleys reales (motor independiente)'),
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
            ('inspect_bets', 0, 0, 360, True, 'Inspector: verifica liquidaciones (revisa 24h atrás) cada 6h (00/06/12/18 UTC)'),
            ('reporte_ligas_ou', 11, 0, 0, True, 'Reporte diario de ligas/compuertas del motor OU descanso (11:00 UTC)'),
            ('ask_llm_real_ventana', 0, 0, 5, True, 'Opinión IA de apuestas reales a T-45 (configurable en umbrales) — cada 5 min'),
            ('paperparleys', 0, 0, 60, True, 'Paperparleys: generar + liquidar parlays en papel (cada 60 min)'),
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
    diferencia = models.FloatField(null=True, blank=True)  # Δ = predicción − línea (pts, trazabilidad)
    cuota = models.FloatField(null=True, blank=True)
    prob = models.FloatField(null=True, blank=True)      # probabilidad calibrada del motor
    ev = models.FloatField(null=True, blank=True)        # prob*cuota - 1
    closing_odds = models.FloatField(null=True, blank=True)  # cuota de cierre (CLV)
    closing_linea = models.FloatField(null=True, blank=True)  # línea vista en el cierre (CLV del básquet)
    # Pinnacle (The Odds API) — solo recolección de datos, no interviene en decisiones.
    pin_pregame_linea = models.FloatField(null=True, blank=True)   # total pregame de Pinnacle
    pin_break_linea = models.FloatField(null=True, blank=True)     # total de Pinnacle en 2Q→3Q
    pin_break_at = models.DateTimeField(null=True, blank=True)     # cuándo se capturó el dato del descanso
    stake = models.IntegerField(default=10000)           # COP virtuales
    # Stake Kelly (en unidades del bankroll de la config), motor basket_ou.
    # El resultado principal del paper es 1 u plana (campo `stake`).
    stake_kelly = models.FloatField(null=True, blank=True)
    llm_verdict = models.BooleanField(null=True, blank=True)   # True=aprobado, False=rechazado, None=no evaluado
    llm_reason = models.TextField(blank=True, default='')      # justificación del LLM
    llm_model = models.CharField(max_length=60, blank=True, default='')
    # Confianza declarada por la IA (0-100), p. ej. la opinión de Luna en córners.
    llm_confidence = models.IntegerField(null=True, blank=True)
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


class BasketSample(models.Model):
    """Muestra de entrenamiento del motor basket_1q2q: un partido acabado.

    Cuartos = suma de AMBOS equipos. `evento_clave` = 'liga|id_api' para no
    repetir descargas.
    """
    liga = models.CharField(max_length=64, db_index=True)
    fecha = models.DateField(null=True, blank=True)
    q1 = models.FloatField()
    q2 = models.FloatField()
    q3 = models.FloatField(null=True, blank=True)
    q4 = models.FloatField(null=True, blank=True)
    total = models.FloatField()                       # final, con prórroga
    partido = models.CharField(max_length=200, blank=True, default='')
    fuente = models.CharField(max_length=80, blank=True, default='')
    evento_clave = models.CharField(max_length=160, unique=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Muestra baloncesto'
        verbose_name_plural = 'Muestras baloncesto'
        indexes = [models.Index(fields=['liga', 'fecha'])]

    def __str__(self):
        return f'{self.liga} · {self.partido} ({self.total})'


class BasketModel(models.Model):
    """Modelo MCO por liga: TOTAL = b0 + b1·(1Q) + b2·(2Q) — motor basket_1q2q."""
    liga = models.CharField(max_length=64, unique=True)
    origen = models.CharField(max_length=80, blank=True, default='')
    n = models.IntegerField(default=0)
    b0 = models.FloatField(default=0.0)
    b1 = models.FloatField(default=0.0)
    b2 = models.FloatField(default=0.0)
    a0 = models.FloatField(default=0.0)              # modelo solo-1Q (FORECAST)
    a1 = models.FloatField(default=0.0)
    r2_dos = models.FloatField(default=0.0)
    r2_uno = models.FloatField(default=0.0)
    rmse_dos = models.FloatField(default=0.0)
    rmse_uno = models.FloatField(default=0.0)
    rmse_naive = models.FloatField(default=0.0)
    rmse_test_dos = models.FloatField(default=0.0)   # holdout (se usa en Φ)
    rmse_test_uno = models.FloatField(default=0.0)
    rmse_test_naive = models.FloatField(default=0.0)
    media_total = models.FloatField(default=0.0)
    media_1q = models.FloatField(default=0.0)
    media_2q = models.FloatField(default=0.0)
    fecha_min = models.DateField(null=True, blank=True)
    fecha_max = models.DateField(null=True, blank=True)
    entrenado_en = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Modelo baloncesto (MCO)'
        verbose_name_plural = 'Modelos baloncesto (MCO)'
        ordering = ['liga']

    def __str__(self):
        return f'{self.liga} (n={self.n}, RMSE test {self.rmse_test_dos:.1f})'


class BasketMarketSnapshot(models.Model):
    """Snapshot as-of del mercado de un partido de baloncesto en el descanso 2Q→3Q.

    Se guarda una fila por partido y por pasada del bot (cada 2 min) mientras
    el partido está en ventana: línea y cuotas completas del mercado "Total de
    puntos - Prórroga incluida". Es la base point-in-time del backtest honesto
    (CLV, benchmark devig, camino de la línea) y NUNCA se reconstruye desde
    fuentes actuales.
    """
    evento_id = models.CharField(max_length=30, db_index=True)
    capturado_en = models.DateTimeField(db_index=True)
    start_time = models.DateTimeField(null=True, blank=True)
    liga = models.CharField(max_length=120, blank=True, default='')
    clave_liga = models.CharField(max_length=64, blank=True, default='', db_index=True)
    home_team = models.CharField(max_length=120, blank=True, default='')
    away_team = models.CharField(max_length=120, blank=True, default='')
    q1 = models.FloatField(null=True, blank=True)
    q2 = models.FloatField(null=True, blank=True)
    period_id = models.CharField(max_length=20, blank=True, default='')
    linea = models.FloatField(null=True, blank=True)
    cuota_over = models.FloatField(null=True, blank=True)
    cuota_under = models.FloatField(null=True, blank=True)
    over_abierta = models.BooleanField(default=False)
    under_abierta = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Snapshot de mercado baloncesto'
        verbose_name_plural = 'Snapshots de mercado baloncesto'
        indexes = [models.Index(fields=['evento_id', 'capturado_en'])]

    def __str__(self):
        return (f'{self.home_team} vs {self.away_team} · {self.linea} '
                f'O={self.cuota_over} U={self.cuota_under}')


class PinnacleSnapshot(models.Model):
    """Dato de Pinnacle (The Odds API) para un partido NBA — solo datos.

    Una fila por evento y tipo: `pregame` (total antes del partido) y `break`
    (total live capturado en el descanso 2Q→3Q). Alimenta las columnas
    P. PRE / P. 2Q→3Q del paperbet de baloncesto. No interviene en ninguna
    decisión de apuesta.
    """
    TIPO_CHOICES = [('pregame', 'Prepartido'), ('break', 'Descanso 2Q→3Q')]

    tipo = models.CharField(max_length=8, choices=TIPO_CHOICES, db_index=True)
    sport_key = models.CharField(max_length=32, db_index=True)
    api_event_id = models.CharField(max_length=64, db_index=True)
    kambi_event_id = models.CharField(max_length=30, blank=True, default='', db_index=True)
    home_team = models.CharField(max_length=120, blank=True, default='')
    away_team = models.CharField(max_length=120, blank=True, default='')
    liga = models.CharField(max_length=120, blank=True, default='')
    commence_time = models.DateTimeField(null=True, blank=True)
    capturado_en = models.DateTimeField(db_index=True)
    linea = models.FloatField(null=True, blank=True)
    cuota_over = models.FloatField(null=True, blank=True)
    cuota_under = models.FloatField(null=True, blank=True)
    market_last_update = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Snapshot Pinnacle (baloncesto)'
        verbose_name_plural = 'Snapshots Pinnacle (baloncesto)'
        unique_together = [('api_event_id', 'tipo')]
        indexes = [
            models.Index(fields=['kambi_event_id', 'tipo']),
            models.Index(fields=['tipo', 'capturado_en']),
        ]

    def __str__(self):
        return (f'[{self.tipo}] {self.home_team} vs {self.away_team} · '
                f'{self.linea} O={self.cuota_over} U={self.cuota_under}')


class PinnacleCallLog(models.Model):
    """Auditoría de las llamadas a The Odds API del recolector de baloncesto
    (créditos gastados/restantes por llamada). Solo datos."""
    capturado_en = models.DateTimeField(db_index=True)
    sport_key = models.CharField(max_length=32)
    tipo = models.CharField(max_length=8)
    ok = models.BooleanField(default=False)
    eventos = models.IntegerField(default=0)
    creditos_restantes = models.IntegerField(null=True, blank=True)
    detalle = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        verbose_name = 'Llamada Pinnacle (baloncesto)'
        verbose_name_plural = 'Llamadas Pinnacle (baloncesto)'
        indexes = [models.Index(fields=['sport_key', 'tipo', 'capturado_en'])]

    def __str__(self):
        return (f'[{self.tipo}] {self.sport_key} ok={self.ok} '
                f'eventos={self.eventos} restantes={self.creditos_restantes}')


class BasketOuShadow(models.Model):
    """Decisión SHADOW del motor Over/Under al descanso (`basket_ou`).

    Una fila por partido (dedup por evento), con el último snapshot válido del
    descanso. Se guarda SIEMPRE, aunque la decisión sea NO APOSTAR (evita el
    sesgo de selección). Incluye la liquidación con stake plano de 1 u.
    """
    evento_id = models.CharField(max_length=30, unique=True)
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)
    start_time = models.DateTimeField(null=True, blank=True)
    liga = models.CharField(max_length=120, blank=True, default='')
    clave_liga = models.CharField(max_length=64, blank=True, default='', db_index=True)
    cfg = models.CharField(max_length=64, blank=True, default='')
    home_team = models.CharField(max_length=120, blank=True, default='')
    away_team = models.CharField(max_length=120, blank=True, default='')
    q1h = models.FloatField(null=True, blank=True)
    q1a = models.FloatField(null=True, blank=True)
    q2h = models.FloatField(null=True, blank=True)
    q2a = models.FloatField(null=True, blank=True)
    linea = models.FloatField(null=True, blank=True)
    odds_over = models.FloatField(null=True, blank=True)
    odds_under = models.FloatField(null=True, blank=True)
    margen = models.FloatField(null=True, blank=True)
    proy = models.FloatField(null=True, blank=True)
    diff = models.FloatField(null=True, blank=True)
    sigma = models.FloatField(null=True, blank=True)
    p_over = models.FloatField(null=True, blank=True)
    p_under = models.FloatField(null=True, blank=True)
    ev_over = models.FloatField(null=True, blank=True)
    ev_under = models.FloatField(null=True, blank=True)
    lado = models.CharField(max_length=8, blank=True, default='')
    p_side = models.FloatField(null=True, blank=True)
    ev_side = models.FloatField(null=True, blank=True)
    odds_side = models.FloatField(null=True, blank=True)
    stake_kelly = models.FloatField(null=True, blank=True)   # unidades del bankroll
    filtros = models.JSONField(default=dict, blank=True)
    decision = models.CharField(max_length=20, blank=True, default='')
    cfg_version = models.CharField(max_length=16, blank=True, default='')
    cal_version = models.CharField(max_length=16, blank=True, default='')
    n_snapshots = models.IntegerField(default=0)
    total_reg = models.FloatField(null=True, blank=True)
    total_ot = models.FloatField(null=True, blank=True)
    resultado = models.CharField(max_length=8, blank=True, default='')  # GANA/PIERDE/PUSH
    ganancia_u = models.FloatField(null=True, blank=True)    # con 1 u plana
    settled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = 'Shadow OU descanso'
        verbose_name_plural = 'Shadows OU descanso'
        indexes = [models.Index(fields=['cfg', 'creado'])]

    def __str__(self):
        return (f'[OU] {self.home_team} vs {self.away_team} — '
                f'{self.decision} ({self.linea})')


class BasketOuCalib(models.Model):
    """Calibración vigente del motor OU (hoja Patron) por config/liga."""
    cfg = models.CharField(max_length=64, db_index=True)
    calculada_en = models.DateTimeField(default=timezone.now)
    n = models.IntegerField(default=0)
    pct_1 = models.FloatField(default=0.25)
    pct_2 = models.FloatField(default=0.25)
    pct_3 = models.FloatField(default=0.25)
    pct_4 = models.FloatField(default=0.25)
    league_mean = models.FloatField(default=0.0)
    sigma = models.FloatField(default=0.0)
    sigma_fuente = models.CharField(max_length=8, default='default')
    detalles = models.JSONField(default=dict, blank=True)
    cfg_version = models.CharField(max_length=16, blank=True, default='')
    congelada = models.BooleanField(default=False)

    class Meta:
        verbose_name = 'Calibración OU descanso'
        verbose_name_plural = 'Calibraciones OU descanso'
        ordering = ['-calculada_en']

    def __str__(self):
        return (f'{self.cfg} n={self.n} sigma={self.sigma:.2f} '
                f'({self.calculada_en:%Y-%m-%d %H:%M})')


class BasketOuSharp(models.Model):
    """Línea del descanso reconstruida del histórico real de casas (OddsPapi).

    Una fila por partido: cuartos con desglose local/visitante, línea y cuotas
    de BetPlay y Pinnacle justo antes del 3Q. Base del replay/backtest del
    motor OU y de la comparación vs línea sharp. Solo datos.
    """
    api_fixture_id = models.CharField(max_length=40, unique=True)
    fuente = models.CharField(max_length=16, default='oddspapi')
    torneo = models.CharField(max_length=64, blank=True, default='')
    clave_liga = models.CharField(max_length=64, blank=True, default='', db_index=True)
    cfg = models.CharField(max_length=16, blank=True, default='')
    home_team = models.CharField(max_length=120, blank=True, default='')
    away_team = models.CharField(max_length=120, blank=True, default='')
    start_time = models.DateTimeField(null=True, blank=True)
    t_descanso = models.DateTimeField(null=True, blank=True)   # fin del 2Q
    t_q3 = models.DateTimeField(null=True, blank=True)         # arranque del 3Q
    q1h = models.FloatField(null=True, blank=True)
    q1a = models.FloatField(null=True, blank=True)
    q2h = models.FloatField(null=True, blank=True)
    q2a = models.FloatField(null=True, blank=True)
    q3 = models.FloatField(null=True, blank=True)
    q4 = models.FloatField(null=True, blank=True)
    total_reg = models.FloatField(null=True, blank=True)
    total_ot = models.FloatField(null=True, blank=True)
    linea = models.FloatField(null=True, blank=True)            # BetPlay
    odds_over = models.FloatField(null=True, blank=True)
    odds_under = models.FloatField(null=True, blank=True)
    pin_linea = models.FloatField(null=True, blank=True)        # Pinnacle (sharp)
    pin_over = models.FloatField(null=True, blank=True)
    pin_under = models.FloatField(null=True, blank=True)
    betplay_evento_id = models.CharField(max_length=30, blank=True, default='',
                                         db_index=True)
    capturado_en = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Línea OU descanso (histórico)'
        verbose_name_plural = 'Líneas OU descanso (histórico)'
        indexes = [models.Index(fields=['clave_liga', 'start_time'])]

    def __str__(self):
        return (f'{self.clave_liga} · {self.home_team} vs {self.away_team} '
                f'({self.linea})')


class FxPaperTrade(models.Model):
    """Operación paper de FX/CFD (motor `fx_deriv`, MT5 Quant Lab).

    Una fila por entrada; se completa al cerrar (TP/SL/canal). `t_signal` es la
    epoch de la barra de señal y con `estrategia` forma la clave de deduplicación
    (una entrada por señal y estrategia). Todo es papel: USD virtuales.
    """
    ESTRATEGIA_CHOICES = [
        ('mrga_h1', 'MRGA EURUSD H1 (TP35/SL10)'),
        ('mrga_m5', 'MRGA EURUSD M5 (TP25/SL10)'),
        ('donchian_xau_h4', 'Donchian XAUUSD H4 (20/10, 2xATR)'),
    ]
    ESTADO_CHOICES = [('OPEN', 'Abierta'), ('CLOSED', 'Cerrada')]
    MOTIVO_CHOICES = [
        ('TP', 'Take profit'), ('TP_GAP', 'Take profit (gap)'),
        ('SL', 'Stop loss'), ('SL_GAP', 'Stop loss (gap)'),
        ('CHANNEL', 'Canal reverso'),
    ]

    estrategia = models.CharField(max_length=20, choices=ESTRATEGIA_CHOICES, db_index=True)
    simbolo = models.CharField(max_length=12)
    direccion = models.SmallIntegerField()          # 1 = long, -1 = short
    t_signal = models.BigIntegerField()             # epoch de la barra de señal (dedupe)
    t_entrada = models.DateTimeField()
    precio_entrada = models.FloatField()
    sl = models.FloatField()
    tp = models.FloatField(null=True, blank=True)
    lots = models.FloatField()
    estado = models.CharField(max_length=8, choices=ESTADO_CHOICES, default='OPEN', db_index=True)
    t_salida = models.DateTimeField(null=True, blank=True)
    precio_salida = models.FloatField(null=True, blank=True)
    motivo = models.CharField(max_length=12, blank=True, default='')
    pnl = models.FloatField(null=True, blank=True)          # USD
    balance_post = models.FloatField(null=True, blank=True)  # balance tras cerrar
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Operación paper FX'
        verbose_name_plural = 'Operaciones paper FX'
        unique_together = [('estrategia', 't_signal')]
        indexes = [models.Index(fields=['estrategia', 'estado'])]

    def __str__(self):
        d = 'LONG' if self.direccion == 1 else 'SHORT'
        return f'[FX] {self.estrategia} {d} {self.simbolo} @ {self.precio_entrada} ({self.estado})'

    @property
    def direccion_txt(self):
        return 'LONG' if self.direccion == 1 else 'SHORT'

    @property
    def net_usd(self):
        return self.pnl if self.estado == 'CLOSED' else None


class FxEngineState(models.Model):
    """Estado persistente por estrategia del motor `fx_deriv`.

    `last_bar_t` = epoch de la última barra cerrada procesada (cursor del
    replay determinista). `trades_today`/`dia_servidor` replican el límite
    diario del EA. La posición abierta se reconstruye de la fila OPEN de
    FxPaperTrade (fuente única de verdad).
    """
    estrategia = models.CharField(max_length=20, unique=True, choices=FxPaperTrade.ESTRATEGIA_CHOICES)
    balance = models.FloatField(default=10000.0)
    last_bar_t = models.BigIntegerField(default=0)
    trades_today = models.IntegerField(default=0)
    dia_servidor = models.CharField(max_length=10, blank=True, default='')
    ultimo_run = models.DateTimeField(null=True, blank=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Estado motor paper FX'
        verbose_name_plural = 'Estados motor paper FX'

    def __str__(self):
        return f'{self.estrategia} · balance {self.balance:.2f} · last_bar_t {self.last_bar_t}'


class LlmRealConfig(models.Model):
    """Config web de la OPINIÓN IA de las apuestas reales (página de umbrales).

    Controla el job que consulta la IA (única consulta por partido) cuando
    faltan `anticipacion_min` minutos para el inicio, además del modelo y el
    endpoint (base URL OpenAI-compatible). La API key NO vive aquí: se guarda
    en el `.env` del proyecto (permisos 600) y nunca se muestra en la web.

    Solo el admin principal la edita desde /auto-betting/configuracion/umbrales/.
    """
    enabled = models.BooleanField(
        default=True, verbose_name="Opinión IA en apuestas reales")
    anticipacion_min = models.PositiveSmallIntegerField(
        default=45, verbose_name="Anticipación de la consulta (min antes del inicio)")
    modelo = models.CharField(
        max_length=80, blank=True, default='',
        verbose_name="Modelo LLM (vacío = LLM_MODEL_REAL del entorno)")
    base_url = models.CharField(
        max_length=200, blank=True, default='',
        verbose_name="Endpoint/base URL (vacío = api.openai.com/v1)")
    actualizado = models.DateTimeField(auto_now=True)
    actualizado_por = models.CharField(max_length=200, blank=True, default='')

    class Meta:
        verbose_name = 'Configuración IA de apuestas reales'
        verbose_name_plural = 'Configuración IA de apuestas reales'

    def __str__(self):
        return (f'IA real: {"ON" if self.enabled else "OFF"} · '
                f'T-{self.anticipacion_min} · {self.modelo or "modelo de entorno"}')

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj


class LeagueRegistry(models.Model):
    """Registro de ligas del motor OU descanso (spec de ligas 2026-10-16).

    Cada liga se valida por separado (nunca se mezcla en la calibración).
    Estados: DISCOVERY (recolectando, sin sombras) -> SHADOW (sombras, sin
    apuestas) -> PAPER (apuestas paper) -> LIVE (dinero real; SOLO con
    aprobación humana explícita, nunca automático).

    `cfg_key` referencia una config congelada de `basket_ou.CFG` (EUROPA/NBA);
    `cfg_json` guarda la config completa para ligas con config propia
    (provisional o medida). El bot en vivo usa `config_efectiva()`.
    """
    ESTADOS = [
        ('DISCOVERY', 'Discovery (recolectando datos)'),
        ('SHADOW', 'Shadow (sombras, sin apuestas)'),
        ('PAPER', 'Paper (apuestas simuladas)'),
        ('LIVE', 'Live (requiere aprobación humana)'),
    ]
    ESTRUCTURAS = [
        ('FIBA_4x10', 'FIBA 4x10'),
        ('NBA_4x12', 'NBA 4x12'),
        ('HALVES_2x20', '2 mitades 2x20'),
    ]

    league_id = models.CharField(max_length=64, unique=True)   # clave_liga del feed
    nombre = models.CharField(max_length=120, blank=True, default='')
    estructura = models.CharField(max_length=16, choices=ESTRUCTURAS,
                                  default='FIBA_4x10')
    ot_minutos = models.PositiveSmallIntegerField(default=5)
    ids_externos = models.JSONField(default=dict, blank=True)
    estado = models.CharField(max_length=10, choices=ESTADOS,
                              default='DISCOVERY', db_index=True)
    cfg_key = models.CharField(max_length=24, blank=True, default='')
    cfg_json = models.JSONField(default=dict, blank=True)
    cfg_version = models.CharField(max_length=16, blank=True, default='')
    notas = models.TextField(blank=True, default='')
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Liga del motor OU descanso'
        verbose_name_plural = 'Ligas del motor OU descanso'
        ordering = ['league_id']

    def config_efectiva(self) -> dict:
        """Config vigente de la liga: cfg_json (provisional/medida) o CFG[cfg_key]."""
        from auto_betting import basket_ou as ou
        if self.cfg_json:
            return dict(self.cfg_json)
        return dict(ou.CFG.get(self.cfg_key) or {})

    def clave_calibracion(self) -> str:
        """Clave con la que se guarda/lee su calibración (BasketOuCalib.cfg)."""
        return self.cfg_key or self.league_id

    def __str__(self):
        return f'{self.league_id} [{self.estado}]'


class TeamAlias(models.Model):
    """Mapeo nombre_proveedor -> team_id interno (spec de ligas §1/§6)."""
    nombre_proveedor = models.CharField(max_length=160, unique=True)
    team_id = models.CharField(max_length=64)
    liga = models.CharField(max_length=64, blank=True, default='')
    fuente = models.CharField(max_length=40, blank=True, default='')
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Alias de equipo'
        verbose_name_plural = 'Alias de equipos'

    def __str__(self):
        return f'{self.nombre_proveedor} -> {self.team_id}'


# --------------------------------------------------------------- PAPERPARLEYS
# Motor de parlays en papel sobre las apuestas reales del motor (AutoBet):
# recorre los picks de cada día, recalibra la probabilidad del modelo con
# deciles rodantes (winrate observado de bets resueltas de días ANTERIORES)
# y genera TODAS las combinaciones de >=2 patas (mismo evento excluido,
# mercados junk fuera) cuyo EV conjunto >= ev_gate, sin tope de parlays
# por día. Cada combinación se traza con su corrida de generación (PPGenRun)
# y sus piernas normalizadas (PPParleyLeg). La liquidación usa el resultado
# real asentado en AutoBet con reglas de combinada: todas ganan -> pago del
# producto de cuotas; una pierde -> 0; patas VOID -> la combinada se reduce
# a las piernas restantes (pago proporcional); sin piernas útiles -> PUSH.


class PPConfig(models.Model):
    """Config del motor paperparleys (singleton pk=1)."""

    ev_gate = models.FloatField(default=1.05, verbose_name="EV mínimo del parlay")
    max_legs = models.IntegerField(default=6, verbose_name="Patas máximas por parlay")
    stake = models.IntegerField(default=1000, verbose_name="Stake COP por parlay")
    min_fit = models.IntegerField(default=50, verbose_name="Mínimo de bets para el fit de deciles")
    junk_mercados = models.TextField(
        default="descanso\nprimera parte\ncuotas del partido",
        verbose_name="Frases de mercado excluidas (una por línea)")
    notas = models.TextField(blank=True, default="")
    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Config Paperparleys"
        verbose_name_plural = "Config Paperparleys"

    def __str__(self):
        return f"PPConfig EV>={self.ev_gate} patas<={self.max_legs} stake={self.stake}"


class PPGenRun(models.Model):
    """Auditabilidad de cada corrida de generación del motor."""

    MODO_CHOICES = [
        ('BACKFILL', 'Backfill histórico'),
        ('MANUAL', 'Manual (manage.py / botón web)'),
        ('LIVE', 'Programada (cron)'),
    ]
    modo = models.CharField(max_length=10, choices=MODO_CHOICES, default='MANUAL', db_index=True)
    dia = models.DateField(null=True, blank=True, verbose_name='Día generado')
    started_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)
    ok = models.BooleanField(default=True)
    error = models.TextField(blank=True, default='')
    args = models.CharField(max_length=300, blank=True, default='')

    n_fit = models.IntegerField(default=0)
    n_pool = models.IntegerField(default=0)
    n_eventos = models.IntegerField(default=0)
    n_generados = models.IntegerField(default=0)
    n_skipped = models.IntegerField(default=0, verbose_name='Picks descartados (junk/sin prob)')
    elapsed_ms = models.IntegerField(default=0)

    fit_edges = models.JSONField(default=list)   # bordes de deciles de predicta_prob
    fit_rates = models.JSONField(default=list)   # winrate por decil (p_rec)
    fit_gwr = models.FloatField(null=True, blank=True, verbose_name='Winrate global del fit')

    class Meta:
        verbose_name = 'Corrida paperparleys'
        verbose_name_plural = 'Corridas paperparleys'
        ordering = ['-started_at']

    def __str__(self):
        return f'{self.modo} {self.dia} · {self.n_generados} parlays ({self.started_at:%m-%d %H:%M})'


class PPParley(models.Model):
    """Parlay en papel generado con los picks reales del motor.

    key = '{dia}|{autobet_ids ordenados}' -> idempotencia entre corridas.
    """
    ESTADO_CHOICES = [
        ('PENDIENTE', 'Pendiente'),
        ('GANADO', 'Ganado'),
        ('PERDIDO', 'Perdido'),
        ('PUSH', 'Push (anulado)'),
        ('VOID', 'Void total'),
    ]

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
                                related_name='paper_parleys')
    dia = models.DateField(db_index=True, verbose_name='Día (Bogotá) de las piernas')
    key = models.CharField(max_length=300, unique=True, db_index=True)
    gen_run = models.ForeignKey(PPGenRun, null=True, blank=True, on_delete=models.SET_NULL,
                                related_name='parlays')

    n_legs = models.IntegerField(db_index=True)
    cuota_producto = models.FloatField()
    prob_producto = models.FloatField()
    ev = models.FloatField()
    stake = models.IntegerField(default=1000)

    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='PENDIENTE', db_index=True)
    payout = models.FloatField(null=True, blank=True)
    settled_at = models.DateTimeField(null=True, blank=True)
    nota = models.CharField(max_length=300, blank=True, default="")
    legs = models.JSONField(default=list)

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Paperparley'
        verbose_name_plural = 'Paperparleys'
        indexes = [models.Index(fields=['usuario', 'dia']),
                   models.Index(fields=['usuario', 'estado'])]

    def __str__(self):
        return f'{self.dia} x{self.n_legs} @{self.cuota_producto:.2f} ev={self.ev:.2f} [{self.estado}]'


class PPParleyLeg(models.Model):
    """Pierna normalizada de un paperparley (copia indexada de legs JSON)."""

    parley = models.ForeignKey(PPParley, on_delete=models.CASCADE, related_name='leg_rows')
    autobet = models.ForeignKey(AutoBet, on_delete=models.PROTECT, related_name='paper_parley_legs')
    posicion = models.IntegerField(default=0)

    evento_id = models.BigIntegerField(null=True, blank=True)
    home_team = models.CharField(max_length=200, blank=True, default='')
    away_team = models.CharField(max_length=200, blank=True, default='')
    liga = models.CharField(max_length=200, blank=True, default='')
    mercado = models.CharField(max_length=120)
    seleccion = models.CharField(max_length=120)

    cuota = models.FloatField()
    prob = models.FloatField(verbose_name='Prob modelo (%)')
    p_rec = models.FloatField(verbose_name='Prob recalibrada (decil)')
    q = models.FloatField(verbose_name='q = p_rec * cuota')

    estado_gen = models.CharField(max_length=10, blank=True, default='')
    estado_final = models.CharField(max_length=10, blank=True, default='')

    class Meta:
        verbose_name = 'Pierna paperparley'
        verbose_name_plural = 'Piernas paperparley'
        indexes = [models.Index(fields=['autobet']), models.Index(fields=['parley', 'posicion'])]

    def __str__(self):
        return f'{self.parley_id} #{self.posicion} {self.seleccion} @{self.cuota:.2f}'
