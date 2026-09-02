from django.test import TestCase, Client
from django.urls import reverse
from cuentas.models import Usuario


class PanelSuperadminTest(TestCase):
    """Verifica el flujo completo del panel de administración de usuarios."""

    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            username='admin', email='admin@predicta.com.co', password='Admin1234!',
            first_name='Admin', last_name='Root',
        )
        self.client = Client()

    def _crear_usuario(self, email, username, password):
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('cuentas:crear_usuario'), {
            'email': email,
            'first_name': 'Juan',
            'last_name': 'Perez',
            'username': username,
            'is_active': 'on',
            'password1': password,
            'password2': password,
        })
        self.assertEqual(resp.status_code, 302, resp.context)
        return Usuario.objects.get(email=email)

    def test_crear_usuario(self):
        u = self._crear_usuario('juan@test.com', 'juan', 'Juanpass123')
        self.assertTrue(u.check_password('Juanpass123'))
        self.assertTrue(u.is_active)

    def test_suspender_reactivar_y_login_bloqueado(self):
        u = self._crear_usuario('juan@test.com', 'juan', 'Juanpass123')
        # Suspender (toggle → is_active=False)
        resp = self.client.post(reverse('cuentas:suspender_usuario', args=[u.id]))
        self.assertEqual(resp.status_code, 302)
        u.refresh_from_db()
        self.assertFalse(u.is_active)
        # Un usuario suspendido NO puede loguearse
        self.client.logout()
        ok = self.client.login(username='juan@test.com', password='Juanpass123')
        self.assertFalse(ok)
        # Reactivar (toggle → is_active=True)
        self.client.force_login(self.admin)
        self.client.post(reverse('cuentas:suspender_usuario', args=[u.id]))
        u.refresh_from_db()
        self.assertTrue(u.is_active)

    def test_cambiar_username_y_password(self):
        u = self._crear_usuario('juan@test.com', 'juan', 'Juanpass123')
        # Cambiar username
        resp = self.client.post(reverse('cuentas:editar_usuario', args=[u.id]), {
            'username': 'juanv2',
            'email': 'juan@test.com',
            'first_name': 'Juan',
            'last_name': 'Perez',
            'is_active': 'on',
        })
        self.assertEqual(resp.status_code, 302)
        u.refresh_from_db()
        self.assertEqual(u.username, 'juanv2')
        # Cambiar contraseña
        resp = self.client.post(reverse('cuentas:cambiar_contraseña', args=[u.id]), {
            'password1': 'NuevaPass456',
            'password2': 'NuevaPass456',
        })
        self.assertEqual(resp.status_code, 302)
        u.refresh_from_db()
        self.assertTrue(u.check_password('NuevaPass456'))

    def test_username_duplicado_rechazado(self):
        self._crear_usuario('juan@test.com', 'juan', 'Juanpass123')
        self._crear_usuario('pedro@test.com', 'pedro', 'Pedropass123')
        u2 = Usuario.objects.get(email='pedro@test.com')
        resp = self.client.post(reverse('cuentas:editar_usuario', args=[u2.id]), {
            'username': 'juan',  # ya existe
            'email': 'pedro@test.com',
            'first_name': 'Pedro',
            'last_name': 'Perez',
            'is_active': 'on',
        })
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'Ya existe una cuenta con este usuario')

    def test_no_puede_suspender_superusuario_ni_a_si_mismo(self):
        u = self._crear_usuario('juan@test.com', 'juan', 'Juanpass123')
        # Intentar suspender al propio admin
        self.client.force_login(self.admin)
        resp = self.client.post(reverse('cuentas:suspender_usuario', args=[self.admin.id]))
        self.assertEqual(resp.status_code, 302)
        self.admin.refresh_from_db()
        self.assertTrue(self.admin.is_active)  # sigue activo

    def test_eliminar_usuario_cascada(self):
        u = self._crear_usuario('juan@test.com', 'juan', 'Juanpass123')
        from auto_betting.models import AutoBetConfig
        AutoBetConfig.objects.create(usuario=u, ticket='ticket-x', punter_id='1')
        self.client.post(reverse('cuentas:eliminar_usuario', args=[u.id]))
        self.assertFalse(Usuario.objects.filter(id=u.id).exists())
        self.assertFalse(AutoBetConfig.objects.filter(usuario_id=u.id).exists())

    def test_usuario_normal_no_accede_al_panel(self):
        u = self._crear_usuario('juan@test.com', 'juan', 'Juanpass123')
        self.client.logout()
        self.client.force_login(u)
        resp = self.client.get(reverse('cuentas:panel_usuarios'))
        self.assertEqual(resp.status_code, 302)  # redirigido, sin acceso

    def test_panel_lista_usuarios_existentes(self):
        """REGRESIÓN: el template iteraba page_obj.object_list pero la vista
        pasaba el contexto como 'usuarios' → el panel salía vacío."""
        self._crear_usuario('juan@test.com', 'juan', 'Juanpass123')
        self._crear_usuario('pedro@test.com', 'pedro', 'Pedropass123')
        self.client.force_login(self.admin)
        resp = self.client.get(reverse('cuentas:panel_usuarios'))
        self.assertEqual(resp.status_code, 200)
        html = resp.content.decode()
        self.assertIn('juan@test.com', html)
        self.assertIn('pedro@test.com', html)
        self.assertIn('Suspender', html)
        self.assertIn('Contraseña', html)
        self.assertNotIn('No hay usuarios registrados', html)
