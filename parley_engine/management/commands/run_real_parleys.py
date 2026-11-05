# -*- coding: utf-8 -*-
"""Motor de parleys reales, independiente del motor de apuestas simples.

Uso:
  manage.py run_real_parleys                 # todos los usuarios activos (config manda)
  manage.py run_real_parleys --live          # fuerza colocación real
  manage.py run_real_parleys --dry-run       # fuerza simulación
  manage.py run_real_parleys --usuario 9     # solo ese usuario
  manage.py run_real_parleys --usuario 9 --live --limit 1
  manage.py run_real_parleys --live --max-placements 3 --interval 60
  manage.py run_real_parleys --sync-only     # solo liquidar/sincronizar

Reglas de seguridad:
- Ventana de 24 h hacia adelante: combina apuestas reales (AutoBet) OPEN de
  Predicta cuyos partidos se juegan entre ahora y dentro de 24 horas
  (``start_time``), no picks recientes.
- Multi-usuario: corre para cada usuario con ``ParleyEngineConfig.activo`` y
  para todo ``AutoBetConfig`` activo que aún no tenga config (se le crea una
  config LIVE con el mismo bankroll/stake que el admin).
- Una sola corrida a la vez (lock propio).
- Colocación por goteo: tope ``max_placements_per_run`` (0 = sin tope) y pausa
  ``place_interval_seconds`` entre apuestas (config, sobreescribible por CLI).
- Sin duplicados: key idempotente ``ids`` + firmas de todos los cupones de la
  cuenta (manuales incluidos). En LIVE, si el sync inicial falla no se apuesta.
- 429/503 en validate o 429 en place = no colocada → se libera la key.
- Timeout/5xx/SUCCESS sin couponRef = ambigua → se busca el cupón real en el
  historial (mismas patas + stake, 2 intentos con 5 s de margen) y se enlaza
  solo; si no aparece, la key se conserva y queda para ``parley_reconcile``.
- Un fallo de un usuario no aborta la corrida de los demás.
- Al terminar, sync del historial de cada usuario y resumen por WhatsApp.

No toca AutoBet, AutoBetConfig, DailyCounter ni paperparleys.
"""
import fcntl
import logging
import math
import os
import time
from datetime import date, datetime, timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError
from django.utils import timezone

from auto_betting.models import AutoBet, AutoBetConfig
from auto_betting.services import login
from capital.models import CapitalConfig
from capital.services import bankroll_cop

from parley_engine.models import (
    ParleyCoupon, ParleyCouponLeg, ParleyEngineConfig, ParleyLedger, ParleyRun,
)
from parley_engine.services import (
    AmbiguousPlacement, RateLimitError, RateLimitedClient, build_coupon_body,
    build_lookup, coupon_signatures, enrich_pool, enum_parlays,
    find_history_match, fit_rows, is_duplicate_candidate, junk_phrases,
    ledger_balance, make_key, pool_autobet, reconcile_ambiguous_coupon,
    record_ledger, sync_history, validate_and_place,
)

logger = logging.getLogger('parley_engine')
LOCK_PATH = '/var/www/predicta.com.co/logs/real_parleys.lock'

# Configuración por defecto para usuarios nuevos: igual que el admin.
DEFAULT_CONFIG = dict(
    activo=True,
    dry_run=False,
    stake=500,
    capital_inicial=100000,
    ev_gate=0.80,
    max_legs=2,
    min_fit=50,
    max_placements_per_run=0,
    place_interval_seconds=30,
)


def _legs_json(legs):
    out = []
    for l in legs:
        o = l.get('current_offer') or {}
        out.append({
            'i': l['id'], 'ev': l['evento'], 'h': l.get('home', ''),
            'a': l.get('away', ''), 'lg': l.get('liga', ''),
            'm': l.get('market_label_actual') or l.get('mercado', ''),
            's': l.get('seleccion', ''), 'line': l.get('linea'),
            'co': l.get('cuota'), 'c': l.get('cuota_actual'),
            'p': l.get('prob'), 'pr': l.get('pr'), 'q': l.get('q'),
            'oid': o.get('outcome_id'), 'boid': o.get('betoffer_id'),
            'off': o.get('odds_decimal'),
        })
    return out


