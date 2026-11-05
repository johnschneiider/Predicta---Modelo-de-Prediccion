# -*- coding: utf-8 -*-
"""Tests del motor Over/Under al descanso (basket_ou).

Vectores T1–T5 del spec (verificados contra el Excel / ref_model.py) + unidades
de calibración (Patron), métricas (Backtest), liquidación y config.
Tolerancia 1e-4 salvo valores del spec redondeados a 3 decimales (delta 1e-3).
"""
import statistics
from datetime import date, timedelta
from io import StringIO
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase
from django.urls import reverse
from django.utils import timezone

from auto_betting import basket_1q2q as bk
from auto_betting import basket_ou as ou
from auto_betting.models import (BasketOuCalib, BasketOuShadow, BasketSample,
                                 LeagueRegistry, PaperBet)

TOL = 1e-4
TOL_3DEC = 1e-3


class VectoresEspecTests(SimpleTestCase):
    """T1–T5 del spec (calibración en defaults, n < 30)."""

    def test_T1_calculadora_europa(self):
        cfg = ou.CFG['EUROPA']
        cal = ou.calibracion_inicial(cfg, 'EUROPA')
        d = ou.decidir(cfg, cal, dict(
            q1h=26, q1a=26, q2h=12, q2a=20, line=174.5,
            odds_over=1.83, odds_under=1.86, fga=60, orb=9, to=12, fta=18))
        self.assertAlmostEqual(d['A'], 168.0, delta=TOL)
        self.assertAlmostEqual(d['C'], 169.625, delta=TOL)
        self.assertAlmostEqual(d['proy'], 171.9, delta=TOL)
        self.assertAlmostEqual(d['diff'], -2.6, delta=TOL)
        self.assertEqual(d['sigma'], 9.0)
        self.assertAlmostEqual(d['p_over'], 0.38633, delta=TOL)
        self.assertAlmostEqual(d['p_under'], 0.61367, delta=TOL)
        self.assertAlmostEqual(d['ev_over'], -0.29301, delta=TOL)
        self.assertAlmostEqual(d['ev_under'], 0.14142, delta=TOL)
        self.assertEqual(d['side'], 'UNDER')
        self.assertEqual(d['decision'], 'NO APOSTAR')
        self.assertEqual(d['stake'], 0.0)
        f = d['filtros']
        self.assertTrue(f['prob'] and f['ev'] and f['cuota']
                        and f['margen'] and f['datos'])
        self.assertFalse(f['diff'])          # falla SOLO |diff| 2.6 < 3

    def test_T2_calculadora_nba(self):
        cfg = ou.CFG['NBA']
        cal = ou.calibracion_inicial(cfg, 'NBA')
        d = ou.decidir(cfg, cal, dict(
            q1h=35, q1a=29, q2h=34, q2a=37, line=252.5,
            odds_over=1.84, odds_under=1.78, fga=97, orb=14, to=18, fta=28))
        self.assertAlmostEqual(d['A'], 270.0, delta=TOL)
        self.assertAlmostEqual(d['C'], 265.625, delta=TOL)
        self.assertAlmostEqual(d['proy'], 259.5, delta=TOL)
        self.assertAlmostEqual(d['diff'], 7.0, delta=TOL)
        self.assertEqual(d['sigma'], 12.0)
        self.assertAlmostEqual(d['p_over'], 0.72017, delta=TOL)
        self.assertAlmostEqual(d['p_under'], 0.27983, delta=TOL)
        self.assertAlmostEqual(d['ev_over'], 0.3251, delta=TOL)
        self.assertAlmostEqual(d['ev_under'], -0.50189, delta=TOL)
        self.assertEqual(d['side'], 'OVER')
        self.assertEqual(d['decision'], 'APOSTAR OVER')
        self.assertAlmostEqual(d['stake'], 30.0, delta=TOL)   # cap 3 % de 1000
        self.assertTrue(all(d['filtros'].values()))

    def test_T3_historial_europa_rigas(self):
        cfg = ou.CFG['EUROPA']
        cal = ou.calibracion_inicial(cfg, 'EUROPA')
        fila = ou.fila_historial(cfg, cal, dict(
            q1=45, q2=51, q3=35, q4=37, line=180.5, odds=1.81, margin=6))
        self.assertAlmostEqual(fila['proy'], 184.094, delta=TOL_3DEC)
        self.assertAlmostEqual(fila['p_side'], 0.655, delta=TOL_3DEC)
        self.assertEqual(fila['side'], 'OVER')
        self.assertTrue(fila['apostar'])
        self.assertEqual(fila['resultado'], 'PIERDE')
        self.assertEqual(fila['ganancia_u'], -1.0)

    def test_T4_historial_europa_efes(self):
        cfg = ou.CFG['EUROPA']
        cal = ou.calibracion_inicial(cfg, 'EUROPA')
        fila = ou.fila_historial(cfg, cal, dict(
            q1=48, q2=52, q3=43, q4=51, line=185.5, odds=1.84, margin=8))
        self.assertAlmostEqual(fila['proy'], 190.031, delta=TOL_3DEC)
        self.assertAlmostEqual(fila['p_side'], 0.693, delta=TOL_3DEC)
        self.assertEqual(fila['side'], 'OVER')
        self.assertTrue(fila['apostar'])
        self.assertEqual(fila['resultado'], 'GANA')
        self.assertAlmostEqual(fila['ganancia_u'], 0.84, delta=TOL)

    def test_T5_historial_nba_orlando(self):
        cfg = ou.CFG['NBA']
        cal = ou.calibracion_inicial(cfg, 'NBA')
        fila = ou.fila_historial(cfg, cal, dict(
            q1=63, q2=61, q3=67, q4=57, line=236.5, odds=1.87, margin=20))
        self.assertAlmostEqual(fila['proy'], 240.094, delta=TOL_3DEC)
        self.assertAlmostEqual(fila['p_side'], 0.618, delta=TOL_3DEC)
        self.assertEqual(fila['side'], 'OVER')
        self.assertFalse(fila['apostar'])     # |diff| 3.59 < 4 (min_diff NBA)


