"""
Modelos del gestor de capital (app `capital`).

Balance paralelo de la cuenta BetPlay de cada usuario:
    balance_paralelo = balance_inicial + P&L asentado desde `ancla` + ajustes.

El P&L asentado se calcula SIEMPRE desde HistorialApuesta (auto_betting),
que es la fuente de verdad de resultados (sincronizada a diario desde
BetPlay `coupon/history.json`). Predicta NO puede leer el balance real de
BetPlay (backend JWT bloqueado por Cloudflare), por eso el balance paralelo
se ancla al saldo declarado por el usuario una única vez.
"""

from django.conf import settings
from django.db import models


class CapitalConfig(models.Model):
    """
    Configuración de gestión de capital — una por usuario.

    - modo FIJO: el stake es el que el usuario tiene en AutoBetConfig.stake
      (comportamiento histórico, sin cambios).
    - modo COMPUESTO: el stake = porcentaje del balance paralelo, con piso
      y techo (stake_min_cop / stake_max_cop).
    """

    MODO_FIJO = 'FIJO'
    MODO_COMPUESTO = 'COMPUESTO'
    MODO_CHOICES = [
        (MODO_FIJO, 'Stake fijo (lo defino yo)'),
        (MODO_COMPUESTO, 'Interés compuesto (% del balance)'),
    ]

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='capital_config',
        verbose_name="Usuario",
    )
    modo = models.CharField(
        max_length=10, choices=MODO_CHOICES, default=MODO_FIJO,
        verbose_name="Modo de gestión del stake",
    )
    # % del balance paralelo a usar como stake por apuesta (modo COMPUESTO).
    porcentaje = models.FloatField(default=2.0, verbose_name="% del balance por apuesta")
    # Balance real de BetPlay declarado por el usuario al activar el modo
    # compuesto. Se usa como ancla del balance paralelo y NO se reescribe
    # (las correcciones posteriores van a CapitalAjuste).
    balance_inicial = models.BigIntegerField(
        null=True, blank=True, verbose_name="Balance declarado (COP)",
    )
    # Momento exacto (UTC) en que se activó el modo compuesto. Solo cuentan
    # en el balance paralelo las apuestas colocadas DESDE este instante.
    ancla = models.DateTimeField(null=True, blank=True, verbose_name="Ancla de activación")

    # Límites de stake en modo COMPUESTO (COP). El piso protege de apostar
    # migajas; el techo protege de stakes desproporcionados en rachas largas.
    stake_min_cop = models.IntegerField(default=500, verbose_name="Stake mínimo (COP)")
    stake_max_cop = models.IntegerField(default=5000, verbose_name="Stake máximo (COP)")

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Configuración de capital"
        verbose_name_plural = "Configuraciones de capital"

    def __str__(self):
        return f"Capital de {self.usuario.email} [{self.modo}]"


class CapitalAjuste(models.Model):
    """
    Ajuste manual (firmado) sobre el balance paralelo de un usuario.

    Útil para reconciliar el balance paralelo con el real de BetPlay cuando
    hay drift: apuestas manuales hechas fuera del sistema, retiros/depósitos,
    o apuestas OPEN anteriores al ancla que asentaron después. Cada ajuste
    queda auditado (quién, cuándo, cuánto, motivo).
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='capital_ajustes',
        verbose_name="Usuario",
    )
    fecha = models.DateTimeField(auto_now_add=True)
    monto_cop = models.BigIntegerField(verbose_name="Monto del ajuste (COP, firmado)")
    motivo = models.CharField(max_length=255, default='Ajuste manual', verbose_name="Motivo")

    class Meta:
        verbose_name = "Ajuste de capital"
        verbose_name_plural = "Ajustes de capital"
        ordering = ['-fecha']

    def __str__(self):
        return f"{self.usuario.email}: {self.monto_cop:+,} COP ({self.motivo})"
