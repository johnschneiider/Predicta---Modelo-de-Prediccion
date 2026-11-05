# -*- coding: utf-8 -*-
"""Tests del motor basket_1q2q (paperbet de baloncesto 1Q+2Q).

Cubren:
  * Fidelidad del MCO: los coeficientes del port deben coincidir con los del
    motor ORIGINAL del repo (valores capturados de motor._ajustar y
    modelos._entrenar_liga sobre un dataset sintético reproducible).
  * Parseo del feed Kambi (cuartos, ventana de descanso, mercado de total).
  * Compuerta completa (|Δ|, cuota del lado, EV) y liquidación (push → VOID).
  * Comandos: dry-run (no escribe), registro + dedup, liquidación con mocks.
  * Guard del liquidador de fútbol (score_paper_bets no toca basket_*).
  * Render de la página dedicada /auto-betting/paperbet/baloncesto/.
"""
from datetime import datetime, timedelta, timezone as dt_timezone
from unittest import mock
from zoneinfo import ZoneInfo

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, TestCase
from django.urls import reverse
from django.utils import timezone
from io import StringIO

from auto_betting import basket_1q2q as bk
from auto_betting import basket_pinnacle as bp
from auto_betting import services as ab
from auto_betting.models import (AutoBet, AutoBetConfig, BasketMarketSnapshot,
                                 BasketModel, BasketSample, DailyCounter,
                                 PaperBet, PinnacleCallLog, PinnacleSnapshot)

# --------------------------------------------------------------------------- #
#  Dataset sintético (mismo random.Random(42) del repo) y valores capturados  #
#  del motor original (motor._ajustar / modelos._entrenar_liga).              #
# --------------------------------------------------------------------------- #
DATOS_REPO = [
    (29.591401976868, 20.37516132834, 81.364893062586), (23.348161072232, 31.04706821246, 85.343368709508),
    (33.382693515573, 21.304082489441, 90.185278233472), (20.446958291571, 23.279569622054, 69.772140199913),
    (20.398039545258, 22.9825647603, 70.194855520501), (28.174122209048, 23.30660933061, 84.216945276275),
    (32.141456850167, 20.097481395171, 88.806515515503), (30.472090924823, 25.10375774777, 87.907149960877),
    (34.358196083102, 25.048918176689, 94.459929821891), (21.450745652502, 32.712415495212, 83.488596956959),
    (32.106924099116, 30.945976800407, 100.145004087625), (34.596736459691, 25.678015658125, 98.399988204833),
    (32.441069963795, 29.277796285464, 100.697522879252), (28.660282178851, 30.568577543224, 90.545747275735),
    (23.418474134773, 24.340819454032, 73.840988648971), (23.491863295415, 21.515021441146, 71.771221279783),
    (29.535266663966, 25.472482684551, 87.951545019302), (23.142605461572, 24.004667330737, 78.082218153989),
    (29.720530778699, 29.136965085005, 91.488145392852), (30.936901969255, 22.451037406429, 86.90440108292),
    (34.842850259549, 29.599996397811, 103.57882460721), (30.269213764848, 32.642778802847, 100.311918809421),
    (23.435721079462, 20.481503658561, 70.654820621658), (24.016113139636, 23.164742653795, 78.684153121908),
    (33.14551439709, 24.720168211977, 95.258759760904), (25.93447851591, 33.718213846108, 91.897029059492),
    (23.973202497471, 23.69941261541, 76.959268438918), (23.941124127844, 28.768789853353, 85.003508555758),
    (25.991007577106, 23.289811387359, 82.716812942592), (27.642894405147, 21.363641182607, 77.676277600941),
    (21.64473695526, 29.411690625546, 81.007031456301), (26.332399501995, 20.952915592279, 76.831533533366),
    (34.941820703601, 27.936715176487, 104.245805743949), (32.911695533517, 20.172215329142, 89.772041271463),
    (30.225655535399, 28.054554956132, 91.672597050791), (29.614426978697, 21.673282603938, 83.922499190395),
    (26.805855594938, 34.307238912816, 96.674344408537), (23.950835761266, 27.508791695754, 79.193965688366),
    (33.689417590172, 33.057778547552, 104.100954668064), (29.58424242299, 29.134553171573, 91.130135778567),
    (31.437662001127, 28.090685451794, 96.968373015966), (27.955305082928, 20.008578441919, 78.274779621601),
    (20.292151135787, 33.936479243969, 84.52197840412), (32.474982940418, 24.61271188104, 90.337774548965),
    (33.170143988061, 34.20424167947, 103.26526990628), (27.289856949749, 21.038187777026, 80.931180833523),
    (31.487516439605, 21.925871967496, 87.840270220877), (28.247053902424, 23.975849434101, 86.850314591796),
    (26.347069103013, 23.176973081631, 80.472868616058), (30.94896603635, 23.017265950845, 87.199155754249),
    (34.927240349913, 29.748170864592, 103.195438170841), (27.763637615534, 21.815062938024, 79.500807255779),
    (25.071283432212, 28.824630776858, 83.098555505791), (23.303260766773, 21.064896290135, 73.010362671975),
    (23.434126757167, 33.581300195092, 89.636800798534), (21.06286024833, 23.570069515535, 72.211098535413),
    (23.213552110557, 21.984677730875, 75.779092519536), (28.565646399879, 27.090065394677, 90.633958539139),
    (32.1124549665, 22.856148715428, 87.811382283586), (26.465767736096, 26.353679345299, 84.064945147551),
]

ESPERADO_AJUSTAR = {
    'b0': 6.779826656779764, 'b1': 1.7002835175662407, 'b2': 1.2417877967508542,
    'a0': 37.950716479035044, 'a1': 1.7350817515000716,
    'r2_dos': 0.9689773487397118, 'r2_uno': 0.6394073777160403,
    'rmse_dos': 1.6351394413163376, 'rmse_uno': 5.574728963117363,
    'rmse_naive': 27.822333625060313,
    'media_total': 86.54105240888217, 'media_1q': 28.004637757176663,
    'media_2q': 25.886388835733733,
}

ESPERADO_ENTRENAR = {
    'b0': 6.3165653568255555, 'b1': 1.725844651198641, 'b2': 1.2323607531948042,
    'rmse_test_dos': 1.376634543919704, 'rmse_test_uno': 5.068181581393423,
    'rmse_test_naive': 26.03009380407719, 'n': 60, 'r2_dos': 0.9689773487397118,
}


def _partido(**kw) -> bk.PartidoLive:
    """Partido en el descanso 2Q→3Q, listo para la compuerta."""
    base = dict(
        evento_id=12345, nombre='A - B', local='A', visitante='B',
        state='STARTED', inicio='2026-10-12T18:00:00Z',
        liga_nombre='España / Liga ACB', liga_tk='liga_acb', region_tk='spain',
        period_id='QUARTER2', corriendo=False, reloj_min=20,
        izq_min=0, izq_seg=0, info_cuartos='Q1: 25-18 | Q2: 23-24',
        marcador_local=48, marcador_visitante=42,
        q1=45, q2=50, linea=91.0,
        cuota_over=1.80, cuota_under=1.95,
        mercado_abierto=True, cuota_over_abierta=True, cuota_under_abierta=True,
    )
    base.update(kw)
    return bk.PartidoLive(**base)


def _modelo(**kw) -> bk.Modelo:
    base = dict(liga='spain/liga_acb', n=100, b0=0.0, b1=1.0, b2=1.0,
                rmse_test_dos=12.0, rmse_test_uno=15.0)
    base.update(kw)
    return bk.Modelo(**base)