class CalculadoraTests(SimpleTestCase):

    def test_faltan_datos_sin_cuota(self):
        cfg = ou.CFG['EUROPA']
        cal = ou.calibracion_inicial(cfg, 'EUROPA')
        d = ou.decidir(cfg, cal, dict(
            q1h=26, q1a=26, q2h=12, q2a=20, line=174.5, odds_over=1.83,
            odds_under=None))
        self.assertEqual(d['decision'], 'FALTAN DATOS')
        self.assertFalse(any(d['filtros'].values()))

    def test_metodo_c_omitido_renormaliza(self):
        cfg = ou.CFG['EUROPA']
        cal = ou.calibracion_inicial(cfg, 'EUROPA')
        d = ou.decidir(cfg, cal, dict(
            q1h=26, q1a=26, q2h=12, q2a=20, line=174.5,
            odds_over=1.83, odds_under=1.86))     # sin fga/orb/to/fta
        self.assertIsNone(d['C'])
        esperado = (cfg['wA'] * 168.0 + cfg['wL'] * 174.5
                    + cfg['wM'] * 174.5) / (cfg['wA'] + cfg['wL'] + cfg['wM'])
        self.assertAlmostEqual(d['proy'], esperado, delta=TOL)

    def test_filtro_margen(self):
        cfg = ou.CFG['NBA']
        cal = ou.calibracion_inicial(cfg, 'NBA')
        # T2 con el mismo total de cuartos pero margen 95 > 20
        d = ou.decidir(cfg, cal, dict(
            q1h=60, q1a=4, q2h=55, q2a=16, line=252.5,
            odds_over=1.84, odds_under=1.78, fga=97, orb=14, to=18, fta=28))
        self.assertAlmostEqual(d['margin'], 95.0, delta=TOL)
        self.assertFalse(d['filtros']['margen'])
        self.assertTrue(d['filtros']['prob'] and d['filtros']['ev']
                        and d['filtros']['diff'])
        self.assertEqual(d['decision'], 'NO APOSTAR')
        self.assertEqual(d['stake'], 0.0)

    def test_probabilidades_linea_entera_dejan_push(self):
        proj, line, sigma = 175.2, 175.0, 9.0
        po, pu = ou.probs(line, proj, sigma)
        push = ou.Phi((line + 0.5 - proj) / sigma) - ou.Phi((line - 0.5 - proj) / sigma)
        self.assertAlmostEqual(po + pu + push, 1.0, delta=1e-12)
        self.assertLess(po + pu, 1.0)


class CalibracionTests(SimpleTestCase):

    def _juego(self, q1, q2, q3, q4, line=None):
        return dict(q1=q1, q2=q2, q3=q3, q4=q4, line=line)

    def test_defaults_con_muestra_corta(self):
        cfg = ou.CFG['EUROPA']
        games = [self._juego(40 + i, 42, 38, 36) for i in range(7)]
        cal = ou.calibrar(games, cfg, 'EUROPA')
        self.assertEqual(cal.n, 7)
        self.assertEqual(cal.pct, (0.25, 0.25, 0.25, 0.25))
        self.assertEqual(cal.league_mean, 160.0)
        self.assertEqual(cal.sigma, 9.0)
        self.assertEqual(cal.sigma_fuente, 'default')
        self.assertFalse(any(cal.significativas))

    def test_patron_significativo_y_sigma_error(self):
        cfg = ou.CFG['EUROPA']
        games = []
        for i in range(40):
            games.append(self._juego(
                57 if i % 2 else 55, 55 if i % 2 else 53,
                48 if i % 2 else 46, 40 if i % 2 else 46))
        cal = ou.calibrar(games, cfg, 'EUROPA')
        self.assertEqual(cal.n, 40)
        esperado = (0.28, 0.27, 0.235, 0.215)
        for a, b in zip(cal.pct, esperado):
            self.assertAlmostEqual(a, b, delta=1e-9)
        self.assertTrue(all(cal.significativas))
        self.assertAlmostEqual(cal.league_mean, 200.0, delta=1e-9)
        self.assertEqual(cal.sigma_fuente, 'err')
        errores = [ou.fila_historial(cfg, cal, g)['error'] for g in games]
        self.assertAlmostEqual(cal.sigma, statistics.stdev(errores), delta=1e-9)

    def test_sin_varianza_no_hay_patron_y_sigma_cero_no_rompe(self):
        cfg = ou.CFG['EUROPA']
        games = [self._juego(50, 50, 50, 50) for _ in range(40)]
        cal = ou.calibrar(games, cfg, 'EUROPA')
        self.assertEqual(cal.pct, (0.25, 0.25, 0.25, 0.25))
        self.assertAlmostEqual(cal.league_mean, 200.0, delta=1e-9)
        self.assertEqual(cal.sigma, 9.0)          # sigma_err = 0 -> default
        self.assertEqual(cal.sigma_fuente, 'default')


