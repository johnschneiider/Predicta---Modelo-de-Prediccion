import time
"""
Servicios de notificaciones WhatsApp.

El envío se hace contra el microservicio local whatsapp-web.js
(127.0.0.1:8084) con API key. Sin teléfono registrado en el usuario, o con
el servicio apagado, el aviso se OMITE (y queda auditado en NotificacionLog).
"""

import logging
import os
from datetime import datetime

import requests

from .models import NotificacionConfig, NotificacionEstado, NotificacionLog

logger = logging.getLogger('notificaciones')

WHATSAPP_SERVICE_URL = "http://127.0.0.1:8084"
INSTANCE_NAME = "PREDICTA"
API_KEY = os.environ.get('WHATSAPP_API_KEY', '')
TIMEOUT_S = 15

# Eventos conocidos
EVENTO_TOKEN_VENCIDO = 'token_betplay_vencido'
EVENTO_TOKEN_OK = 'token_betplay_ok'
EVENTO_APUESTAS = 'apuestas_colocadas'
EVENTO_PARLEYS = 'parleys_colocados'

_EMOJI_DEPORTE = {'Fútbol': '⚽', 'NBA': '🏀', 'MLB': '⚾'}

MENSAJE_BIENVENIDA = (
    '👋 ¡Hola! Soy *Predicta*, el sistema de apuestas inteligentes '
    'de predicta.com.co 🤖\n\n'
    'A partir de ahora recibirás por este canal mensajes de información: '
    'alertas de tu cuenta, estado de tus apuestas y novedades importantes.\n\n'
    '📌 Ten en cuenta que este es un canal solo de avisos: no leo ni respondo '
    'mensajes por aquí.\n\n'
    '¡Mucha suerte con tus apuestas! 🍀'
)


def normalizar_telefono(telefono):
    """Limpia y normaliza a formato internacional (57XXXXXXXXXX)."""
    digits = ''.join(ch for ch in (telefono or '') if ch.isdigit())
    if len(digits) == 10 and digits.startswith('3'):
        digits = '57' + digits
    return digits


def whatsapp_enviar(telefono, mensaje):
    """
    Envía un mensaje de texto por WhatsApp vía el microservicio local.
    Devuelve (ok: bool, detalle: str).
    """
    numero = normalizar_telefono(telefono)
    if not numero:
        return False, 'número inválido'

    for intento in range(3):
        try:
            resp = requests.post(
                f"{WHATSAPP_SERVICE_URL}/message/sendText/{INSTANCE_NAME}",
                headers={'Content-Type': 'application/json', 'X-Api-Key': API_KEY},
                json={'number': numero, 'textMessage': {'text': mensaje}},
                timeout=TIMEOUT_S,
            )
            if resp.status_code == 200:
                return True, 'enviado'
            if resp.status_code == 429 and intento < 2:
                time.sleep(10 * (intento + 1))  # backoff 10s, 20s
                continue
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except requests.RequestException as e:
            if intento < 2:
                time.sleep(5)
                continue
            return False, f"error de conexión: {e}"


def enviar_bienvenida(usuario):
    """
    Envía el mensaje de bienvenida al WhatsApp del usuario (auditado en
    NotificacionLog, evento 'bienvenida').

    Devuelve (estado, detalle) con estado ∈ {ENVIADO, ERROR, OMITIDO}.
    """
    tel = normalizar_telefono(usuario.telefono)
    if not tel:
        NotificacionLog.objects.create(
            usuario=usuario, evento='bienvenida', destino='',
            estado=NotificacionLog.ESTADO_OMITIDO,
            detalle='sin teléfono registrado',
        )
        return NotificacionLog.ESTADO_OMITIDO, 'sin teléfono registrado'
    ok, detalle = whatsapp_enviar(tel, MENSAJE_BIENVENIDA)
    estado = NotificacionLog.ESTADO_ENVIADO if ok else NotificacionLog.ESTADO_ERROR
    NotificacionLog.objects.create(
        usuario=usuario, evento='bienvenida', destino=tel,
        estado=estado, detalle=detalle,
    )
    return estado, detalle


def notificar_usuario(usuario, evento, mensaje, estado_evento, forzar=False):
    """
    Notifica a un usuario SOLO si cambia el estado del evento (dedupe) y el
    usuario tiene teléfono. Auditado en NotificacionLog.

    forzar=True: envía aunque el estado no haya cambiado (recordatorio
    insistente, p. ej. token vencido en cada revisión programada).

    Devuelve 'enviado' | 'error' | 'omitido' | 'sin_cambios'.
    """
    cfg = NotificacionConfig.get_solo()

    prev, _ = NotificacionEstado.objects.get_or_create(
        usuario=usuario, evento=evento, defaults={'estado': ''},
    )

    if prev.estado == estado_evento and not forzar:
        return 'sin_cambios'

    telefono = normalizar_telefono(usuario.telefono)

    if not cfg.activo:
        NotificacionLog.objects.create(
            usuario=usuario, evento=evento, destino=telefono or '',
            estado=NotificacionLog.ESTADO_OMITIDO,
            detalle='servicio de notificaciones desactivado',
        )
        return 'omitido'

    if not telefono:
        # Sin teléfono: no marcar el estado, para que al registrar el número
        # (si el evento sigue activo) se notifique en la próxima revisión.
        NotificacionLog.objects.create(
            usuario=usuario, evento=evento, destino='',
            estado=NotificacionLog.ESTADO_OMITIDO,
            detalle='usuario sin número de WhatsApp registrado',
        )
        return 'omitido'

    if not mensaje:
        # Transición de recuperación (ej. ticket OK de nuevo): solo se marca
        # el estado, no se envía mensaje.
        prev.estado = estado_evento
        prev.save()
        return 'estado_actualizado'

    ok, detalle = whatsapp_enviar(telefono, mensaje)
    NotificacionLog.objects.create(
        usuario=usuario, evento=evento, destino=telefono,
        estado=NotificacionLog.ESTADO_ENVIADO if ok else NotificacionLog.ESTADO_ERROR,
        detalle=detalle,
    )
    if ok:
        prev.estado = estado_evento
        prev.save()
    return 'enviado' if ok else 'error'