class MotorMCOFidelidadTests(TestCase):
    def test_ajustar_igual_al_motor_original(self):
        m = bk.ajustar(DATOS_REPO, 'test', 'sintetico')
        self.assertEqual(m.n, 60)
        for campo, esperado in ESPERADO_AJUSTAR.items():
            self.assertAlmostEqual(getattr(m, campo), esperado, places=9,
                                   msg=f'campo {campo}')

    def test_entrenar_holdout_igual_al_original(self):
        m = bk.entrenar(DATOS_REPO, 'test', minimo=30)
        self.assertIsNotNone(m)
        for campo, esperado in ESPERADO_ENTRENAR.items():
            self.assertAlmostEqual(getattr(m, campo), esperado, places=9,
                                   msg=f'campo {campo}')

    def test_entrenar_exige_minimo(self):
        self.assertIsNone(bk.entrenar(DATOS_REPO[:29], 'x', minimo=30))

    def test_plano_exacto(self):
        pts = [(1, 2), (2, 1), (3, 3), (4, 5), (2, 4), (5, 2)]
        datos = [(x1, x2, 10 + 2 * x1 + 3 * x2) for x1, x2 in pts]
        m = bk.ajustar(datos, 'plano')
        self.assertAlmostEqual(m.b0, 10.0, places=9)
        self.assertAlmostEqual(m.b1, 2.0, places=9)
        self.assertAlmostEqual(m.b2, 3.0, places=9)
        self.assertAlmostEqual(m.r2_dos, 1.0, places=9)
        self.assertAlmostEqual(m.rmse_dos, 0.0, places=9)

    def test_predecir_y_phi(self):
        m = _modelo()
        r = bk.predecir(m, 45, 50, 91.0)
        self.assertAlmostEqual(r.prediccion, 95.0, places=9)
        self.assertAlmostEqual(r.diferencia, 4.0, places=9)
        self.assertEqual(r.veredicto, 'OVER')
        sigma = 12.0 * bk.FACTOR_RMSE
        self.assertAlmostEqual(r.prob_over, bk._normal_cdf(4.0 / sigma), places=9)
        r0 = bk.predecir(m, 45, 46, 91.0)      # Δ = 0
        self.assertAlmostEqual(r0.prob_over, 0.5, places=9)


class ParseoTests(TestCase):
    def test_parsear_cuartos(self):
        self.assertEqual(bk.parsear_cuartos('Q1: 20-29 | Q2: 19-24'),
                         {'Q1': 49, 'Q2': 43})
        self.assertEqual(bk.parsear_cuartos('Q1: 10-10 | Q2: 1-2 | Q3: 3-4 | Q4: 5-6'),
                         {'Q1': 20, 'Q2': 3, 'Q3': 7, 'Q4': 11})
        self.assertEqual(bk.parsear_cuartos('QOT: 8-6'), {'QOT': 14})
        self.assertEqual(bk.parsear_cuartos(''), {})

    def test_es_total_partido(self):
        self.assertTrue(bk._es_total_partido('Total de puntos - Prórroga incluida'))
        self.assertFalse(bk._es_total_partido('Total de puntos de FC Barcelona - Prórroga incluida'))
        self.assertFalse(bk._es_total_partido('Total de puntos - Cuarto 4'))
        self.assertFalse(bk._es_total_partido('Total de puntos - 1.ª parte'))

    def test_parsear_evento_descanso(self):
        bloque = {
            'event': {
                'id': 555, 'name': 'A - B', 'homeName': 'A', 'awayName': 'B',
                'state': 'STARTED', 'start': '2026-10-12T18:00:00Z',
                'path': [{'termKey': 'basketball'},
                         {'termKey': 'spain', 'name': 'España'},
                         {'termKey': 'liga_acb', 'name': 'Liga ACB'}],
                'group': 'España / Liga ACB',
            },
            'liveData': {
                'matchClock': {'periodId': 'QUARTER2', 'running': False,
                               'minute': 20, 'minutesLeftInPeriod': 0,
                               'secondsLeftInMinute': 0},
                'score': {'home': '48', 'away': '42',
                          'info': 'Q1: 25-18 | Q2: 23-24'},
            },
            'betOffers': [{
                'betOfferType': {'id': 6, 'name': 'Más/Menos de'},
                'criterion': {'label': 'Total de puntos - Prórroga incluida'},
                'suspended': False,
                'outcomes': [
                    {'type': 'OT_OVER', 'status': 'OPEN',
                     'line': 169500, 'odds': 1800},
                    {'type': 'OT_UNDER', 'status': 'OPEN',
                     'line': 169500, 'odds': 1880},
                ]}],
        }
        p = bk.parsear_evento(bloque)
        self.assertEqual(p.clave_liga, 'spain/liga_acb')
        self.assertEqual((p.q1, p.q2), (43, 47))
        self.assertTrue(p.q2_completo)
        self.assertTrue(bk.en_ventana_descanso(p))
        self.assertEqual(p.linea, 169.5)
        self.assertEqual(p.cuota_over, 1.8)
        self.assertEqual(p.cuota_under, 1.88)
        self.assertTrue(p.hay_cuota_over and p.hay_cuota_under)

    def test_parsear_evento_ignora_totales_de_equipo_y_cuarto(self):
        base = {
            'event': {'id': 1, 'name': 'A - B', 'homeName': 'A', 'awayName': 'B',
                      'state': 'STARTED', 'start': '',
                      'path': [{'termKey': 'basketball'}, {'termKey': 'nba'}]},
            'liveData': {'matchClock': {'periodId': 'QUARTER2', 'running': False,
                                        'minute': 20, 'minutesLeftInPeriod': 0,
                                        'secondsLeftInMinute': 0},
                         'score': {'home': '48', 'away': '42',
                                   'info': 'Q1: 25-18 | Q2: 23-24'}},
            'betOffers': [
                {'betOfferType': {'id': 6}, 'suspended': False,
                 'criterion': {'label': 'Total de puntos de A - Prórroga incluida'},
                 'outcomes': [{'type': 'OT_OVER', 'status': 'OPEN',
                               'line': 90000, 'odds': 1800}]},
                {'betOfferType': {'id': 6}, 'suspended': False,
                 'criterion': {'label': 'Total de puntos - Cuarto 4'},
                 'outcomes': [{'type': 'OT_OVER', 'status': 'OPEN',
                               'line': 40000, 'odds': 1800}]},
            ]}
        p = bk.parsear_evento(base)
        self.assertIsNone(p.linea)
        self.assertFalse(p.mercado_abierto)


class CompuertaTests(TestCase):
    def test_apuesta_valida_over(self):
        ev = bk.evaluar(_partido(), _modelo())
        self.assertTrue(ev['ok'], ev['motivo'])
        self.assertEqual(ev['lado'], 'OVER')
        self.assertAlmostEqual(ev['diferencia'], 4.0, places=9)
        self.assertGreater(ev['ev'], bk.EV_MINIMA)

    def test_apuesta_valida_under(self):
        ev = bk.evaluar(_partido(linea=99.0), _modelo())
        self.assertTrue(ev['ok'], ev['motivo'])
        self.assertEqual(ev['lado'], 'UNDER')

    def test_delta_insuficiente(self):
        ev = bk.evaluar(_partido(linea=93.0), _modelo(),
                        delta_min=3.0, delta_max=5.0)
        self.assertFalse(ev['ok'])
        self.assertIn('< 3.0', ev['motivo'])

    def test_delta_fuera_de_rango(self):
        ev = bk.evaluar(_partido(linea=88.0), _modelo(),
                        delta_min=3.0, delta_max=5.0)
        self.assertFalse(ev['ok'])
        self.assertIn('> 5.0', ev['motivo'])

    def test_limites_amplios_permiten_delta_chico(self):
        ev = bk.evaluar(_partido(linea=94.0, cuota_over=2.10), _modelo(),
                        delta_min=0.0, delta_max=500.0)
        self.assertTrue(ev['ok'], ev['motivo'])
        self.assertAlmostEqual(ev['diferencia'], 1.0, places=9)

    def test_lado_suspendido(self):
        ev = bk.evaluar(_partido(cuota_over_abierta=False), _modelo())
        self.assertFalse(ev['ok'])
        self.assertIn('suspendido', ev['motivo'])

    def test_sin_cuota(self):
        ev = bk.evaluar(_partido(cuota_over=None), _modelo())
        self.assertFalse(ev['ok'])
        self.assertIn('no publica cuota', ev['motivo'])

    def test_ev_negativo_pasa_sin_filtro(self):
        # Modo muestreo (2026-10-13): EV_MINIMA=0 → el EV negativo NO descarta;
        # queda registrado para trazabilidad.
        ev = bk.evaluar(_partido(cuota_over=1.10), _modelo())
        self.assertTrue(ev['ok'], ev['motivo'])
        self.assertLess(ev['ev'], 0.0)

    def test_ev_filtro_explicito(self):
        ev = bk.evaluar(_partido(cuota_over=1.10), _modelo(), ev_min=0.02)
        self.assertFalse(ev['ok'])
        self.assertIn('EV', ev['motivo'])

    def test_sin_modelo(self):
        ev = bk.evaluar(_partido(), None)
        self.assertFalse(ev['ok'])
        self.assertIn('sin modelo propio', ev['motivo'])

    def test_fuera_de_ventana(self):
        ev = bk.evaluar(_partido(q2=None, q3=15,
                                 period_id='QUARTER3'), _modelo())
        self.assertFalse(ev['ok'])
        self.assertIn('descanso', ev['motivo'])

    def test_finalizado_no_es_ventana(self):
        p = _partido(state='RESULT')
        self.assertFalse(bk.en_ventana_descanso(p))


