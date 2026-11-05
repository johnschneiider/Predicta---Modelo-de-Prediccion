# -*- coding: utf-8 -*-
"""Tests de la migración x12_v2 (paperbet -> dinero real), 2026-10-03.

Cubren:
  1. `x12_engine.predict_x12_probs_for` reproduce EXACTAMENTE la probabilidad
     que quedó guardada en el paperbet (mismos features/modelo/margen).
  2. La compuerta del pipeline real (`strategy.select_bets` rama x12 con
     `precalibrated=True` y MarketFilterConfig['x12']) decide igual que la
     compuerta del paper (`run_paper_bets._paper_x12`): P>=0.45, edge>=5pp
     vs fair devig, cuota>=1.80 y SIN shrinkage de calibración.
  3. La cuota mínima 1.80 de x12 es parte de la estrategia y no la recorta el
     piso per-user (caso admin: cuota_minima=2.0) — condición exacta del ROI.
  4. Integración: `run_auto_bets --email admin` incluye Resultado Final (x12)
     y solo apuesta para el admin (los demás usuarios no se tocan).
  5. `--dry-run` no escribe nada.
"""

import datetime
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from auto_betting.management.commands.run_paper_bets import CAL_MARGIN
from auto_betting.models import AutoBet, AutoBetConfig, MarketFilterConfig
from auto_betting.strategy import select_bets
from auto_betting.x12_engine import predict_x12_probs_for

# Compuerta exacta del paper (run_paper_bets._paper_x12).
PAPER_MIN_P = 0.45
PAPER_MIN_EDGE = 0.05      # = MIN_EDGE_VS_MARKET de strategy.py
PAPER_MIN_CUOTA = 1.80

X12_FILTERS = {
    'x12': {'min_p': PAPER_MIN_P, 'min_confidence': 0.35, 'enabled': True,
            'min_ev': 0.0, 'min_cuota': PAPER_MIN_CUOTA},
}


def paper_gate(raw_home, raw_draw, raw_away, o1, ox, o2):
    """Decide '1'/'X'/'2' con las condiciones exactas del paperbet."""
    inv = [1.0 / o1, 1.0 / ox, 1.0 / o2]
    total = sum(inv)
    fair = [i / total for i in inv]
    out = {}
    for sel, raw, fair_p, cuota in (('1', raw_home, fair[0], o1),
                                    ('X', raw_draw, fair[1], ox),
                                    ('2', raw_away, fair[2], o2)):
        p_cal = max(0.03, raw - CAL_MARGIN)
        out[sel] = bool(p_cal >= PAPER_MIN_P
                        and (p_cal - fair_p) >= PAPER_MIN_EDGE
                        and cuota >= PAPER_MIN_CUOTA)
    return out


def offers(o1, ox, o2):
    return [
        {'type': 'OT_ONE', 'odds_decimal': o1},
        {'type': 'OT_CROSS', 'odds_decimal': ox},
        {'type': 'OT_TWO', 'odds_decimal': o2},
    ]


def run_real_x12(raw_home, raw_draw, raw_away, o1, ox, o2, cuota_minima=2.0, filters=None):
    """Corre la rama x12 del pipeline real (precalibrada, como x12_engine)."""
    probs = {'home': max(0.03, raw_home - CAL_MARGIN),
             'draw': max(0.03, raw_draw - CAL_MARGIN),
             'away': max(0.03, raw_away - CAL_MARGIN)}
    md = {'market': 'x12', 'type': 'x12', 'probs': probs,
          'confidence': 1.0, 'precalibrated': True, 'odds': offers(o1, ox, o2)}
    cands = select_bets([md], cuota_minima=cuota_minima, min_p=0.45,
                        min_confidence=0.35,
                        market_filters=filters or X12_FILTERS)
    return {c['side'] for c in cands}


