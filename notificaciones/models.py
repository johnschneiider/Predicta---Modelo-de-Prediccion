"""
Modelos de notificaciones WhatsApp.

- NotificacionConfig: singleton con el interruptor maestro del servicio.
- NotificacionEstado: último estado conocido por (usuario, evento) — evita
  enviar el mismo aviso todos los días (solo transiciones).
- NotificacionLog: auditoría de cada intento de envío (enviado / error / omitido).
"""

from django.conf import settings
from django.db import models


class NotificacionConfig(models.Model):
    """Configuración global del servicio de notificaciones (una sola fila)."""

    activo = models.BooleanField(
        default=True, verbose_name="Notificaciones activas",
        help_text="Interruptor maestro: si se apaga, nadie recibe avisos de WhatsApp.",
    )

    class Meta:
        verbose_name = "Configuración de notificaciones"
        verbose_name_plural = "Configuración de notificaciones"

    def save(self, *args, **kwargs):
        # Singleton: siempre una sola fila.
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def get_solo(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def __str__(self):
        return f"Notificaciones {'activas' if self.activo else 'apagadas'}"


class NotificacionEstado(models.Model):
    """
    Último estado conocido de un evento por usuario (dedupe de avisos).
    Solo se notifica cuando el estado CAMBIA (ej. ticket OK → FALLO).
    """

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name='notificacion_estados',
    )
    evento = models.CharField(max_length=50)
    estado = models.CharField(max_length=30, blank=True, default='')
    actualizado = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = [('usuario', 'evento')]
        verbose_name = "Estado de notificación"
        verbose_name_plural = "Estados de notificación"

    def __str__(self):
        return f"{self.usuario.email} · {self.evento} = {self.estado or '—'}"


class NotificacionLog(models.Model):
    """Auditoría de envíos (o intentos) de notificación."""

    ESTADO_ENVIADO = 'ENVIADO'
    ESTADO_ERROR = 'ERROR'
    ESTADO_OMITIDO = 'OMITIDO'
    ESTADO_CHOICES = [
        (ESTADO_ENVIADO, 'Enviado'),
        (ESTADO_ERROR, 'Error'),
        (ESTADO_OMITIDO, 'Omitido'),
    ]

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name='notificacion_logs',
    )
    evento = models.CharField(max_length=50)
    destino = models.CharField(max_length=30, blank=True, default='')
    estado = models.CharField(max_length=10, choices=ESTADO_CHOICES, default=ESTADO_ENVIADO)
    detalle = models.TextField(blank=True, default='')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-fecha']
        verbose_name = "Log de notificación"
        verbose_name_plural = "Logs de notificaciones"

    def __str__(self):
        return f"[{self.fecha:%Y-%m-%d %H:%M}] {self.evento} → {self.destino} ({self.estado})"
