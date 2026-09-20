"""
Modelos del Inspector de apuestas.

InspeccionApuesta: una fila por apuesta liquidada verificada (o intentada).
Guarda el veredicto de la verificación independiente contra la base de datos
local (API-Football) y el estado de los avisos de WhatsApp.
"""

from django.db import models


class InspeccionApuesta(models.Model):
    """Resultado de inspeccionar UNA apuesta liquidada de HistorialApuesta."""

    VEREDICTO_OK = 'OK'
    VEREDICTO_REVISAR = 'REVISAR'
    VEREDICTO_NO_VERIFICABLE = 'NO_VERIFICABLE'
    VEREDICTO_CHOICES = [
        (VEREDICTO_OK, 'Legítima (resultado coincide con los datos)'),
        (VEREDICTO_REVISAR, 'Posible liquidación incorrecta — revisión manual'),
        (VEREDICTO_NO_VERIFICABLE, 'No verificable (evidencia insuficiente)'),
    ]

    DIR_PERDIDA = 'perdida_dudosa'      # Kambi LOST, los datos dicen que debió ganar
    DIR_VICTORIA = 'victoria_dudosa'    # Kambi WON, los datos dicen que debió perder
    DIRECCION_CHOICES = [
        (DIR_PERDIDA, 'Posible pérdida mal liquidada'),
        (DIR_VICTORIA, 'Posible victoria mal liquidada (sobre-pago)'),
    ]

    apuesta = models.OneToOneField(
        'auto_betting.HistorialApuesta',
        on_delete=models.CASCADE,
        related_name='inspeccion',
        verbose_name='Apuesta',
    )
    veredicto = models.CharField(max_length=15, choices=VEREDICTO_CHOICES, verbose_name='Veredicto')
    direccion = models.CharField(max_length=20, choices=DIRECCION_CHOICES, blank=True, default='',
                                 verbose_name='Dirección de la discrepancia')
    estado_kambi = models.CharField(max_length=10, blank=True, default='', verbose_name='Estado BetPlay')
    estado_esperado = models.CharField(max_length=10, blank=True, default='', verbose_name='Estado según datos')
    confianza = models.CharField(max_length=10, blank=True, default='', verbose_name='Confianza del match')
    detalle = models.CharField(max_length=400, blank=True, default='', verbose_name='Detalle de la verificación')
    margen = models.FloatField(null=True, blank=True, verbose_name='Margen |valor-línea| (None=sin línea)')
    fixture_api_id = models.IntegerField(null=True, blank=True, verbose_name='Fixture API-Football')
    fuente = models.CharField(max_length=60, blank=True, default='API-Football', verbose_name='Fuente de datos')

    reintentos = models.PositiveIntegerField(default=0, verbose_name='Reintentos de verificación')
    intentos_aviso = models.PositiveIntegerField(default=0, verbose_name='Intentos de aviso (usuario)')
    intentos_aviso_admin = models.PositiveIntegerField(default=0, verbose_name='Intentos de aviso (admin)')
    aviso_usuario = models.BooleanField(default=False, verbose_name='Usuario avisado')
    aviso_admin = models.BooleanField(default=False, verbose_name='Admin avisado')

    creado = models.DateTimeField(auto_now_add=True)
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Inspección de apuesta'
        verbose_name_plural = 'Inspecciones de apuestas'
        ordering = ['-creado']
        indexes = [
            models.Index(fields=['veredicto', '-creado']),
            models.Index(fields=['-creado']),
        ]

    def __str__(self):
        return f"[{self.veredicto}] {self.apuesta} ({self.detalle[:60]})"