class MetricasTests(SimpleTestCase):

    def _fila(self, apostar=True, side='OVER', resultado=None, ganancia=None,
              total=None, linea=None):
        return dict(apostar=apostar, side=side, resultado=resultado,
                    ganancia_u=ganancia, total=total, linea=linea)

    def test_roi_push_en_denominador_y_wilson(self):
        cfg = ou.CFG['EUROPA']
        rows = ([self._fila(resultado='GANA', ganancia=0.9) for _ in range(6)]
                + [self._fila(resultado='PIERDE', ganancia=-1.0) for _ in range(3)]
                + [self._fila(resultado='PUSH', ganancia=0.0)]
                + [self._fila(apostar=False)])
        m = ou.metricas(rows, cfg)
        self.assertEqual(m['n_shadow'], 11)
        self.assertEqual(m['n_apuestas'], 10)     # el push cuenta
        self.assertEqual((m['w'], m['l'], m['push']), (6, 3, 1))
        self.assertAlmostEqual(m['ganancia_u'], 2.4, delta=1e-9)
        self.assertAlmostEqual(m['roi'], 0.24, delta=1e-9)
        self.assertAlmostEqual(m['acierto'], 6 / 9, delta=1e-9)
        self.assertAlmostEqual(m['wilson_low'], 0.354197, delta=TOL)
        self.assertAlmostEqual(m['wilson_high'], 0.879420, delta=TOL)
        self.assertAlmostEqual(m['breakeven'], 1 / 1.9, delta=1e-9)
        self.assertEqual(m['veredicto'], 'MUESTRA INSUFICIENTE')

    def test_veredictos(self):
        cfg = ou.CFG['EUROPA']
        meta = ([self._fila(resultado='GANA', ganancia=0.9) for _ in range(36)]
                + [self._fila(resultado='PIERDE', ganancia=-1.0) for _ in range(4)])
        self.assertEqual(ou.metricas(meta, cfg)['veredicto'], 'META CUMPLIDA')
        bajo = ([self._fila(resultado='GANA', ganancia=0.9) for _ in range(15)]
                + [self._fila(resultado='PIERDE', ganancia=-1.0) for _ in range(15)])
        self.assertEqual(ou.metricas(bajo, cfg)['veredicto'],
                         'POR DEBAJO DE 60%')

    def test_acierto_por_lado_y_margen_medio(self):
        cfg = ou.CFG['EUROPA']
        rows = [
            self._fila(side='OVER', resultado='GANA', ganancia=0.9,
                       total=184.0, linea=180.0),
            self._fila(side='OVER', resultado='GANA', ganancia=0.9,
                       total=186.0, linea=180.0),
            self._fila(side='UNDER', resultado='PIERDE', ganancia=-1.0,
                       total=182.0, linea=180.0),
        ]
        m = ou.metricas(rows, cfg)
        self.assertAlmostEqual(m['acierto_over'], 1.0, delta=1e-9)
        self.assertAlmostEqual(m['acierto_under'], 0.0, delta=1e-9)
        self.assertAlmostEqual(m['margen_medio'], (4 + 6 - 2) / 3, delta=1e-9)


class ReconstruccionTests(SimpleTestCase):
    """Selector de la línea principal desde el histórico de casas (OddsPapi)."""

    def _ent(self, precio, fecha, active=True):
        return {'createdAt': fecha, 'price': precio, 'active': active}

    def _catalogo(self):
        def m(period, hcp, o1, o2):
            return {'period': period, 'handicap': hcp,
                    'outcomes': [{'outcomeId': o1, 'outcomeName': 'Over'},
                                 {'outcomeId': o2, 'outcomeName': 'Under'}]}
        return {100: m('result', 172.5, 1, 2),
                101: m('result', 173.5, 3, 4),
                102: m('result', 174.5, 5, 6),
                103: m('p1+p2', 85.5, 7, 8)}

    def _hist(self, catalogo, precios, fecha='2026-10-13T18:00:00Z',
              active=True):
        hist = {}
        for mid, m in catalogo.items():
            hist[str(mid)] = {'outcomes': {}}
            for oc in m['outcomes']:
                hist[str(mid)]['outcomes'][str(oc['outcomeId'])] = {
                    'players': {'0': [self._ent(precios[oc['outcomeId']],
                                                fecha, active)]}}
        return hist

    def test_parsear_cuartos_split(self):
        s = ou.parsear_cuartos_split('Q1: 27-14 | Q2: 23-29 | Q3: 0-0')
        self.assertEqual(s['Q1'], (27, 14))
        self.assertEqual(s['Q2'], (23, 29))
        self.assertEqual(s['Q3'], (0, 0))
        self.assertEqual(ou.parsear_cuartos_split(''), {})

    def test_elige_la_mas_balanceada_activa(self):
        catalogo = self._catalogo()
        hist = self._hist(catalogo, {1: 1.9, 2: 1.9, 3: 1.8, 4: 1.95,
                                     5: 2.1, 6: 1.75, 7: 1.85, 8: 1.85})
        t_corte = ou._ts('2026-10-13T19:00:00Z')
        sel = ou.linea_principal_descanso(hist, catalogo, t_corte)
        self.assertEqual(sel['linea'], 172.5)      # 1.9/1.9 => 50 %
        self.assertEqual(sel['over'], 1.9)
        self.assertEqual(sel['under'], 1.9)

        hist['100']['outcomes']['1']['players']['0'][0]['active'] = False
        sel = ou.linea_principal_descanso(hist, catalogo, t_corte)
        self.assertEqual(sel['linea'], 173.5)

    def test_ignora_entradas_posteriores_al_corte(self):
        catalogo = {100: self._catalogo()[100]}
        hist = self._hist(catalogo, {1: 1.9, 2: 1.9},
                          fecha='2026-10-13T19:30:00Z')
        t_corte = ou._ts('2026-10-13T19:00:00Z')
        self.assertIsNone(
            ou.linea_principal_descanso(hist, catalogo, t_corte))

    def test_ignora_mercados_que_no_son_totales_del_partido(self):
        catalogo = {103: self._catalogo()[103]}   # p1+p2 (primera parte)
        hist = self._hist(catalogo, {7: 1.85, 8: 1.85})
        t_corte = ou._ts('2026-10-13T19:00:00Z')
        self.assertIsNone(
            ou.linea_principal_descanso(hist, catalogo, t_corte))


