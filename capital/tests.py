"""
Tests del gestor de capital: balance paralelo, resolución de stake por modo
y protección del escenario "sin saldo".
"""

from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from auto_betting.models import AutoBetConfig, HistorialApuesta
from cuentas.models import Usuario

from .models import CapitalAjuste, CapitalConfig, CapitalLegada
from .services import (
    bankroll_cop, get_config, normalizar_stake_cop, resolve_stake,
    snapshot_legadas,
)


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
        # 2% de 248.000 = 4.960 → múltiplo de 100 más cercano → 5.000 COP
        self.assertEqual(stake, 5000000)

    def test_open_descuenta_stake_en_tiempo_real(self):
        # OPEN colocado desde el ancla: el stake ya salió del balance (como
        # en la cuenta real). Antes del ancla: no cuenta (ya estaba incluido
        # en el balance declarado).
        self._activar_compuesto(balance=100000)
        self._historial('OPEN', stake=999000, payout=0)          # −999 COP
        antigua = self._historial('OPEN', stake=888000, payout=0, days_ago=30)
        antigua.placed_date = timezone.now() - timedelta(days=30)  # pre-ancla
        antigua.save()
        self.assertEqual(bankroll_cop(self.usuario), 100000 - 999)
        stake, _ = resolve_stake(self.config)
        # 2% de 99.001 = 1.980,02 → múltiplo de 100 más cercano → 2.000 COP
        self.assertEqual(stake, 2000000)

    def test_compuesto_redondea_a_numero_redondo(self):
        # Balance 100123 → 2% = 2002.46 → 2000 COP (múltiplo de 100).
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
        # 2% de 262.500 = 5.250 → múltiplo de 100 más cercano → 5.300 COP
        self.assertEqual(stake, 5300000)

    # ── apuestas legadas (OPEN al activar) ───────────────────────────────
    def test_legada_won_acredita_payout_completo(self):
        # Apuesta OPEN previa al ancla: su stake ya estaba descontado del
        # balance declarado. Al asentar WON, la cuenta real recibe el payout
        # completo → el paralelo debe sumar payout (no payout − stake).
        legada = self._historial('OPEN', stake=800000, payout=0, days_ago=12)
        self._activar_compuesto(balance=50000)  # ancla = now − 10 días
        self.assertEqual(snapshot_legadas(self.usuario), 1)
        legada.bet_status = 'WON'
        legada.payout = 1904000
        legada.save()
        self.assertEqual(bankroll_cop(self.usuario), 50000 + 1904)

    def test_legada_lost_no_descuenta_otra_vez(self):
        # LOST: el stake ya salió del balance declarado → paralelo no cambia.
        legada = self._historial('OPEN', stake=800000, payout=0, days_ago=12)
        self._activar_compuesto(balance=50000)
        snapshot_legadas(self.usuario)
        legada.bet_status = 'LOST'
        legada.save()
        self.assertEqual(bankroll_cop(self.usuario), 50000)

    def test_legada_no_duplica_apuestas_nuevas(self):
        # Apuesta NUEVA (placed >= ancla) no entra como legada: cuenta profit.
        self._activar_compuesto(balance=50000)
        snapshot_legadas(self.usuario)  # sin OPEN previos → 0 legadas
        self._historial('WON', stake=800000, payout=1904000)  # profit +1104
        self.assertEqual(bankroll_cop(self.usuario), 50000 + 1104)

    # ── stake descontado al colocar (tiempo real) ─────────────────────────

    def _autobet_open(self, stake=800000, coupon_ref=777000001):
        from auto_betting.models import AutoBet
        return AutoBet.objects.create(
            usuario=self.usuario, evento_id=1,
            home_team='A', away_team='B', liga='L', start_time=timezone.now(),
            mercado='M',
            seleccion='X', cuota=2.0,
            corners_predichos=0.0, predicta_prob=50.0,
            confidence=0.0, edge=0.0, ev=0.0,
            stake=stake, coupon_ref=coupon_ref, estado='OPEN',
        )

    def test_autobet_open_sin_sincronizar_descuenta(self):
        # Apuesta recién colocada (AutoBet OPEN, aún sin sync): baja el balance.
        self._activar_compuesto(balance=50000)
        self._autobet_open(stake=800000)  # 800 COP
        self.assertEqual(bankroll_cop(self.usuario), 50000 - 800)

    def test_no_doble_conteo_al_sincronizar(self):
        # Cuando el sync importa el cupón a HistorialApuesta, el stake no se
        # descuenta dos veces (AutoBet se excluye por coupon_ref).
        self._activar_compuesto(balance=50000)
        self._autobet_open(stake=800000, coupon_ref=777000001)
        self._historial('OPEN', stake=800000, payout=0)
        hist = HistorialApuesta.objects.get(usuario=self.usuario, bet_status='OPEN',
                                            coupon_ref__isnull=False)
        hist.coupon_ref = 777000001
        hist.save()
        self.assertEqual(bankroll_cop(self.usuario), 50000 - 800)

    def test_ganar_aumenta_balance_con_payout_completo(self):
        # Colocada (desc cuenta stake) → WON (sube payout completo).
        self._activar_compuesto(balance=50000)
        apuesta = self._historial('OPEN', stake=800000, payout=0)
        self.assertEqual(bankroll_cop(self.usuario), 50000 - 800)
        apuesta.bet_status = 'WON'
        apuesta.payout = 1904000
        apuesta.save()
        self.assertEqual(bankroll_cop(self.usuario), 50000 - 800 + 1904)

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
            'stake': '500',  # COP real (el form convierte a Kambi ×1000)
            'max_apuestas_diarias': '20',
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
        self.assertEqual(self.config.stake, 500000)  # 500 COP → Kambi

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
        self.assertEqual(self.config.stake, 500000)    # stake fijo intacto (500 COP → Kambi)
        self.assertEqual(self.config.ticket, 'nuevo-ticket')  # datos se editan y persisten
        self.assertEqual(self.config.punter_id, 'nuevo-id')

    def test_stake_se_guarda_en_cop_y_convierte(self):
        """El usuario escribe COP; el form convierte a unidades Kambi ×1000."""
        from auto_betting.forms import AutoBetConfigForm
        form = AutoBetConfigForm(data={
            'ticket': 't', 'punter_id': 'p', 'cuota_minima': '2.0',
            'stake': '1200', 'max_apuestas_diarias': '20',
            'horas_adelante': '24', 'activo': 'on',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['stake'], 1200000)

        # Valores inválidos no pasan.
        form2 = AutoBetConfigForm(data={
            'ticket': 't', 'punter_id': 'p', 'cuota_minima': '2.0',
            'stake': '0', 'max_apuestas_diarias': '20',
            'horas_adelante': '24', 'activo': 'on',
        })
        self.assertFalse(form2.is_valid())
        self.assertIn('stake', form2.errors)

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


class NormalizacionStakeTests(TestCase):
    """Política anti-bloqueo (2026-09-02): piso 500 COP y números redondos."""

    def test_piso_global_500(self):
        self.assertEqual(normalizar_stake_cop(0), 500)
        self.assertEqual(normalizar_stake_cop(300), 500)

    def test_multiplos_de_100_bajo_10000(self):
        self.assertEqual(normalizar_stake_cop(525), 500)
        self.assertEqual(normalizar_stake_cop(550), 600)
        self.assertEqual(normalizar_stake_cop(9999), 10000)

    def test_multiplos_de_1000(self):
        self.assertEqual(normalizar_stake_cop(10850), 11000)
        self.assertEqual(normalizar_stake_cop(49999), 50000)

    def test_multiplos_de_10000(self):
        self.assertEqual(normalizar_stake_cop(149999), 150000)
        self.assertEqual(normalizar_stake_cop(1234567), 1200000)

    def test_valores_ya_redondos_no_cambian(self):
        for v in (500, 600, 9900, 10000, 11000, 150000):
            self.assertEqual(normalizar_stake_cop(v), v)

    def test_hacia_abajo_y_arriba(self):
        self.assertEqual(normalizar_stake_cop(525, hacia='abajo'), 500)
        self.assertEqual(normalizar_stake_cop(525, hacia='arriba'), 600)
        self.assertEqual(normalizar_stake_cop(149999, hacia='abajo'), 140000)


class ResolveStakeAntibloqueoTests(TestCase):
    """El stake que SALE hacia BetPlay siempre es un número redondo."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email='anti@test.com', username='anti', password='pass123',
        )
        self.config = AutoBetConfig.objects.create(
            usuario=self.usuario, ticket='t', punter_id='p', stake=500000,
        )

    def test_fijo_no_redondo_se_normaliza(self):
        self.config.stake = 525000  # 525 COP (legacy)
        self.config.save()
        stake, motivo = resolve_stake(self.config)
        self.assertEqual((stake, motivo), (500000, 'fijo'))

    def test_fijo_stake_cero_no_apuesta(self):
        self.config.stake = 0
        self.config.save()
        stake, motivo = resolve_stake(self.config)
        self.assertIsNone(stake)
        self.assertEqual(motivo, 'sin_saldo')

    def test_form_fijo_rechaza_menor_a_500(self):
        from auto_betting.forms import AutoBetConfigForm
        form = AutoBetConfigForm(data={
            'ticket': 't', 'punter_id': 'p', 'cuota_minima': '2.0',
            'stake': '300', 'max_apuestas_diarias': '20',
            'horas_adelante': '24', 'activo': 'on',
        })
        self.assertFalse(form.is_valid())
        self.assertIn('stake', form.errors)

    def test_form_fijo_normaliza_525_a_500(self):
        from auto_betting.forms import AutoBetConfigForm
        form = AutoBetConfigForm(data={
            'ticket': 't', 'punter_id': 'p', 'cuota_minima': '2.0',
            'stake': '525', 'max_apuestas_diarias': '20',
            'horas_adelante': '24', 'activo': 'on',
        })
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.cleaned_data['stake'], 500000)
        self.assertEqual(form._stake_ajustado, (525, 500))
