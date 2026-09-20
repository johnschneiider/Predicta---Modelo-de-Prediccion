# -*- coding: utf-8 -*-
"""Avisos de WhatsApp del Inspector (usuarios + admin)."""

import logging
import time

from notificaciones.models import NotificacionConfig, NotificacionLog
from notificaciones.services import normalizar_telefono, whatsapp_enviar

logger = logging.getLogger('inspector')

EVENTO_USUARIO = 'inspector_revision'
EVENTO_ADMIN = 'inspector_alerta_admin'

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


def _stake_cop(bet):
    try:
        return f'{bet.stake / 1000:,.0f}'.replace(',', '.')
    except Exception:  # noqa: BLE001
        return '—'


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
        f'inconsistencia en la liquidación de una de tus apuestas y ya '
        f'solicitamos la revisión manual.\n\n'
        f'⚽ {bet.home_team} vs {bet.away_team}\n'
        f'🎯 {bet.mercado}: {bet.seleccion}\n'
        f'📅 {_fecha(bet)}\n'
        f'📌 BetPlay la dio por *perdida*, pero según los datos {cond}.\n\n'
        f'Estamos verificando con BetPlay. Si la revisión confirma el error, '
        f'te contactaremos con los siguientes pasos. No necesitas hacer nada '
        f'por ahora.\n\n'
        f'— Predicta · Control automático de apuestas'
    )
    return _enviar(usuario, EVENTO_USUARIO, msg)


def enviar_aviso_admin_grupo(inspections, admin_user):
    """WhatsApp al admin agrupando por caso (fixture + dirección).

    inspections: lista NO vacía de InspeccionApuesta del mismo caso.
    """
    first = inspections[0]
    bet0 = first.apuesta
    n_afectados = len(inspections)  # filas listadas (una por cupón/usuario afectado)
    if first.direccion == 'perdida_dudosa':
        titulo = 'Posible apuesta PERDIDA mal liquidada'
    else:
        titulo = 'Posible apuesta GANADA no sustentada (sobre-pago)'

    lineas = []
    for insp in inspections:
        b = insp.apuesta
        _odds = b.bet_odds if b.bet_odds else b.played_odds
        _odds_txt = f"cuota {_odds:g}" if _odds else "cuota s/d"
        _stake_txt = f'{b.stake / 1000:,.0f}'.replace(',', '.')
        _tipo = 'sistema' if b.is_system else 'manual'
        lineas.append(
            f"• {b.usuario.email} — cupón {b.coupon_ref} "
            f"({_tipo}, {_odds_txt}, stake {_stake_txt} COP)"
        )
    mkt_low = (bet0.mercado or '').lower()
    caveat = ''
    if any(k in mkt_low for k in ('opta', 'tiros', 'disparos', 'esquina', 'corner')):
        caveat = ('\n⚠️ Mercado de conteo (Opta): pueden existir diferencias de '
                  '±1-2 vs API-Football; verificar la fuente antes de reclamar.')

    msg = (
        f'🚨 *Inspector Predicta — Revisión manual*\n\n'
        f'{titulo} ({n_afectados} {"cupones" if n_afectados > 1 else "cupón"})\n'
        f'• Partido: {bet0.home_team} vs {bet0.away_team}\n'
        f'• Mercado: {bet0.mercado} — {bet0.seleccion}\n'
        f'• Estado BetPlay: {first.estado_kambi} → esperado: {first.estado_esperado}\n'
        f'• Evidencia: {first.detalle}\n'
        f'• Afectados:\n' + '\n'.join(lineas) + '\n'
        f'{caveat}\n'
        f'🧾 Solicitar revisión manual en BetPlay.'
    )
    return _enviar(admin_user, EVENTO_ADMIN, msg)


def enviar_aviso_admin(inspection, admin_user):
    """WhatsApp al admin solicitando revisión manual."""
    bet = inspection.apuesta
    usuario = bet.usuario
    if inspection.direccion == 'perdida_dudosa':
        titulo = 'Posible apuesta PERDIDA mal liquidada'
    else:
        titulo = 'Posible apuesta GANADA no sustentada (sobre-pago)'
    caveat = ''
    mkt_low = (bet.mercado or '').lower()
    if any(k in mkt_low for k in ('opta', 'tiros', 'disparos', 'esquina', 'corner')):
        caveat = ('\n⚠️ Nota: los mercados de remates/córners se liquidan con Opta; '
                  'puede haber diferencias de conteo vs API-Football (±1-2). '
                  'Verificar la fuente antes de reclamar.')
    msg = (
        f'🚨 *Inspector Predicta — Revisión manual*\n\n'
        f'{titulo}\n'
        f'• Usuario: {usuario.email}\n'
        f'• Apuesta: {bet.home_team} vs {bet.away_team}\n'
        f'• Mercado: {bet.mercado}\n'
        f'• Selección: {bet.seleccion}\n'
        f'• Estado BetPlay: {inspection.estado_kambi} → esperado: {inspection.estado_esperado}\n'
        f'• Evidencia: {inspection.detalle}\n'
        f'• Cupón: {bet.coupon_ref} ({"sistema" if bet.is_system else "manual"})\n'
        f'• Stake: {_stake_cop(bet)} COP\n'
        f'{caveat}\n'
        f'🧾 Solicitar revisión manual en BetPlay.'
    )
    return _enviar(admin_user, EVENTO_ADMIN, msg)