class LiquidacionYConfigTests(SimpleTestCase):

    def test_liquidar(self):
        res, gan = ou.liquidar_apuesta('OVER', 175, 175.0, 1.9)
        self.assertEqual((res, gan), ('PUSH', 0.0))
        res, gan = ou.liquidar_apuesta('OVER', 174.5, 175.0, 1.9)
        self.assertEqual(res, 'GANA')
        self.assertAlmostEqual(gan, 0.9, delta=1e-9)
        self.assertEqual(ou.liquidar_apuesta('UNDER', 174.5, 175.0, 1.9),
                         ('PIERDE', -1.0))
        res, gan = ou.liquidar_apuesta('UNDER', 175.5, 175.0, 1.9)
        self.assertEqual(res, 'GANA')
        self.assertAlmostEqual(gan, 0.9, delta=1e-9)

    def test_fila_sin_linea(self):
        cfg = ou.CFG['EUROPA']
        cal = ou.calibracion_inicial(cfg, 'EUROPA')
        fila = ou.fila_historial(cfg, cal, dict(
            q1=45, q2=51, q3=35, q4=37, line=None, odds=None, margin=None))
        self.assertAlmostEqual(fila['total'], 168.0, delta=1e-9)
        self.assertIsNone(fila['side'])
        self.assertFalse(fila['apostar'])

    def test_cfg_version_estable_y_sensible(self):
        v1 = ou.cfg_version(ou.CFG['EUROPA'])
        v2 = ou.cfg_version(dict(ou.CFG['EUROPA']))
        self.assertEqual(v1, v2)
        otra = dict(ou.CFG['EUROPA'])
        otra['min_prob'] = 0.55
        self.assertNotEqual(v1, ou.cfg_version(otra))

    def test_mapa_ligas(self):
        self.assertEqual(ou.LIGAS_CFG['euroleague'], 'EUROPA')
        self.assertEqual(ou.LIGAS_CFG['eurocup'], 'EUROPA')
        self.assertEqual(ou.LIGAS_CFG['fiba_europe_cup'], 'EUROPA')
        self.assertEqual(ou.LIGAS_CFG['nba'], 'NBA')
        self.assertNotIn('fiba_champions_league', ou.LIGAS_CFG)  # BCL excluida
        self.assertNotIn('nba_preseason', ou.LIGAS_CFG)          # fuera del vivo
        self.assertEqual(ou.CFG_DE_LIGA['nba_preseason'], 'NBA')
        self.assertEqual(ou.CAL_LIGAS['EUROPA'], ('euroleague', 'eurocup'))