class X12EngineReproductionTests(TestCase):
    """El motor real reproduce la P guardada en el paperbet (mismo estado)."""

    # (lid, home, away, start, sel, prob_guardada, margen_era)
    # margen_era: 0.02 para filas >= 1-oct (post-recalibración).
    CASOS = [
        (90, 'Fremad Amager', 'B 93', datetime.datetime(2026, 10, 2, 17, 0, tzinfo=datetime.timezone.utc), '1', 0.5133, 0.02),
        (105, 'Finn Harps', 'Kerry', datetime.datetime(2026, 10, 2, 18, 45, tzinfo=datetime.timezone.utc), '2', 0.5296, 0.02),
    ]

    def test_reproduce_paper_probs(self):
        for lid, home, away, start, sel, guardada, margin in self.CASOS:
            with self.subTest(match=f'{home} vs {away}'):
                probs = predict_x12_probs_for(lid, home, away, start)
                self.assertIsNotNone(probs)
                key = {'1': 'home', 'X': 'draw', '2': 'away'}[sel]
                # x12_engine ya aplica el margen de 2pp; deshacerlo da la P cruda.
                raw = probs[key] + CAL_MARGIN
                self.assertAlmostEqual(raw, guardada + margin, places=4)

    def test_equipos_sin_estado_devuelven_none(self):
        start = datetime.datetime(2026, 10, 2, 17, 0, tzinfo=datetime.timezone.utc)
        self.assertIsNone(predict_x12_probs_for(90, 'Equipo Inexistente FC', 'Otro FC', start))


class X12GateEquivalenceTests(TestCase):
    """select_bets(x12 precalibrado) == compuerta del paper, caso a caso."""

    CASOS = [
        # raw_home, raw_draw, raw_away, o1, ox, o2
        (0.55, 0.25, 0.20, 2.10, 3.40, 3.40),   # '1' con valor claro -> pasa
        (0.50, 0.25, 0.25, 2.20, 3.30, 3.30),   # '1' con edge justo
        (0.47, 0.25, 0.28, 2.20, 3.30, 3.30),   # '1' sin edge
        (0.53, 0.30, 0.17, 1.79, 4.00, 4.00),   # '1' con cuota < 1.80 -> no
        (0.53, 0.30, 0.17, 1.85, 3.60, 3.60),   # '1' con cuota 1.85 -> sí
        (0.30, 0.55, 0.15, 3.40, 2.10, 4.00),   # 'X' con valor claro
        (0.25, 0.50, 0.25, 3.00, 2.40, 3.00),   # 'X' sin edge
        (0.20, 0.25, 0.55, 4.00, 3.40, 2.05),   # '2' con valor claro
        (0.24, 0.26, 0.50, 4.00, 3.40, 2.30),   # '2' con edge justo
        (0.27, 0.25, 0.48, 4.00, 3.40, 2.20),   # '2' sin edge
        (0.44, 0.28, 0.28, 1.90, 3.20, 3.20),   # p_cal 0.42 < 0.45 -> no
    ]

    def test_equivalencia_exacta(self):
        for raw_h, raw_x, raw_a, o1, ox, o2 in self.CASOS:
            with self.subTest(o=(o1, ox, o2)):
                real = run_real_x12(raw_h, raw_x, raw_a, o1, ox, o2)
                paper = paper_gate(raw_h, raw_x, raw_a, o1, ox, o2)
                esperado = {s for s, ok in paper.items() if ok}
                self.assertEqual(real, esperado)

    def test_cuota_minima_180_no_la_recorta_el_piso_del_usuario(self):
        # Caso admin: cuota_minima=2.0; una pick a 1.90 con valor debe pasar
        # igual (la compuerta exacta del paper exige 1.80, no 2.0).
        real = run_real_x12(0.55, 0.25, 0.20, 1.90, 3.20, 3.20, cuota_minima=2.0)
        self.assertIn('1', real)
        # ...pero por debajo de 1.80 el paper también la rechaza.
        real2 = run_real_x12(0.55, 0.25, 0.20, 1.79, 3.40, 3.40, cuota_minima=2.0)
        self.assertNotIn('1', real2)

    def test_precalibrado_no_sufre_shrinkage(self):
        # Con precalibrated=True la P no se encoge; sin el flag, sí.
        raw = (0.62, 0.20, 0.18)
        probs = {'home': raw[0] - CAL_MARGIN, 'draw': raw[1] - CAL_MARGIN, 'away': raw[2] - CAL_MARGIN}
        md = {'market': 'x12', 'type': 'x12', 'probs': probs, 'confidence': 1.0,
              'precalibrated': True, 'odds': offers(2.10, 3.40, 3.40)}
        cands = select_bets([md], cuota_minima=2.0, market_filters=X12_FILTERS)
        self.assertTrue(any(c['side'] == '1' for c in cands))
        p_real = next(c['p'] for c in cands if c['side'] == '1')
        self.assertAlmostEqual(p_real, raw[0] - CAL_MARGIN, places=6)
        # Sin el flag entra la calibración (shrinkage) y la P baja.
        import copy
        md2 = copy.deepcopy(md)
        md2['precalibrated'] = False
        cands2 = select_bets([md2], cuota_minima=2.0, market_filters=X12_FILTERS)
        if cands2:
            self.assertNotAlmostEqual(cands2[0]['p'], p_real, places=3)


