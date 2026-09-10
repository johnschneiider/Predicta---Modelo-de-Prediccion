"""
Verificación inteligente de tickets BetPlay — notifica por WhatsApp.

Corre cada hora (CronSchedule cada_n_minutos=60).

Lógica:
- Login OK + venía de FALLO → WhatsApp "recuperado".
- Login OK + seguía OK → silencio (estado OK).
- Login OK + cerca de TTL estimado → WhatsApp "vence pronto" (a T-6h y T-2h).
- Login FALLA (primera vez) → WhatsApp inmediato "venció" + log TTL empírico.
- Login FALLA (seguía) → recordatorio cada 4h (no spam).
"""

from django.core.management.base import BaseCommand
import time

from django.utils import timezone

from auto_betting.models import AutoBetConfig
from auto_betting.services import login
from notificaciones.models import NotificacionEstado, NotificacionLog
from notificaciones.services import notificar_usuario

# Eventos
EVENTO_VENCIDO = 'token_betplay_vencido'
EVENTO_OK = 'token_betplay_ok'
EVENTO_POR_VENCER = 'token_betplay_por_vencer'

# TTL estimado (horas). Basado en evidencia: admin renovó 09-08 02:23 UTC,
# OK a 09-10 03:00, fallo a 09-10 ~10:30 → TTL ~49-56h. Usamos 48h conservador.
# Se ajusta con datos empíricos del log (evento='ttl_medicion').
TTL_ESTIMADO = 56  # límite superior medido (admin: 49-56h)  # límite superior medido (admin: 49-56h)

# Umbrales de aviso pre-expiración (horas antes del TTL estimado)
AVISOS_PRE = [6, 2]

# Recordatorio mientras vencido (cada N horas)
RECORDATORIO_H = 4