class ComandoRunPaperBetsOuTests(TestCase):
    """Bot del descanso: shadow + apuesta + liquidación con feed simulado."""

    def _partido_t2(self, **over):
        datos = dict(
            evento_id=9910001, nombre='Orlando vs Cleveland',
            local='Orlando', visitante='Cavaliers', state='STARTED',
            inicio='2026-10-15T10:00:00Z', liga_nombre='NBA',
            liga_tk='nba', region_tk='', period_id='QUARTER2',
            corriendo=False, izq_min=0, izq_seg=0,
            info_cuartos='Q1: 35-29 | Q2: 34-37', q1=64.0, q2=71.0,
            marcador_local=69, marcador_visitante=66,
            linea=252.5, cuota_over=1.84, cuota_under=1.78,
            mercado_abierto=True, cuota_over_abierta=True,
            cuota_under_abierta=True)
        datos.update(over)
        return bk.PartidoLive(**datos)

    def test_dry_run_no_escribe(self):
        with mock.patch.object(bk, 'fetch_live_partidos',
                               return_value=[self._partido_t2()]):
            call_command('run_paper_bets_ou', '--dry-run', stdout=StringIO())
        self.assertEqual(BasketOuShadow.objects.count(), 0)
        self.assertEqual(PaperBet.objects.count(), 0)

    def test_shadow_apuesta_dedup_y_liquidacion(self):
        partido = self._partido_t2()
        with mock.patch.object(bk, 'fetch_live_partidos', return_value=[partido]):
            call_command('run_paper_bets_ou', stdout=StringIO())
        sh = BasketOuShadow.objects.get(evento_id='9910001')
        self.assertEqual(sh.decision, 'APOSTAR OVER')
        # Sin posesiones (feed real) el Método C se omite: proy = 257.97,
        # p_side ≈ 0.6757 (T2 con C daría 259.5 / 0.72017)
        self.assertAlmostEqual(sh.proy, 257.96875, delta=TOL)
        self.assertAlmostEqual(sh.p_side, 0.67571, delta=TOL)
        self.assertAlmostEqual(sh.stake_kelly, 30.0, delta=TOL)
        self.assertEqual(sh.cfg, 'NBA')
        self.assertEqual(sh.n_snapshots, 1)

        bet = PaperBet.objects.get(motor=ou.MOTOR, evento_id='9910001')
        self.assertEqual(bet.seleccion, ou.SEL_OVER)
        self.assertEqual(bet.stake, 10000)
        self.assertAlmostEqual(bet.stake_kelly, 30.0, delta=TOL)
        self.assertEqual(bet.cuota, 1.84)
        self.assertEqual(bet.estado, 'OPEN')

        # segunda pasada: dedup de apuesta y n_snapshots sube
        with mock.patch.object(bk, 'fetch_live_partidos', return_value=[partido]):
            call_command('run_paper_bets_ou', stdout=StringIO())
        self.assertEqual(PaperBet.objects.filter(motor=ou.MOTOR).count(), 1)
        sh.refresh_from_db()
        self.assertEqual(sh.n_snapshots, 2)

        # partido terminado en el feed: se liquida (total 249 < 252.5 → PIERDE)
        finalizado = self._partido_t2(
            state='FINISHED', period_id='QUARTER4', corriendo=False,
            info_cuartos='Q1: 35-29 | Q2: 34-37 | Q3: 30-28 | Q4: 29-27',
            q3=58.0, q4=56.0, reloj_min=40,
            marcador_local=128, marcador_visitante=121)
        with mock.patch.object(bk, 'fetch_live_partidos',
                               return_value=[finalizado]):
            call_command('run_paper_bets_ou', stdout=StringIO())
        bet.refresh_from_db()
        sh.refresh_from_db()
        self.assertEqual(bet.estado, 'LOST')
        self.assertEqual(bet.payout, 0.0)
        self.assertEqual(sh.resultado, 'PIERDE')
        self.assertEqual(sh.ganancia_u, -1.0)
        self.assertEqual(sh.total_ot, 249.0)
        self.assertEqual(sh.total_reg, 249.0)


class ComandoCalibrarOuTests(TestCase):
    """Calibración nocturna desde BasketSample, con regla de congelado."""

    def _poblar(self, n=31):
        for i in range(n):
            q1 = 40.0 + (i % 3)
            BasketSample.objects.create(
                liga='euroleague', fecha=date(2026, 1, 1) + timedelta(days=i),
                q1=q1, q2=41.0, q3=38.0, q4=37.0, total=q1 + 116.0,
                partido=f'P{i}', fuente='test', evento_clave=f'euroleague|t{i}')

    def test_calibra_y_congela(self):
        self._poblar(31)
        # un partido con prórroga: total > regulación → se excluye
        BasketSample.objects.create(
            liga='euroleague', fecha=date(2026, 2, 1), q1=40.0, q2=40.0,
            q3=40.0, q4=40.0, total=175.0, partido='OT', fuente='test',
            evento_clave='euroleague|ot')
        call_command('calibrar_ou', stdout=StringIO())
        cal = BasketOuCalib.objects.filter(cfg='EUROPA').latest('calculada_en')
        self.assertEqual(cal.n, 31)
        self.assertEqual(cal.sigma_fuente, 'err')
        self.assertGreater(cal.sigma, 0)

        # congelada: no se recalcula sin --force
        cal.congelada = True
        cal.save(update_fields=['congelada'])
        call_command('calibrar_ou', '--cfg', 'EUROPA', stdout=StringIO())
        self.assertEqual(
            BasketOuCalib.objects.filter(cfg='EUROPA').count(), 1)
        call_command('calibrar_ou', '--cfg', 'EUROPA', '--force',
                     stdout=StringIO())
        self.assertEqual(
            BasketOuCalib.objects.filter(cfg='EUROPA').count(), 2)


class VistaOuTests(TestCase):
    """Página hija del motor OU + botón desde la página 1Q+2Q."""

    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username='ou_t', email='ou_t@test.com', password='x',
            is_superuser=True)
        self.client = Client()
        self.client.force_login(self.user)

    def test_pagina_hija_responde(self):
        r = self.client.get(reverse('auto_betting:paperbet_basket_ou'))
        self.assertEqual(r.status_code, 200)
        html = r.content.decode()
        self.assertIn('Over/Under al descanso', html)
        self.assertIn(ou.MOTOR, html)

    def test_padre_enlaza_hija(self):
        r = self.client.get(reverse('auto_betting:paperbet_basket'))
        self.assertEqual(r.status_code, 200)
        self.assertIn('/auto-betting/paperbet/baloncesto/ou-descanso/',
                      r.content.decode())

    def test_pagina_muestra_sombra_y_apuesta(self):
        BasketOuShadow.objects.create(
            evento_id='77', liga='Euroliga', clave_liga='euroleague',
            cfg='EUROPA', home_team='Alfa', away_team='Beta',
            q1h=20, q1a=18, q2h=22, q2a=19, linea=170.5,
            odds_over=1.85, odds_under=1.9, decision='APOSTAR OVER',
            lado='OVER', p_side=0.63, ev_side=0.16, odds_side=1.85,
            stake_kelly=30.0, resultado='GANA', ganancia_u=0.85,
            settled_at=timezone.now())
        PaperBet.objects.create(
            evento_id='77', start_time=timezone.now(),
            home_team='Alfa', away_team='Beta', liga='Euroliga',
            mercado=ou.MERCADO, motor=ou.MOTOR, seleccion=ou.SEL_OVER,
            linea=170.5, cuota=1.85, prob=0.63, ev=0.16, stake=10000,
            estado='WON', payout=18500)
        r = self.client.get(reverse('auto_betting:paperbet_basket_ou'))
        html = r.content.decode()
        self.assertIn('Alfa vs Beta', html)
        self.assertIn('APOSTAR OVER', html)
        self.assertIn('GANADA', html)
        self.assertIn('100.0%', html)         # acierto 1/1 en la tabla global