class X12PanelTests(TestCase):
    """El mercado x12_v2 queda configurable en el panel de umbrales."""

    def test_campos_x12_en_formulario_y_filtros(self):
        from auto_betting.forms import MarketFilterConfigForm
        form = MarketFilterConfigForm()
        for name in ('x12_enabled', 'x12_min_p', 'x12_min_confidence',
                     'x12_min_ev', 'x12_min_cuota'):
            self.assertIn(name, form.fields)
        cfg = MarketFilterConfig.get_solo()
        filtros = cfg.as_market_filters()
        self.assertIn('x12', filtros)
        # Valores por defecto = compuerta exacta del paper.
        self.assertEqual(filtros['x12']['min_p'], 0.45)
        self.assertEqual(filtros['x12']['min_cuota'], 1.80)
        self.assertTrue(filtros['x12']['enabled'])


class RunAutoBetsX12IntegrationTests(TestCase):
    """run_auto_bets incluye x12 y solo opera sobre el usuario pedido."""

    def setUp(self):
        User = get_user_model()
        self.admin = User.objects.create_user(
            username='admin_t', email='admin_t@test.com', password='x', is_superuser=True)
        self.otro = User.objects.create_user(
            username='otro_t', email='otro_t@test.com', password='x')
        for u in (self.admin, self.otro):
            AutoBetConfig.objects.create(
                usuario=u, ticket='ticket-test', punter_id='1',
                cuota_minima=2.0, stake=500000, max_apuestas_diarias=20,
                horas_adelante=24, activo=True)
        MarketFilterConfig.get_solo()

    def _match(self):
        return {
            'event_id': 999001,
            'home': 'Fremad Amager', 'away': 'B 93',
            'league': '2. Division (Dinamarca)',
            'league_path': 'Dinamarca/2. Division',
            'start_time': datetime.datetime(2026, 10, 2, 17, 0, tzinfo=datetime.timezone.utc),
        }

    @mock.patch('auto_betting.management.commands.run_auto_bets.place_bet')
    @mock.patch('auto_betting.management.commands.run_auto_bets.validate_coupon')
    @mock.patch('auto_betting.management.commands.run_auto_bets.fetch_market_odds')
    @mock.patch('auto_betting.management.commands.run_auto_bets.fetch_total_shots_odds')
    @mock.patch('auto_betting.management.commands.run_auto_bets.get_official_predictions')
    @mock.patch('auto_betting.strategy.validate_market_data')
    @mock.patch('auto_betting.management.commands.run_auto_bets.map_teams')
    @mock.patch('auto_betting.management.commands.run_auto_bets.find_predicta_league')
    @mock.patch('auto_betting.management.commands.run_auto_bets.fetch_upcoming_matches')
    @mock.patch('auto_betting.management.commands.run_auto_bets.login')
    def test_admin_recibe_x12_y_el_resto_no(self, m_login, m_matches, m_league, m_teams,
                                            m_coverage, m_official, m_shots, m_odds,
                                            m_validate, m_place):
        m_login.return_value = ('token', 'rk')
        m_matches.return_value = [self._match()]
        league = mock.Mock(id=90)
        league.name = '2. Division (Dinamarca)'
        m_league.return_value = league
        m_teams.return_value = ('Fremad Amager', 'B 93')
        m_coverage.return_value = {'goals_total': True}
        m_official.return_value = {}
        m_shots.return_value = []
        # Cuotas 1X2: 1.90/3.20/3.20 -> la P real del motor ('1' ~0.51)
        # supera la compuerta exacta a cuota 1.90 (por debajo del piso 2.0 del admin).
        m_odds.side_effect = lambda event_id, label: offers(1.90, 3.20, 3.20)
        m_validate.return_value = (True, {})
        m_place.return_value = (True, {'coupon_ref': 1, 'bet_ref': 2, 'potential_payout': 950})

        call_command('run_auto_bets', email='admin_t@test.com', verbosity=0)

        admin_bets = AutoBet.objects.filter(usuario=self.admin)
        self.assertTrue(admin_bets.exists(), 'el admin debe recibir al menos una apuesta x12')
        bet = admin_bets.first()
        self.assertEqual(bet.mercado, 'Resultado Final')
        self.assertIn(bet.seleccion, ('1', 'X', '2'))
        # La P jugada es la del motor (precalibrada), no una P encogida.
        probs = predict_x12_probs_for(90, 'Fremad Amager', 'B 93',
                                      self._match()['start_time'])
        esperada = round(probs[{'1': 'home', 'X': 'draw', '2': 'away'}[bet.seleccion]] * 100, 2)
        self.assertAlmostEqual(bet.predicta_prob, esperada, places=2)
        # El otro usuario NO se toca (--email admin).
        self.assertFalse(AutoBet.objects.filter(usuario=self.otro).exists())

    @mock.patch('auto_betting.management.commands.run_auto_bets.place_bet')
    @mock.patch('auto_betting.management.commands.run_auto_bets.fetch_market_odds')
    @mock.patch('auto_betting.management.commands.run_auto_bets.fetch_total_shots_odds')
    @mock.patch('auto_betting.management.commands.run_auto_bets.get_official_predictions')
    @mock.patch('auto_betting.strategy.validate_market_data')
    @mock.patch('auto_betting.management.commands.run_auto_bets.map_teams')
    @mock.patch('auto_betting.management.commands.run_auto_bets.find_predicta_league')
    @mock.patch('auto_betting.management.commands.run_auto_bets.fetch_upcoming_matches')
    def test_dry_run_no_escribe_ni_apuesta(self, m_matches, m_league, m_teams,
                                          m_coverage, m_official, m_shots, m_odds, m_place):
        m_matches.return_value = [self._match()]
        lg = mock.Mock(id=90)
        lg.name = '2. Division (Dinamarca)'
        m_league.return_value = lg
        m_teams.return_value = ('Fremad Amager', 'B 93')
        m_coverage.return_value = {'goals_total': True}
        m_official.return_value = {}
        m_shots.return_value = []
        m_odds.side_effect = lambda event_id, label: offers(1.90, 3.20, 3.20)

        call_command('run_auto_bets', email='admin_t@test.com', dry_run=True, verbosity=0)
        self.assertFalse(AutoBet.objects.exists())
        m_place.assert_not_called()