class Command(BaseCommand):
    help = "Verificación inteligente de tickets BetPlay con notificaciones WhatsApp"

    def handle(self, *args, **options):
        now = timezone.now()
        configs = AutoBetConfig.objects.select_related('usuario').filter(activo=True)

        if not configs.exists():
            self.stdout.write("Sin configuraciones activas.")
            return

        for i, config in enumerate(configs):
            if i > 0:
                time.sleep(5)  # evita 429 de WhatsApp
            usuario = config.usuario
            token, _ = login(config.ticket, config.punter_id)

            est_vencido, _ = NotificacionEstado.objects.get_or_create(
                usuario=usuario, evento=EVENTO_VENCIDO, defaults={'estado': ''}
            )
            est_por_vencer, _ = NotificacionEstado.objects.get_or_create(
                usuario=usuario, evento=EVENTO_POR_VENCER, defaults={'estado': ''}
            )

            if token:
                # ── TICKET OK ──
                if est_vencido.estado == 'FALLO':
                    nombre = usuario.first_name or usuario.username or 'usuario'
                    msg = (
                        f"✅ *Predicta — Sesión recuperada*\n\n"
                        f"Hola {nombre}, tu sesión BetPlay está activa nuevamente.\n"
                        f"Las apuestas automáticas siguen operando con normalidad.\n\n"
                        f"— Predicta · Monitoreo automático"
                    )
                    notificar_usuario(usuario, EVENTO_OK, msg, estado_evento='OK', forzar=True)
                    self.stdout.write(f"✅ {usuario.email}: recuperado — WhatsApp enviado")
                else:
                    notificar_usuario(usuario, EVENTO_OK, '', estado_evento='OK')
                    self.stdout.write(f"✅ {usuario.email}: ticket OK")

                est_vencido.estado = 'OK'
                est_vencido.save()

                # Pre-expiración
                if config.ticket_actualizado:
                    h_desde = (now - config.ticket_actualizado).total_seconds() / 3600
                    h_restantes = TTL_ESTIMADO - h_desde

                    for umbral in AVISOS_PRE:
                        if h_restantes <= umbral and est_por_vencer.estado != str(umbral):
                            nombre = usuario.first_name or usuario.username or 'usuario'
                            msg = (
                                f"⚠️ *Predicta — Tu sesión vence pronto*\n\n"
                                f"Hola {nombre}, tu sesión BetPlay lleva {h_desde:.0f}h activa "
                                f"y se estima que vence en ~{h_restantes:.0f}h.\n\n"
                                f"Renueva tu ticket para evitar interrupciones:\n"
                                f"👉 https://www.predicta.com.co/auto-betting/configuracion/\n\n"
                                f"— Predicta · Monitoreo automático"
                            )
                            notificar_usuario(usuario, EVENTO_POR_VENCER, msg,
                                            estado_evento=str(umbral), forzar=True)
                            self.stdout.write(f"⚠️ {usuario.email}: aviso pre-expiración ({umbral}h)")
                            break

                    # Reset por_vencer si ticket fue renovado hace poco
                    if h_desde < min(AVISOS_PRE) and est_por_vencer.estado:
                        est_por_vencer.estado = ''
                        est_por_vencer.save()

            else:
                # ── TICKET FALLA ──
                nombre = usuario.first_name or usuario.username or 'usuario'
                h_desde_renov = None
                if config.ticket_actualizado:
                    h_desde_renov = (now - config.ticket_actualizado).total_seconds() / 3600

                if est_vencido.estado != 'FALLO':
                    # Primera detección → alerta inmediata
                    info = f" (renovado hace {h_desde_renov:.0f}h)" if h_desde_renov else ""
                    msg = (
                        f"🔴 *Predicta — Tu sesión BetPlay venció*\n\n"
                        f"Hola {nombre}, tu sesión BetPlay ya no es válida{info}.\n"
                        f"Las apuestas automáticas están en pausa para tu cuenta.\n\n"
                        f"Renueva tu ticket ahora:\n"
                        f"👉 https://www.predicta.com.co/auto-betting/configuracion/\n\n"
                        f"— Predicta · Monitoreo automático"
                    )
                    notificar_usuario(usuario, EVENTO_VENCIDO, msg, estado_evento='FALLO', forzar=True)

                    # Registrar TTL empírico
                    if h_desde_renov:
                        NotificacionLog.objects.create(
                            usuario=usuario, evento='ttl_medicion',
                            destino='', estado=NotificacionLog.ESTADO_ENVIADO,
                            detalle=f'TTL={h_desde_renov:.1f}h'
                        )

                    self.stdout.write(f"🔴 {usuario.email}: vencido{info} — alerta enviada")
                else:
                    # Ya estaba vencido → recordatorio cada RECORDATORIO_H
                    ultimo = NotificacionLog.objects.filter(
                        usuario=usuario, evento=EVENTO_VENCIDO,
                        estado=NotificacionLog.ESTADO_ENVIADO
                    ).first()
                    if ultimo:
                        h_ultimo = (now - ultimo.fecha).total_seconds() / 3600
                        if h_ultimo >= RECORDATORIO_H:
                            info = f", lleva {h_desde_renov:.0f}h desde la renovación" if h_desde_renov else ""
                            msg = (
                                f"🔴 *Predicta — Recordatorio de sesión*\n\n"
                                f"Hola {nombre}, tu sesión BetPlay sigue vencida{info}.\n\n"
                                f"Renueva tu ticket:\n"
                                f"👉 https://www.predicta.com.co/auto-betting/configuracion/\n\n"
                                f"— Predicta · Monitoreo automático"
                            )
                            notificar_usuario(usuario, EVENTO_VENCIDO, msg, estado_evento='FALLO', forzar=True)
                            self.stdout.write(f"🔴 {usuario.email}: recordatorio (sigue vencido)")
                        else:
                            falta = RECORDATORIO_H - h_ultimo
                            self.stdout.write(f"🔴 {usuario.email}: sigue vencido (próx aviso en {falta:.1f}h)")
                    else:
                        info = f" (renovado hace {h_desde_renov:.0f}h)" if h_desde_renov else ""
                        msg = (
                            f"🔴 *Predicta — Tu sesión BetPlay venció*\n\n"
                            f"Hola {nombre}, tu sesión BetPlay ya no es válida{info}.\n"
                            f"Las apuestas automáticas están en pausa.\n\n"
                            f"Renueva tu ticket:\n"
                            f"👉 https://www.predicta.com.co/auto-betting/configuracion/\n\n"
                            f"— Predicta · Monitoreo automático"
                        )
                        notificar_usuario(usuario, EVENTO_VENCIDO, msg, estado_evento='FALLO', forzar=True)
                        self.stdout.write(f"🔴 {usuario.email}: alerta enviada (sin log previo)")