class ComandoScoreOuTests(TestCase):
    """Liquidador de respaldo (API-Sports mockeado)."""

    def test_liquida_apuesta_y_sombra(self):
        from django.utils import timezone
        ahora = timezone.now()
        bet = PaperBet.objects.create(
            evento_id='9910002', start_time=ahora - timedelta(hours=3),
            home_team='A', away_team='B', mercado=ou.MERCADO, motor=ou.MOTOR,
            seleccion=ou.SEL_OVER, linea=200.0, cuota=1.9, stake=10000)
        sh = BasketOuShadow.objects.create(
            evento_id='9910002', start_time=ahora - timedelta(hours=3),
            home_team='A', away_team='B', lado='OVER', linea=200.0,
            odds_side=1.9, decision='APOSTAR OVER')
        with mock.patch.object(bk, 'resultado_oficial', return_value=207.0):
            call_command('score_paper_bets_ou', stdout=StringIO())
        bet.refresh_from_db()
        sh.refresh_from_db()
        self.assertEqual(bet.estado, 'WON')
        self.assertEqual(bet.payout, 19000.0)
        self.assertEqual(sh.resultado, 'GANA')
        self.assertAlmostEqual(sh.ganancia_u, 0.9, delta=1e-9)
        self.assertEqual(sh.total_ot, 207.0)


class EstructurasTests(SimpleTestCase):
    """Generalización a N periodos (spec complementaria de ligas)."""

    def test_periodos_primera_mitad(self):
        self.assertEqual(ou.periodos_primera_mitad('FIBA_4x10'), [1, 2])
        self.assertEqual(ou.periodos_primera_mitad('NBA_4x12'), [1, 2])
        self.assertEqual(ou.periodos_primera_mitad('HALVES_2x20'), [1])

    def test_estructura_por_defecto(self):
        self.assertEqual(ou.estructura_de(ou.CFG['EUROPA']), 'FIBA_4x10')
        self.assertEqual(ou.n_periodos_de(ou.CFG['EUROPA']), 4)
        self.assertEqual(ou.n_periodos_de({'estructura': 'HALVES_2x20'}), 2)
        self.assertEqual(ou.n_periodos_de({'estructura': 'desconocida'}), 4)

    def test_A_metodo(self):
        pct4 = (0.25, 0.25, 0.25, 0.25)
        self.assertAlmostEqual(ou.A_metodo(84.0, pct4, 'FIBA_4x10'), 168.0,
                               delta=TOL)
        self.assertAlmostEqual(ou.A_metodo(84.0, (0.5, 0.5), 'HALVES_2x20'),
                               168.0, delta=TOL)

    def _cfg_halves(self):
        cfg = dict(ou.CFG_ESTRUCTURA['HALVES_2x20'])
        cfg.update(league_avg=160.0, sigma_default=9.0, min_diff=3.0,
                   max_margin=18)
        return cfg

    def test_calibracion_inicial_halves(self):
        cal = ou.calibracion_inicial(self._cfg_halves(), 'H')
        self.assertEqual(cal.pct, (0.5, 0.5))
        self.assertEqual(len(cal.t_stats), 2)

    def test_decidir_halves_con_h1(self):
        cfg = self._cfg_halves()
        cal = ou.calibracion_inicial(cfg, 'H')
        d = ou.decidir(cfg, cal, dict(h1=84.0, margen=6.0, line=170.5,
                                      odds_over=1.83, odds_under=1.86))
        proy = (cfg['wA'] * 168.0 + (cfg['wL'] + cfg['wM']) * 170.5) / \
            (cfg['wA'] + cfg['wL'] + cfg['wM'])
        self.assertAlmostEqual(d['A'], 168.0, delta=TOL)
        self.assertAlmostEqual(d['proy'], proy, delta=TOL)
        self.assertAlmostEqual(d['diff'], proy - 170.5, delta=TOL)
        self.assertEqual(d['margin'], 6.0)
        self.assertTrue(d['filtros']['margen'])
        self.assertEqual(d['decision'], 'NO APOSTAR')   # |diff| y prob bajos

    def test_decidir_halves_sin_margen_bloquea(self):
        cfg = self._cfg_halves()
        cal = ou.calibracion_inicial(cfg, 'H')
        d = ou.decidir(cfg, cal, dict(h1=84.0, line=170.5,
                                      odds_over=1.83, odds_under=1.86))
        self.assertIsNone(d['margin'])
        self.assertFalse(d['filtros']['margen'])
        self.assertEqual(d['decision'], 'NO APOSTAR')

    def test_fila_historial_halves(self):
        cfg = self._cfg_halves()
        cal = ou.calibracion_inicial(cfg, 'H')
        fila = ou.fila_historial(cfg, cal, dict(periodos=[84.0, 80.0],
                                                 line=170.5, odds=1.85))
        self.assertAlmostEqual(fila['total'], 164.0, delta=TOL)
        self.assertAlmostEqual(fila['A'], 168.0, delta=TOL)


