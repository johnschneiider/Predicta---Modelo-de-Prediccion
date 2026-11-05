# -*- coding: utf-8 -*-
"""Tests del motor independiente de parleys (sin tocar el motor real)."""
from datetime import date, timedelta
from unittest import mock

import requests
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import Client, SimpleTestCase, TestCase
from django.utils import timezone

from capital.models import CapitalConfig
from parley_engine.models import (
    ParleyCoupon, ParleyCouponLeg, ParleyEngineConfig, ParleyLedger, ParleyRun,
)
from parley_engine.services import (
    AmbiguousPlacement, RateLimitError, RateLimitedClient, build_lookup,
    coupon_signatures, enum_parlays, is_duplicate_candidate,
    ledger_balance, record_ledger, record_settlement_if_needed,
    resolve_current_pick, upsert_history_coupon, validate_and_place,
)


class PureLogicTests(SimpleTestCase):
    def test_build_lookup(self):
        rows = [(60 if i % 2 else 40, 'WIN' if i % 2 else 'LOSE')
                for i in range(100)]
        p_rec, info = build_lookup(rows, min_fit=50)
        self.assertIsNotNone(p_rec)
        self.assertEqual(info['n_fit'], 100)
        self.assertTrue(0 <= p_rec(60) <= 1)
        self.assertTrue(0 <= p_rec(40) <= 1)

    def test_enum_parlays_pairs_and_triples(self):
        def leg(i, q):
            return ({'id': i, 'q': q}, q)
        groups = [[leg(1, 1.2)], [leg(2, 1.2)], [leg(3, 1.2)]]
        pairs = list(enum_parlays(groups, 1.0, max_legs=2, min_legs=2))
        self.assertEqual(len(pairs), 3)
        alln = list(enum_parlays(groups, 1.0, max_legs=3, min_legs=2))
        self.assertEqual(len(alln), 4)  # 3 pares + 1 triple

    def test_resolve_current_pick_football(self):
        offers = [{
            'market_label': 'Total de Tiros (Resuelta usando Opta Data)',
            'outcome_id': 11, 'label': 'Más de', 'line': 30.5,
            'odds': 1940, 'odds_decimal': 1.94, 'status': 'OPEN',
        }]
        bet = {'mercado': 'Total de Tiros (Resuelta usando Opta Data)',
               'seleccion': 'Over 30.5'}
        got = resolve_current_pick(bet, offers)
        self.assertIsNotNone(got)
        self.assertEqual(got['offer']['outcome_id'], 11)
        self.assertAlmostEqual(got['offer']['odds_decimal'], 1.94)

    def test_resolve_current_pick_hándicap(self):
        offers = [{
            'market_label': 'Hándicap de Puntos - Prórroga incluida',
            'outcome_id': 22, 'label': 'Memphis Grizzlies', 'line': 1.5,
            'odds': 3050, 'odds_decimal': 3.05, 'status': 'OPEN',
        }]
        bet = {'mercado': 'Hándicap', 'seleccion': 'Memphis Grizzlies +1.5'}
        got = resolve_current_pick(bet, offers)
        self.assertIsNotNone(got)
        self.assertEqual(got['offer']['outcome_id'], 22)

    def test_resolve_current_pick_ambiguity(self):
        offers = [
            {'market_label': 'Total de Tiros (Resuelta usando Opta Data)',
             'outcome_id': 1, 'label': 'Más de', 'line': 30.5,
             'odds': 1940, 'odds_decimal': 1.94, 'status': 'OPEN'},
            {'market_label': 'Total de Tiros (Resuelta usando Opta Data)',
             'outcome_id': 2, 'label': 'Más de', 'line': 30.5,
             'odds': 1950, 'odds_decimal': 1.95, 'status': 'OPEN'},
        ]
        bet = {'mercado': 'Total de Tiros (Resuelta usando Opta Data)',
               'seleccion': 'Over 30.5'}
        self.assertIsNone(resolve_current_pick(bet, offers))


def _resp(status, data, headers=None):
    r = mock.Mock()
    r.status_code = status
    r.headers = headers or {}
    r.json.return_value = data
    r.text = ''
    return r


class RateLimitTests(SimpleTestCase):
    def test_retry_after_429(self):
        sleeps = []
        client = RateLimitedClient(requests_per_minute=6000, max_backoff=10,
                                   sleep_fn=sleeps.append)
        with mock.patch('parley_engine.services.requests.request',
                        side_effect=[_resp(429, {}, {'Retry-After': '1'}),
                                     _resp(200, {'ok': True})]):
            status, data, _ = client.request('GET', 'http://test')
        self.assertEqual(status, 200)
        self.assertTrue(data['ok'])
        self.assertTrue(any(s >= 1 for s in sleeps))

    def test_place_5xx_is_ambiguous(self):
        sleeps = []
        client = RateLimitedClient(requests_per_minute=6000, max_backoff=1,
                                   sleep_fn=sleeps.append)
        with mock.patch('parley_engine.services.requests.request',
                        return_value=_resp(500, {'err': 'x'})):
            with self.assertRaises(AmbiguousPlacement):
                client.request('POST', 'http://test', idempotent=False)


class PlaceEnvelopeTests(SimpleTestCase):
    def _client(self):
        return RateLimitedClient(requests_per_minute=6000, max_backoff=1,
                                 sleep_fn=lambda s: None)

    def test_success_returns_place_request_id(self):
        client = self._client()
        with mock.patch('parley_engine.services.requests.request',
                        side_effect=[_resp(200, {'status': 'SUCCESS',
                                                 'validSession': True}),
                                     _resp(200, {'status': 'SUCCESS',
                                                 'coupon': {'couponRef': 1}})]):
            ok, res, req = validate_and_place(client, 'tok', {'stake': 1})
        self.assertTrue(ok)
        self.assertEqual(res['coupon']['couponRef'], 1)
        self.assertTrue(req)

    def test_success_without_coupon_ref_is_ambiguous(self):
        client = self._client()
        with mock.patch('parley_engine.services.requests.request',
                        side_effect=[_resp(200, {'status': 'SUCCESS',
                                                 'validSession': True}),
                                     _resp(200, {'status': 'SUCCESS'})]):
            with self.assertRaises(AmbiguousPlacement) as ctx:
                validate_and_place(client, 'tok', {'stake': 1})
        self.assertTrue(ctx.exception.request_id)

    def test_place_5xx_carries_request_id(self):
        client = self._client()
        with mock.patch('parley_engine.services.requests.request',
                        side_effect=[_resp(200, {'status': 'SUCCESS',
                                                 'validSession': True}),
                                     _resp(500, {'err': 'x'})]):
            with self.assertRaises(AmbiguousPlacement) as ctx:
                validate_and_place(client, 'tok', {'stake': 1})
        self.assertTrue(ctx.exception.request_id)

    def test_validate_rejected_has_no_request_id(self):
        client = self._client()
        with mock.patch('parley_engine.services.requests.request',
                        return_value=_resp(200, {'status': 'FAILED'})):
            ok, res, req = validate_and_place(client, 'tok', {'stake': 1})
        self.assertFalse(ok)
        self.assertEqual(res['stage'], 'validate')
        self.assertEqual(req, '')


class DuplicateGuardTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin', email='admin-dup@test.local', password='x')
        self.cfg = ParleyEngineConfig.objects.create(
            usuario=self.user, activo=True, dry_run=True,
            capital_inicial=100000, stake=500)
        self.dia = date(2026, 10, 30)

    def _coupon(self, oids=(11, 22)):
        c = ParleyCoupon.objects.create(
            usuario=self.user, coupon_ref=500001, is_motor=False,
            dia=self.dia, stake=500, status='WON', n_legs=len(oids))
        for i, oid in enumerate(oids, start=1):
            ParleyCouponLeg.objects.create(
                coupon=c, position=i, event_id=100 + i,
                mercado='Total de Tiros', seleccion=f'Outcome {oid}',
                linea=None, outcome_id=oid)
        return c

    def _legs(self, oids=(11, 22)):
        return [
            {'id': i, 'evento': 100 + i,
             'mercado': 'Total de Tiros', 'seleccion': f'Over {i}',
             'current_offer': {'outcome_id': oid, 'market_label':
                               'Total de Tiros', 'label': f'Outcome {oid}',
                               'line': None}}
            for i, oid in enumerate(oids, start=1)]

    def test_outcome_signature_detects_duplicate(self):
        self._coupon()
        sigs = coupon_signatures(self.user, timezone.now() - timedelta(hours=48))
        self.assertTrue(is_duplicate_candidate(self._legs(), sigs))

    def test_other_combination_is_not_duplicate(self):
        self._coupon()
        sigs = coupon_signatures(self.user, timezone.now() - timedelta(hours=48))
        self.assertFalse(is_duplicate_candidate(self._legs((33, 44)), sigs))

    def test_motor_coupon_also_counts(self):
        c = ParleyCoupon.objects.create(
            usuario=self.user, coupon_ref=500002, is_motor=True,
            dia=self.dia, stake=500, status='OPEN', n_legs=2)
        ParleyCouponLeg.objects.create(
            coupon=c, position=1, event_id=101, mercado='M', seleccion='S',
            outcome_id=11)
        ParleyCouponLeg.objects.create(
            coupon=c, position=2, event_id=102, mercado='M', seleccion='S',
            outcome_id=22)
        sigs = coupon_signatures(self.user, timezone.now() - timedelta(hours=48))
        self.assertTrue(is_duplicate_candidate(self._legs(), sigs))


class LedgerTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin', email='admin-ledger@test.local', password='x')
        self.cfg = ParleyEngineConfig.objects.create(
            usuario=self.user, activo=True, dry_run=True,
            capital_inicial=1000, stake=500)

    def test_ledger_placement_and_settlement_idempotent(self):
        c = ParleyCoupon.objects.create(
            usuario=self.user, coupon_ref=9001, is_motor=True,
            stake=500, status='OPEN', n_legs=2)
        self.assertEqual(ledger_balance(self.user, self.cfg), 1000)
        record_ledger(self.user, 'PLACEMENT', -500, coupon=c)
        self.assertEqual(ledger_balance(self.user, self.cfg), 500)
        record_settlement_if_needed(c, 300)
        self.assertEqual(ledger_balance(self.user, self.cfg), 800)
        record_settlement_if_needed(c, 300)
        self.assertEqual(ledger_balance(self.user, self.cfg), 800)
        self.assertEqual(
            ParleyLedger.objects.filter(coupon=c, tipo='SETTLEMENT').count(), 1)


def _history_coupon(ref=999001):
    return {
        'couponRef': ref,
        'placedDate': '2026-10-29T21:49:18.911Z',
        'couponRows': [
            {'index': 0, 'outcomeId': 11, 'status': 'WON', 'playedOdds': 1930},
            {'index': 1, 'outcomeId': 22, 'status': 'WON', 'playedOdds': 3100},
        ],
        'outcomes': [
            {'outcomeId': 11, 'eventId': 101, 'betOfferId': 1001,
             'label': 'Más de 30.5', 'line': 30500, 'status': 'WON'},
            {'outcomeId': 22, 'eventId': 102, 'betOfferId': 1002,
             'label': 'Memphis Grizzlies +1.5', 'line': 1500, 'status': 'WON'},
        ],
        'events': [
            {'eventId': 101, 'homeName': 'A', 'awayName': 'B',
             'sport': 'FOOTBALL', 'eventGroups': [{'name': 'Liga A'}]},
            {'eventId': 102, 'homeName': 'C', 'awayName': 'D',
             'sport': 'BASKETBALL', 'eventGroups': [{'name': 'NBA'}]},
        ],
        'betOffers': [
            {'betOfferId': 1001,
             'criterion': 'Total de Tiros (Resuelta usando Opta Data)'},
            {'betOfferId': 1002,
             'criterion': 'Hándicap de Puntos - Prórroga incluida'},
        ],
        'bets': [{
            'betRef': 123, 'betStatus': 'WON', 'stake': 500000,
            'payout': 2991500, 'potentialPayout': 2991500,
            'playedOdds': 5983, 'couponRowIndexes': [0, 1],
        }],
    }


class SyncHistoryTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin', email='admin-sync@test.local', password='x')
        self.cfg = ParleyEngineConfig.objects.create(
            usuario=self.user, activo=True, dry_run=True,
            capital_inicial=100000, stake=500)

    def test_manual_combo_all_legs(self):
        c = upsert_history_coupon(self.user, _history_coupon())
        self.assertIsNotNone(c)
        self.assertEqual(c.n_legs, 2)
        self.assertEqual(c.sport, 'MIXED')
        self.assertEqual(c.leg_rows.count(), 2)
        self.assertIn('Tiros', c.leg_rows.get(position=1).mercado)
        self.assertFalse(c.is_motor)

    def test_stale_legs_removed_when_coupon_shrinks(self):
        c = ParleyCoupon.objects.create(
            usuario=self.user, coupon_ref=999001, is_motor=True,
            stake=500, status='OPEN', n_legs=3)
        for pos, oid in ((1, 11), (2, 22), (3, 33)):
            ParleyCouponLeg.objects.create(
                coupon=c, position=pos, event_id=100 + pos,
                mercado='Viejo', seleccion=f'Vieja {pos}', outcome_id=oid)
        upsert_history_coupon(self.user, _history_coupon())
        c.refresh_from_db()
        self.assertEqual(c.n_legs, 2)
        self.assertEqual(c.leg_rows.count(), 2)
        self.assertFalse(c.leg_rows.filter(position=3).exists())

    def test_motor_combo_settles_ledger_once(self):
        c = ParleyCoupon.objects.create(
            usuario=self.user, coupon_ref=999001, is_motor=True,
            stake=500, status='OPEN', n_legs=2)
        record_ledger(self.user, 'PLACEMENT', -500, coupon=c)
        upsert_history_coupon(self.user, _history_coupon())
        c.refresh_from_db()
        self.assertEqual(c.status, 'WON')
        self.assertEqual(c.payout, 2991.5)
        self.assertEqual(
            ParleyLedger.objects.filter(coupon=c, tipo='SETTLEMENT').count(), 1)
        upsert_history_coupon(self.user, _history_coupon())
        self.assertEqual(
            ParleyLedger.objects.filter(coupon=c, tipo='SETTLEMENT').count(), 1)


class PanelTests(TestCase):
    def test_panel_shows_all_legs(self):
        user = get_user_model().objects.create_user(
            username='admin', email='admin-panel@test.local', password='x')
        c = ParleyCoupon.objects.create(
            usuario=user, coupon_ref=888001, is_motor=True,
            dia=date(2026, 10, 29), placed_date=timezone.now(),
            stake=500, payout=1000, status='WON', n_legs=2,
            played_odds=2.0, sport='FOOTBALL')
        ParleyCouponLeg.objects.create(
            coupon=c, position=1, home_team='A', away_team='B',
            mercado='Total de goles', seleccion='Más de 2.5', linea=2.5,
            cuota_colocada=2.0, estado_final='WON')
        ParleyCouponLeg.objects.create(
            coupon=c, position=2, home_team='C', away_team='D',
            mercado='Ambos Equipos Marcarán', seleccion='Sí',
            cuota_colocada=1.8, estado_final='WON')
        cli = Client()
        cli.force_login(user)
        resp = cli.get('/parleys/', secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '888001')
        self.assertContains(resp, 'Total de goles')
        self.assertContains(resp, 'Ambos Equipos Marcarán')

    def test_panel_hides_manual_coupons(self):
        user = get_user_model().objects.create_user(
            username='admin', email='admin-panel2@test.local', password='x')
        manual = ParleyCoupon.objects.create(
            usuario=user, coupon_ref=777001, is_motor=False,
            dia=date(2026, 10, 28), placed_date=timezone.now() - timedelta(days=2),
            stake=1000, status='WON', n_legs=2, sport='FOOTBALL')
        ParleyCouponLeg.objects.create(
            coupon=manual, position=1, home_team='A', away_team='B',
            mercado='Total de goles', seleccion='Más de 2.5',
            cuota_colocada=2.0, estado_final='WON')
        ParleyCouponLeg.objects.create(
            coupon=manual, position=2, home_team='C', away_team='D',
            mercado='Ambos Equipos Marcarán', seleccion='Sí',
            cuota_colocada=1.8, estado_final='WON')
        motor_ayer = ParleyCoupon.objects.create(
            usuario=user, coupon_ref=777002, is_motor=True,
            dia=date(2026, 10, 29), placed_date=timezone.now() - timedelta(days=1),
            stake=500, status='OPEN', n_legs=2, sport='FOOTBALL')
        ParleyCouponLeg.objects.create(
            coupon=motor_ayer, position=1, home_team='E', away_team='F',
            mercado='Total de goles', seleccion='Más de 1.5',
            cuota_colocada=1.5, estado_final='OPEN')
        ParleyCouponLeg.objects.create(
            coupon=motor_ayer, position=2, home_team='G', away_team='H',
            mercado='Ambos Equipos Marcarán', seleccion='No',
            cuota_colocada=2.0, estado_final='OPEN')
        excepcion = ParleyCoupon.objects.create(
            usuario=user, coupon_ref=13291906849, is_motor=False,
            dia=date(2026, 10, 29), placed_date=timezone.now() - timedelta(days=1),
            stake=500, payout=2991.5, status='WON', n_legs=2, sport='FOOTBALL')
        ParleyCouponLeg.objects.create(
            coupon=excepcion, position=1, home_team='I', away_team='J',
            mercado='Hándicap', seleccion='Memphis Grizzlies +1.5',
            cuota_colocada=2.0, estado_final='WON')
        ParleyCouponLeg.objects.create(
            coupon=excepcion, position=2, home_team='K', away_team='L',
            mercado='Total de puntos', seleccion='Más de 220.5',
            cuota_colocada=1.8, estado_final='WON')
        cli = Client()
        cli.force_login(user)
        resp = cli.get('/parleys/', secure=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, '777002')
        self.assertContains(resp, '13291906849')
        self.assertNotContains(resp, '777001')


class CommandDryRunTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin', email='admin-cmd@test.local', password='x')
        self.cfg = ParleyEngineConfig.objects.create(
            usuario=self.user, activo=True, dry_run=True,
            capital_inicial=100000, stake=500, max_legs=2, ev_gate=0.8)

    @mock.patch('parley_engine.management.commands.run_real_parleys.LOCK_PATH',
                '/tmp/opencode/test_real_parleys.lock')
    @mock.patch('parley_engine.management.commands.run_real_parleys.Command._sync',
                return_value=0)
    @mock.patch('parley_engine.management.commands.run_real_parleys.enrich_pool')
    @mock.patch('parley_engine.management.commands.run_real_parleys.pool_autobet')
    @mock.patch('parley_engine.management.commands.run_real_parleys.fit_rows')
    def test_dry_run_counts_without_writing(self, fit, pool, enrich, _sync):
        fit.return_value = [(60 if i % 2 else 40, 'WIN' if i % 2 else 'LOSE')
                            for i in range(100)]
        dedup = {('e1', 'm', 's'): {'id': 1}, ('e2', 'm', 's'): {'id': 2}}
        pool.return_value = (dedup, {'101': [('e1', 'm', 's')],
                                     '102': [('e2', 'm', 's')]}, 0)
        enrich.return_value = ([
            [{'id': 1, 'evento': 101, 'home': 'A', 'away': 'B', 'liga': 'L',
              'mercado': 'M', 'seleccion': 'S', 'cuota': 2.0, 'prob': 60,
              'cuota_actual': 2.0, 'current_offer': {'outcome_id': 11}}],
            [{'id': 2, 'evento': 102, 'home': 'C', 'away': 'D', 'liga': 'L',
              'mercado': 'M', 'seleccion': 'S', 'cuota': 2.0, 'prob': 60,
              'cuota_actual': 2.0, 'current_offer': {'outcome_id': 22}}],
        ], 0)
        call_command('run_real_parleys')
        run = ParleyRun.objects.latest('id')
        self.assertEqual(run.modo, 'DRY')
        self.assertEqual(run.n_candidates, 1)
        self.assertEqual(run.n_would_place, 1)
        self.assertEqual(run.n_placed, 0)
        self.assertEqual(ParleyCoupon.objects.filter(is_motor=True).count(), 0)
        self.assertEqual(ParleyLedger.objects.count(), 0)
        # La ventana debe ser de partidos futuros: [ahora, ahora + 24 h].
        args, _ = pool.call_args
        self.assertEqual(args[0], self.user.pk)
        self.assertLessEqual(abs((args[1] - timezone.now()).total_seconds()), 30)
        self.assertEqual(args[2] - args[1], timedelta(hours=24))
        self.assertEqual(fit.call_args[0][1], args[1])