def _create_legs(coupon, legs):
    for i, l in enumerate(legs, start=1):
        o = l.get('current_offer') or {}
        ab_id = l['id'] if AutoBet.objects.filter(pk=l['id']).exists() else None
        ParleyCouponLeg.objects.create(
            coupon=coupon, autobet_id=ab_id, position=i,
            event_id=l.get('evento'), home_team=l.get('home', ''),
            away_team=l.get('away', ''), liga=l.get('liga', ''),
            mercado=l.get('market_label_actual') or l.get('mercado', ''),
            seleccion=l.get('seleccion', ''), linea=l.get('linea'),
            cuota_original=l.get('cuota'), cuota_colocada=l.get('cuota_actual'),
            prob=l.get('prob'), p_rec=l.get('pr'), q=l.get('q'),
            outcome_id=o.get('outcome_id'), betoffer_id=o.get('betoffer_id'),
            estado_final='OPEN')


def _legs_para_aviso(coupon):
    """Normaliza patas desde el JSON del cupón (motor o reconciliado)."""
    out = []
    for l in (coupon.legs or []):
        out.append({
            'h': l.get('h') or l.get('home_team', ''),
            'a': l.get('a') or l.get('away_team', ''),
            'm': l.get('m') or l.get('mercado', ''),
            's': l.get('s') or l.get('seleccion', ''),
            'c': l.get('c') or l.get('cuota_colocada'),
        })
    return out


def _parleys_para_aviso(run):
    """Parleys confirmados de esta corrida, listos para el mensaje WhatsApp."""
    out = []
    for c in run.coupons.filter(coupon_ref__isnull=False).order_by('id'):
        out.append({
            'coupon_ref': c.coupon_ref,
            'stake': c.stake,
            'odds': c.played_odds,
            'payout': c.potential_payout,
            'legs': _legs_para_aviso(c),
        })
    return out