# ── Historial: serie de balance de la CUENTA (2026-10-19) ─────────────────

from auto_betting.models import HistorialApuesta  # noqa: E402
from capital.models import CapitalConfig          # noqa: E402
from cuentas.models import PermisoMenu            # noqa: E402


class HistorialBalanceCuentaTests(TestCase):
    """La vista `historial` expone `balance_cuenta` acotado a los filtros
    activos (tipo, deporte y fechas) para `#chartBalanceCuenta`."""

    def setUp(self):
        User = get_user_model()
        self.usuario = User.objects.create_user(
            username='hist_bal', email='hist_bal@test.com', password='x')
        # El middleware de menú bloquea la URL sin el permiso explícito.
        PermisoMenu.objects.create(
            usuario=self.usuario, codigo='ap_betplay', permitido=True)
        CapitalConfig.objects.create(
            usuario=self.usuario, balance_inicial=100000,
            ancla=timezone.now() - datetime.timedelta(days=10))
        self._seq = 0
        # Dos deportes y ambos tipos para que los filtros tengan efecto.
        self._historial('WON', stake=500000, payout=950000,
                        sport='FOOTBALL', is_system=True)   # +450 COP
        self._historial('OPEN', stake=8000, payout=0,
                        sport='FOOTBALL', is_system=False)  # −8 COP
        self._historial('LOST', stake=200000, payout=0,
                        sport='BASKETBALL', is_system=False,
                        placed_hours_ago=36, event_hours_ago=30)  # −200

    def _historial(self, status, stake, payout, sport='FOOTBALL',
                   is_system=True, placed_hours_ago=24, event_hours_ago=20):
        """stake/payout van en unidades Kambi (= COP × 1000)."""
        self._seq += 1
        return HistorialApuesta.objects.create(
            usuario=self.usuario, coupon_ref=777000000 + self._seq,
            placed_date=timezone.now() - datetime.timedelta(hours=placed_hours_ago),
            event_start_date=timezone.now() - datetime.timedelta(hours=event_hours_ago),
            bet_status=status, stake=stake, payout=payout, sport=sport,
            is_system=is_system)

    def test_historial_expone_balance_cuenta(self):
        self.client.force_login(self.usuario)

        # Sin filtros: la serie real completa de la cuenta.
        resp = self.client.get('/auto-betting/historial/')
        self.assertEqual(resp.status_code, 200)
        cuenta = resp.context['balance_cuenta']
        self.assertIsNotNone(cuenta)
        self.assertEqual(cuenta['modo'], 'real')
        self.assertFalse(cuenta['filtrado'])
        self.assertFalse(cuenta['parcial'])
        self.assertGreater(len(cuenta['points']), 1)
        self.assertTrue(all('bal' in p for p in cuenta['points']))
        self.assertEqual(cuenta['final'], 100242)  # +450 −8 −200
        self.assertContains(resp, 'chartBalanceCuenta')
        self.assertContains(resp, 'balanceCuentaData')

        # Con fechas: la serie se recorta (ya no es idéntica a la global),
        # pero sigue siendo el saldo real, no el aporte de apuestas.
        hoy = timezone.localdate()
        desde = hoy - datetime.timedelta(days=2)
        resp_rango = self.client.get('/auto-betting/historial/', {
            'desde': desde.isoformat(),
            'hasta': hoy.isoformat(),
        })
        self.assertEqual(resp_rango.status_code, 200)
        rango = resp_rango.context['balance_cuenta']
        self.assertIsNotNone(rango)
        self.assertEqual(rango['modo'], 'real')
        self.assertTrue(rango['filtrado'])
        self.assertFalse(rango['parcial'])
        self.assertNotEqual(rango['points'], cuenta['points'])
        self.assertEqual(
            rango['points'][0]['t'],
            timezone.make_aware(datetime.datetime.combine(
                desde, datetime.time.min)).isoformat())
        self.assertTrue(resp_rango.context['balance_timeline']['filtrado'])
        self.assertContains(resp_rango, 'chartBalanceCuenta')
        self.assertContains(resp_rango, 'balanceCuentaData')

        # Con deporte: la curva pasa a ser el aporte de esas apuestas y su
        # final ya no coincide con el de la cuenta completa.
        resp_sport = self.client.get('/auto-betting/historial/', {
            'sport': 'FOOTBALL',
        })
        self.assertEqual(resp_sport.status_code, 200)
        sport = resp_sport.context['balance_cuenta']
        self.assertIsNotNone(sport)
        self.assertEqual(sport['modo'], 'filtrado')
        self.assertTrue(sport['filtrado'])
        self.assertTrue(sport['parcial'])
        self.assertEqual(sport['final'], 100442)  # +450 −8 (solo FOOTBALL)
        self.assertNotEqual(sport['final'], cuenta['final'])
        self.assertNotEqual(sport['points'], cuenta['points'])
        self.assertContains(resp_sport, 'chartBalanceCuenta')
        self.assertContains(resp_sport, 'balanceCuentaData')
