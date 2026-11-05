# -*- coding: utf-8 -*-
"""Tests de la config web de la IA de apuestas reales (T-45) + ventana.

Cubre: helpers puros (endpoint/base), .env (leer/escribir key), lista de
modelos (mock del proveedor), ventana T-X (selección e idempotencia del job),
formulario/página de umbrales y endpoint JSON de modelos.
"""
import json
import tempfile
from datetime import timedelta
from io import StringIO
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from auto_betting import llm_validator as lv
from auto_betting.models import AutoBet, LlmRealConfig


class HelpersPurosTests(SimpleTestCase):

    def test_endpoint_efectivo(self):
        self.assertEqual(lv.endpoint_efectivo(''), lv.OPENAI_ENDPOINT)
        self.assertEqual(lv.endpoint_efectivo('https://api.openai.com/v1'),
                         'https://api.openai.com/v1/responses')
        self.assertEqual(
            lv.endpoint_efectivo('https://gw.example.com/v1/responses'),
            'https://gw.example.com/v1/responses')

    def test_base_v1_efectiva(self):
        self.assertEqual(lv.base_v1_efectiva(''), lv.DEFAULT_BASE_V1)
        self.assertEqual(lv.base_v1_efectiva('https://api.openai.com/v1/'),
                         'https://api.openai.com/v1')
        self.assertEqual(lv.base_v1_efectiva('https://x.ai/v1/responses'),
                         'https://x.ai/v1')