class ConfigProvisionalTests(SimpleTestCase):
    """Heurísticas de la config provisional (spec de ligas §2)."""

    def test_vector_de_prueba_spec(self):
        cfg = ou.config_provisional('liga_x', [{'total': 165.0}] * 10)
        self.assertEqual(cfg['sigma_default'], 9.9)
        self.assertEqual(cfg['min_diff'], 3.0)
        self.assertEqual(cfg['max_margin'], 17)
        self.assertEqual(cfg['proveniente'], 'provisional')
        self.assertEqual(cfg['n_hist'], 10)
        self.assertEqual(cfg['estructura'], 'FIBA_4x10')
        self.assertEqual(cfg['wL'], 0.45)          # heredado de la estructura

    def test_hereda_estructura_halves(self):
        cfg = ou.config_provisional('x', [{'total': 160.0}], 'HALVES_2x20')
        self.assertEqual(cfg['estructura'], 'HALVES_2x20')

    def test_sin_historia(self):
        self.assertIsNone(ou.config_provisional('x', []))


class SuavizadoTests(SimpleTestCase):
    """Vectores de prueba del suavizado (spec de ligas §5, k0=20)."""

    def test_vectores(self):
        self.assertAlmostEqual(ou.suavizar(10, 170, 165), 166.6667, delta=1e-3)
        self.assertAlmostEqual(ou.suavizar(10, 0.26, 0.25), 0.25333, delta=1e-4)
        self.assertAlmostEqual(ou.sigma_suavizada(10, 11.0, 9.9), 10.28,
                               delta=0.01)

    def test_calibrar_shrinkage_suaviza_media(self):
        cfg = ou.config_provisional('x', [{'total': 160.0}])
        cfg['calibration_mode'] = 'shrinkage'
        games = [dict(q1=50.0, q2=50.0, q3=50.0, q4=50.0) for _ in range(10)]
        cal = ou.calibrar(games, cfg, 'x')
        self.assertAlmostEqual(cal.league_mean,
                               ou.suavizar(10, 200.0, 160.0), delta=1e-9)
        self.assertEqual(cal.pct, (0.25, 0.25, 0.25, 0.25))


class CompuertasTests(SimpleTestCase):
    """Máquina de estados DISCOVERY→SHADOW→PAPER→(LIVE manual)."""

    def _stats_ok(self):
        return dict(n_partidos_limpios=30, cobertura_linea_descanso=0.85,
                    cobertura_periodos=0.96, mismatch_reconciliacion=0.02,
                    n_shadow=100, rmse_modelo=8.9, rmse_linea=9.0,
                    slope_b=0.30, slope_b_lo=0.10, slope_b_hi=0.50,
                    n_paper=300, margen_medio_vs_linea=0.4, roi_plano=0.05)

    def test_todo_ok_pasa(self):
        g = ou.evaluar_compuerta(self._stats_ok())
        self.assertTrue(g['G1'] and g['G2'] and g['G3'])
        self.assertEqual(g['falta'], {'G1': '', 'G2': '', 'G3': ''})

    def test_g1_falla_por_muestra(self):
        s = self._stats_ok()
        s['n_partidos_limpios'] = 12
        g = ou.evaluar_compuerta(s)
        self.assertFalse(g['G1'])
        self.assertIn('faltan 18 partidos limpios', g['falta']['G1'])

    def test_g2_falla_si_ic_incluye_cero(self):
        s = self._stats_ok()
        s['slope_b_lo'], s['slope_b_hi'] = -0.05, 0.4
        g = ou.evaluar_compuerta(s)
        self.assertFalse(g['G2'])
        self.assertIn('incluye 0', g['falta']['G2'])

    def test_g2_falla_si_rmse_modelo_peor(self):
        s = self._stats_ok()
        s['rmse_modelo'] = 9.5
        g = ou.evaluar_compuerta(s)
        self.assertFalse(g['G2'])
        self.assertIn('RMSE modelo > RMSE línea', g['falta']['G2'])

    def test_g3_requiere_positivos(self):
        s = self._stats_ok()
        s['roi_plano'] = -0.01
        g = ou.evaluar_compuerta(s)
        self.assertFalse(g['G3'])

    def test_siguiente_estado_sin_live_automatico(self):
        g = ou.evaluar_compuerta(self._stats_ok())
        self.assertEqual(ou.siguiente_estado('DISCOVERY', g), 'SHADOW')
        self.assertEqual(ou.siguiente_estado('SHADOW', g), 'PAPER')
        self.assertEqual(ou.siguiente_estado('PAPER', g), 'PAPER')   # live manual
        self.assertEqual(
            ou.siguiente_estado('DISCOVERY', ou.evaluar_compuerta({})),
            'DISCOVERY')

    def test_regresion_simple(self):
        xs = [1, 2, 3, 4, 5]
        ys = [2, 4, 6, 8, 10]
        r = ou.regresion_simple(xs, ys)
        self.assertAlmostEqual(r['b'], 2.0, delta=1e-9)
        self.assertAlmostEqual(r['lo'], 2.0, delta=1e-9)   # ajuste perfecto
        self.assertAlmostEqual(r['hi'], 2.0, delta=1e-9)
        self.assertIsNone(ou.regresion_simple([1, 2], [1, 2]))