class VentanaDescansoTests(TestCase):
    """Variante de proveedor: descanso etiquetado QUARTER3 con Q3 a 0-0."""

    def _placeholder(self, **kw):
        base = dict(
            q3=0, period_id='QUARTER3', corriendo=False,
            izq_min=10, izq_seg=0,
            info_cuartos='Q1: 25-18 | Q2: 23-24 | Q3: 0-0')
        base.update(kw)
        return _partido(**base)

    def test_placeholder_q3_cero_es_ventana(self):
        self.assertTrue(bk.en_ventana_descanso(self._placeholder()))

    def test_placeholder_entra_a_la_compuerta(self):
        ev = bk.evaluar(self._placeholder(), _modelo())
        self.assertTrue(ev['ok'], ev['motivo'])
        self.assertEqual(ev['lado'], 'OVER')

    def test_q3_cero_pero_jugando_no_es_ventana(self):
        self.assertFalse(bk.en_ventana_descanso(
            self._placeholder(corriendo=True)))

    def test_q3_cero_con_reloj_movido_no_es_ventana(self):
        self.assertFalse(bk.en_ventana_descanso(
            self._placeholder(izq_min=9, izq_seg=59)))

    def test_q3_con_puntos_no_es_ventana(self):
        self.assertFalse(bk.en_ventana_descanso(
            self._placeholder(q3=6, izq_min=7, izq_seg=30)))

    def test_q3_cero_en_quarter4_no_es_ventana(self):
        self.assertFalse(bk.en_ventana_descanso(
            self._placeholder(period_id='QUARTER4')))

    def test_q3_cero_publicado_en_quarter2_es_ventana(self):
        self.assertTrue(bk.en_ventana_descanso(
            self._placeholder(period_id='QUARTER2', izq_min=0, izq_seg=0)))


class LiquidacionTests(TestCase):
    def test_over_gana_pierde_push(self):
        self.assertEqual(bk.liquidar(bk.SEL_OVER, 170, 175), 'WON')
        self.assertEqual(bk.liquidar(bk.SEL_OVER, 170, 165), 'LOST')
        self.assertEqual(bk.liquidar(bk.SEL_OVER, 170, 170), 'VOID')

    def test_under_gana_pierde_push(self):
        self.assertEqual(bk.liquidar(bk.SEL_UNDER, 170, 165), 'WON')
        self.assertEqual(bk.liquidar(bk.SEL_UNDER, 170, 175), 'LOST')
        self.assertEqual(bk.liquidar(bk.SEL_UNDER, 169.5, 169.5), 'VOID')

    def test_similitud_por_contencion_y_alias(self):
        # Nombres cortos de API-Sports no deben impedir la liquidación.
        n = bk._norm
        p = bk._parecido
        self.assertGreaterEqual(p(n('Abejas de León'), n('Abejas')), 0.5)
        self.assertGreaterEqual(p(n('Santos De San Luis'), n('Santos')), 0.5)
        self.assertGreaterEqual(p(n('Anyang KGC'), n('Anyang JungKwanJang')), 0.5)
        self.assertGreaterEqual(p(n('Talk N Text Tropang Giga'),
                                  n('TNT Tropang 5G')), 0.5)
        self.assertLess(p(n('Real Madrid'), n('Barcelona')), 0.5)


