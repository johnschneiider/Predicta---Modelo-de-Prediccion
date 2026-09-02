"""
Tests del gestor de capital: balance paralelo, resolución de stake por modo
y protección del escenario "sin saldo".
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from auto_betting.models import AutoBetConfig, HistorialApuesta
from cuentas.models import Usuario

from .models import CapitalAjuste, CapitalConfig
from .services import bankroll_cop, get_config, resolve_stake


class CapitalServicesTests(TestCase):

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email='cap@test.com', username='cap', password='x',
        )
        self.config = AutoBetConfig.objects.create(
            usuario=self.usuario, ticket='t', punter_id='p', stake=500000,
        )

    _seq = 0

    def _historial(self, status, stake=500000, payout=0, days_ago=1):
        self._seq += 1
        return HistorialApuesta.objects.create(
            usuario=self.usuario,
            coupon_ref=900000000 + self._seq,  # coupon_ref es numérico
            placed_date=timezone.now() - timedelta(days=days_ago),
            bet_status=status, stake=stake, payout=payout,
        )

    def _activar_compuesto(self, balance=250000, pct=2.0, min_s=500, max_s=5000):
        cfg = get_config(self.usuario)
        cfg.modo = CapitalConfig.MODO_COMPUESTO
        cfg.balance_inicial = balance
        cfg.ancla = timezone.now() - timedelta(days=10)
        cfg.porcentaje = pct
        cfg.stake_min_cop = min_s
        cfg.stake_max_cop = max_s
        cfg.save()
        return cfg

    # ── modo FIJO ────────────────────────────────────────────────────────

    def test_modo_fijo_devuelve_stake_de_config(self):
        stake, motivo = resolve_stake(self.config)
        self.assertEqual((stake, motivo), (500000, 'fijo'))

    # ── modo COMPUESTO ───────────────────────────────────────────────────

    def test_compuesto_sin_balance_no_apuesta(self):
        cfg = get_config(self.usuario)
        cfg.modo = CapitalConfig.MODO_COMPUESTO
        cfg.save()
        stake, motivo = resolve_stake(self.config)
        self.assertIsNone(stake)
        self.assertEqual(motivo, 'sin_balance')

    def test_compuesto_stake_porcentaje(self):
        # Balance 250000, 2% → 5000 COP → 5.000.000 unidades Kambi.
        self._activar_compuesto()
        stake, motivo = resolve_stake(self.config)
        self.assertEqual(stake, 5000000)
        self.assertEqual(motivo, 'compuesto')

    def test_compuesto_refleja_pnl_asentado(self):
        # -2.000 COP asentados desde el ancla → balance 248000 → 2% = 4960.
        self._activar_compuesto()
        self._historial('LOST', stake=2000000, payout=0)      # −2.000 COP
        self._historial('WON', stake=500000, payout=500000)   # +0 COP
        stake, _ = resolve_stake(self.config)
        # 2% de 248.000 = 4.960 → floor a múltiplos de 100 → 4.900 COP
        self.assertEqual(stake, 4900000)

    def test_compuesto_ignora_open_y_apuestas_previas_al_ancla(self):
        self._activar_compuesto(balance=100000)
        # OPEN: no cuenta. Anterior al ancla: no cuenta.
        self._historial('OPEN', stake=999000, payout=0)
        antigua = self._historial('LOST', stake=999000, payout=0, days_ago=30)
        antigua.placed_date = timezone.now() - timedelta(days=30)
        antigua.save()
        self.assertEqual(bankroll_cop(self.usuario), 100000)
        stake, _ = resolve_stake(self.config)
        self.assertEqual(stake, 2000000)  # 2% de 100000 = 2000 COP

    def test_compuesto_redondea_abajo_a_multiplos_de_100(self):
        # Balance 100123 → 2% = 2002.46 → 2000 COP.
        self._activar_compuesto(balance=100123)
        stake, _ = resolve_stake(self.config)
        self.assertEqual(stake, 2000000)

    def test_compuesto_con_balance_cero_o_negativo_no_apuesta(self):
        self._activar_compuesto(balance=0)
        self.assertIsNone(resolve_stake(self.config)[0])
        self._activar_compuesto(balance=-5000)
        stake, motivo = resolve_stake(self.config)
        self.assertIsNone(stake)
        self.assertEqual(motivo, 'sin_saldo')

    def test_compuesto_stake_bajo_minimo_no_apuesta(self):
        # Balance 10000, 2% = 200 < min 500 → no apostar.
        self._activar_compuesto(balance=10000)
        stake, motivo = resolve_stake(self.config)
        self.assertIsNone(stake)
        self.assertEqual(motivo, 'stake_minimo')

    def test_compuesto_stake_techo(self):
        # Balance 1.000.000, 10% = 100000 → techo 5000 COP.
        self._activar_compuesto(balance=1000000, pct=10.0)
        stake, _ = resolve_stake(self.config)
        self.assertEqual(stake, 5000000)

    # ── ajustes manuales ─────────────────────────────────────────────────

    def test_ajuste_manual_mueve_el_balance(self):
        self._activar_compuesto(balance=250000, max_s=10000)
        CapitalAjuste.objects.create(usuario=self.usuario, monto_cop=+12500,
                                     motivo='Reconciliación')
        self.assertEqual(bankroll_cop(self.usuario), 262500)
        stake, _ = resolve_stake(self.config)
        # 2% de 262.500 = 5.250 → floor a múltiplos de 100 → 5.200 COP
        self.assertEqual(stake, 5200000)

    # ── navegación / context processor ───────────────────────────────────
    def test_navbar_balance_solo_con_modo_activado(self):
        from django.test import RequestFactory
        from .context_processors import navbar_balance

        rf = RequestFactory()
        req = rf.get('/')
        req.user = self.usuario

        # Sin activar: sin balance.
        ctx = navbar_balance(req)
        self.assertIsNone(ctx['navbar_balance'])

        # Activado: $ con formato colombiano.
        self._activar_compuesto(balance=1234567)
        ctx = navbar_balance(req)
        self.assertEqual(ctx['navbar_balance'], '$1.234.567')
        self.assertFalse(ctx['navbar_balance_negativo'])


class ConfiguracionViewTests(TestCase):
    """Flujo completo de la página /auto-betting/configuracion/."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email='view@test.com', username='view', password='pass123',
        )
        self.config = AutoBetConfig.objects.create(
            usuario=self.usuario, ticket='t', punter_id='p', stake=500000,
        )
        self.client.login(username='view@test.com', password='pass123')

    def _post(self, **extra):
        data = {
            'ticket': 't', 'punter_id': 'p', 'cuota_minima': '2.0',
            'stake': '500000', 'max_apuestas_diarias': '20',
            'horas_adelante': '24', 'activo': 'on',
            'modo': 'FIJO', 'porcentaje': '2.0', 'balance_inicial': '',
            'stake_min_cop': '500', 'stake_max_cop': '5000',
        }
        data.update(extra)
        return self.client.post('/auto-betting/configuracion/', data)

    def test_activacion_compuesto_ancla_balance(self):
        self._post(modo='COMPUESTO', balance_inicial='250000')
        cap = CapitalConfig.objects.get(usuario=self.usuario)
        self.assertEqual(cap.modo, 'COMPUESTO')
        self.assertEqual(cap.balance_inicial, 250000)
        self.assertIsNotNone(cap.ancla)
        # Regresión 2026-09-02: al cambiar de modo NO se pierde nada.
        self.config.refresh_from_db()
        self.assertEqual(self.config.ticket, 't')
        self.assertEqual(self.config.punter_id, 'p')
        self.assertEqual(self.config.stake, 500000)

    def test_compuesto_sin_balance_no_activa(self):
        resp = self._post(modo='COMPUESTO', balance_inicial='')
        cap = CapitalConfig.objects.get(usuario=self.usuario)
        self.assertEqual(cap.modo, 'FIJO')  # no se guardó
        self.assertContains(resp, 'debes indicar el balance actual')

    def test_volver_a_fijo_conserva_stake_y_ancla(self):
        self._post(modo='COMPUESTO', balance_inicial='250000')
        self._post(modo='FIJO', ticket='nuevo-ticket', punter_id='nuevo-id')
        cap = CapitalConfig.objects.get(usuario=self.usuario)
        self.config.refresh_from_db()
        self.assertEqual(cap.modo, 'FIJO')
        self.assertEqual(cap.balance_inicial, 250000)  # ancla conservada
        self.assertEqual(self.config.stake, 500000)    # stake fijo intacto
        self.assertEqual(self.config.ticket, 'nuevo-ticket')  # datos se editan y persisten
        self.assertEqual(self.config.punter_id, 'nuevo-id')

    def test_redeclarar_balance_crea_ajuste(self):
        self._post(modo='COMPUESTO', balance_inicial='250000')
        # -2.000 COP asentados → balance paralelo 248.000 → declara 300.000
        HistorialApuesta.objects.create(
            usuario=self.usuario, coupon_ref=9101,
            placed_date=timezone.now(),
            bet_status='LOST', stake=2000000, payout=0,
        )
        self._post(modo='COMPUESTO', balance_inicial='300000')
        ajuste = CapitalAjuste.objects.get(usuario=self.usuario)
        self.assertEqual(ajuste.monto_cop, 52000)  # 300.000 − 248.000
        # El ancla original no se mueve.
        cap = CapitalConfig.objects.get(usuario=self.usuario)
        self.assertEqual(cap.balance_inicial, 250000)