class RegistroLigasTests(TestCase):
    """Seed del registro (migración 0038) y compuerta del bot en vivo."""

    def _partido(self, **over):
        datos = dict(
            evento_id=9910001, nombre='Orlando vs Cleveland',
            local='Orlando', visitante='Cavaliers', state='STARTED',
            inicio='2026-10-15T10:00:00Z', liga_nombre='NBA',
            liga_tk='nba', region_tk='', period_id='QUARTER2',
            corriendo=False, izq_min=0, izq_seg=0,
            info_cuartos='Q1: 35-29 | Q2: 34-37', q1=64.0, q2=71.0,
            marcador_local=69, marcador_visitante=66,
            linea=252.5, cuota_over=1.84, cuota_under=1.78,
            mercado_abierto=True, cuota_over_abierta=True,
            cuota_under_abierta=True)
        datos.update(over)
        return bk.PartidoLive(**datos)

    def test_seed_migracion(self):
        self.assertEqual(LeagueRegistry.objects.filter(estado='PAPER').count(), 4)
        self.assertEqual(
            LeagueRegistry.objects.filter(estado='DISCOVERY').count(), 10)
        nba = LeagueRegistry.objects.get(league_id='nba')
        self.assertEqual(nba.cfg_key, 'NBA')
        self.assertEqual(nba.estructura, 'NBA_4x12')

    def test_liga_sin_registro_no_escribe(self):
        p = self._partido(liga_tk='liga_inexistente', region_tk='xx')
        out = StringIO()
        with mock.patch.object(bk, 'fetch_live_partidos', return_value=[p]):
            call_command('run_paper_bets_ou', stdout=out)
        self.assertEqual(BasketOuShadow.objects.count(), 0)
        self.assertEqual(PaperBet.objects.count(), 0)
        self.assertIn('liga sin registro', out.getvalue())

    def test_discovery_no_escribe(self):
        # Candidata seedeada en DISCOVERY (japón B2).
        p = self._partido(liga_tk='b2_league', region_tk='japan')
        out = StringIO()
        with mock.patch.object(bk, 'fetch_live_partidos', return_value=[p]):
            call_command('run_paper_bets_ou', stdout=out)
        self.assertEqual(BasketOuShadow.objects.count(), 0)
        self.assertEqual(PaperBet.objects.count(), 0)
        self.assertIn('DISCOVERY', out.getvalue())

    def test_shadow_guarda_sombra_sin_apuesta(self):
        LeagueRegistry.objects.filter(league_id='nba').update(estado='SHADOW')
        p = self._partido()
        out = StringIO()
        with mock.patch.object(bk, 'fetch_live_partidos', return_value=[p]):
            call_command('run_paper_bets_ou', stdout=out)
        sh = BasketOuShadow.objects.get(evento_id='9910001')
        self.assertEqual(sh.decision, 'APOSTAR OVER')
        self.assertEqual(sh.cfg, 'NBA')
        self.assertEqual(PaperBet.objects.count(), 0)
        self.assertIn('sin apuesta', out.getvalue())

    def test_paper_liga_apuesta(self):
        p = self._partido()
        with mock.patch.object(bk, 'fetch_live_partidos', return_value=[p]):
            call_command('run_paper_bets_ou', stdout=StringIO())
        self.assertEqual(PaperBet.objects.filter(motor=ou.MOTOR).count(), 1)

    def test_paper_detenido_si_flag_apagado(self):
        p = self._partido()
        out = StringIO()
        with mock.patch('auto_betting.management.commands.run_paper_bets_ou.'
                        'PAPER_BETS_ENABLED', False):
            with mock.patch.object(bk, 'fetch_live_partidos', return_value=[p]):
                call_command('run_paper_bets_ou', stdout=out)
        self.assertEqual(BasketOuShadow.objects.count(), 1)
        self.assertEqual(PaperBet.objects.count(), 0)
        self.assertIn('paper detenido', out.getvalue())


class VerificarYLigaReporteTests(TestCase):
    """Comandos verificar_liga_ou / reporte_ligas_ou (smoke funcional)."""

    def test_verificar_prepara_config_provisional(self):
        for i in range(5):
            BasketSample.objects.create(
                liga='japan/b2_league', q1=40.0, q2=44.0, q3=38.0, q4=42.0,
                total=164.0, partido=f'P{i}', fuente='test',
                evento_clave=f'kambi|9100{i}')
        out = StringIO()
        call_command('verificar_liga_ou', 'japan/b2_league', '--preparar',
                     stdout=out)
        reg = LeagueRegistry.objects.get(league_id='japan/b2_league')
        self.assertTrue(reg.cfg_json)
        self.assertEqual(reg.cfg_json['proveniente'], 'provisional')
        self.assertEqual(reg.cfg_json['n_hist'], 5)
        self.assertTrue(reg.cfg_version)
        self.assertEqual(reg.estado, 'DISCOVERY')   # sin --aplicar no promueve

    def test_verificar_no_promueve_sin_datos(self):
        out = StringIO()
        call_command('verificar_liga_ou', 'fiba_champions_league', '--aplicar',
                     stdout=out)
        reg = LeagueRegistry.objects.get(league_id='fiba_champions_league')
        self.assertEqual(reg.estado, 'DISCOVERY')
        self.assertIn('sin cambio de estado', out.getvalue())

    def test_reporte_ligas_imprime_registro(self):
        out = StringIO()
        call_command('reporte_ligas_ou', stdout=out)
        texto = out.getvalue()
        self.assertIn('euroleague', texto)
        self.assertIn('japan/b2_league', texto)
        self.assertIn('DISCOVERY', texto)
