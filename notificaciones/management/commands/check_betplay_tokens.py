"""
Verifica el login de BetPlay de cada cuenta activa y notifica por WhatsApp
a cada usuario cuando su ticket vence o queda inválido.

Dedupe: solo notifica en la TRANSICIÓN a FALLO (no spamea en cada corrida). Si el
ticket vuelve a funcionar, el estado vuelve a OK y una nueva caída avisará de
nuevo. Usuarios sin teléfono registrado: se omite el envío (auditado).

Cron (2026-09-02, pedido de John): 3 veces al día en hora colombiana —
22:00, 06:00 y 13:00 COT → 03:00, 11:00 y 18:00 UTC.
"""

from django.core.management.base import BaseCommand

from auto_betting.models import AutoBetConfig
from auto_betting.services import login
from notificaciones.services import (
    EVENTO_TOKEN_OK, EVENTO_TOKEN_VENCIDO, notificar_usuario,
)


class Command(BaseCommand):
    help = "Verifica tickets de BetPlay y notifica vencimientos por WhatsApp"

    def handle(self, *args, **options):
        configs = AutoBetConfig.objects.select_related('usuario').filter(activo=True)
        if not configs.exists():
            self.stdout.write("Sin configuraciones activas.")
            return

        for config in configs:
            usuario = config.usuario
            token, _ = login(config.ticket, config.punter_id)
            if token:
                estado = 'OK'
                notificar_usuario(
                    usuario, EVENTO_TOKEN_OK,
                    '',  # sin mensaje: solo marca el estado
                    estado_evento='OK',
                )
                self.stdout.write(f"✅ {usuario.email}: ticket OK")
            else:
                nombre = usuario.first_name or usuario.username or 'usuario'
                mensaje = (
                    "🔐 *Predicta — Alerta de sesión BetPlay*\n\n"
                    f"Hola {nombre}, le informamos que la sesión de su cuenta "
                    "BetPlay en Predicta expiró o dejó de ser válida.\n\n"
                    "Por seguridad, las apuestas automáticas quedaron en pausa "
                    "para su cuenta hasta que la sesión se renueve.\n\n"
                    "Para reactivarlas, actualice su ticket desde el panel de "
                    "configuración:\n"
                    "👉 https://www.predicta.com.co/auto-betting/configuracion/\n\n"
                    "Si ya lo actualizó, puede ignorar este mensaje: el sistema "
                    "verificará su sesión nuevamente en la próxima revisión programada.\n\n"
                    "— Predicta · Monitoreo automático de sesiones"
                )
                resultado = notificar_usuario(
                    usuario, EVENTO_TOKEN_VENCIDO, mensaje, estado_evento='FALLO',
                )
                self.stdout.write(
                    f"❌ {usuario.email}: ticket inválido — notificación: {resultado}"
                )