def construir_mensaje_apuestas(apuestas, deporte):
    """Mensaje WhatsApp con las apuestas colocadas en una corrida.

    `apuestas`: lista de dicts con partido, mercado, seleccion, cuota, stake_cop.
    Formato legible en móvil: un bloque por apuesta (partido en negrita y la
    selección en su propia línea) con línea en blanco entre bloques.
    """
    emoji = _EMOJI_DEPORTE.get(deporte, '🎯')
    n = len(apuestas)
    plural = 's' if n != 1 else ''
    cab = f"{emoji} *Predicta — {n} apuesta{plural} colocada{plural}* ({deporte})"
    stake = apuestas[0].get('stake_cop') if apuestas else None
    if stake:
        cab += f"\nStake: {stake:,.0f} COP c/u"
    bloques = []
    for i, a in enumerate(apuestas[:10], 1):
        cuota = float(a.get('cuota') or 0)
        mercado = (a.get('mercado') or '').strip()
        seleccion = a.get('seleccion', '')
        pick = f"→ {mercado}: {seleccion} @{cuota:.2f}" if mercado else f"→ {seleccion} @{cuota:.2f}"
        bloques.append(f"{i}) *{a.get('partido', '')}*\n{pick}")
    if n > 10:
        bloques.append(f"… y {n - 10} más")
    return cab + "\n\n" + "\n\n".join(bloques)


def notificar_apuestas(usuario, apuestas, deporte):
    """Resumen WhatsApp de las apuestas colocadas en esta corrida.

    Solo se llama cuando hubo ≥1 apuesta (una notificación por corrida).
    Devuelve el resultado de notificar_usuario: 'enviado' | 'error' | 'omitido'.
    """
    if not apuestas:
        return 'sin_apuestas'
    mensaje = construir_mensaje_apuestas(apuestas, deporte)
    return notificar_usuario(
        usuario, EVENTO_APUESTAS, mensaje,
        estado_evento=datetime.now().isoformat(timespec='seconds'),
        forzar=True,
    )


def construir_mensaje_parleys(parleys):
    """Mensaje WhatsApp con los parleys colocados en una corrida.

    `parleys`: lista de dicts con stake, odds, payout y legs
    (cada pata: h, a, m, s, c). Formato móvil: cabecera con totales y un
    bloque por parley (máximo 10, luego "… y N más").
    """
    n = len(parleys)
    plural = 's' if n != 1 else ''
    stake = float(parleys[0].get('stake') or 0) if parleys else 0.0
    total_stake = sum(float(p.get('stake') or 0) for p in parleys)
    total_payout = sum(float(p.get('payout') or 0) for p in parleys)

    cab = f"🎲 *Predicta — {n} parley{plural} colocado{plural}*"
    if stake:
        cab += f"\nStake: {stake:,.0f} COP c/u"
    if total_stake and abs(total_stake - stake) > 0.001:
        cab += f" · Total: {total_stake:,.0f} COP"
    if total_payout:
        cab += f"\nPago potencial total: {total_payout:,.0f} COP"

    bloques = []
    for i, p in enumerate(parleys[:10], 1):
        lineas = []
        for leg in (p.get('legs') or []):
            home = (leg.get('h') or '').strip()
            away = (leg.get('a') or '').strip()
            partido = f"{home} vs {away}".strip()
            mercado = (leg.get('m') or '').strip()
            seleccion = leg.get('s') or ''
            cuota = float(leg.get('c') or 0)
            pick = (f"→ {mercado}: {seleccion} @{cuota:.2f}"
                    if mercado else f"→ {seleccion} @{cuota:.2f}")
            lineas.append(f"*{partido}*\n{pick}" if partido else pick)
        cuota_total = float(p.get('odds') or 0)
        payout = float(p.get('payout') or 0)
        pie = f"Cuota {cuota_total:.2f}" if cuota_total else ''
        if payout:
            pie += (f" · Pago {payout:,.0f} COP" if pie
                    else f"Pago {payout:,.0f} COP")
        bloques.append(
            f"{i}) " + "\n".join(lineas) + (f"\n{pie}" if pie else ''))
    if n > 10:
        bloques.append(f"… y {n - 10} más")
    return cab + "\n\n" + "\n\n".join(bloques)


def notificar_parleys(usuario, parleys, referencia=''):
    """Resumen WhatsApp de los parleys colocados en esta corrida.

    Solo se llama cuando hubo ≥1 parley. Una notificación por corrida.
    Devuelve 'enviado' | 'error' | 'omitido' | 'sin_parleys'.
    """
    if not parleys:
        return 'sin_parleys'
    mensaje = construir_mensaje_parleys(parleys)
    return notificar_usuario(
        usuario, EVENTO_PARLEYS, mensaje,
        estado_evento=(referencia
                       or datetime.now().isoformat(timespec='seconds')),
        forzar=True,
    )