class ComandoRunPaperBasketTests(TestCase):
    def setUp(self):
        # Sin filtro liga-dia en los tests del comando (el filtro real vive
        # en el JSON de produccion; aqui se prueba con celda fuera en un
        # test dedicado).
        patcher = mock.patch('auto_betting.management.commands.'
                             'run_paper_bets_basket.cargar_filtro_ligadia',
                             return_value=None)
        self.addCleanup(patcher.stop)
        patcher.start()
        BasketModel.objects.create(
            liga='spain/liga_acb', origen='test', n=100,
            b0=0.0, b1=1.0, b2=1.0, rmse_test_dos=12.0, rmse_test_uno=15.0)

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_filtro_ligadia_descarta_celda_fuera_de_whitelist(self, fetch):
        # Whitelist con un dia distinto al actual -> el partido se descarta.
        fetch.return_value = [_partido()]
        dia_otro = (timezone.now().astimezone(ZoneInfo('America/Bogota'))
                    .weekday() + 1) % 7
        out = StringIO()
        with mock.patch.object(bk, 'LADOS_PAPER_ACTIVOS',
                               frozenset({'OVER'})):
            with mock.patch(
                    'auto_betting.management.commands.'
                    'run_paper_bets_basket.cargar_filtro_ligadia',
                    return_value={('spain/liga_acb', dia_otro)}):
                call_command('run_paper_bets_basket', stdout=out)
        self.assertEqual(PaperBet.objects.count(), 0)
        self.assertIn('[FILTRO LIGA-DIA] descartado', out.getvalue())

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_dry_run_no_escribe(self, fetch):
        fetch.return_value = [_partido()]
        out = StringIO()
        call_command('run_paper_bets_basket', '--dry-run', stdout=out)
        self.assertEqual(PaperBet.objects.count(), 0)
        self.assertIn('simuladas', out.getvalue())
        self.assertIn('DRY', out.getvalue())

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_registra_y_deduplica(self, fetch):
        fetch.return_value = [_partido()]
        out = StringIO()
        with mock.patch.object(bk, 'LADOS_PAPER_ACTIVOS',
                               frozenset({'OVER'})):
            call_command('run_paper_bets_basket', stdout=out)
            self.assertEqual(PaperBet.objects.count(), 1)
            b = PaperBet.objects.get()
            self.assertEqual(b.motor, bk.MOTOR)
            self.assertEqual(b.evento_id, '12345')
            self.assertEqual(b.seleccion, bk.SEL_OVER)
            self.assertEqual(b.mercado, bk.MERCADO)
            self.assertEqual(b.estado, 'OPEN')
            self.assertAlmostEqual(b.cuota, 1.80)
            self.assertAlmostEqual(b.linea, 91.0)
            self.assertIsNotNone(b.ev)
            # Segunda corrida: mismo partido → no duplica.
            call_command('run_paper_bets_basket', stdout=out)
            self.assertEqual(PaperBet.objects.count(), 1)

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_over_se_omite_por_defecto(self, fetch):
        fetch.return_value = [_partido()]
        out = StringIO()
        call_command('run_paper_bets_basket', stdout=out)
        self.assertEqual(PaperBet.objects.count(), 0)
        self.assertIn('depurado', out.getvalue())

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_sin_modelo_no_escribe(self, fetch):
        BasketModel.objects.all().delete()
        fetch.return_value = [_partido()]
        out = StringIO()
        call_command('run_paper_bets_basket', stdout=out)
        self.assertEqual(PaperBet.objects.count(), 0)
        self.assertIn('sin modelo propio', out.getvalue())

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_fallback_global_apuesta(self, fetch):
        # Sin modelo propio ni muestras: el modelo global de respaldo apuesta.
        BasketModel.objects.all().delete()
        BasketModel.objects.create(
            liga=bk.CLAVE_GLOBAL, origen='pooled', n=500,
            b0=0.0, b1=1.0, b2=1.0, rmse_test_dos=12.0, rmse_test_uno=15.0)
        fetch.return_value = [_partido()]
        out = StringIO()
        with mock.patch.object(bk, 'LADOS_PAPER_ACTIVOS',
                               frozenset({'OVER'})):
            call_command('run_paper_bets_basket', stdout=out)
            self.assertEqual(PaperBet.objects.count(), 1)
            self.assertEqual(PaperBet.objects.get().seleccion, bk.SEL_OVER)
            self.assertIn('__global__', out.getvalue())

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_cosecha_muestras_del_feed(self, fetch):
        fetch.return_value = [_partido(
            state='ENDED', marcador_local=95, marcador_visitante=45,
            q3=30, q4=25, info_cuartos='Q1: 25-18 | Q2: 23-24 | Q3: 15-15 | Q4: 10-15')]
        out = StringIO()
        call_command('run_paper_bets_basket', stdout=out)
        s = BasketSample.objects.get()
        self.assertEqual(s.fuente, 'kambi')
        self.assertEqual(s.liga, 'spain/liga_acb')
        self.assertEqual(s.evento_clave, 'kambi|12345')
        self.assertAlmostEqual(s.total, 140.0)
        self.assertIn('muestras cosechadas: 1', out.getvalue())

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_liquida_del_feed_por_evento(self, fetch):
        self._bet_open(evento_id='12345', seleccion=bk.SEL_OVER,
                       linea=91.0, cuota=1.80)
        fetch.return_value = [_partido(state='ENDED', marcador_local=95,
                                       marcador_visitante=45)]
        call_command('run_paper_bets_basket', stdout=StringIO())
        b = PaperBet.objects.get()
        self.assertEqual(b.estado, 'WON')
        self.assertAlmostEqual(b.payout, 18000.0)
        self.assertIn('kambi', b.resultado_real)

    # ------------------------------------------------------------------ #
    #  Fase 1: snapshots point-in-time + cierre (CLV)                    #
    # ------------------------------------------------------------------ #
    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_snapshot_del_universo_completo_en_ventana(self, fetch):
        # En ventana con modelo (12345), en ventana SIN modelo (888) y
        # fuera de ventana (777, ya en 3Q).
        sin_modelo = _partido(evento_id=888, liga_tk='superettan',
                              region_tk=None, liga_nombre='Superettan')
        en_3q = _partido(evento_id=777, q2=52, q3=12, period_id='QUARTER3')
        fetch.return_value = [_partido(), sin_modelo, en_3q]
        call_command('run_paper_bets_basket', stdout=StringIO())

        snaps = BasketMarketSnapshot.objects.order_by('evento_id')
        self.assertEqual(snaps.count(), 2)          # 777 queda fuera
        self.assertEqual(list(snaps.values_list('evento_id', flat=True)),
                         ['12345', '888'])
        s = snaps.get(evento_id='12345')
        self.assertEqual(s.clave_liga, 'spain/liga_acb')
        self.assertEqual((s.q1, s.q2), (45, 50))
        self.assertAlmostEqual(s.linea, 91.0)
        self.assertAlmostEqual(s.cuota_over, 1.80)
        self.assertAlmostEqual(s.cuota_under, 1.95)
        self.assertTrue(s.over_abierta and s.under_abierta)
        self.assertIsNotNone(s.start_time)
        self.assertEqual(s.period_id, 'QUARTER2')

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_placeholder_q3_captura_snapshot_y_apuesta(self, fetch):
        fetch.return_value = [_partido(
            q3=0, period_id='QUARTER3', corriendo=False, izq_min=10,
            izq_seg=0, info_cuartos='Q1: 25-18 | Q2: 23-24 | Q3: 0-0')]
        with mock.patch.object(bk, 'LADOS_PAPER_ACTIVOS',
                               frozenset({'OVER'})):
            call_command('run_paper_bets_basket', stdout=StringIO())
            self.assertEqual(BasketMarketSnapshot.objects.count(), 1)
            self.assertEqual(PaperBet.objects.count(), 1)
            self.assertEqual(BasketMarketSnapshot.objects.get().period_id,
                             'QUARTER3')

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_dry_run_no_captura(self, fetch):
        fetch.return_value = [_partido()]
        call_command('run_paper_bets_basket', '--dry-run', stdout=StringIO())
        self.assertEqual(BasketMarketSnapshot.objects.count(), 0)
        self.assertEqual(PaperBet.objects.count(), 0)

    def _bet_open(self, **kw):
        base = dict(
            evento_id='12345', start_time=timezone.now() - timedelta(minutes=30),
            home_team='A', away_team='B', liga='España / Liga ACB',
            mercado=bk.MERCADO, motor=bk.MOTOR, seleccion=bk.SEL_OVER,
            linea=91.0, cuota=1.80, prob=0.60, ev=0.08, stake=10000,
            estado='OPEN')
        base.update(kw)
        return PaperBet.objects.create(**base)

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_cierre_se_actualiza_y_congela(self, fetch):
        self._bet_open()
        # 1) En ventana con cuota nueva del mismo lado → actualiza cierre.
        fetch.return_value = [_partido(cuota_over=1.78)]
        call_command('run_paper_bets_basket', stdout=StringIO())
        b = PaperBet.objects.get()
        self.assertAlmostEqual(b.closing_odds, 1.78)
        self.assertAlmostEqual(b.closing_linea, 91.0)
        # 2) La línea se movió → cierre guarda la línea nueva (verdad del feed).
        fetch.return_value = [_partido(cuota_over=1.70, linea=93.0)]
        call_command('run_paper_bets_basket', stdout=StringIO())
        b.refresh_from_db()
        self.assertAlmostEqual(b.closing_odds, 1.70)
        self.assertAlmostEqual(b.closing_linea, 93.0)
        # 3) Lado suspendido → se conserva la última cuota abierta.
        fetch.return_value = [_partido(cuota_over=1.55, linea=93.0,
                                       cuota_over_abierta=False)]
        call_command('run_paper_bets_basket', stdout=StringIO())
        b.refresh_from_db()
        self.assertAlmostEqual(b.closing_odds, 1.70)
        # 4) El partido sale de ventana (3Q) → el cierre queda congelado.
        fetch.return_value = [_partido(q2=52, q3=12, period_id='QUARTER3',
                                       cuota_over=1.40)]
        call_command('run_paper_bets_basket', stdout=StringIO())
        b.refresh_from_db()
        self.assertAlmostEqual(b.closing_odds, 1.70)
        self.assertAlmostEqual(b.closing_linea, 93.0)

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_cierre_solo_para_el_lado_apostado(self, fetch):
        self._bet_open(seleccion=bk.SEL_UNDER, linea=91.0, cuota=1.95)
        fetch.return_value = [_partido(cuota_over=1.50, cuota_under=2.10)]
        call_command('run_paper_bets_basket', stdout=StringIO())
        b = PaperBet.objects.get()
        self.assertAlmostEqual(b.closing_odds, 2.10)     # el lado UNDER


