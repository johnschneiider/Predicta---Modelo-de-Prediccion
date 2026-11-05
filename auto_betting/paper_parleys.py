# -*- coding: utf-8 -*-
"""PAPERPARLEYS — motor de parlays en papel sobre el motor real (AutoBet).

Reglas (aprobadas 2026-10-22, backtest R8s):
- Fit de deciles: winrate observado por decil de `predicta_prob` sobre las
  bets RESUELTAS (WIN/LOSE) del MISMO usuario creadas en días ANTERIORES
  (sin leakage: el fit de un día solo ve la historia previa).
- Pool del día: picks deduplicados por (evento, mercado, seleccion);
  se excluyen mercados junk (frases de PPConfig.junk_mercados) y picks
  sin prob o cuota.
- Parlay: TODAS las combinaciones de 2..max_legs patas (config), a lo sumo
  una pata por evento, con EV conjunto >= ev_gate:
      EV = prod(p_rec_i) * prod(cuota_i)   (p_rec = decil recalibrado)
  Sin tope de parlays por día (decisión del dueño).
- Stake plana PPConfig.stake (COP). Idempotente por key 'dia|autobet_ids'.
- Trazabilidad: PPGenRun (fit, volumen, tiempos) + legs JSON + PPParleyLeg.

Liquidación (`settle()`): lee el estado real de cada leg en AutoBet.
- todas WIN -> GANADO, payout = stake * prod(cuotas)
- alguna LOSE -> PERDIDO, payout = 0
- pata VOID/ERROR/CASHOUT -> la combinada se reduce a las piernas útiles
  restantes (regla de combinada); si no queda ninguna -> PUSH (stake
  devuelto, payout = stake)
- alguna pierna aún OPEN -> sigue PENDIENTE
"""
import bisect
import itertools
import math
import time

from django.conf import settings
from django.db import connection, reset_queries
from django.utils import timezone
from psycopg2.extras import execute_values

from .models import PPConfig, PPGenRun, PPParley, PPParleyLeg

SQL_USERS = """
  SELECT usuario_id, COUNT(*) FROM auto_betting_autobet
  WHERE (creado AT TIME ZONE 'America/Bogota')::date = %s
  GROUP BY usuario_id
"""
SQL_POOL = """
  SELECT id, evento_id, mercado, seleccion, cuota, predicta_prob, liga,
         estado, home_team, away_team, start_time, edge
  FROM auto_betting_autobet
  WHERE usuario_id = %s
    AND (creado AT TIME ZONE 'America/Bogota')::date = %s
    AND cuota IS NOT NULL AND predicta_prob IS NOT NULL AND cuota > 0
    AND estado IN ('WIN','LOSE','OPEN')
  ORDER BY id
"""
SQL_FIT = """
  SELECT predicta_prob, estado
  FROM auto_betting_autobet
  WHERE usuario_id = %s AND predicta_prob IS NOT NULL
    AND estado IN ('WIN','LOSE')
    AND (creado AT TIME ZONE 'America/Bogota')::date < %s
  ORDER BY id
"""


def get_cfg():
    cfg, _ = PPConfig.objects.get_or_create(pk=1)
    return cfg


def junk_phrases(cfg=None):
    cfg = cfg or get_cfg()
    return [ln.strip().lower() for ln in (cfg.junk_mercados or '').splitlines()
            if ln.strip()]


def build_lookup(fit_rows, min_fit):
    """Bordes de deciles + winrate por decil -> funcion p_rec(prob)."""
    n = len(fit_rows)
    if n < min_fit:
        return None, {'n_fit': n}
    data = sorted((p, 1 if e == 'WIN' else 0) for p, e in fit_rows)
    probs = [p for p, _ in data]
    edges = [probs[min(int(math.ceil(k * n / 10.0)), n) - 1] for k in range(1, 10)]
    buckets = [[0, 0] for _ in range(10)]
    for p, w in data:
        idx = min(bisect.bisect_left(edges, p), 9)
        buckets[idx][0] += 1
        buckets[idx][1] += w
    rates = [None if tot < 20 else (w / tot) for tot, w in buckets]
    gwr = sum(w for _, w in data) / n

    def p_rec(pr):
        idx = min(bisect.bisect_left(edges, pr), 9)
        r = rates[idx]
        return r if r is not None else gwr

    return p_rec, {'n_fit': n, 'edges': edges, 'rates': rates, 'gwr': gwr}


