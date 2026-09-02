"""
Verifica el login de BetPlay de cada cuenta activa y notifica por WhatsApp
a cada usuario cuando su ticket vence o queda inválido.

Dedupe: solo notifica en la TRANSICIÓN a FALLO (no spamea a diario). Si el
ticket vuelve a funcionar, el estado vuelve a OK y una nueva caída avisará
de nuevo. Usuarios sin teléfono registrado: se omite el envío (auditado).

Cron sugerido: 07:10 UTC (después de run_auto_bets 06:10 y del sync 06:00).
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
                mensaje = (
                    f"🔑 Hola {usuario.first_name or usuario.username}:\n"
                    f"El ticket de BetPlay de tu cuenta en Predicta venció o es inválido. "
                    f"El auto-betting NO apostará hasta que lo actualices.\n\n"
                    f"👉 https://www.predicta.com.co/auto-betting/configuracion/"
                )
                resultado = notificar_usuario(
                    usuario, EVENTO_TOKEN_VENCIDO, mensaje, estado_evento='FALLO',
                )
                self.stdout.write(
                    f"❌ {usuario.email}: ticket inválido — notificación: {resultado}"
                )