class ComandoScoreBasketTests(TestCase):
    def _bet(self, **kw):
        base = dict(
            evento_id='999', start_time=timezone.now() - timedelta(hours=2),
            home_team='Real Madrid', away_team='Barcelona',
            liga='España / Liga ACB', mercado=bk.MERCADO, motor=bk.MOTOR,
            seleccion=bk.SEL_OVER, linea=170.0, cuota=1.90, prob=0.60,
            ev=0.14, stake=10000, estado='OPEN')
        base.update(kw)
        return PaperBet.objects.create(**base)

    @mock.patch.object(bk, 'resultado_oficial', return_value=175.0)
    def test_liquida_ganada(self, _res):
        self._bet()
        out = StringIO()
        call_command('score_paper_bets_basket', stdout=out)
        b = PaperBet.objects.get()
        self.assertEqual(b.estado, 'WON')
        self.assertAlmostEqual(b.payout, 19000.0)
        self.assertIn('175', b.resultado_real)
        self.assertIsNotNone(b.settled_at)

    @mock.patch.object(bk, 'resultado_oficial', return_value=165.0)
    def test_liquida_perdida(self, _res):
        self._bet()
        call_command('score_paper_bets_basket', stdout=StringIO())
        b = PaperBet.objects.get()
        self.assertEqual(b.estado, 'LOST')
        self.assertEqual(b.payout, 0.0)

    @mock.patch.object(bk, 'resultado_oficial', return_value=170.0)
    def test_push_es_void_con_stake(self, _res):
        self._bet()
        call_command('score_paper_bets_basket', stdout=StringIO())
        b = PaperBet.objects.get()
        self.assertEqual(b.estado, 'VOID')
        self.assertEqual(b.payout, 10000.0)
        self.assertIn('push', b.resultado_real)

    @mock.patch.object(bk, 'resultado_oficial', return_value=None)
    def test_sin_resultado_40h_es_void(self, _res):
        self._bet(start_time=timezone.now() - timedelta(hours=41))
        call_command('score_paper_bets_basket', stdout=StringIO())
        b = PaperBet.objects.get()
        self.assertEqual(b.estado, 'VOID')
        self.assertEqual(b.payout, 10000.0)
        self.assertIn('sin cobertura', b.resultado_real)

    @mock.patch.object(bk, 'resultado_oficial', return_value=None)
    def test_reciente_sigue_open(self, _res):
        self._bet(start_time=timezone.now() - timedelta(hours=1))
        call_command('score_paper_bets_basket', stdout=StringIO())
        self.assertEqual(PaperBet.objects.get().estado, 'OPEN')

    @mock.patch.object(bk, 'resultado_oficial', return_value=175.0)
    def test_dry_run_no_escribe(self, _res):
        self._bet()
        call_command('score_paper_bets_basket', '--dry-run', stdout=StringIO())
        self.assertEqual(PaperBet.objects.get().estado, 'OPEN')

    def test_score_paper_bets_futbol_no_toca_basket(self):
        self._bet()
        out = StringIO()
        call_command('score_paper_bets', stdout=out)
        self.assertEqual(PaperBet.objects.get().estado, 'OPEN')
        self.assertIn('Sin apuestas OPEN', out.getvalue())


class VistaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='basket_t', email='basket_t@test.com', password='x',
            is_superuser=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_pagina_dedicada_responde(self):
        r = self.client.get(reverse('auto_betting:paperbet_basket'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Paperbet Baloncesto', html)
        self.assertIn(bk.MOTOR, html)

    def test_pagina_muestra_apuesta(self):
        PaperBet.objects.create(
            evento_id='1', start_time=timezone.now(),
            home_team='A', away_team='B', liga='X / Y', mercado=bk.MERCADO,
            motor=bk.MOTOR, seleccion=bk.SEL_OVER, linea=160.5, cuota=1.9,
            prob=0.6, ev=0.14, stake=10000, estado='OPEN')
        r = self.client.get(reverse('auto_betting:paperbet_basket'))
        html = r.content.decode()
        self.assertIn('A vs B', html)
        self.assertIn('PENDIENTE', html)

    def test_paperbet_general_enlaza_baloncesto(self):
        r = self.client.get(reverse('auto_betting:paperbet'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('/auto-betting/paperbet/baloncesto/', r.content.decode())

    def test_pagina_filtra_ligas_perdedoras(self):
        ahora = timezone.now()
        base = dict(start_time=ahora, home_team='A', away_team='B',
                    mercado=bk.MERCADO, motor=bk.MOTOR,
                    seleccion=bk.SEL_UNDER, linea=160.5, cuota=1.9,
                    prob=0.55, ev=0.045, stake=10000)
        PaperBet.objects.create(liga='Ganadora / Liga', estado='WON',
                                payout=19000, **base)
        PaperBet.objects.create(liga='Perdedora / Liga', estado='LOST',
                                payout=0, **base)
        # Modo ganadoras (comportamiento previo) via ?filtro=ganadoras.
        r = self.client.get(reverse('auto_betting:paperbet_basket'),
                            {'filtro': 'ganadoras'})
        html = r.content.decode()
        self.assertIn('Ganadora / Liga', html)
        self.assertNotIn('Perdedora / Liga', html)
        self.assertIn('ROI (ganadoras)', html)
        r2 = self.client.get(reverse('auto_betting:paperbet_basket'),
                             {'todas': '1'})
        self.assertIn('Perdedora / Liga', r2.content.decode())

    def test_pagina_filtro_ligadia(self):
        ahora = timezone.now()
        dia = ahora.astimezone(ZoneInfo('America/Bogota')).weekday()
        base = dict(start_time=ahora, home_team='A', away_team='B',
                    mercado=bk.MERCADO, motor=bk.MOTOR,
                    seleccion=bk.SEL_UNDER, linea=160.5, cuota=1.9,
                    prob=0.55, ev=0.045, stake=10000)
        PaperBet.objects.create(liga='Celda OK', estado='WON',
                                payout=19000, **base)
        PaperBet.objects.create(liga='Fuera de celda', estado='LOST',
                                payout=0, **base)
        with mock.patch('auto_betting.management.commands.'
                        'run_paper_bets_basket.cargar_filtro_ligadia',
                        return_value={('Celda OK', dia)}):
            r = self.client.get(reverse('auto_betting:paperbet_basket'))
        html = r.content.decode()
        self.assertIn('Celda OK', html)
        self.assertIn('Filtro liga×día', html)


# --------------------------------------------------------------------------- #
#  Recolector Pinnacle (The Odds API) — solo datos                            #
# --------------------------------------------------------------------------- #
def _ev_api(id_, home, away, commence, punto=222.0, over=1.94, under=1.93):
    """Evento The Odds API con totals de Pinnacle."""
    return {
        'id': id_, 'sport_key': 'basketball_nba', 'sport_title': 'NBA',
        'home_team': home, 'away_team': away, 'commence_time': commence,
        'bookmakers': [{
            'key': 'pinnacle', 'title': 'Pinnacle',
            'last_update': '2026-10-13T09:00:00Z',
            'markets': [{'key': 'totals', 'outcomes': [
                {'name': 'Over', 'point': punto, 'price': over},
                {'name': 'Under', 'point': punto, 'price': under}]}],
        }],
    }


def _iso_en(minutos):
    return (timezone.now() + timedelta(minutes=minutos)).strftime('%Y-%m-%dT%H:%M:%SZ')


def _mocks_pinnacle(evs_by_key):
    """Patches de _fetch_events/_fetch_totals: devuelven por sport_key."""
    def events(sport_key):
        return evs_by_key.get(sport_key, [])

    def totals(sport_key):
        return evs_by_key.get(sport_key, []), 490, 1

    return (mock.patch.object(bp, '_fetch_events', side_effect=events),
            mock.patch.object(bp, '_fetch_totals', side_effect=totals))


class PinnacleRecolectorTests(TestCase):
    def test_match_nombres_entre_ecosistemas(self):
        p = _partido(local='Los Angeles Clippers', visitante='Boston Celtics',
                     inicio='2026-10-13T18:00:00Z')
        ev = {'commence_time': '2026-10-13T18:00:00Z',
              'home_team': 'LA Clippers', 'away_team': 'Boston Celtics'}
        self.assertIs(bp._match_kambi(ev, [p]), p)
        # Hora fuera de la ventana de ±4 h → no hay match.
        ev2 = dict(ev, commence_time='2026-10-14T06:00:00Z')
        self.assertIsNone(bp._match_kambi(ev2, [p]))

    def test_pregame_guarda_partidos_de_la_jornada(self):
        p = _partido(local='Brooklyn Nets', visitante='Charlotte Hornets',
                     inicio=_iso_en(80))
        ev = _ev_api('ev1', 'Brooklyn Nets', 'Charlotte Hornets', _iso_en(80))
        m1, m2 = _mocks_pinnacle({'basketball_nba': [ev]})
        with m1, m2 as totals:
            n = bp.recolectar_pregame([p], None)
        self.assertEqual(n, 1)
        s = PinnacleSnapshot.objects.get(tipo='pregame')
        self.assertEqual(s.kambi_event_id, str(p.evento_id))
        self.assertEqual(s.api_event_id, 'ev1')
        self.assertAlmostEqual(s.linea, 222.0)
        self.assertAlmostEqual(s.cuota_over, 1.94)
        self.assertTrue(PinnacleCallLog.objects.get(tipo='pregame').ok)
        # Segunda corrida inmediata: throttle → sin nueva llamada.
        m3, m4 = _mocks_pinnacle({'basketball_nba': [ev]})
        with m3, m4 as totals2:
            self.assertEqual(bp.recolectar_pregame([p], None), 0)
        self.assertEqual(totals2.call_count, 0)

    def test_pregame_no_llama_si_falta_mucho(self):
        p = _partido(inicio=_iso_en(600))
        ev = _ev_api('ev1', 'A', 'B', _iso_en(600))
        m1, m2 = _mocks_pinnacle({'basketball_nba': [ev]})
        with m1, m2 as totals:
            self.assertEqual(bp.recolectar_pregame([p], None), 0)
        self.assertEqual(totals.call_count, 0)

    def test_break_guarda_solo_ventana(self):
        p = _partido(local='Brooklyn Nets', visitante='Charlotte Hornets',
                     inicio=_iso_en(-40))
        match = _ev_api('ev1', 'Brooklyn Nets', 'Charlotte Hornets', _iso_en(-40),
                        punto=225.5, over=1.90, under=1.96)
        otro = _ev_api('ev2', 'Otro A', 'Otro B', _iso_en(-30))
        m1, m2 = _mocks_pinnacle({'basketball_nba': [match, otro]})
        with m1, m2:
            n = bp.recolectar_break([p], [p], None)
        self.assertEqual(n, 1)
        s = PinnacleSnapshot.objects.get(tipo='break')
        self.assertEqual(s.api_event_id, 'ev1')
        self.assertEqual(s.kambi_event_id, str(p.evento_id))
        self.assertAlmostEqual(s.linea, 225.5)
        self.assertEqual(PinnacleSnapshot.objects.filter(tipo='break').count(), 1)

    def test_break_backoff_tras_fallo(self):
        p = _partido(local='Brooklyn Nets', visitante='Charlotte Hornets')
        ev = _ev_api('ev1', 'Brooklyn Nets', 'Charlotte Hornets', p.inicio)
        with mock.patch.object(bp, '_fetch_events',
                               side_effect=lambda k: [ev] if k == 'basketball_nba' else []), \
                mock.patch.object(bp, '_fetch_totals',
                                  side_effect=RuntimeError('boom')) as totals:
            self.assertEqual(bp.recolectar_break([p], [p], None), 0)
            self.assertEqual(bp.recolectar_break([p], [p], None), 0)  # backoff
        self.assertEqual(totals.call_count, 1)
        self.assertFalse(PinnacleCallLog.objects.get(tipo='break').ok)

    def test_min_creditos_frena(self):
        p = _partido(inicio=_iso_en(80))
        ev = _ev_api('ev1', 'A', 'B', _iso_en(80))
        PinnacleCallLog.objects.create(
            capturado_en=timezone.now(), sport_key='basketball_nba',
            tipo='break', ok=True, eventos=1, creditos_restantes=5)
        m1, m2 = _mocks_pinnacle({'basketball_nba': [ev]})
        with m1, m2 as totals:
            self.assertEqual(bp.recolectar([p], [p], None), (0, 0))
        self.assertEqual(totals.call_count, 0)

    def test_deshabilitado_por_env(self):
        p = _partido(inicio=_iso_en(80))
        ev = _ev_api('ev1', 'A', 'B', _iso_en(80))
        m1, m2 = _mocks_pinnacle({'basketball_nba': [ev]})
        with mock.patch.dict('os.environ', {'BASKET_PINNACLE_DISABLED': '1'}), m1, m2 as totals:
            self.assertEqual(bp.recolectar([p], [p], None), (0, 0))
        self.assertEqual(totals.call_count, 0)

    def test_dry_run_no_llama(self):
        p = _partido(inicio=_iso_en(80))
        with mock.patch.object(bp, '_fetch_totals') as totals:
            self.assertEqual(bp.recolectar([p], [p], None, dry=True), (0, 0))
        self.assertEqual(totals.call_count, 0)

    def test_rellenar_pinnacle_en_apuesta(self):
        ahora = timezone.now()
        PinnacleSnapshot.objects.create(
            tipo='pregame', sport_key='basketball_nba', api_event_id='ev1',
            kambi_event_id='12345', capturado_en=ahora,
            linea=222.0, cuota_over=1.94, cuota_under=1.93)
        PinnacleSnapshot.objects.create(
            tipo='break', sport_key='basketball_nba', api_event_id='ev1',
            kambi_event_id='12345', capturado_en=ahora,
            linea=225.5, cuota_over=1.90, cuota_under=1.96)
        bet = PaperBet.objects.create(
            evento_id='12345', start_time=ahora, home_team='A', away_team='B',
            liga='NBA', mercado=bk.MERCADO, motor=bk.MOTOR,
            seleccion=bk.SEL_OVER, linea=225.5, cuota=1.90, stake=10000)
        bp.rellenar_pinnacle(bet)
        bet.refresh_from_db()
        self.assertAlmostEqual(bet.pin_pregame_linea, 222.0)
        self.assertAlmostEqual(bet.pin_break_linea, 225.5)
        self.assertIsNotNone(bet.pin_break_at)

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_comando_recolecta_y_rellena(self, fetch):
        BasketModel.objects.create(
            liga='spain/liga_acb', origen='test', n=100,
            b0=0.0, b1=1.0, b2=1.0, rmse_test_dos=12.0, rmse_test_uno=15.0)
        p = _partido(local='Brooklyn Nets', visitante='Charlotte Hornets',
                     inicio=_iso_en(-40))
        fetch.return_value = [p]
        ev = _ev_api('ev1', 'Brooklyn Nets', 'Charlotte Hornets', p.inicio,
                     punto=225.5, over=1.90, under=1.96)
        m1, m2 = _mocks_pinnacle({'basketball_nba': [ev]})
        out = StringIO()
        with m1, m2, mock.patch.object(
                bk, 'LADOS_PAPER_ACTIVOS', frozenset({'OVER'})):
            call_command('run_paper_bets_basket', stdout=out)
        self.assertIn('Pinnacle (solo datos): llamadas pregame=0 break=1',
                      out.getvalue())
        bet = PaperBet.objects.get()
        self.assertAlmostEqual(bet.pin_break_linea, 225.5)
        self.assertIsNotNone(bet.pin_break_at)


class PinnacleVistaTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='basket_pin', email='basket_pin@test.com', password='x',
            is_superuser=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_pagina_muestra_columnas_y_datos_pinnacle(self):
        ahora = timezone.now()
        bet = PaperBet.objects.create(
            evento_id='77', start_time=ahora, home_team='Nets', away_team='Hornets',
            liga='NBA', mercado=bk.MERCADO, motor=bk.MOTOR,
            seleccion=bk.SEL_OVER, linea=225.5, cuota=1.90, stake=10000)
        PinnacleSnapshot.objects.create(
            tipo='break', sport_key='basketball_nba', api_event_id='ev77',
            kambi_event_id='77', capturado_en=ahora,
            linea=225.5, cuota_over=1.90, cuota_under=1.96)
        bp.rellenar_pinnacle(bet)
        r = self.client.get(reverse('auto_betting:paperbet_basket'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('P. PRE', html)
        self.assertIn('P. 2Q→3Q', html)
        self.assertIn('225.5', html)

    def test_break_sin_datos_activa_backoff(self):
        """Si Pinnacle no tiene dato del ventana, la llamada queda 'no ok' y
        la siguiente pasada espera (no reintenta cada 2 min)."""
        p = _partido(local='Brooklyn Nets', visitante='Charlotte Hornets')
        ev = _ev_api('ev1', 'Brooklyn Nets', 'Charlotte Hornets', p.inicio)
        sin_datos = dict(ev, bookmakers=[{'key': 'pinnacle', 'markets': []}])
        with mock.patch.object(bp, '_fetch_events',
                               side_effect=lambda k: [ev] if k == 'basketball_nba' else []), \
                mock.patch.object(bp, '_fetch_totals',
                                  side_effect=lambda k: ([sin_datos], 480, 1)) as totals:
            self.assertEqual(bp.recolectar_break([p], [p], None), 1)
            self.assertEqual(bp.recolectar_break([p], [p], None), 0)  # backoff
        self.assertEqual(totals.call_count, 1)
        self.assertFalse(PinnacleCallLog.objects.get(tipo='break').ok)
        self.assertEqual(PinnacleSnapshot.objects.count(), 0)


class ParserEjecucionRealTests(TestCase):
    def test_parsear_evento_guarda_ids_y_metadatos(self):
        bloque = {
            'event': {
                'id': 555, 'name': 'A - B', 'homeName': 'A', 'awayName': 'B',
                'state': 'STARTED', 'start': '2026-10-27T18:00:00Z',
                'path': [{'termKey': 'basketball'},
                         {'termKey': 'argentina', 'name': 'Argentina'},
                         {'termKey': 'lnb', 'name': 'LNB'}],
                'group': 'Argentina / LNB',
            },
            'liveData': {
                'matchClock': {'periodId': 'QUARTER2', 'running': False,
                               'minute': 20, 'minutesLeftInPeriod': 0,
                               'secondsLeftInMinute': 0},
                'score': {'home': '48', 'away': '42',
                          'info': 'Q1: 25-18 | Q2: 23-24'},
            },
            'betOffers': [{
                'id': 2709349334,
                'betOfferType': {'id': 6, 'name': 'Más/Menos de'},
                'criterion': {'label': 'Total de puntos - Prórroga incluida'},
                'suspended': False,
                'tags': [{'name': 'live'}],
                'outcomes': [
                    {'id': 4392284370, 'type': 'OT_OVER', 'status': 'OPEN',
                     'line': 220500, 'odds': 1820, 'label': 'Más de 220.5',
                     'displayOrder': 1, 'cashOutStatus': 'AVAILABLE'},
                    {'id': 4392284371, 'type': 'OT_UNDER', 'status': 'OPEN',
                     'line': 220500, 'odds': 1880, 'label': 'Menos de 220.5',
                     'displayOrder': 2, 'cashOutStatus': ''},
                ]}],
        }
        p = bk.parsear_evento(bloque)
        self.assertEqual(p.betoffer_id, 2709349334)
        self.assertEqual(p.outcome_over_id, 4392284370)
        self.assertEqual(p.outcome_under_id, 4392284371)
        self.assertEqual(p.outcome_over_odds, 1820)
        self.assertEqual(p.outcome_under_odds, 1880)
        self.assertEqual(p.outcome_over_label, 'Más de 220.5')
        self.assertEqual(p.outcome_under_label, 'Menos de 220.5')
        self.assertEqual(p.outcome_over_status, 'OPEN')
        self.assertEqual(p.outcome_under_status, 'OPEN')
        self.assertEqual(p.outcome_over_display_order, 1)
        self.assertEqual(p.outcome_under_display_order, 2)
        self.assertEqual(p.outcome_over_cashout, 'AVAILABLE')
        self.assertEqual(p.criterion['label'],
                         'Total de puntos - Prórroga incluida')
        self.assertEqual(p.betoffer_tags, [{'name': 'live'}])
        self.assertEqual(p.event_path[1]['termKey'], 'argentina')


class CuponLiveTests(TestCase):
    @staticmethod
    def _outcome_dict(**kw):
        base = {
            'betoffer_id': 2709349334,
            'outcome_id': 4392284371,
            'label': 'Menos de 220.5',
            'odds': 1820,
            'odds_decimal': 1.82,
            'line': 220.5,
            'type': 'OT_UNDER',
            'status': 'OPEN',
            'cashout_status': '',
            'display_order': 2,
            'criterion': {'label': 'Total de puntos - Prórroga incluida'},
            'betoffer_tags': [{'name': 'live'}],
            'event_id': 555,
        }
        base.update(kw)
        return base

    def test_cupon_live_no_se_marca_pregame(self):
        body = ab._build_coupon(
            self._outcome_dict(is_live=True),
            {'event_id': 555, 'path': []}, 500000)
        sel = body['selectedOutcomes'][0]
        self.assertTrue(sel['isLiveBetoffer'])
        self.assertFalse(sel['isPrematchBetoffer'])

    def test_cupon_sin_flag_conserva_el_comportamiento_actual(self):
        body = ab._build_coupon(
            self._outcome_dict(), {'event_id': 555, 'path': []}, 500000)
        sel = body['selectedOutcomes'][0]
        self.assertTrue(sel['isLiveBetoffer'])
        self.assertTrue(sel['isPrematchBetoffer'])


class ComandoRunBasketRealTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='basket_real@test.local',
            email='basket_real@test.local',
            password='x')
        AutoBetConfig.objects.create(
            usuario=self.user, ticket='test-ticket', punter_id='1',
            stake=500000, max_apuestas_diarias=20, activo=True)
        BasketModel.objects.create(
            liga='argentina/lnb', origen='test', n=100,
            b0=0.0, b1=1.0, b2=1.0,
            rmse_test_dos=12.0, rmse_test_uno=15.0)

    @staticmethod
    def _partido_real(**kw):
        base = dict(
            evento_id=98765,
            liga_nombre='Argentina / LNB',
            liga_tk='lnb',
            region_tk='argentina',
            betoffer_id=2709349334,
            outcome_under_id=4392284371,
            outcome_under_odds=1950,
            linea=105.0,
            outcome_under_label='Menos de 105.0',
            outcome_under_status='OPEN',
            criterion={'label': 'Total de puntos - Prórroga incluida'},
            betoffer_tags=[],
            event_path=[{'termKey': 'basketball'},
                        {'termKey': 'argentina', 'name': 'Argentina'},
                        {'termKey': 'lnb', 'name': 'LNB'}],
        )
        base.update(kw)
        return _partido(**base)

    @mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                'bk.fetch_live_partidos')
    def test_dry_run_no_escribe_ni_toca_contador(self, fetch):
        fetch.return_value = [self._partido_real()]
        out = StringIO()
        call_command('run_basket_1q2q_bets', '--dry-run', stdout=out)
        self.assertEqual(AutoBet.objects.count(), 0)
        self.assertEqual(DailyCounter.objects.count(), 0)
        txt = out.getvalue()
        self.assertIn('DRY-RUN', txt)
        self.assertIn('outcome_id=4392284371', txt)
        self.assertIn('betoffer_id=2709349334', txt)

    @mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                'bk.fetch_live_partidos')
    def test_real_registra_y_deduplica_sin_dailycounter(self, fetch):
        fetch.return_value = [self._partido_real()]
        out = StringIO()
        with mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                        'ab.login', return_value=('token', 'routing')), \
             mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                        'ab.validate_coupon', return_value=(True, {})), \
             mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                        'ab.place_bet',
                        return_value=(True, {'coupon_ref': 111, 'bet_ref': 222,
                                             'potential_payout': 975000})), \
             mock.patch('notificaciones.services.notificar_apuestas',
                        return_value='omitido'):
            call_command('run_basket_1q2q_bets', '--real', '--yes', stdout=out)
            self.assertEqual(AutoBet.objects.count(), 1)
            bet = AutoBet.objects.get()
            self.assertEqual(bet.mercado, bk.MERCADO)
            self.assertEqual(bet.seleccion, bk.SEL_UNDER)
            self.assertEqual(bet.evento_id, 98765)
            self.assertEqual(bet.stake, 500000)
            self.assertEqual(bet.coupon_ref, 111)
            self.assertEqual(DailyCounter.objects.count(), 0)
            call_command('run_basket_1q2q_bets', '--real', '--yes', stdout=out)
            self.assertEqual(AutoBet.objects.count(), 1)

    @mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                'bk.fetch_live_partidos')
    def test_validate_only_no_coloca(self, fetch):
        fetch.return_value = [self._partido_real()]
        out = StringIO()
        with mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                        'ab.login', return_value=('token', 'routing')), \
             mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                        'ab.validate_coupon', return_value=(True, {})), \
             mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                        'ab.place_bet') as place:
            call_command('run_basket_1q2q_bets', '--real', '--yes',
                         '--validate-only', stdout=out)
        self.assertEqual(AutoBet.objects.count(), 0)
        self.assertEqual(DailyCounter.objects.count(), 0)
        place.assert_not_called()
        self.assertIn('Validación OK', out.getvalue())
        self.assertIn('no se colocó dinero', out.getvalue())

    def test_validate_only_exige_real_y_yes(self):
        err = StringIO()
        call_command('run_basket_1q2q_bets', '--validate-only', stderr=err)
        self.assertIn('requiere --real --yes', err.getvalue())

    @mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                'bk.fetch_live_partidos')
    def test_max_bets_limita_a_una(self, fetch):
        fetch.return_value = [
            self._partido_real(evento_id=98765),
            self._partido_real(evento_id=98766),
        ]
        out = StringIO()
        with mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                        'ab.login', return_value=('token', 'routing')), \
             mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                        'ab.validate_coupon', return_value=(True, {})), \
             mock.patch('auto_betting.management.commands.run_basket_1q2q_bets.'
                        'ab.place_bet',
                        return_value=(True, {'coupon_ref': 111, 'bet_ref': 222,
                                             'potential_payout': 975000})), \
             mock.patch('notificaciones.services.notificar_apuestas',
                        return_value='omitido'):
            call_command('run_basket_1q2q_bets', '--real', '--yes',
                         '--max-bets', '1', stdout=out)
        self.assertEqual(AutoBet.objects.count(), 1)
        self.assertEqual(DailyCounter.objects.count(), 0)
        self.assertIn('Tope de corrida alcanzado', out.getvalue())

    def test_consulta_de_futbol_excluye_el_mercado_basket(self):
        now = timezone.now()
        base = dict(
            usuario=self.user, evento_id=1, home_team='A', away_team='B',
            liga='X', start_time=now, seleccion=bk.SEL_UNDER, linea=91.0,
            cuota=1.95, corners_predichos=50, predicta_prob=50,
            edge=0, ev=0, stake=500000, estado='OPEN')
        AutoBet.objects.create(mercado=bk.MERCADO, **base)
        AutoBet.objects.create(mercado='Total de goles', **base)
        hoy = timezone.localdate()
        n = (AutoBet.objects.filter(usuario=self.user, creado__date=hoy)
             .exclude(mercado=bk.MERCADO).count())
        self.assertEqual(n, 1)

    def test_scheduler_tiene_la_tarea_real(self):
        from auto_betting.management.commands.run_scheduler import (
            ANTI_CONCURRENCY, COMANDOS, LOGS)
        self.assertIn('run_basket_1q2q_bets', COMANDOS)
        self.assertIn('run_basket_1q2q_bets', LOGS)
        self.assertIn('run_basket_1q2q_bets', ANTI_CONCURRENCY)