class CommandLiveMockTests(TestCase):
    """Ejercita la rama LIVE sin tocar BetPlay (validate/place mockeados)."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin', email='admin-live@test.local', password='x')
        self.cfg = ParleyEngineConfig.objects.create(
            usuario=self.user, activo=True, dry_run=False,
            capital_inicial=100000, stake=500, max_legs=2, ev_gate=0.8)
        from auto_betting.models import AutoBetConfig
        AutoBetConfig.objects.create(
            usuario=self.user, ticket='fake-ticket', punter_id='1')
        CapitalConfig.objects.create(
            usuario=self.user, modo=CapitalConfig.MODO_FIJO,
            balance_inicial=100000, ancla=timezone.now())

    @mock.patch('parley_engine.management.commands.run_real_parleys.LOCK_PATH',
                '/tmp/opencode/test_real_parleys_live.lock')
    @mock.patch('parley_engine.management.commands.run_real_parleys.Command._sync',
                return_value=0)
    @mock.patch('parley_engine.management.commands.run_real_parleys.validate_and_place')
    @mock.patch('parley_engine.management.commands.run_real_parleys.login')
    @mock.patch('parley_engine.management.commands.run_real_parleys.enrich_pool')
    @mock.patch('parley_engine.management.commands.run_real_parleys.pool_autobet')
    @mock.patch('parley_engine.management.commands.run_real_parleys.fit_rows')
    def test_live_creates_coupon_and_ledger(self, fit, pool, enrich, login_m,
                                            place_m, _sync):
        fit.return_value = [(60 if i % 2 else 40, 'WIN' if i % 2 else 'LOSE')
                            for i in range(100)]
        dedup = {('e1', 'm', 's'): {'id': 1}, ('e2', 'm', 's'): {'id': 2}}
        pool.return_value = (dedup, {'101': [('e1', 'm', 's')],
                                     '102': [('e2', 'm', 's')]}, 0)
        offer = {'outcome_id': 11, 'betoffer_id': 1001, 'odds': 2000,
                 'odds_decimal': 2.0, 'label': 'Más de', 'line': 2.5,
                 'type': 'OT_OVER', 'status': 'OPEN', 'criterion': {},
                 'betoffer_tags': [], 'display_order': 0,
                 'cashout_status': ''}
        offer2 = dict(offer, outcome_id=22, betoffer_id=1002)
        enrich.return_value = ([
            [{'id': 1, 'evento': 101, 'home': 'A', 'away': 'B', 'liga': 'L',
              'mercado': 'M', 'seleccion': 'Over 2.5', 'linea': 2.5,
              'cuota': 2.0, 'prob': 60, 'cuota_actual': 2.0,
              'market_label_actual': 'M', 'current_offer': offer}],
            [{'id': 2, 'evento': 102, 'home': 'C', 'away': 'D', 'liga': 'L',
              'mercado': 'M', 'seleccion': 'Over 2.5', 'linea': 2.5,
              'cuota': 2.0, 'prob': 60, 'cuota_actual': 2.0,
              'market_label_actual': 'M', 'current_offer': offer2}],
        ], 0)
        login_m.return_value = ('token', 'rk')
        place_m.return_value = (True, {'coupon': {
            'couponRef': 777001,
            'bets': [{'betRef': 888001, 'betStatus': 'OPEN',
                      'playedOdds': 4000, 'potentialPayout': 2000000}],
        }}, 'req-place-1')
        call_command('run_real_parleys')
        c = ParleyCoupon.objects.get(coupon_ref=777001)
        self.assertTrue(c.is_motor)
        self.assertEqual(c.n_legs, 2)
        self.assertEqual(c.leg_rows.count(), 2)
        self.assertEqual(c.status, 'OPEN')
        self.assertEqual(c.request_id, 'req-place-1')
        self.assertEqual(
            ParleyLedger.objects.filter(coupon=c, tipo='PLACEMENT').count(), 1)
        run = ParleyRun.objects.latest('id')
        self.assertEqual(run.n_placed, 1)
        self.assertEqual(run.ok, True)
        self.assertAlmostEqual(run.ledger_end, 99500.0)


def _ok_place(ref):
    return (True, {'coupon': {
        'couponRef': ref,
        'bets': [{'betRef': ref + 1, 'betStatus': 'OPEN',
                  'playedOdds': 4000, 'potentialPayout': 2000000}],
    }}, f'req-{ref}')


class CommandSafetyTests(TestCase):
    """Dedup, goteo y manejo de errores de colocación."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin', email='admin-safety@test.local', password='x')
        self.cfg = ParleyEngineConfig.objects.create(
            usuario=self.user, activo=True, dry_run=False,
            capital_inicial=100000, stake=500, max_legs=2, ev_gate=0.8,
            max_placements_per_run=5, place_interval_seconds=0)
        from auto_betting.models import AutoBetConfig
        AutoBetConfig.objects.create(
            usuario=self.user, ticket='fake-ticket', punter_id='1')
        CapitalConfig.objects.create(
            usuario=self.user, modo=CapitalConfig.MODO_FIJO,
            balance_inicial=100000, ancla=timezone.now())

    def _wire(self, fit, pool, enrich):
        fit.return_value = [(60 if i % 2 else 40, 'WIN' if i % 2 else 'LOSE')
                            for i in range(100)]
        dedup = {('e1', 'm', 's'): {'id': 1},
                 ('e2', 'm', 's'): {'id': 2},
                 ('e3', 'm', 's'): {'id': 3}}
        pool.return_value = (
            dedup,
            {'101': [('e1', 'm', 's')], '102': [('e2', 'm', 's')],
             '103': [('e3', 'm', 's')]}, 0)
        groups = []
        for n in (1, 2, 3):
            offer = {
                'outcome_id': 10 + n, 'betoffer_id': 1000 + n, 'odds': 2000,
                'odds_decimal': 2.0, 'label': 'Over 2.5', 'line': 2.5,
                'type': 'OT_OVER', 'status': 'OPEN', 'criterion': {},
                'betoffer_tags': [], 'display_order': 0, 'cashout_status': '',
            }
            groups.append([{
                'id': n, 'evento': 100 + n, 'home': f'H{n}', 'away': f'A{n}',
                'liga': 'L', 'mercado': 'M', 'seleccion': 'Over 2.5',
                'linea': 2.5, 'cuota': 2.0, 'prob': 60, 'cuota_actual': 2.0,
                'market_label_actual': 'M', 'current_offer': offer}])
        enrich.return_value = (groups, 0)

    @mock.patch('parley_engine.management.commands.run_real_parleys.find_history_match',
                return_value=None)
    @mock.patch('parley_engine.management.commands.run_real_parleys.time.sleep')
    @mock.patch('parley_engine.management.commands.run_real_parleys.LOCK_PATH',
                '/tmp/opencode/test_amb.lock')
    @mock.patch('parley_engine.management.commands.run_real_parleys.Command._sync',
                return_value=0)
    @mock.patch('parley_engine.management.commands.run_real_parleys.validate_and_place')
    @mock.patch('parley_engine.management.commands.run_real_parleys.login')
    @mock.patch('parley_engine.management.commands.run_real_parleys.enrich_pool')
    @mock.patch('parley_engine.management.commands.run_real_parleys.pool_autobet')
    @mock.patch('parley_engine.management.commands.run_real_parleys.fit_rows')
    def test_ambiguous_marks_run_not_ok_and_keeps_key(
            self, fit, pool, enrich, login_m, place_m, _sync, sleep_m, find_m):
        login_m.return_value = ('token', 'rk')
        self._wire(fit, pool, enrich)
        place_m.side_effect = AmbiguousPlacement('timeout', request_id='req-amb')
        call_command('run_real_parleys')
        run = ParleyRun.objects.latest('id')
        self.assertFalse(run.ok)
        self.assertIn('ambigua', run.error)
        pc = ParleyCoupon.objects.get(is_motor=True)
        self.assertEqual(pc.status, 'ERROR')
        self.assertEqual(pc.request_id, 'req-amb')
        self.assertEqual(ParleyLedger.objects.count(), 0)
        amb_key = pc.key
        amb_outcomes = {l['oid'] for l in pc.legs}
        # Segunda corrida: la key ambigua NO se reintenta; solo se colocan las
        # combinaciones nuevas (las otras dos parejas de eventos).
        place_m.reset_mock()
        place_m.side_effect = [_ok_place(730001), _ok_place(730002)]
        call_command('run_real_parleys')
        self.assertEqual(
            ParleyCoupon.objects.filter(key=amb_key).count(), 1)
        self.assertEqual(place_m.call_count, 2)
        for call in place_m.call_args_list:
            body = call.args[2]
            oids = {o['outcomeId'] for o in body['selectedOutcomes']}
            self.assertNotEqual(oids, amb_outcomes)
        self.assertEqual(ParleyRun.objects.latest('id').n_placed, 2)

    @mock.patch('parley_engine.management.commands.run_real_parleys.time.sleep')
    @mock.patch('parley_engine.management.commands.run_real_parleys.LOCK_PATH',
                '/tmp/opencode/test_429.lock')
    @mock.patch('parley_engine.management.commands.run_real_parleys.Command._sync',
                return_value=0)
    @mock.patch('parley_engine.management.commands.run_real_parleys.validate_and_place')
    @mock.patch('parley_engine.management.commands.run_real_parleys.login')
    @mock.patch('parley_engine.management.commands.run_real_parleys.enrich_pool')
    @mock.patch('parley_engine.management.commands.run_real_parleys.pool_autobet')
    @mock.patch('parley_engine.management.commands.run_real_parleys.fit_rows')
    def test_rate_limit_releases_key(
            self, fit, pool, enrich, login_m, place_m, _sync, sleep_m):
        login_m.return_value = ('token', 'rk')
        self._wire(fit, pool, enrich)
        place_m.side_effect = RateLimitError('HTTP 429 tras 5 intentos')
        call_command('run_real_parleys')
        self.assertFalse(ParleyRun.objects.latest('id').ok)
        self.assertEqual(ParleyCoupon.objects.filter(is_motor=True).count(), 0)
        self.assertEqual(ParleyLedger.objects.count(), 0)

    @mock.patch('parley_engine.management.commands.run_real_parleys.find_history_match',
                return_value=None)
    @mock.patch('parley_engine.management.commands.run_real_parleys.time.sleep')
    @mock.patch('parley_engine.management.commands.run_real_parleys.LOCK_PATH',
                '/tmp/opencode/test_noref.lock')
    @mock.patch('parley_engine.management.commands.run_real_parleys.Command._sync',
                return_value=0)
    @mock.patch('parley_engine.management.commands.run_real_parleys.validate_and_place')
    @mock.patch('parley_engine.management.commands.run_real_parleys.login')
    @mock.patch('parley_engine.management.commands.run_real_parleys.enrich_pool')
    @mock.patch('parley_engine.management.commands.run_real_parleys.pool_autobet')
    @mock.patch('parley_engine.management.commands.run_real_parleys.fit_rows')
    def test_success_without_coupon_ref_keeps_error(
            self, fit, pool, enrich, login_m, place_m, _sync, sleep_m, find_m):
        login_m.return_value = ('token', 'rk')
        self._wire(fit, pool, enrich)
        place_m.return_value = (True, {'coupon': {}}, 'req-x')
        call_command('run_real_parleys')
        self.assertFalse(ParleyRun.objects.latest('id').ok)
        pc = ParleyCoupon.objects.get(is_motor=True)
        self.assertEqual(pc.status, 'ERROR')
        self.assertEqual(pc.request_id, 'req-x')
        self.assertEqual(ParleyLedger.objects.count(), 0)

    @mock.patch('parley_engine.management.commands.run_real_parleys.time.sleep')
    @mock.patch('parley_engine.management.commands.run_real_parleys.LOCK_PATH',
                '/tmp/opencode/test_cap.lock')
    @mock.patch('parley_engine.management.commands.run_real_parleys.Command._sync',
                return_value=0)
    @mock.patch('parley_engine.management.commands.run_real_parleys.validate_and_place')
    @mock.patch('parley_engine.management.commands.run_real_parleys.login')
    @mock.patch('parley_engine.management.commands.run_real_parleys.enrich_pool')
    @mock.patch('parley_engine.management.commands.run_real_parleys.pool_autobet')
    @mock.patch('parley_engine.management.commands.run_real_parleys.fit_rows')
    def test_cap_limits_placements(
            self, fit, pool, enrich, login_m, place_m, _sync, sleep_m):
        login_m.return_value = ('token', 'rk')
        self._wire(fit, pool, enrich)
        self.cfg.max_placements_per_run = 1
        self.cfg.save(update_fields=['max_placements_per_run'])
        place_m.side_effect = [_ok_place(700001)]
        call_command('run_real_parleys')
        run = ParleyRun.objects.latest('id')
        self.assertEqual(run.n_placed, 1)
        self.assertEqual(run.n_candidates, 3)
        self.assertEqual(ParleyCoupon.objects.filter(is_motor=True).count(), 1)
        self.assertEqual(
            ParleyLedger.objects.filter(tipo='PLACEMENT').count(), 1)
        self.assertEqual(place_m.call_count, 1)

    @mock.patch('parley_engine.management.commands.run_real_parleys.time.sleep')
    @mock.patch('parley_engine.management.commands.run_real_parleys.LOCK_PATH',
                '/tmp/opencode/test_pace.lock')
    @mock.patch('parley_engine.management.commands.run_real_parleys.Command._sync',
                return_value=0)
    @mock.patch('parley_engine.management.commands.run_real_parleys.validate_and_place')
    @mock.patch('parley_engine.management.commands.run_real_parleys.login')
    @mock.patch('parley_engine.management.commands.run_real_parleys.enrich_pool')
    @mock.patch('parley_engine.management.commands.run_real_parleys.pool_autobet')
    @mock.patch('parley_engine.management.commands.run_real_parleys.fit_rows')
    def test_pacing_between_placements(
            self, fit, pool, enrich, login_m, place_m, _sync, sleep_m):
        login_m.return_value = ('token', 'rk')
        self._wire(fit, pool, enrich)
        self.cfg.max_placements_per_run = 2
        self.cfg.place_interval_seconds = 120
        self.cfg.save(update_fields=['max_placements_per_run',
                                     'place_interval_seconds'])
        place_m.side_effect = [_ok_place(710001), _ok_place(710002)]
        call_command('run_real_parleys')
        self.assertEqual(ParleyRun.objects.latest('id').n_placed, 2)
        sleep_m.assert_called()
        wait = sleep_m.call_args_list[0].args[0]
        self.assertTrue(0 < wait <= 120)

    @mock.patch('parley_engine.management.commands.run_real_parleys.time.sleep')
    @mock.patch('parley_engine.management.commands.run_real_parleys.LOCK_PATH',
                '/tmp/opencode/test_dup.lock')
    @mock.patch('parley_engine.management.commands.run_real_parleys.Command._sync',
                return_value=0)
    @mock.patch('parley_engine.management.commands.run_real_parleys.validate_and_place')
    @mock.patch('parley_engine.management.commands.run_real_parleys.login')
    @mock.patch('parley_engine.management.commands.run_real_parleys.enrich_pool')
    @mock.patch('parley_engine.management.commands.run_real_parleys.pool_autobet')
    @mock.patch('parley_engine.management.commands.run_real_parleys.fit_rows')
    def test_manual_duplicate_skipped(
            self, fit, pool, enrich, login_m, place_m, _sync, sleep_m):
        login_m.return_value = ('token', 'rk')
        self._wire(fit, pool, enrich)
        manual = ParleyCoupon.objects.create(
            usuario=self.user, coupon_ref=550001, is_motor=False,
            dia=timezone.localdate(), stake=500, status='WON', n_legs=2)
        ParleyCouponLeg.objects.create(
            coupon=manual, position=1, event_id=101, mercado='M',
            seleccion='Outcome 11', outcome_id=11)
        ParleyCouponLeg.objects.create(
            coupon=manual, position=2, event_id=102, mercado='M',
            seleccion='Outcome 12', outcome_id=12)
        place_m.side_effect = [_ok_place(720001), _ok_place(720002)]
        call_command('run_real_parleys')
        run = ParleyRun.objects.latest('id')
        self.assertEqual(run.n_placed, 2)  # solo las 2 combinaciones nuevas
        self.assertGreaterEqual(run.n_skipped, 1)
        self.assertEqual(place_m.call_count, 2)
        self.assertEqual(
            ParleyCoupon.objects.filter(is_motor=True).count(), 2)

    def test_reconcile_lists_error_coupons(self):
        from io import StringIO
        c = ParleyCoupon.objects.create(
            usuario=self.user, key='2026-10-30|1-2', is_motor=True,
            dia=timezone.localdate(), stake=500, status='ERROR', n_legs=2,
            request_id='req-rec', legs=[])
        out = StringIO()
        call_command('parley_reconcile', stdout=out)
        text = out.getvalue()
        self.assertIn(c.key, text)
        self.assertIn('req-rec', text)


