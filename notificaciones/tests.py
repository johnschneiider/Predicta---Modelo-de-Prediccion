"""
Tests de notificaciones: envío, dedupe por transición de estado, omisión sin
teléfono, normalización de número y acceso exclusivo del admin a la landing.
"""

from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from auto_betting.models import AutoBetConfig
from cuentas.models import Usuario

from .models import NotificacionConfig, NotificacionEstado, NotificacionLog
from .services import (
    EVENTO_TOKEN_VENCIDO, normalizar_telefono, notificar_usuario,
    whatsapp_enviar,
)


class NotificacionesServiceTests(TestCase):

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email='notif@test.com', username='notif', password='***',
            telefono='3001234567',
        )

    # ── normalización ─────────────────────────────────────────────────────

    def test_normalizar_telefono(self):
        self.assertEqual(normalizar_telefono('3001234567'), '573001234567')
        self.assertEqual(normalizar_telefono('+57 300 123 4567'), '573001234567')
        self.assertEqual(normalizar_telefono(''), '')
        self.assertEqual(normalizar_telefono(None), '')

    # ── envío vía microservicio (mock HTTP) ───────────────────────────────

    @patch('notificaciones.services.requests.post')
    def test_whatsapp_enviar_ok(self, mock_post):
        mock_post.return_value.status_code = 200
        ok, detalle = whatsapp_enviar('3001234567', 'hola')
        self.assertTrue(ok)
        # El request va al microservicio local con el número normalizado.
        args, kwargs = mock_post.call_args
        self.assertIn('8084', args[0])
        self.assertEqual(kwargs['json']['number'], '573001234567')

    @patch('notificaciones.services.requests.post')
    def test_whatsapp_enviar_error_http(self, mock_post):
        mock_post.return_value.status_code = 500
        mock_post.return_value.text = 'boom'
        ok, detalle = whatsapp_enviar('3001234567', 'hola')
        self.assertFalse(ok)
        self.assertIn('500', detalle)

    # ── notificación con dedupe ───────────────────────────────────────────

    @patch('notificaciones.services.whatsapp_enviar', return_value=(True, 'enviado'))
    def test_notifica_solo_en_transicion_a_fallo(self, mock_env):
        # Primera vez FALLO → envía.
        r = notificar_usuario(self.usuario, EVENTO_TOKEN_VENCIDO, 'msg', 'FALLO')
        self.assertEqual(r, 'enviado')
        self.assertTrue(mock_env.called)

        # Mismo estado FALLO → sin cambios (sin spam).
        r = notificar_usuario(self.usuario, EVENTO_TOKEN_VENCIDO, 'msg', 'FALLO')
        self.assertEqual(r, 'sin_cambios')
        self.assertEqual(mock_env.call_count, 1)

        # Recuperación OK → solo marca el estado, no envía mensaje.
        r = notificar_usuario(self.usuario, EVENTO_TOKEN_VENCIDO, '', 'OK')
        self.assertEqual(r, 'estado_actualizado')
        self.assertEqual(NotificacionEstado.objects.get(usuario=self.usuario).estado, 'OK')
        self.assertEqual(mock_env.call_count, 1)

        # Nueva caída → vuelve a enviar.
        r = notificar_usuario(self.usuario, EVENTO_TOKEN_VENCIDO, 'msg', 'FALLO')
        self.assertEqual(r, 'enviado')
        self.assertEqual(mock_env.call_count, 2)

    @patch('notificaciones.services.whatsapp_enviar', return_value=(True, 'enviado'))
    def test_sin_telefono_omite_y_no_marca_estado(self, mock_env):
        self.usuario.telefono = ''
        self.usuario.save()
        r = notificar_usuario(self.usuario, EVENTO_TOKEN_VENCIDO, 'msg', 'FALLO')
        self.assertEqual(r, 'omitido')
        self.assertFalse(mock_env.called)
        # El estado NO queda marcado → al registrar el teléfono se notificará.
        estado = NotificacionEstado.objects.get(usuario=self.usuario)
        self.assertEqual(estado.estado, '')
        self.assertEqual(NotificacionLog.objects.count(), 1)

    def test_servicio_apagado_omite(self):
        cfg = NotificacionConfig.get_solo()
        cfg.activo = False
        cfg.save()
        with patch('notificaciones.services.whatsapp_enviar',
                   return_value=(True, 'enviado')) as mock_env:
            r = notificar_usuario(self.usuario, EVENTO_TOKEN_VENCIDO, 'msg', 'FALLO')
        self.assertEqual(r, 'omitido')
        self.assertFalse(mock_env.called)


class LandingWhatsAppTests(TestCase):

    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            email='admin@test.com', username='admin', password='***',
        )
        self.usuario = Usuario.objects.create_user(
            email='user@test.com', username='user', password='***',
        )

    def test_landing_solo_admin(self):
        self.client.force_login(self.usuario)
        resp = self.client.get(reverse('notificaciones:whatsapp_landing'))
        self.assertNotEqual(resp.status_code, 200)  # usuario normal: fuera

        self.client.force_login(self.admin)
        resp = self.client.get(reverse('notificaciones:whatsapp_landing'))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Vincular WhatsApp')