class Command(BaseCommand):
    help = 'Genera y coloca parleys reales para todos los usuarios elegibles.'

    def add_arguments(self, parser):
        parser.add_argument('--usuario', type=int, default=0,
                            help='Solo ese usuario (pk). 0 = todos los elegibles.')
        parser.add_argument('--live', action='store_true',
                            help='Fuerza colocación real (requiere config activa).')
        parser.add_argument('--dry-run', action='store_true',
                            help='Fuerza simulación aunque la config sea LIVE.')
        parser.add_argument('--limit', type=int, default=0,
                            help='Máximo de colocaciones por usuario (0=sin tope).')
        parser.add_argument('--max-placements', type=int, default=None,
                            help='Tope de colocaciones por usuario (por defecto config; 0=sin tope).')
        parser.add_argument('--interval', type=int, default=None,
                            help='Segundos entre colocaciones (por defecto config).')
        parser.add_argument('--fecha', type=str, default='',
                            help='Simula la corrida al final de ese día Bogotá '
                                 '(YYYY-MM-DD), mirando 24 h hacia adelante.')
        parser.add_argument('--sync-only', action='store_true',
                            help='Solo sincroniza historial/ledger, no genera parleys.')
        parser.add_argument('--no-whatsapp', action='store_true',
                            help='No envía el resumen por WhatsApp (pruebas/operación).')

    # ─────────────────────────────────────────────────────────────────────
    # Orquestación multi-usuario
    # ─────────────────────────────────────────────────────────────────────

    def handle(self, *args, **opts):
        if opts['live'] and opts['dry_run']:
            raise CommandError('--live y --dry-run son excluyentes')
        if opts['sync_only'] and (opts['live'] or opts['dry_run']):
            raise CommandError('--sync-only no se combina con --live/--dry-run')

        # Lock propio: nunca dos corridas de parleys a la vez.
        os.makedirs(os.path.dirname(LOCK_PATH), exist_ok=True)
        lock = open(LOCK_PATH, 'w')
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            self.stdout.write('parleys: ya hay una corrida en curso')
            lock.close()
            return

        try:
            try:
                dia, cutoff_start = self._window(opts)
            except ValueError:
                raise CommandError(
                    f'Fecha inválida: {opts["fecha"]!r} (usar YYYY-MM-DD)')
            cutoff_end = cutoff_start + timedelta(hours=24)
            users = self._target_users(opts)
            if not users:
                self.stdout.write('parleys: sin usuarios candidatos')
                return
            for user in users:
                try:
                    self._run_for_user(
                        user, opts, dia, cutoff_start, cutoff_end)
                except Exception as exc:
                    logger.exception('run_real_parleys falló para %s', user)
                    self.stderr.write(
                        f'parleys {user.username}: {type(exc).__name__}: {exc}')
        finally:
            lock.close()

    def _window(self, opts):
        """Devuelve (día Bogotá, inicio de la ventana de 24 h)."""
        if opts['fecha']:
            dia = date.fromisoformat(opts['fecha'])
            # Simula la corrida al final de ese día (Bogotá): partidos de
            # las siguientes 24 h.
            cutoff_start = timezone.make_aware(datetime.combine(
                dia + timedelta(days=1), datetime.min.time()))
        else:
            dia = timezone.localdate()
            cutoff_start = timezone.now()
        return dia, cutoff_start

    def _target_users(self, opts):
        """Usuarios elegibles: config parley activa + AutoBetConfig activo.

        No hay usuario hardcodeado. Si un AutoBetConfig activo aún no tiene
        ParleyEngineConfig, se incluye para creársela en la rama LIVE.
        """
        User = get_user_model()
        if opts['usuario']:
            user = User.objects.filter(pk=opts['usuario']).first()
            if user is None:
                raise CommandError(f'Usuario {opts["usuario"]} no existe')
            return [user]

        users = []
        seen = set()
        for cfg in (ParleyEngineConfig.objects.filter(activo=True)
                    .select_related('usuario').order_by('usuario_id')):
            if cfg.usuario_id not in seen:
                users.append(cfg.usuario)
                seen.add(cfg.usuario_id)
        for ac in (AutoBetConfig.objects.filter(activo=True)
                   .exclude(ticket='').exclude(punter_id='')
                   .select_related('usuario').order_by('usuario_id')):
            if ac.usuario_id not in seen:
                users.append(ac.usuario)
                seen.add(ac.usuario_id)
        return users

    def _is_live(self, config, opts):
        if opts['dry_run']:
            return False
        if opts['live']:
            return True
        if config is None:
            return True  # usuario nuevo: se crea LIVE, igual que el admin
        return not config.dry_run

    def _run_for_user(self, user, opts, dia, cutoff_start, cutoff_end):
        ac = AutoBetConfig.objects.filter(usuario=user).first()
        config = ParleyEngineConfig.objects.filter(usuario=user).first()

        if config is not None and not config.activo:
            self.stdout.write(f'parleys {user.username}: motor inactivo')
            return
        live = self._is_live(config, opts)
        if config is None and not live:
            self.stdout.write(f'parleys {user.username}: sin config parley (dry)')
            return

        stake_ref = config.stake if config else DEFAULT_CONFIG['stake']
        if live:
            if ac is None or not ac.activo or not ac.ticket or not ac.punter_id:
                self.stdout.write(
                    f'parleys {user.username}: sin AutoBetConfig activo/vinculado')
                return
            cap = CapitalConfig.objects.filter(usuario=user).first()
            if cap is None or cap.balance_inicial is None or cap.ancla is None:
                self.stdout.write(
                    f'parleys {user.username}: sin balance declarado')
                return
            bankroll = bankroll_cop(user)
            if bankroll is None or bankroll < stake_ref:
                self.stdout.write(
                    f'parleys {user.username}: saldo insuficiente '
                    f'({bankroll if bankroll is not None else "?"} < {stake_ref})')
                return
            token, _ = login(ac.ticket, ac.punter_id)
            if not token:
                self.stdout.write(
                    f'parleys {user.username}: login BetPlay falló (ticket vencido)')
                return
        else:
            token = None

        if opts['sync_only']:
            if config is None:
                self.stdout.write(
                    f'parleys {user.username}: sin config parley (sync)')
                return
            self._sync_only(user, config)
            return

        if config is None:
            config = ParleyEngineConfig.objects.create(
                usuario=user, **DEFAULT_CONFIG)
            self.stdout.write(
                f'parleys {user.username}: config creada '
                f'(LIVE, 100.000 COP, stake 500, sin tope)')

        if config.stake <= 0:
            self.stdout.write(
                f'parleys {user.username}: stake inválido ({config.stake})')
            return

        max_placements = (opts['max_placements']
                          if opts['max_placements'] is not None
                          else config.max_placements_per_run)
        if max_placements < 0:
            raise CommandError('--max-placements no puede ser negativo')
        place_interval = max(0, opts['interval']
                             if opts['interval'] is not None
                             else config.place_interval_seconds)
        cap = max_placements
        if opts['limit'] and (cap == 0 or opts['limit'] < cap):
            cap = opts['limit']

        args = ' '.join(f'{k}={v}' for k, v in opts.items() if v)
        run = ParleyRun.objects.create(
            usuario=user, modo='LIVE' if live else 'DRY', dia=dia,
            args=f'{args} user={user.username}'[:300])
        t0 = time.time()
        client = RateLimitedClient(
            requests_per_minute=config.requests_per_minute,
            max_backoff=config.max_backoff_seconds,
            timeout=config.request_timeout)
        try:
            run.ledger_start = ledger_balance(user, config)
            # 1) sincronizar historial/ledger antes de decidir capital.
            # En LIVE, sin historial fresco no se puede garantizar que no
            # haya duplicados: se aborta la corrida en vez de apostar a ciegas.
            try:
                self._sync(user, client, run)
            except Exception as exc:
                logger.warning('sync inicial falló (%s): %s', user.username, exc)
                run.n_errors += 1
                if live:
                    run.ok = False
                    run.error = f'Sync inicial falló; no se coloca a ciegas: {exc}'
                    self.stderr.write(f'parleys {user.username}: {run.error}')
                    return

            # 2) fit histórico (solo apuestas anteriores a la ventana)
            p_rec, info = build_lookup(
                fit_rows(user.id, cutoff_start), config.min_fit)
            if p_rec is None:
                run.error = f'Sin fit suficiente ({info})'
                self.stdout.write(f'parleys {user.username}: {run.error}')
                return

            # 3) pool de picks OPEN con partido en las próximas 24 h
            frases = junk_phrases(config)
            dedup, eventos, n_skip = pool_autobet(
                user.id, cutoff_start, cutoff_end, frases)
            run.n_picks = len(dedup)
            run.n_eventos = len(eventos)
            run.n_skipped += n_skip
            if len(eventos) < 2:
                self.stdout.write(
                    f'parleys {user.username}: sin combinables '
                    f'({len(dedup)} picks, {len(eventos)} eventos)')
                return

            # 4) cuotas actuales por pick (rate limit)
            offers_cache = {}
            groups, skipped = enrich_pool(
                dedup, eventos, client, offers_cache)
            run.n_skipped += skipped
            if len(groups) < 2:
                self.stdout.write(
                    f'parleys {user.username}: sin combinables con cuota '
                    f'actual ({len(groups)} eventos)')
                return

            enum_groups = []
            for opts_ in groups:
                g = []
                for leg in opts_:
                    pr = p_rec(leg['prob'])
                    q = pr * leg['cuota_actual']
                    if q <= 0:
                        continue
                    leg = dict(leg)
                    leg['pr'] = pr
                    leg['q'] = q
                    g.append((leg, q))
                if g:
                    enum_groups.append(g)
            if len(enum_groups) < 2:
                return

            # 5) todas las combinaciones que pasan EV con cuota actual
            candidates = list(enum_parlays(
                enum_groups, config.ev_gate, config.max_legs, min_legs=2))
            candidates.sort(key=lambda legs: -math.prod(l['q'] for l in legs))
            run.n_candidates = len(candidates)
            # Firmas de todos los cupones de la cuenta: nada se duplica,
            # venga del motor, Predicta o de una colocación manual, aunque el
            # pick se haya creado hace días.
            signatures = coupon_signatures(user)
            self.stdout.write(
                f'parleys {user.username}: {len(candidates)} candidatos · '
                f'{len(dedup)} picks · {len(enum_groups)} eventos · '
                f'fit={info.get("n_fit")} · {"LIVE" if live else "DRY"} · '
                f'máx {cap or "sin tope"} colocaciones · pausa '
                f'{place_interval}s')

            # 6) presupuesto: ledger interno y balance paralelo real.
            # `bankroll_cop` NO descuenta los parleys hasta el próximo sync
            # de historial; el ledger sí. Se usa el menor de los dos y se
            # descuenta localmente en cada colocación.
            dry_balance = ledger_balance(user, config)
            budget = dry_balance
            if live:
                bankroll_now = bankroll_cop(user)
                if bankroll_now is None:
                    run.error = 'Sin balance paralelo para colocar'
                    self.stdout.write(f'parleys {user.username}: {run.error}')
                    return
                budget = min(float(dry_balance), float(bankroll_now))

            last_place_ts = None
            for legs in candidates:
                key = make_key(legs)
                if ParleyCoupon.objects.filter(key=key).exists():
                    run.n_pending += 1
                    continue
                if is_duplicate_candidate(legs, signatures):
                    # Ya existe un cupón con estas mismas patas hoy (manual,
                    # Predicta o motor): no se vuelve a apostar.
                    run.n_skipped += 1
                    self.stdout.write(
                        f'  SKIP dup {key} · ya existe cupón con estas patas')
                    continue
                ahora = timezone.now()
                if any(l.get('start_time') and l['start_time'] <= ahora
                       for l in legs):
                    # El partido arrancó entre el escaneo y la colocación.
                    run.n_skipped += 1
                    continue
                if budget < config.stake:
                    run.n_skipped += 1
                    self.stdout.write(
                        f'parleys {user.username}: capital agotado '
                        f'(disponible {budget:.2f} < {config.stake})')
                    break

                if not live:
                    budget -= config.stake
                    run.n_would_place += 1
                    self.stdout.write(
                        f'  DRY {key} · {len(legs)} patas · EV '
                        f'{math.prod(l["q"] for l in legs):.3f} · '
                        f'cuota {math.prod(l["cuota_actual"] for l in legs):.3f}')
                    if cap and run.n_would_place >= cap:
                        self.stdout.write(
                            f'parleys: tope DRY de {cap} alcanzado')
                        break
                    continue

                # Poco a poco: pausa real entre colocaciones (no entre lecturas).
                if last_place_ts is not None and place_interval > 0:
                    wait = place_interval - (time.monotonic() - last_place_ts)
                    if wait > 0:
                        self.stdout.write(
                            f'parleys: pausa {wait:.0f}s antes de la siguiente')
                        time.sleep(wait)

                # Placeholder: evita duplicar si la respuesta es ambigua.
                try:
                    pc = ParleyCoupon.objects.create(
                        usuario=user, key=key, is_motor=True, dia=dia,
                        stake=config.stake, n_legs=len(legs),
                        legs=_legs_json(legs), engine_run=run, status='OPEN')
                except IntegrityError:
                    # Otra corrida insertó la misma key: ya está cubierta.
                    run.n_pending += 1
                    continue
                body = build_coupon_body(legs, config.stake)
                try:
                    ok, res, place_req_id = validate_and_place(
                        client, token, body)
                except AmbiguousPlacement as exc:
                    # No se sabe si quedó colocada. Se intenta reconciliar de
                    # inmediato contra el historial (mismas patas + stake); si
                    # aparece, se enlaza y se contabiliza. Si no aparece, la
                    # key se conserva (jamás se duplica) y queda para revisión.
                    pc.request_id = exc.request_id or ''
                    pc.save(update_fields=['request_id'])
                    target = self._try_reconcile(
                        client, token, pc, legs, config,
                        run.started_at - timedelta(minutes=2))
                    if target is not None:
                        budget -= config.stake
                        run.n_placed += 1
                        self.stdout.write(
                            f'  RECONCILIADO {key} · '
                            f'coupon={target.coupon_ref} · {target.status}')
                        break
                    pc.status = 'ERROR'
                    pc.save(update_fields=['status'])
                    run.n_errors += 1
                    run.ok = False
                    run.error = (f'Colocación ambigua sin match en historial '
                                 f'(requestId={exc.request_id or "?"}): {exc}')
                    self.stderr.write(f'parleys {user.username}: {run.error}')
                    break
                except RateLimitError as exc:
                    # 429/503 en validate o 429 en place: BetPlay NO procesó
                    # la apuesta; es seguro liberar la key para el próximo run.
                    pc.delete()
                    run.n_errors += 1
                    run.ok = False
                    run.n_rate_limits = len(client.events)
                    run.error = f'Rate limit: {exc}'
                    self.stderr.write(f'parleys {user.username}: {run.error}')
                    break

                if not ok:
                    # Validación/colocación rechazada: se libera para reintentar.
                    pc.delete()
                    run.n_errors += 1
                    stage = (res or {}).get('stage')
                    logger.warning('place rechazado %s (%s): %s',
                                   user.username, stage, res)
                    continue

                coup = res.get('coupon') or {}
                if not coup.get('couponRef'):
                    # Defensa extra: SUCCESS sin cupón no es confirmable.
                    pc.request_id = place_req_id or ''
                    pc.save(update_fields=['request_id'])
                    target = self._try_reconcile(
                        client, token, pc, legs, config,
                        run.started_at - timedelta(minutes=2))
                    if target is not None:
                        budget -= config.stake
                        run.n_placed += 1
                        self.stdout.write(
                            f'  RECONCILIADO {key} · '
                            f'coupon={target.coupon_ref} · {target.status}')
                        break
                    pc.status = 'ERROR'
                    pc.save(update_fields=['status'])
                    run.n_errors += 1
                    run.ok = False
                    run.error = (f'Respuesta sin couponRef y sin match en '
                                 f'historial (requestId={place_req_id or "?"})')
                    self.stderr.write(f'parleys {user.username}: {run.error}')
                    break
                bet = (coup.get('bets') or [{}])[0]
                pc.coupon_ref = coup.get('couponRef')
                pc.bet_ref = bet.get('betRef')
                pc.status = bet.get('betStatus') or 'OPEN'
                pc.played_odds = (bet.get('playedOdds') or 0) / 1000.0 or None
                pc.potential_payout = (
                    bet.get('potentialPayout') or 0) / 1000.0 or None
                pc.request_id = place_req_id or ''
                pc.save()
                _create_legs(pc, legs)
                record_ledger(
                    user, 'PLACEMENT', -config.stake, coupon=pc, nota=key)
                budget -= config.stake
                run.n_placed += 1
                last_place_ts = time.monotonic()
                self.stdout.write(
                    f'  OK {key} · coupon={pc.coupon_ref} · '
                    f'{len(legs)} patas · cuota {pc.played_odds} · '
                    f'payout {pc.potential_payout}')
                if cap and run.n_placed >= cap:
                    self.stdout.write(
                        f'parleys: tope de {cap} colocaciones alcanzado')
                    break

            # 7) sync final: llena placed_date y liquida lo que ya resolvió.
            if live:
                try:
                    self._sync(user, client, run)
                except Exception as exc:
                    logger.warning(
                        'sync final parleys %s falló: %s', user.username, exc)
                self._notify(user, run, opts)
        except Exception as exc:
            run.ok = False
            run.error = f'{type(exc).__name__}: {exc}'
            logger.exception('run_real_parleys falló para %s', user.username)
        finally:
            try:
                run.n_rate_limits = len(client.events)
                run.ledger_end = ledger_balance(user, config)
                run.elapsed_ms = int((time.time() - t0) * 1000)
                run.finished_at = timezone.now()
                run.save()
            except Exception:
                logger.exception('no se pudo guardar ParleyRun')

    def _notify(self, user, run, opts):
        if opts.get('no_whatsapp'):
            return
        parleys = _parleys_para_aviso(run)
        if not parleys:
            return
        try:
            from notificaciones.services import notificar_parleys
            res = notificar_parleys(
                user, parleys,
                referencia=run.started_at.isoformat(timespec='seconds'))
            self.stdout.write(
                f'parleys {user.username}: WhatsApp {res} '
                f'({len(parleys)} cupones)')
        except Exception as exc:
            logger.warning(
                'WhatsApp parleys %s falló: %s', user.username, exc)

    def _try_reconcile(self, client, token, pc, legs, config, since):
        """Tras una respuesta ambigua, busca el cupón real en el historial.

        Dos intentos con 5 s de margen (el historial puede tardar en reflejar
        la apuesta). Devuelve el cupón enlazado o None.
        """
        for attempt in (1, 2):
            match = None
            try:
                match = find_history_match(
                    client, token, legs, config.stake, since)
            except Exception as exc:
                logger.warning(
                    'reconciliación ambigua falló (intento %s): %s',
                    attempt, exc)
            if match:
                try:
                    return reconcile_ambiguous_coupon(pc, match)
                except Exception:
                    logger.exception('no se pudo enlazar el cupón ambiguo')
                    return None
            if attempt == 1:
                time.sleep(5)
        return None

    def _sync(self, user, client, run=None):
        ac = AutoBetConfig.objects.filter(usuario=user).first()
        if not ac or not ac.ticket:
            return 0
        token, _ = login(ac.ticket, ac.punter_id)
        if not token:
            return 0
        return sync_history(user, client, token, range_size=1000)

    def _sync_only(self, user, config):
        client = RateLimitedClient(
            requests_per_minute=config.requests_per_minute,
            max_backoff=config.max_backoff_seconds,
            timeout=config.request_timeout)
        n = self._sync(user, client)
        self.stdout.write(
            f'parleys sync {user.username}: {n} cupones actualizados')