def _fit_rows(usuario_id, dia):
    with connection.cursor() as c:
        c.execute(SQL_FIT, [usuario_id, dia])
        return c.fetchall()


def _pool(usuario_id, dia, frases, max_edge=None):
    """Picks del dia dedup por (evento, mercado, seleccion): (dedup, eventos, skip)."""
    with connection.cursor() as c:
        c.execute(SQL_POOL, [usuario_id, dia])
        rows = c.fetchall()
    dedup = {}
    eventos = {}
    n_skip = 0
    for (bid, ev_id, mkt, sel, cuota, prob, liga, estado, home, away, st, edge) in rows:
        mm = (mkt or '').lower()
        if any(f in mm for f in frases):
            n_skip += 1
            continue
        if max_edge is not None and (edge is None or float(edge) > max_edge):
            n_skip += 1
            continue
        key = (ev_id, mkt, sel)
        if key in dedup:
            n_skip += 1
            continue
        dedup[key] = dict(id=bid, evento=ev_id, mercado=mkt, seleccion=sel,
                          cuota=float(cuota), prob=float(prob), liga=liga or '',
                          estado=estado, home=home, away=away,
                          start_time=st)
        eventos.setdefault(ev_id or f'ev{bid}', []).append(key)
    return dedup, eventos, n_skip


def _enum_parlays(dedup, eventos, p_rec, ev_gate, max_legs,
                  min_legs=2, max_ev=None):
    """DFS: por evento, ninguna o 1 pata. Cada parlay valido se emite una vez.

    Generador: no materializa todas las combinaciones en memoria.
    """
    groups = []
    for ev in sorted(eventos):
        opts = []
        for key in eventos[ev]:
            l = dedup[key]
            pr = p_rec(l['prob'])
            l['pr'] = pr
            q = pr * l['cuota']
            if q > 0:
                opts.append((l, q, pr))
        groups.append(opts)
    n_groups = len(groups)
    if n_groups < min_legs:
        return
    qmax_rest = [0.0] * (n_groups + 1)
    for i in range(n_groups - 1, -1, -1):
        b = qmax_rest[i + 1]
        for _, q, _ in groups[i]:
            if q > b:
                b = q
        qmax_rest[i] = b

    def rec(i, prod, legs, count):
        if count + (n_groups - i) < min_legs:
            return
        if prod * qmax_rest[i] < ev_gate:
            # ya no puede crecer mas: unico completamiento valido es parar
            if count >= min_legs and prod >= ev_gate and (
                    max_ev is None or prod <= max_ev):
                yield list(legs)
            return
        if i == n_groups:
            if count >= min_legs and prod >= ev_gate and (
                    max_ev is None or prod <= max_ev):
                yield list(legs)
            return
        if prod * qmax_rest[i + 1] >= ev_gate or prod >= ev_gate:
            yield from rec(i + 1, prod, legs, count)
        if count < max_legs:
            for (l, q, pr) in groups[i]:
                nq = prod * q
                if nq >= ev_gate or nq * qmax_rest[i + 1] >= ev_gate:
                    legs.append(l)
                    yield from rec(i + 1, nq, legs, count + 1)
                    legs.pop()
        return

    yield from rec(0, 1.0, [], 0)


