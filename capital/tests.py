"""
Tests del gestor de capital: balance paralelo, resolución de stake por modo
y protección del escenario "sin saldo".
"""

from datetime import datetime, time, timedelta

from django.test import TestCase
from django.utils import timezone

from auto_betting.models import AutoBetConfig, HistorialApuesta
from cuentas.models import Usuario

from .models import CapitalAjuste, CapitalConfig, CapitalLegada
from .services import (
    balance_filtrado, balance_timeline, bankroll_cop, get_config,
    normalizar_stake_cop, resolve_stake, snapshot_legadas,
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

    def test_compuesto_bajo_minimo_usa_minimo(self):
        # Balance 10000, 2% = 200 < min 500 → se apuesta el MÍNIMO (500 COP).
        # Política 2026-09-02: el piso es un suelo operativo, no un freno.
        self._activar_compuesto(balance=10000)
        stake, motivo = resolve_stake(self.config)
        self.assertEqual((stake, motivo), (500000, 'compuesto'))

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

    # ── serie del gráfico: en juego y total ──────────────────────────────

    def test_balance_timeline_en_juego_y_total(self):
        # OPEN: el stake se descuenta del balance pero sigue siendo dinero
        # del usuario → en_juego lo refleja y total = balance + en_juego.
        from .services import balance_timeline
        self._activar_compuesto(balance=100000)
        self._historial('OPEN', stake=999000, payout=0, days_ago=0)
        tl = balance_timeline(self.usuario)
        self.assertEqual(tl['final'], 100000 - 999)
        self.assertEqual(tl['en_juego'], 999)
        self.assertEqual(tl['total'], 100000)
        ultimo = tl['points'][-1]
        self.assertEqual(ultimo['total'], ultimo['bal'] + ultimo['en_juego'])
        self.assertEqual(ultimo['en_juego'], 999)

    def test_balance_timeline_al_asentar_sale_de_en_juego(self):
        from .services import balance_timeline
        self._activar_compuesto(balance=100000)
        apuesta = self._historial('OPEN', stake=500000, payout=0, days_ago=1)
        self.assertEqual(balance_timeline(self.usuario)['total'], 100000)
        apuesta.bet_status = 'WON'
        apuesta.payout = 950000
        apuesta.save()
        tl = balance_timeline(self.usuario)
        # −500 (stake) + 950 (payout) = +450 → balance 100450, nada en juego.
        self.assertEqual(tl['final'], 100450)
        self.assertEqual(tl['en_juego'], 0)
        self.assertEqual(tl['total'], 100450)

    # ── modo filtrado: dinero de los partidos del rango ──────────────────

    def test_balance_timeline_filtrado_muestra_dinero_de_partidos(self):
        from datetime import datetime, time as dtime
        from .services import balance_timeline
        self._activar_compuesto(balance=100000)
        hoy = timezone.localdate()
        # WON con partido HOY 08:00 → asienta ~11:00: realizado +450
        ganada = self._historial('WON', stake=500000, payout=950000, days_ago=1)
        ganada.event_start_date = timezone.make_aware(datetime.combine(hoy, dtime(8, 0)))
        ganada.save()
        # OPEN con partido HOY 20:00 → en juego 800
        abierta = self._historial('OPEN', stake=800000, payout=0, days_ago=1)
        abierta.event_start_date = timezone.make_aware(datetime.combine(hoy, dtime(20, 0)))
        abierta.save()
        # OPEN con partido en 5 días → fuera del rango, no cuenta
        fuera = self._historial('OPEN', stake=999000, payout=0, days_ago=1)
        fuera.event_start_date = timezone.make_aware(
            datetime.combine(hoy + timedelta(days=5), dtime(20, 0)))
        fuera.save()

        tl = balance_timeline(self.usuario, desde=hoy, hasta=hoy)
        self.assertTrue(tl['filtrado'])
        self.assertEqual(tl['en_juego'], 800)
        self.assertEqual(tl['realizado'], 450)
        self.assertEqual(tl['total'], 1250)
        for p in tl['points']:
            self.assertEqual(p['total'], p['en_juego'] + p['realizado'])
        self.assertEqual(tl['points'][-1]['total'], 1250)

        # Sin filtro: modo cuenta (bal + en juego de toda la cuenta).
        full = balance_timeline(self.usuario)
        self.assertFalse(full['filtrado'])
        self.assertEqual(full['en_juego'], 800 + 999)
        self.assertEqual(full['total'], full['bankroll'] + full['en_juego'])

    def test_balance_timeline_filtrado_incluye_autobet_pendiente(self):
        from .services import balance_timeline
        self._activar_compuesto(balance=50000)
        self._autobet_open(stake=800000, coupon_ref=888000001)
        hoy = timezone.localdate()
        tl = balance_timeline(self.usuario, desde=hoy, hasta=hoy)
        self.assertTrue(tl['filtrado'])
        self.assertEqual(tl['en_juego'], 800)
        self.assertEqual(tl['realizado'], 0)
        self.assertEqual(tl['total'], 800)

    # ── crecimiento del capital por rango (tarjeta del historial) ────────

    def test_crecimiento_capital_sin_fechas_usa_todo_el_periodo(self):
        # Regresión 2026-10-12: sin filtros la tarjeta desaparecía.
        from .services import crecimiento_capital
        self._activar_compuesto(balance=100000)
        self._historial('WON', stake=500000, payout=1000000, days_ago=1)  # +500
        c = crecimiento_capital(self.usuario)
        self.assertIsNotNone(c)
        self.assertFalse(c['sin_datos'])
        self.assertEqual(c['inicio'], 100000)
        self.assertEqual(c['fin'], 100500)
        self.assertEqual(c['delta'], 500)
        self.assertEqual(c['pct'], 0.5)
        self.assertEqual(c['fecha_fin'], timezone.localdate().strftime('%d/%m'))

    def test_crecimiento_capital_rango_antes_del_ancla_no_desaparece(self):
        # Regresión 2026-10-12: un rango anterior al ancla ocultaba la tarjeta.
        from .services import crecimiento_capital
        self._activar_compuesto(balance=100000)  # ancla: hace 10 días
        hoy = timezone.localdate()
        c = crecimiento_capital(self.usuario,
                                desde=hoy - timedelta(days=30),
                                hasta=hoy - timedelta(days=20))
        self.assertIsNotNone(c)
        self.assertTrue(c['sin_datos'])
        self.assertEqual(c['motivo'], 'antes_ancla')
        self.assertIsNone(c['pct'])
        self.assertIsNone(c['delta'])

    def test_crecimiento_capital_rango_futuro_sin_movimientos(self):
        from .services import crecimiento_capital
        self._activar_compuesto(balance=100000)
        hoy = timezone.localdate()
        c = crecimiento_capital(self.usuario,
                                desde=hoy + timedelta(days=5),
                                hasta=hoy + timedelta(days=8))
        self.assertTrue(c['sin_datos'])
        self.assertEqual(c['motivo'], 'sin_movimientos')

    def test_crecimiento_capital_desde_antes_del_ancla_arranca_en_el_ancla(self):
        from .services import crecimiento_capital
        cfg = self._activar_compuesto(balance=100000)
        self._historial('WON', stake=500000, payout=1000000, days_ago=3)  # +500
        hoy = timezone.localdate()
        c = crecimiento_capital(self.usuario, desde=hoy - timedelta(days=20), hasta=hoy)
        self.assertFalse(c['sin_datos'])
        self.assertEqual(c['inicio'], 100000)
        self.assertEqual(c['fin'], 100500)
        self.assertEqual(c['pct'], 0.5)
        self.assertEqual(c['fecha_inicio'],
                         timezone.localtime(cfg.ancla).date().strftime('%d/%m'))

    def test_crecimiento_capital_sin_modo_compuesto_devuelve_none(self):
        from .services import crecimiento_capital
        self.assertIsNone(crecimiento_capital(self.usuario))

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


class BalanceFiltradoTests(TestCase):
    """Serie de la tarjeta nueva: saldo real recortado o aporte filtrado."""

    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            email='filtrado@test.com', username='filtrado', password='x',
        )
        self.cfg = get_config(self.usuario)
        self.cfg.modo = CapitalConfig.MODO_COMPUESTO
        self.cfg.balance_inicial = 100000
        self.cfg.ancla = timezone.now() - timedelta(days=10)
        self.cfg.save()
        self._seq = 0

    def _apuesta(self, status, stake, payout=0, sport='FOOTBALL',
                 is_system=True, placed_days_ago=3, event_hours_ago=None):
        """Crea una apuesta con fechas relativas; stake/payout en Kambi."""
        self._seq += 1
        event = None
        if event_hours_ago is not None:
            event = timezone.now() - timedelta(hours=event_hours_ago)
        return HistorialApuesta.objects.create(
            usuario=self.usuario,
            coupon_ref=880000000 + self._seq,
            placed_date=timezone.now() - timedelta(days=placed_days_ago),
            event_start_date=event,
            bet_status=status, stake=stake, payout=payout,
            sport=sport, is_system=is_system,
        )

    def test_sin_filtros_devuelve_balance_timeline(self):
        self._apuesta('WON', stake=500000, payout=950000,
                      event_hours_ago=30)
        esperado = balance_timeline(self.usuario)
        obtenido = balance_filtrado(self.usuario)
        self.assertEqual(obtenido['points'], esperado['points'])
        self.assertEqual(obtenido['inicial'], esperado['inicial'])
        self.assertEqual(obtenido['final'], esperado['final'])
        self.assertEqual(obtenido['modo'], 'real')
        self.assertFalse(obtenido['filtrado'])
        self.assertFalse(obtenido['parcial'])

    def test_solo_fechas_recorta_y_arranca_en_saldo_real(self):
        # Antes de la ventana: su stake ya está reflejado en el saldo real
        # de partida; NO se vuelve a descontar.
        self._apuesta('LOST', stake=10000, payout=0, placed_days_ago=8,
                      event_hours_ago=24 * 7)
        # Dentro de la ventana: WON con +20 COP netos.
        self._apuesta('WON', stake=20000, payout=50000, placed_days_ago=3,
                      event_hours_ago=48)
        # OPEN dentro: −5 COP.
        self._apuesta('OPEN', stake=5000, payout=0, placed_days_ago=1)

        hoy = timezone.localdate()
        desde = hoy - timedelta(days=5)
        serie = balance_filtrado(self.usuario, desde=desde, hasta=hoy)

        self.assertEqual(serie['modo'], 'real')
        self.assertTrue(serie['filtrado'])
        self.assertFalse(serie['parcial'])
        self.assertEqual(serie['inicial'], 99990)   # 100000 − 10 previos
        self.assertEqual(serie['final'], 100015)    # −20 +50 −5

        inicio = timezone.make_aware(datetime.combine(desde, time.min))
        fin = timezone.make_aware(datetime.combine(hoy, time.max))
        self.assertEqual(datetime.fromisoformat(serie['points'][0]['t']), inicio)
        self.assertEqual(serie['points'][0]['bal'], 99990)
        self.assertEqual(datetime.fromisoformat(serie['points'][-1]['t']), fin)
        self.assertEqual(serie['points'][-1]['bal'], 100015)
        for p in serie['points']:
            t = datetime.fromisoformat(p['t'])
            self.assertGreaterEqual(t, inicio)
            self.assertLessEqual(t, fin)

    def test_sport_cambia_la_serie_y_usa_modo_filtrado(self):
        self._apuesta('WON', stake=10000, payout=30000, sport='FOOTBALL',
                      placed_days_ago=2, event_hours_ago=30)
        self._apuesta('LOST', stake=50000, payout=0, sport='BASKETBALL',
                      placed_days_ago=2, event_hours_ago=30)

        hoy = timezone.localdate()
        desde = hoy - timedelta(days=5)
        futbol = balance_filtrado(
            self.usuario, desde=desde, hasta=hoy, sport='FOOTBALL')
        basket = balance_filtrado(
            self.usuario, desde=desde, hasta=hoy, sport='BASKETBALL')
        todos = balance_filtrado(self.usuario, desde=desde, hasta=hoy)

        self.assertEqual(futbol['modo'], 'filtrado')
        self.assertTrue(futbol['filtrado'])
        self.assertTrue(futbol['parcial'])
        self.assertEqual(basket['modo'], 'filtrado')
        self.assertEqual(todos['modo'], 'real')
        self.assertEqual(futbol['inicial'], 100000)
        self.assertEqual(futbol['final'], 100020)   # −10 +30
        self.assertEqual(basket['final'], 99950)    # −50
        self.assertEqual(todos['final'], 99970)     # ambos aportes
        self.assertNotEqual(futbol['points'], basket['points'])
        self.assertNotEqual(futbol['points'], todos['points'])
        self.assertTrue(all(set(p) == {'t', 'bal'} for p in futbol['points']))

    def test_tipo_sistema_y_manual_filtran(self):
        self._apuesta('WON', stake=10000, payout=20000, sport='FOOTBALL',
                      is_system=True, placed_days_ago=2, event_hours_ago=30)
        self._apuesta('LOST', stake=30000, payout=0, sport='BASKETBALL',
                      is_system=False, placed_days_ago=2, event_hours_ago=30)

        hoy = timezone.localdate()
        desde = hoy - timedelta(days=5)
        sistema = balance_filtrado(
            self.usuario, desde=desde, hasta=hoy, tipo='sistema')
        manual = balance_filtrado(
            self.usuario, desde=desde, hasta=hoy, tipo='manual')
        todos = balance_filtrado(self.usuario, desde=desde, hasta=hoy)

        self.assertEqual(sistema['modo'], 'filtrado')
        self.assertEqual(manual['modo'], 'filtrado')
        self.assertTrue(sistema['parcial'])
        self.assertTrue(manual['parcial'])
        self.assertEqual(sistema['final'], 100010)  # +10
        self.assertEqual(manual['final'], 99970)    # −30
        self.assertEqual(todos['final'], 99980)     # ambos
        self.assertNotEqual(sistema['points'], manual['points'])

    def test_sin_ancla_o_balance_devuelve_none(self):
        otro = Usuario.objects.create_user(
            email='sinancla@test.com', username='sinancla', password='x',
        )
        self.assertIsNone(balance_filtrado(otro))
        cfg = get_config(otro)
        cfg.balance_inicial = 100000
        cfg.save()
        self.assertIsNone(balance_filtrado(otro))

    def test_rango_invertido_devuelve_none(self):
        hoy = timezone.localdate()
        self.assertIsNone(balance_filtrado(
            self.usuario, desde=hoy, hasta=hoy - timedelta(days=2)))
