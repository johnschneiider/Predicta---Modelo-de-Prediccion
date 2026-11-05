# -*- coding: utf-8 -*-
"""Tests del control de acceso a las opciones del menú de usuario (navbar).

Norma 2026-10-13: por defecto TODO denegado; el superadmin asigna opción por
opción desde el panel de usuarios. Superusuarios: acceso total.
"""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase
from django.urls import reverse

from cuentas.menu import permisos_efectivos
from cuentas.models import PermisoMenu

Usuario = get_user_model()


class PermisosMenuTests(TestCase):
    def setUp(self):
        self.admin = Usuario.objects.create_superuser(
            username='admin_perm', email='admin_perm@test.com',
            password='Admin1234!', first_name='Admin', last_name='P')
        self.user = Usuario.objects.create_user(
            username='pepe', email='pepe@test.com', password='Pepe1234!',
            first_name='Pepe', last_name='L')
        self.client = Client()

    # ------------------------------------------------------------------ #
    #  Modelo / helpers                                                   #
    # ------------------------------------------------------------------ #
    def test_permisos_efectivos_por_defecto_denegado(self):
        efectivos = permisos_efectivos(self.user)
        self.assertTrue(efectivos)
        self.assertFalse(any(efectivos.values()))

    def test_superusuario_todo_permitido(self):
        efectivos = permisos_efectivos(self.admin)
        self.assertTrue(efectivos)
        self.assertTrue(all(efectivos.values()))

    def test_fila_explicita_concede(self):
        PermisoMenu.objects.create(usuario=self.user, codigo='ap_paperbet',
                                   permitido=True)
        efectivos = permisos_efectivos(self.user)
        self.assertTrue(efectivos['ap_paperbet'])
        self.assertFalse(efectivos['ap_betplay'])

    # ------------------------------------------------------------------ #
    #  Navbar                                                             #
    # ------------------------------------------------------------------ #
    def test_menu_oculto_sin_permisos(self):
        self.client.force_login(self.user)
        r = self.client.get(reverse('cuentas:dashboard'))
        html = r.content.decode()
        self.assertNotIn('Paperbet (Motores)', html)
        self.assertNotIn('Predicción NBA', html)
        self.assertIn('Mi cuenta', html)
        self.assertIn('Salir', html)

    def test_asignar_y_mostrar_menu(self):
        self.client.force_login(self.admin)
        r = self.client.post(
            reverse('cuentas:permisos_usuario', args=[self.user.id]),
            {'permitido': ['pred_dashboard', 'ap_paperbet']})
        self.assertEqual(r.status_code, 302)
        self.assertTrue(PermisoMenu.objects.get(
            usuario=self.user, codigo='ap_paperbet').permitido)
        self.assertFalse(PermisoMenu.objects.get(
            usuario=self.user, codigo='datos_importar').permitido)

        self.client.logout()
        self.client.force_login(self.user)
        r = self.client.get(reverse('cuentas:dashboard'))
        html = r.content.decode()
        self.assertIn('Paperbet (Motores)', html)      # asignada
        self.assertIn('📊 Dashboard', html)            # asignada
        self.assertNotIn('⬆️ Importar', html)          # no asignada
        self.assertNotIn('Apuestas BetPlay', html)     # no asignada

    # ------------------------------------------------------------------ #
    #  Middleware (bloqueo de URL directa)                                #
    # ------------------------------------------------------------------ #
    def test_middleware_permite_asignada_y_bloquea_resto(self):
        PermisoMenu.objects.create(usuario=self.user, codigo='ap_paperbet',
                                   permitido=True)
        self.client.force_login(self.user)
        # Asignada → la vista real responde.
        self.assertEqual(
            self.client.get(reverse('auto_betting:paperbet')).status_code, 200)
        # Subpágina dependiente de la opción → también permitida.
        self.assertEqual(
            self.client.get(reverse('auto_betting:paperbet_basket')).status_code,
            200)
        # No asignada → redirige al dashboard con mensaje.
        r = self.client.get(reverse('football_data:import'))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(r.url, reverse('cuentas:dashboard'))

    def test_middleware_no_bloquea_superusuario(self):
        self.client.force_login(self.admin)
        r = self.client.get(reverse('football_data:import'))
        self.assertEqual(r.status_code, 200)

    # ------------------------------------------------------------------ #
    #  Panel de permisos                                                  #
    # ------------------------------------------------------------------ #
    def test_panel_solo_superadmin(self):
        self.client.force_login(self.user)
        r = self.client.get(
            reverse('cuentas:permisos_usuario', args=[self.user.id]))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/cuentas/login/', r.url)

    def test_no_edita_permisos_de_superusuario(self):
        otro_admin = Usuario.objects.create_superuser(
            username='admin2_perm', email='admin2_perm@test.com',
            password='Admin1234!', first_name='A2', last_name='X')
        self.client.force_login(self.admin)
        r = self.client.get(
            reverse('cuentas:permisos_usuario', args=[otro_admin.id]))
        self.assertEqual(r.status_code, 302)
        self.assertEqual(PermisoMenu.objects.filter(usuario=otro_admin).count(), 0)