def generate_day(dia, usuario_ids=None, modo='LIVE', cfg=None, args='',
                 max_legs=None, min_legs=None, max_edge=None, max_ev=None,
                 ev_gate=None):
    """Genera (idempotente) los parlays del dia dado. Devuelve dict resumen.

    Cada corrida deja una fila PPGenRun con el fit y los volumenes usados.
    """
    cfg = cfg or get_cfg()
    frases = junk_phrases(cfg)
    ev_gate = float(ev_gate if ev_gate is not None else cfg.ev_gate)
    max_legs = int(max_legs or cfg.max_legs)
    min_legs = int(min_legs or 2)
    max_edge = None if max_edge is None else float(max_edge)
    max_ev = None if max_ev is None else float(max_ev)
    stake = int(cfg.stake)
    min_fit = int(cfg.min_fit)

    if usuario_ids is None:
        with connection.cursor() as c:
            c.execute(SQL_USERS, [dia])
            usuario_ids = [u for (u, _) in c.fetchall()]

    run = PPGenRun.objects.create(modo=modo, dia=dia, args=args)
    res = {'modo': modo, 'dia': str(dia), 'usuarios': len(usuario_ids),
           'generados': 0, 'existentes': 0, 'candidatos': 0, 'run_id': run.id}
    t0 = time.time()
    try:
        for uid in usuario_ids:
            p_rec, info = build_lookup(_fit_rows(uid, dia), min_fit)
            if p_rec is None:
                continue
            dedup, eventos, n_skip = _pool(uid, dia, frases, max_edge)
            if len(eventos) < min_legs:
                continue
            combos = _enum_parlays(dedup, eventos, p_rec, ev_gate, max_legs,
                                   min_legs, max_ev)
            primero = next(combos, None)
            if primero is None:
                continue
            run.fit_edges = info['edges']
            run.fit_rates = info['rates']
            run.fit_gwr = info['gwr']
            run.n_fit = info['n_fit']
            run.n_pool = len(dedup)
            run.n_eventos = len(eventos)
            run.n_skipped = n_skip
            run.save(update_fields=['fit_edges', 'fit_rates', 'fit_gwr',
                                    'n_fit', 'n_pool', 'n_eventos', 'n_skipped'])
            nuevos, existentes, n_combos = _upsert_parlays(
                uid, dia, itertools.chain((primero,), combos), stake, run)
            res['generados'] += nuevos
            res['existentes'] += existentes
            res['candidatos'] += n_combos
            if settings.DEBUG:
                reset_queries()
        run.ok = True
    except Exception as exc:
        run.ok = False
        run.error = f'{type(exc).__name__}: {exc}'
        raise
    finally:
        run.n_generados = res['generados']
        run.elapsed_ms = int((time.time() - t0) * 1000)
        run.finished_at = timezone.now()
        run.save(update_fields=['ok', 'error', 'elapsed_ms', 'finished_at',
                                'n_generados'])
    return res


def _upsert_parlays(uid, dia, combos, stake, run, chunk_size=2000):
    """Inserta por lotes; `combos` puede ser un generador (memoria acotada)."""
    nuevos = 0
    existentes = 0
    candidatos = 0
    batch = []

    def flush(batch):
        nonlocal nuevos, existentes
        objs = [PPParley(
            usuario_id=uid, dia=dia, key=key, gen_run=run,
            n_legs=len(legs_sorted), cuota_producto=cuota_prod,
            prob_producto=prob_prod, ev=cuota_prod * prob_prod, stake=stake,
            legs=[{'i': l['id'], 'ev': l['evento'], 'h': l['home'],
                   'a': l['away'], 'lg': l['liga'], 'm': l['mercado'],
                   's': l['seleccion'], 'c': l['cuota'], 'p': l['prob'],
                   'pr': l['pr'], 'e': l['estado']} for l in legs_sorted],
        ) for (key, legs_sorted, cuota_prod, prob_prod) in batch]
        if not objs:
            return
        keys = [o.key for o in objs]
        existing = set(PPParley.objects.filter(key__in=keys)
                       .values_list('key', flat=True))
        to_create = [o for o in objs if o.key not in existing]
        existentes += len(objs) - len(to_create)
        nuevos += len(to_create)
        if to_create:
            PPParley.objects.bulk_create(to_create, batch_size=2000,
                                         ignore_conflicts=True)
            made = PPParley.objects.filter(
                key__in=[o.key for o in to_create]).in_bulk(field_name='key')
            leg_rows = []
            for o in to_create:
                p = made.get(o.key)
                if p is None:
                    continue
                for pos, dleg in enumerate(o.legs, start=1):
                    leg_rows.append(PPParleyLeg(
                        parley_id=p.id, autobet_id=dleg['i'], posicion=pos,
                        evento_id=dleg['ev'], home_team=dleg['h'],
                        away_team=dleg['a'], liga=dleg['lg'],
                        mercado=dleg['m'], seleccion=dleg['s'],
                        cuota=dleg['c'], prob=dleg['p'], p_rec=dleg['pr'],
                        q=dleg['pr'] * dleg['c'], estado_gen=dleg['e']))
            if leg_rows:
                PPParleyLeg.objects.bulk_create(leg_rows, batch_size=4000)
        if settings.DEBUG:
            reset_queries()

    for legs in combos:
        candidatos += 1
        legs_sorted = sorted(legs, key=lambda l: l['id'])
        ids = [l['id'] for l in legs_sorted]
        key = f'{dia}|{"-".join(str(i) for i in ids)}'
        cuota_prod = 1.0
        prob_prod = 1.0
        for l in legs_sorted:
            cuota_prod *= l['cuota']
            prob_prod *= l['pr']
        batch.append((key, legs_sorted, cuota_prod, prob_prod))
        if len(batch) >= chunk_size:
            flush(batch)
            batch = []
    if batch:
        flush(batch)
    return nuevos, existentes, candidatos