class ApiKeyEnvTests(TestCase):

    def test_guardar_y_leer_preservando_resto(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '.env'
            p.write_text('OTRA=1\nLLM_API_KEY=viejita\nMAS=2\n')
            lv.guardar_api_key('nueva-clave-123', path=p)
            self.assertEqual(lv.api_key_real(path=p), 'nueva-clave-123')
            contenido = p.read_text()
            self.assertIn('OTRA=1', contenido)
            self.assertIn('MAS=2', contenido)
            self.assertNotIn('viejita', contenido)
            self.assertEqual(oct(p.stat().st_mode)[-3:], '600')

    def test_agrega_si_no_existe(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '.env'
            p.write_text('X=1\n')
            lv.guardar_api_key('kk', path=p)
            self.assertEqual(lv.api_key_real(path=p), 'kk')
            self.assertIn('X=1', p.read_text())

    def test_rechaza_vacia_o_multilinea(self):
        with self.assertRaises(ValueError):
            lv.guardar_api_key('')
        with self.assertRaises(ValueError):
            lv.guardar_api_key('a\nb')


class ListarModelosTests(SimpleTestCase):

    def _resp(self, status, payload):
        r = mock.Mock()
        r.status_code = status
        r.json.return_value = payload
        r.text = json.dumps(payload)
        return r

    def test_ok_ordena_y_llama_base(self):
        resp = self._resp(200, {'data': [{'id': 'b'}, {'id': 'a'}]})
        with mock.patch.object(lv.requests, 'get', return_value=resp) as g:
            modelos, error = lv.listar_modelos('', api_key='k')
        self.assertIsNone(error)
        self.assertEqual(modelos, ['a', 'b'])
        self.assertEqual(g.call_args.args[0],
                         'https://api.openai.com/v1/models')

    def test_error_del_proveedor(self):
        with mock.patch.object(lv.requests, 'get',
                               return_value=self._resp(401, {'error': 'nope'})):
            modelos, error = lv.listar_modelos('', api_key='k')
        self.assertEqual(modelos, [])
        self.assertIn('HTTP 401', error)

    def test_sin_key_no_llama(self):
        with mock.patch.object(lv.requests, 'get') as g:
            modelos, error = lv.listar_modelos('', api_key='')
        g.assert_not_called()
        self.assertEqual(modelos, [])
        self.assertIn('no configurada', error)


class VentanaTests(TestCase):

    def _bet(self, minutos, evento_id, **kw):
        User = get_user_model()
        u, _ = User.objects.get_or_create(username='u1',
                                          defaults=dict(email='u1@t.co'))
        return AutoBet.objects.create(
            usuario=u, evento_id=evento_id, home_team='A', away_team='B',
            liga='Liga', mercado='Total de goles', seleccion='Over 2.5',
            cuota=1.9, corners_predichos=0.0, predicta_prob=55.0,
            edge=5.0, ev=0.10, stake=10000, estado='OPEN',
            start_time=timezone.now() + timedelta(minutes=minutos), **kw)

    def test_llm_ventana_alcanzada(self):
        ahora = timezone.now()
        self.assertTrue(lv.llm_ventana_alcanzada(ahora + timedelta(minutes=40)))
        self.assertFalse(lv.llm_ventana_alcanzada(ahora + timedelta(minutes=90)))
        self.assertTrue(lv.llm_ventana_alcanzada(None))    # sin hora: se pide
        LlmRealConfig.objects.filter(pk=1).update(enabled=False)
        self.assertFalse(lv.llm_ventana_alcanzada(ahora + timedelta(minutes=10)))
        LlmRealConfig.objects.filter(pk=1).update(enabled=True,
                                                  anticipacion_min=60)
        self.assertTrue(lv.llm_ventana_alcanzada(ahora + timedelta(minutes=50)))

    def test_job_ventana_solo_consulta_la_del_rango(self):
        en = self._bet(40, evento_id=10)        # dentro de T-45
        self._bet(90, evento_id=11)             # fuera
        self._bet(-10, evento_id=12)            # ya iniciado
        ya = self._bet(30, evento_id=13)        # ya tiene opinión
        AutoBet.objects.filter(pk=ya.pk).update(llm_asked_at=timezone.now())

        llamadas = []

        def fake(autobet, bet):
            llamadas.append(autobet.id)
            return True, 'ok'

        with mock.patch(
                'auto_betting.management.commands.ask_llm_real.opinar_apuesta',
                side_effect=fake):
            call_command('ask_llm_real', '--ventana', stdout=StringIO())
        self.assertEqual(llamadas, [en.id])

    def test_job_ventana_apagado_no_consulta(self):
        self._bet(40, evento_id=20)
        cfg = LlmRealConfig.get_solo()
        cfg.enabled = False
        cfg.save(update_fields=['enabled'])
        out = StringIO()
        with mock.patch(
                'auto_betting.management.commands.ask_llm_real.opinar_apuesta'
        ) as m:
            call_command('ask_llm_real', '--ventana', stdout=out)
        m.assert_not_called()
        self.assertIn('desactivada', out.getvalue())


class UmbralesLlmViewTests(TestCase):

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_superuser(
            username='adm', email='adm@x.co', password='x')
        self.client = Client()
        self.client.force_login(self.admin)

    def test_pagina_muestra_bloque_llm(self):
        r = self.client.get(reverse('auto_betting:configuracion_umbrales'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Opinión IA', html)
        self.assertIn('Anticipación', html)
        self.assertIn('API key', html)

    def test_post_guarda_config_y_key(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / '.env'
            p.write_text('A=1\n')
            with mock.patch.object(lv, 'ENV_PATH', p):
                r = self.client.post(
                    reverse('auto_betting:configuracion_umbrales'),
                    {'guardar_llm': '1', 'enabled': 'on',
                     'anticipacion_min': '50', 'modelo': 'gpt-5.6-luna',
                     'base_url': 'https://api.openai.com/v1',
                     'api_key': 'clave-test-123'})
            self.assertEqual(r.status_code, 302)
            cfg = LlmRealConfig.get_solo()
            self.assertTrue(cfg.enabled)
            self.assertEqual(cfg.anticipacion_min, 50)
            self.assertEqual(cfg.base_url, 'https://api.openai.com/v1')
            self.assertEqual(lv.api_key_real(path=p), 'clave-test-123')

    def test_post_blank_key_conserva(self):
        r = self.client.post(
            reverse('auto_betting:configuracion_umbrales'),
            {'guardar_llm': '1', 'anticipacion_min': '45', 'api_key': ''})
        self.assertEqual(r.status_code, 302)
        cfg = LlmRealConfig.get_solo()
        self.assertEqual(cfg.anticipacion_min, 45)

    def test_endpoint_modelos_json_ok(self):
        with mock.patch('auto_betting.llm_validator.listar_modelos',
                        return_value=(['m1', 'm2'], None)), \
             mock.patch('auto_betting.llm_validator.api_key_real',
                        return_value='k'):
            r = self.client.get(reverse('auto_betting:llm_modelos'))
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['modelos'], ['m1', 'm2'])
        self.assertIsNone(data['error'])

    def test_endpoint_modelos_muestra_error(self):
        with mock.patch('auto_betting.llm_validator.listar_modelos',
                        return_value=([], 'HTTP 401: bad key')), \
             mock.patch('auto_betting.llm_validator.api_key_real',
                        return_value='k'):
            r = self.client.get(reverse('auto_betting:llm_modelos'))
        data = r.json()
        self.assertFalse(data['ok'])
        self.assertIn('HTTP 401', data['error'])