class PoolWindowTests(TestCase):
    """El escaneo debe cubrir partidos que empiezan en las próximas 24 h."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin', email='admin-window@test.local', password='x')

    def _bet(self, evento_id, start_time, creado=None):
        from auto_betting.models import AutoBet
        b = AutoBet.objects.create(
            usuario=self.user, evento_id=evento_id,
            home_team=f'H{evento_id}', away_team=f'A{evento_id}',
            liga='L', start_time=start_time,
            mercado='Total de goles', seleccion='Over 2.5',
            cuota=2.0, corners_predichos=10, predicta_prob=55.0,
            edge=5.0, ev=0.1)
        if creado is not None:
            AutoBet.objects.filter(pk=b.pk).update(creado=creado)
        return b

    def test_window_uses_match_start_not_pick_creation(self):
        from parley_engine.services import pool_autobet
        now = timezone.now()
        started = self._bet(9101, now - timedelta(hours=1))
        soon = self._bet(9102, now + timedelta(hours=2))
        later = self._bet(9103, now + timedelta(hours=23, minutes=59))
        beyond = self._bet(9104, now + timedelta(hours=25))
        old_pick = self._bet(9105, now + timedelta(hours=5),
                             creado=now - timedelta(days=4))
        dedup, eventos, _ = pool_autobet(
            self.user.pk, now, now + timedelta(hours=24), [])
        ids = {l['id'] for l in dedup.values()}
        self.assertNotIn(started.pk, ids)
        self.assertNotIn(beyond.pk, ids)
        self.assertIn(soon.pk, ids)
        self.assertIn(later.pk, ids)
        self.assertIn(old_pick.pk, ids)
        self.assertEqual(len(eventos), 3)


class ReconcileAmbiguousTests(TestCase):
    """El ambiguo se resuelve contra el historial, sin duplicar ni reintentar."""

    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username='admin', email='admin-rec@test.local', password='x')
        self.cfg = ParleyEngineConfig.objects.create(
            usuario=self.user, activo=True, dry_run=False,
            capital_inicial=100000, stake=500, max_legs=2, ev_gate=0.8,
            max_placements_per_run=5, place_interval_seconds=0)
        from auto_betting.models import AutoBetConfig
        AutoBetConfig.objects.create(
            usuario=self.user, ticket='fake-ticket', punter_id='1')
        CapitalConfig.objects.create(
            usuario=self.user, modo=CapitalConfig.MODO_FIJO,
            balance_inicial=100000, ancla=timezone.now())

    def _wire(self, fit, pool, enrich):
        fit.return_value = [(60 if i % 2 else 40, 'WIN' if i % 2 else 'LOSE')
                            for i in range(100)]
        dedup = {('e1', 'm', 's'): {'id': 1},
                 ('e2', 'm', 's'): {'id': 2}}
        pool.return_value = (
            dedup, {'101': [('e1', 'm', 's')], '102': [('e2', 'm', 's')]}, 0)
        groups = []
        for n in (1, 2):
            offer = {
                'outcome_id': 10 + n, 'betoffer_id': 1000 + n, 'odds': 2000,
                'odds_decimal': 2.0, 'label': 'Over 2.5', 'line': 2.5,
                'type': 'OT_OVER', 'status': 'OPEN', 'criterion': {},
                'betoffer_tags': [], 'display_order': 0, 'cashout_status': '',
            }
            groups.append([{
                'id': n, 'evento': 100 + n, 'home': f'H{n}', 'away': f'A{n}',
                'liga': 'L', 'mercado': 'M', 'seleccion': 'Over 2.5',
                'linea': 2.5, 'cuota': 2.0, 'prob': 60, 'cuota_actual': 2.0,
                'market_label_actual': 'M', 'current_offer': offer}])
        enrich.return_value = (groups, 0)

    @mock.patch('parley_engine.management.commands.run_real_parleys.find_history_match')
    @mock.patch('parley_engine.management.commands.run_real_parleys.time.sleep')
    @mock.patch('parley_engine.management.commands.run_real_parleys.LOCK_PATH',
                '/tmp/opencode/test_rec.lock')
    @mock.patch('parley_engine.management.commands.run_real_parleys.Command._sync',
                return_value=0)
    @mock.patch('parley_engine.management.commands.run_real_parleys.validate_and_place')
    @mock.patch('parley_engine.management.commands.run_real_parleys.login')
    @mock.patch('parley_engine.management.commands.run_real_parleys.enrich_pool')
    @mock.patch('parley_engine.management.commands.run_real_parleys.pool_autobet')
    @mock.patch('parley_engine.management.commands.run_real_parleys.fit_rows')
    def test_ambiguous_found_in_history_is_linked(
            self, fit, pool, enrich, login_m, place_m, _sync, sleep_m,
            find_m):
        login_m.return_value = ('token', 'rk')
        self._wire(fit, pool, enrich)
        place_m.side_effect = AmbiguousPlacement('timeout', request_id='req-a')
        find_m.return_value = _history_coupon()
        call_command('run_real_parleys')
        run = ParleyRun.objects.latest('id')
        self.assertEqual(run.n_placed, 1)
        self.assertEqual(run.n_errors, 0)
        self.assertTrue(run.ok)
        c = ParleyCoupon.objects.get(coupon_ref=999001)
        self.assertTrue(c.is_motor)
        self.assertTrue(c.key)
        self.assertEqual(c.status, 'WON')
        self.assertEqual(c.n_legs, 2)
        self.assertEqual(c.leg_rows.count(), 2)
        self.assertFalse(ParleyCoupon.objects.filter(
            usuario=self.user, status='ERROR').exists())
        self.assertEqual(
            ParleyLedger.objects.filter(coupon=c, tipo='PLACEMENT').count(), 1)
        self.assertEqual(
            ParleyLedger.objects.filter(coupon=c, tipo='SETTLEMENT').count(), 1)
        self.assertAlmostEqual(ledger_balance(self.user, self.cfg), 102491.5)

    @mock.patch('parley_engine.management.commands.run_real_parleys.find_history_match')
    @mock.patch('parley_engine.management.commands.run_real_parleys.time.sleep')
    @mock.patch('parley_engine.management.commands.run_real_parleys.LOCK_PATH',
                '/tmp/opencode/test_rec_merge.lock')
    @mock.patch('parley_engine.management.commands.run_real_parleys.Command._sync',
                return_value=0)
    @mock.patch('parley_engine.management.commands.run_real_parleys.validate_and_place')
    @mock.patch('parley_engine.management.commands.run_real_parleys.login')
    @mock.patch('parley_engine.management.commands.run_real_parleys.enrich_pool')
    @mock.patch('parley_engine.management.commands.run_real_parleys.pool_autobet')
    @mock.patch('parley_engine.management.commands.run_real_parleys.fit_rows')
    def test_ambiguous_merges_with_sync_created_row(
            self, fit, pool, enrich, login_m, place_m, _sync, sleep_m,
            find_m):
        login_m.return_value = ('token', 'rk')
        self._wire(fit, pool, enrich)
        # El sync (corrido antes en la misma corrida real) ya creó la fila
        # "manual" para el cupón que en realidad colocó el motor.
        ParleyCoupon.objects.create(
            usuario=self.user, coupon_ref=999001, is_motor=False,
            dia=timezone.localdate(), stake=500, status='WON', n_legs=2)
        place_m.side_effect = AmbiguousPlacement('5xx', request_id='req-m')
        find_m.return_value = _history_coupon()
        call_command('run_real_parleys')
        self.assertEqual(
            ParleyCoupon.objects.filter(coupon_ref=999001).count(), 1)
        c = ParleyCoupon.objects.get(coupon_ref=999001)
        self.assertTrue(c.is_motor)
        self.assertTrue(c.key)
        self.assertEqual(ParleyCoupon.objects.filter(
            usuario=self.user).count(), 1)
        self.assertEqual(
            ParleyLedger.objects.filter(coupon=c, tipo='PLACEMENT').count(), 1)
        self.assertAlmostEqual(ledger_balance(self.user, self.cfg), 102491.5)


class MultiUserCommandTests(TestCase):
    """Sin usuario hardcodeado: dos cuentas reciben sus propios parleys.

    user1 ya tiene ParleyEngineConfig; user2 solo tiene AutoBetConfig activo y
    debe recibir una config LIVE creada automáticamente con los parámetros del
    admin (100.000 COP, stake 500, sin tope).
    """

    def setUp(self):
        from auto_betting.models import AutoBetConfig
        self.u1 = get_user_model().objects.create_user(
            username='u1', email='u1@test.local', password='x')
        self.u2 = get_user_model().objects.create_user(
            username='u2', email='u2@test.local', password='x')
        self.c1 = ParleyEngineConfig.objects.create(
            usuario=self.u1, activo=True, dry_run=False,
            capital_inicial=100000, stake=500, max_legs=2, ev_gate=0.8,
            max_placements_per_run=0, place_interval_seconds=0)
        for u in (self.u1, self.u2):
            AutoBetConfig.objects.create(
                usuario=u, ticket=f'fake-{u.username}', punter_id=str(u.pk))
            CapitalConfig.objects.create(
                usuario=u, modo=CapitalConfig.MODO_FIJO,
                balance_inicial=100000, ancla=timezone.now())

    @mock.patch('parley_engine.management.commands.run_real_parleys.LOCK_PATH',
                '/tmp/opencode/test_real_parleys_multi.lock')
    @mock.patch('parley_engine.management.commands.run_real_parleys.Command._sync',
                return_value=0)
    @mock.patch('parley_engine.management.commands.run_real_parleys.validate_and_place')
    @mock.patch('parley_engine.management.commands.run_real_parleys.login')
    @mock.patch('parley_engine.management.commands.run_real_parleys.enrich_pool')
    @mock.patch('parley_engine.management.commands.run_real_parleys.pool_autobet')
    @mock.patch('parley_engine.management.commands.run_real_parleys.fit_rows')
    def test_two_users_get_their_own_coupon(self, fit, pool, enrich, login_m,
                                            place_m, _sync):
        fit.return_value = [(60 if i % 2 else 40, 'WIN' if i % 2 else 'LOSE')
                            for i in range(100)]
        login_m.return_value = ('token', 'rk')
        place_m.side_effect = [_ok_place(811001), _ok_place(811002)]

        def _groups(base):
            offers = []
            for n in (0, 1):
                offers.append({
                    'outcome_id': base + n, 'betoffer_id': base + 100 + n,
                    'odds': 2000, 'odds_decimal': 2.0, 'label': 'Over 2.5',
                    'line': 2.5, 'type': 'OT_OVER', 'status': 'OPEN',
                    'criterion': {}, 'betoffer_tags': [], 'display_order': 0,
                    'cashout_status': '',
                })
            out = []
            for n, offer in enumerate(offers):
                out.append([{
                    'id': base + n, 'evento': base + 500 + n,
                    'home': f'H{base}{n}', 'away': f'A{base}{n}',
                    'liga': 'L', 'mercado': 'M', 'seleccion': 'Over 2.5',
                    'linea': 2.5, 'cuota': 2.0, 'prob': 60,
                    'cuota_actual': 2.0, 'market_label_actual': 'M',
                    'current_offer': offer,
                }])
            return out, 0

        def _pool(uid, start, end, frases):
            base = 1 if uid == self.u1.pk else 21
            dedup = {
                (f'e{base}', 'M', 'Over 2.5'): {'id': base},
                (f'e{base + 1}', 'M', 'Over 2.5'): {'id': base + 1},
            }
            return dedup, {str(base): [], str(base + 1): []}, 0

        pool.side_effect = _pool
        enrich.side_effect = [_groups(1), _groups(21)]
        call_command('run_real_parleys')

        # user2 recibe config creada con los mismos parámetros del admin.
        cfg2 = ParleyEngineConfig.objects.get(usuario=self.u2)
        self.assertTrue(cfg2.activo)
        self.assertFalse(cfg2.dry_run)
        self.assertEqual(cfg2.capital_inicial, 100000)
        self.assertEqual(cfg2.stake, 500)
        self.assertEqual(cfg2.max_placements_per_run, 0)

        # Un cupón por usuario, sin mezclar dueños.
        self.assertEqual(ParleyCoupon.objects.filter(
            usuario=self.u1, is_motor=True).count(), 1)
        self.assertEqual(ParleyCoupon.objects.filter(
            usuario=self.u2, is_motor=True).count(), 1)
        self.assertEqual(ParleyRun.objects.filter(usuario=self.u1).count(), 1)
        self.assertEqual(ParleyRun.objects.filter(usuario=self.u2).count(), 1)
        self.assertAlmostEqual(ledger_balance(self.u1, self.c1), 99500.0)
        self.assertAlmostEqual(ledger_balance(self.u2, cfg2), 99500.0)


class ParleyWhatsAppMessageTests(SimpleTestCase):
    def test_message_has_totals_and_legs(self):
        from notificaciones.services import construir_mensaje_parleys
        msg = construir_mensaje_parleys([{
            'stake': 500, 'odds': 4.0, 'payout': 2000,
            'legs': [
                {'h': 'A', 'a': 'B', 'm': 'Total de goles',
                 's': 'Over 2.5', 'c': 2.0},
                {'h': 'C', 'a': 'D', 'm': 'Total de tiros',
                 's': 'Over 9.5', 'c': 2.0},
            ],
        }])
        self.assertIn('1 parley colocado', msg)
        self.assertIn('500 COP c/u', msg)
        self.assertIn('A vs B', msg)
        self.assertIn('Over 2.5', msg)
        self.assertIn('2,000 COP', msg)
