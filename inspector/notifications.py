# -*- coding: utf-8 -*-
"""Avisos de WhatsApp del Inspector (SOLO al usuario afectado).

Decisión John (2026-09-20): el admin no recibe WhatsApp del inspector;
revisa las inspecciones en el panel web /inspector/.
"""

import time

from notificaciones.models import NotificacionConfig, NotificacionLog
from notificaciones.services import normalizar_telefono, whatsapp_enviar

EVENTO_USUARIO = 'inspector_revision'

SLEEP_ENTRE_ENVIOS = 5  # segundos (evita 429 del microservicio WhatsApp)


def _enviar(usuario, evento, mensaje):
    """Envía un WhatsApp y lo audita. Devuelve True si quedó enviado/omitido-sin-tel."""
    cfg = NotificacionConfig.get_solo()
    tel = normalizar_telefono(getattr(usuario, 'telefono', ''))
    if not cfg.activo:
        NotificacionLog.objects.create(
            usuario=usuario, evento=evento, destino=tel or '',
            estado=NotificacionLog.ESTADO_OMITIDO,
            detalle='servicio de notificaciones desactivado',
        )
        return False
    if not tel:
        NotificacionLog.objects.create(
            usuario=usuario, evento=evento, destino='',
            estado=NotificacionLog.ESTADO_OMITIDO,
            detalle='usuario sin número de WhatsApp registrado',
        )
        return True  # no hay nada que reintentar
    ok, det = whatsapp_enviar(tel, mensaje)
    NotificacionLog.objects.create(
        usuario=usuario, evento=evento, destino=tel,
        estado=NotificacionLog.ESTADO_ENVIADO if ok else NotificacionLog.ESTADO_ERROR,
        detalle=(det or '')[:400],
    )
    if ok:
        time.sleep(SLEEP_ENTRE_ENVIOS)
    return ok


def _fecha(bet):
    if not bet.event_start_date:
        return '—'
    return bet.event_start_date.strftime('%d/%m/%Y')


def enviar_aviso_usuario(inspection):
    """WhatsApp al usuario afectado (solo pérdida dudosa: debió ganar)."""
    bet = inspection.apuesta
    usuario = bet.usuario
    nombre = usuario.first_name or usuario.username or 'jugador'
    if inspection.estado_esperado == 'VOID':
        cond = 'correspondía ANULARLA (la línea quedó empatada)'
    else:
        cond = 'las condiciones para ganar SÍ se cumplieron'
    msg = (
        f'🔍 *Predicta — Revisión de apuesta*\n\n'
        f'Hola {nombre}, nuestro control automático detectó una posible '
        f'inconsistencia en la liquidación de una de tus apuestas.\n\n'
        f'⚽ {bet.home_team} vs {bet.away_team}\n'
        f'🎯 {bet.mercado}: {bet.seleccion}\n'
        f'📅 {_fecha(bet)}\n'
        f'📌 BetPlay la dio por *perdida*, pero según los datos {cond}.\n\n'
        f'Hemos registrado el caso para revisión manual. Si se confirma el '
        f'error, te contactaremos con los siguientes pasos. No necesitas hacer '
        f'nada por ahora.\n\n'
        f'— Predicta · Control automático de apuestas'
    )
    return _enviar(usuario, EVENTO_USUARIO, msg)