class PaperGatedTests(TestCase):
    @staticmethod
    def _raw(**kw):
        base = dict(
            evento_id='90001',
            home_team='A',
            away_team='B',
            liga='Test / League',
            mercado=bk.MERCADO,
            motor=bk.MOTOR,
            seleccion=bk.SEL_UNDER,
            linea=100.0,
            cuota=1.90,
            prob=0.55,
            ev=0.05,
            diferencia=-4.0,
            stake=10000,
            start_time=timezone.now(),
            estado='OPEN',
        )
        base.update(kw)
        return PaperBet.objects.create(**base)

    def test_clona_solo_los_que_pasan_y_deduplica(self):
        self._raw(evento_id='1', diferencia=-4.0, ev=0.05)
        self._raw(evento_id='2', diferencia=-1.1, ev=0.05)
        self._raw(evento_id='3', diferencia=-4.0, ev=-0.01)
        self._raw(evento_id='4', diferencia=-6.0, ev=0.05)
        self._raw(evento_id='6', diferencia=-4.0, ev=0.05, estado='LOST')

        out = StringIO()
        call_command('run_paper_bets_basket_gated', stdout=out)
        gated = PaperBet.objects.filter(motor=bk.MOTOR_GATED)
        self.assertEqual(gated.count(), 1)
        b = gated.get()
        self.assertEqual(b.evento_id, '1')
        self.assertEqual(b.estado, 'OPEN')
        self.assertEqual(b.stake, 10000)
        self.assertIn('1 nuevas', out.getvalue())

        call_command('run_paper_bets_basket_gated', stdout=StringIO())
        self.assertEqual(
            PaperBet.objects.filter(motor=bk.MOTOR_GATED).count(), 1)

    @mock.patch('auto_betting.management.commands.score_paper_bets_basket.'
                'bk.resultado_oficial', return_value=110.0)
    def test_score_liquida_gated(self, _res):
        b = self._raw(
            evento_id='77', motor=bk.MOTOR_GATED,
            start_time=timezone.now() - timedelta(hours=3))
        call_command('score_paper_bets_basket', '--days-back', '10',
                     stdout=StringIO())
        b.refresh_from_db()
        self.assertEqual(b.estado, 'LOST')
        self.assertEqual(b.payout, 0)

    @mock.patch('auto_betting.management.commands.run_paper_bets_basket.'
                'bk.fetch_live_partidos')
    def test_liquida_gated_del_feed(self, fetch):
        b = self._raw(
            evento_id='12345', motor=bk.MOTOR_GATED,
            start_time=timezone.now() - timedelta(hours=1),
            linea=91.0, cuota=1.80)
        fetch.return_value = [
            _partido(state='ENDED', marcador_local=95,
                     marcador_visitante=45),
        ]
        call_command('run_paper_bets_basket', stdout=StringIO())
        b.refresh_from_db()
        self.assertEqual(b.estado, 'LOST')

    def test_pagina_gated_filtra_motor(self):
        User = get_user_model()
        user = User.objects.create_user(
            username='gated_view@test.local',
            email='gated_view@test.local', password='x',
            is_superuser=True)
        self.client.force_login(user)
        self._raw(evento_id='1')
        self._raw(evento_id='2', motor=bk.MOTOR_GATED)
        r = self.client.get(
            reverse('auto_betting:paperbet_basket') + '?gated=1&todas=1')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, bk.MOTOR_GATED)
        self.assertContains(r, 'compuerta')

    def test_scheduler_tiene_tarea_gated(self):
        from auto_betting.management.commands.run_scheduler import (
            ANTI_CONCURRENCY, COMANDOS, LOGS)
        self.assertIn('run_paper_bets_basket_gated', COMANDOS)
        self.assertIn('run_paper_bets_basket_gated', LOGS)
        self.assertIn('run_paper_bets_basket_gated', ANTI_CONCURRENCY)