def settle(dia_hasta=None):
    """Liquida PENDIENTE cuyas piernas ya estan asentadas en AutoBet.

    dia_hasta: solo atiende parlays con dia < dia_hasta (hoy no liquida).
    """
    SQL = """
      SELECT l.pid, l.stake, l.leg_id, l.cuota, a.estado
      FROM (
        SELECT p.id AS pid, p.stake, lg.id AS leg_id, lg.cuota, lg.autobet_id
        FROM auto_betting_ppparley p
        JOIN auto_betting_ppparleyleg lg ON lg.parley_id = p.id
        WHERE p.estado = 'PENDIENTE'
          AND (p.dia < %s OR %s IS NULL)
      ) l
      LEFT JOIN auto_betting_autobet a ON a.id = l.autobet_id
      ORDER BY l.pid
    """
    with connection.cursor() as c:
        c.execute(SQL, [dia_hasta, dia_hasta])
        rows = c.fetchall()
    by_parley = {}
    for (pid, stake, leg_id, cuota, estado) in rows:
        by_parley.setdefault(pid, []).append((leg_id, cuota, estado))
    n = n_won = n_lost = n_push = 0
    updates = []
    pids = []

    def flush():
        if not updates:
            return
        with connection.cursor() as c:
            execute_values(
                c.cursor,
                "UPDATE auto_betting_ppparley AS p SET estado=v.estado, "
                "payout=v.payout::double precision, settled_at=now(), "
                "nota=v.nota, actualizado=now() "
                "FROM (VALUES %s) AS v(estado, payout, nota, id) "
                "WHERE p.id = v.id::bigint",
                updates, template="(%s, %s, %s, %s)", page_size=1000)
            c.execute(
                "UPDATE auto_betting_ppparleyleg l SET estado_final=a.estado "
                "FROM auto_betting_autobet a WHERE a.id = l.autobet_id "
                "AND l.parley_id = ANY(%s)", [pids])
        updates.clear()
        pids.clear()
        if settings.DEBUG:
            reset_queries()

    for pid, legs in by_parley.items():
        state_ids = [st for (_, _, st) in legs]
        if any(st in (None, 'OPEN') for st in state_ids):
            continue
        BAD = 'LOSE'
        TRASH = ('VOID', 'ERROR', 'CASHOUT')
        utiles = [(lg, cu) for (lg, cu, st) in legs if st not in TRASH]
        voids = len(legs) - len(utiles)
        if not utiles:
            payout, est = None, 'PUSH'
        elif any(st == BAD for (_, _, st) in legs):
            payout, est = 0.0, 'PERDIDO'
        else:
            prod = 1.0
            for (_, cu) in utiles:
                prod *= cu
            payout, est = stake * prod, 'GANADO'
        nota = f'void={voids}' if voids else ''
        updates.append((est, payout, nota, pid))
        pids.append(pid)
        n += 1
        if est == 'GANADO':
            n_won += 1
        elif est == 'PERDIDO':
            n_lost += 1
        else:
            n_push += 1
        if len(updates) >= 1000:
            flush()
    flush()
    return {'liquidos': n, 'ganados': n_won, 'perdidos': n_lost, 'push': n_push}