class PlaceBetLiveDelayTests(TestCase):
    """Regresión incidente 2026-11-04/05: LIVE_DELAY_PENDING con couponRef
    ES una apuesta colocada (y debe registrarse una sola vez), no un fallo
    que provoque reintentos y apuestas repetidas reales."""

    def _out(self):
        return {
            'betoffer_id': 1, 'outcome_id': 2,
            'label': 'Menos de 249.5', 'odds': 1800,
            'odds_decimal': 1.80, 'line': 249.5, 'type': 'OT_UNDER',
            'status': 'OPEN', 'cashout_status': '', 'display_order': 1,
            'criterion': {}, 'betoffer_tags': [], 'event_id': 9,
            'is_live': True,
        }

    @mock.patch('auto_betting.services._req')
    def test_live_delay_con_couponref_es_exito(self, req):
        req.return_value = (200, {
            'status': 'LIVE_DELAY_PENDING', 'delayBeforeAcceptingBet': 1,
            'couponRef': 13321026129,
            'coupon': {'couponRef': 13321026129,
                       'bets': [{'betRef': 123, 'potentialPayout': 47000}]},
        })
        ok, resp = ab.place_bet('t', self._out(),
                                {'event_id': 9, 'path': []}, 25000000)
        self.assertTrue(ok)
        self.assertEqual(resp['coupon_ref'], 13321026129)
        self.assertEqual(resp['bet_ref'], 123)
        self.assertTrue(resp['delay_pending'])

    @mock.patch('auto_betting.services._req')
    def test_live_delay_sin_couponref_sigue_siendo_fallo(self, req):
        req.return_value = (200, {
            'status': 'LIVE_DELAY_PENDING', 'delayBeforeAcceptingBet': 1})
        ok, resp = ab.place_bet('t', self._out(),
                                {'event_id': 9, 'path': []}, 25000000)
        self.assertFalse(ok)

    @mock.patch('auto_betting.services._req')
    def test_success_normal_queda_igual(self, req):
        req.return_value = (200, {
            'status': 'SUCCESS',
            'coupon': {'couponRef': 42,
                       'bets': [{'betRef': 7, 'potentialPayout': 50000}]},
        })
        ok, resp = ab.place_bet('t', self._out(),
                                {'event_id': 9, 'path': []}, 25000000)
        self.assertTrue(ok)
        self.assertEqual(resp['coupon_ref'], 42)
        self.assertFalse(resp['delay_pending'])
