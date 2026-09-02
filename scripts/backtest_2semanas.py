"""
Backtest 2 SEMANAS (18-Ago → 31-Ago 2026) — v2 con tolerancia a fallos.
- Masking por lote con copia de seguridad en JSON (recuperable ante crash).
- Reintentos en operaciones de DB (PostgreSQL SSL inestable bajo concurrencia).
- 6 workers de predicción en paralelo.
"""
import json
import math
import os
import sys
import time
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()

from datetime import timedelta

from django.db import connections

from football_data.models import Match
from value_betting.mapping import fuzzy_match_team

FIELDS = ('fthg', 'ftag', 'hthg', 'htag', 'hst', 'ast', 'hc', 'ac')
SAVE_DIR = '/tmp/backtest_actuals'


def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0 if k >= 0 else 0.0
    term = math.exp(-lam)
    s = term
    for i in range(1, int(k) + 1):
        term *= lam / i
        s += term
    return s


def p_over(line, lam):
    return 1.0 - poisson_cdf(math.floor(line), lam)


def p_under(line, lam):
    return poisson_cdf(math.floor(line), lam)


def web_engine(home, away, league):
    from ai_predictions.simple_models import SimplePredictionService, ModeloHibridoGeneral
    from ai_predictions.official_prediction_model import official_prediction_model
    from ai_predictions.corners_model import corners_model
    from ai_predictions.enhanced_both_teams_score import enhanced_both_teams_score_model
    from ai_predictions.shots_prediction_model import shots_prediction_model
    from ai_predictions.xg_shots_model import xg_shots_model

    all_preds = {}
    svc = SimplePredictionService()
    try:
        lst = svc.get_all_simple_predictions(home, away, league, 'goals_total')
        hyb = ModeloHibridoGeneral().predecir(home, away, league, 'goals_total')
        if hyb and hyb.get('prediction', 0) > 0:
            lst.append(hyb)
        if lst:
            all_preds['goals_total'] = lst
    except Exception:
        pass
    try:
        lst = []
        p1 = shots_prediction_model.predict_shots_on_target_total(home, away, league)
        if p1:
            lst.append(p1)
        p2 = xg_shots_model.predict_shots_on_target_total(home, away, league)
        if p2:
            lst.append(p2)
        if lst:
            all_preds['shots_on_target_total'] = lst
    except Exception:
        pass
    try:
        c = corners_model.predecir(home, away, league, 'corners_total')
        if c:
            all_preds['corners_total'] = [c]
    except Exception:
        pass
    try:
        lst = svc.get_all_simple_predictions(home, away, league, 'both_teams_score')
        p = enhanced_both_teams_score_model.predict(home, away, league)
        if p is not None:
            lst.append({'model_name': 'Enhanced Both Teams Score', 'prediction': float(p),
                        'confidence': 0.80, 'total_matches': 100})
        if lst:
            all_preds['both_teams_score'] = lst
    except Exception:
        pass

    return official_prediction_model.calculate_official_predictions(all_preds)


def autobetting_engine(home, away, league):
    from auto_betting.strategy import get_official_predictions
    return get_official_predictions(home, away, league)


def valuebetting_engine(home, away, league):
    from value_betting.services import generate_full_prediction
    return generate_full_prediction(home, away, league)


ENGINE_FNS = {'WEB': web_engine, 'AUTO': autobetting_engine, 'VALUE': valuebetting_engine}


def engine_worker(args):
    import logging
    logging.disable(logging.INFO)
    from django.db import connections
    connections.close_all()
    home, away, league_id, tag = args
    try:
        from football_data.models import League
        league = League.objects.get(id=league_id)
        return tag, ENGINE_FNS[tag](home, away, league)
    except Exception as e:
        return tag, 'ERR:' + str(e)[:120]


def retry(fn, tries=5, wait=3):
    for i in range(tries):
        try:
            return fn()
        except Exception as e:
            print(f'    [retry {i+1}] {type(e).__name__}: {e}', flush=True)
            connections.close_all()
            time.sleep(wait * (i + 1))
    raise RuntimeError('DB operation failed after retries')


def mask_results(cutoff_date):
    def _do():
        qs = Match.objects.filter(date__gte=cutoff_date)
        n = 0
        for m in qs:
            changed = False
            for f in FIELDS:
                if getattr(m, f) is not None:
                    setattr(m, f, None)
                    changed = True
            if changed:
                m.save(update_fields=list(FIELDS))
                n += 1
        return n
    return retry(_do)


def restore_results(cutoff_date, actuals):
    def _do():
        n = 0
        for m in Match.objects.filter(date__gte=cutoff_date):
            orig = actuals.get(str(m.id))
            if not orig:
                continue
            for f, v in orig.items():
                setattr(m, f, v)
            m.save(update_fields=list(FIELDS))
            n += 1
        return n
    return retry(_do)


OVERRIDES = {
    ('Osasuna', 'Getafe'): 904326,
    ('Cagliari', 'Inter'): 907354,
    ('Celta Vigo', 'Athletic Bilbao'): 904327,
    ('Corinthians-SP', 'Santos-SP'): 919422,
}


def find_match(h):
    ov = OVERRIDES.get((h.home_team, h.away_team))
    if ov:
        return Match.objects.get(id=ov)
    if not h.event_start_date:
        return None
    d = h.event_start_date.date()
    for delta in (-1, 0, 1):
        day = d + timedelta(days=delta)
        for m in Match.objects.filter(date=day):
            if (fuzzy_match_team(h.home_team, [m.home_team], threshold=0.6)
                    and fuzzy_match_team(h.away_team, [m.away_team], threshold=0.6)):
                return m
    return None


def side_of(s):
    s = s.strip().lower()
    if s.startswith('más') or s.startswith('mas'):
        return 'over'
    if s.startswith('menos'):
        return 'under'
    if s in ('sí', 'si'):
        return 'si'
    return 'no'


def main():
    from collections import defaultdict, Counter
    from auto_betting.models import HistorialApuesta, MarketFilterConfig
    from cuentas.models import Usuario

    admin = Usuario.objects.get(username='admin')
    bets = list(HistorialApuesta.objects.filter(
        usuario=admin, is_system=True,
        placed_date__date__gte='2026-08-18',
        placed_date__date__lte='2026-08-31',
        bet_status__in=['WON', 'LOST']).order_by('placed_date'))
    print(f'Apuestas asentadas (admin) 18→31 Ago: {len(bets)}', flush=True)

    mf = MarketFilterConfig.get_solo().as_market_filters()

    def threshold(h):
        merc = (h.mercado or '').lower()
        side = side_of(h.seleccion)
        if 'goles' in merc:
            return mf['goals_over']['min_p'] if side == 'over' else mf['goals_under']['min_p']
        if 'puerta' in merc:
            return (mf['shots_on_target_over']['min_p'] if side == 'over'
                    else mf['shots_on_target_under']['min_p'])
        if 'ambos' in merc:
            return mf['btts_si']['min_p'] if side == 'si' else mf['btts_no']['min_p']
        if 'esquina' in merc:
            return mf['corners_over']['min_p'] if side == 'over' else mf['corners_under']['min_p']
        return 0.55

    def actual_outcome(h, stats):
        side = side_of(h.seleccion)
        if 'ambos' in (h.mercado or '').lower():
            fh, fa = stats.get('fthg'), stats.get('ftag')
            if fh is None or fa is None:
                return None, 'sin resultado', False
            btts = fh > 0 and fa > 0
            return (btts if side == 'si' else not btts), f"res {fh}-{fa}", True
        if 'puerta' in (h.mercado or '').lower():
            hs, as_ = stats.get('hst'), stats.get('ast')
            if hs is None or as_ is None:
                return None, 'sin sot', False
            tot = hs + as_
            return (tot > h.linea, f"sot {tot}", True) if side == 'over' else (tot < h.linea, f"sot {tot}", True)
        if 'goles' in (h.mercado or '').lower():
            fh, fa = stats.get('fthg'), stats.get('ftag')
            if fh is None or fa is None:
                return None, 'sin resultado', False
            tot = fh + fa
            return (tot > h.linea, f"goles {tot}", True) if side == 'over' else (tot < h.linea, f"goles {tot}", True)
        if 'esquina' in (h.mercado or '').lower():
            hc, ac = stats.get('hc'), stats.get('ac')
            if hc is None or ac is None:
                return None, 'sin corners', False
            tot = hc + ac
            return (tot > h.linea, f"cor {tot}", True) if side == 'over' else (tot < h.linea, f"cor {tot}", True)
        return None, 'mercado no soportado', False

    os.makedirs(SAVE_DIR, exist_ok=True)

    from multiprocessing import Pool
    pool = Pool(processes=6)

    results = []
    skip = []
    batches = sorted({b.placed_date.date() for b in bets}, reverse=True)

    t0 = time.time()
    for bi, batch_date in enumerate(batches):
        batch_bets = [b for b in bets if b.placed_date.date() == batch_date]
        rows = []
        for b in batch_bets:
            m = find_match(b)
            if m is None:
                skip.append((b, 'sin match en DB'))
                continue
            stats = {f: getattr(m, f) for f in FIELDS}
            rows.append((b, m, stats))

        all_actuals = {str(m.id): {f: getattr(m, f) for f in FIELDS}
                       for m in Match.objects.filter(date__gte=batch_date)}
        save_path = os.path.join(SAVE_DIR, f'{batch_date}.json')
        with open(save_path, 'w') as fh:
            json.dump(all_actuals, fh)

        n_masked = mask_results(batch_date)

        jobs, order = [], {}
        for b, m, _stats in rows:
            for tag in ENGINE_FNS:
                j = (m.home_team, m.away_team, m.league_id, tag)
                if j not in order:
                    order[j] = len(jobs)
                    jobs.append(j)
        cache = {}
        if jobs:
            try:
                outs = pool.map(engine_worker, jobs, chunksize=2)
                for j, out in zip(jobs, outs):
                    cache[j] = out[1] if isinstance(out, tuple) and len(out) == 2 else out
            except Exception as e:
                print(f'  !! pool error: {e}', flush=True)

        for b, m, stats in rows:
            win, desc, evaluable = actual_outcome(b, stats)
            if not evaluable:
                skip.append((b, desc))
                continue
            side = side_of(b.seleccion)
            thr = threshold(b)
            stake_cop = (b.stake or 0) / 1000.0

            for tag in ENGINE_FNS:
                pred = cache.get((m.home_team, m.away_team, m.league_id, tag))
                if pred is None or (isinstance(pred, str) and pred.startswith('ERR')):
                    results.append({'sys': tag, 'bet': b, 'placed': False, 'p': None,
                                    'win': win, 'pnl': 0.0})
                    continue

                p_side = None
                lam = None
                if tag == 'WEB':
                    off = pred
                    if 'ambos' in (b.mercado or '').lower():
                        if 'both_teams_score' in off:
                            p_side = off['both_teams_score']['prediction']
                    elif 'puerta' in (b.mercado or '').lower():
                        if 'shots_on_target_total' in off:
                            lam = off['shots_on_target_total']['prediction']
                    elif 'goles' in (b.mercado or '').lower():
                        if 'goals_total' in off:
                            lam = off['goals_total']['prediction']
                elif tag == 'AUTO':
                    if 'ambos' in (b.mercado or '').lower():
                        if 'both_teams_score' in pred:
                            p_side = pred['both_teams_score']['yes']
                    elif 'puerta' in (b.mercado or '').lower():
                        if 'shots_on_target' in pred:
                            lam = pred['shots_on_target']['lambda']
                    elif 'goles' in (b.mercado or '').lower():
                        if 'goals_total' in pred:
                            lam = pred['goals_total']['lambda']
                elif tag == 'VALUE':
                    if 'ambos' in (b.mercado or '').lower():
                        p_side = pred.get('p_bts_yes')
                    elif 'puerta' in (b.mercado or '').lower():
                        p_side = None
                    elif 'goles' in (b.mercado or '').lower():
                        lam = pred.get('lambda_total')
                if lam is not None:
                    p_side = p_over(b.linea, lam) if side == 'over' else p_under(b.linea, lam)

                if p_side is None:
                    results.append({'sys': tag, 'bet': b, 'placed': False, 'p': None,
                                    'win': win, 'pnl': 0.0})
                    continue

                would_bet = p_side >= thr
                pnl = (stake_cop * ((b.played_odds or 1) - 1)) if (would_bet and win) else (
                    -stake_cop if would_bet else 0.0)
                results.append({'sys': tag, 'bet': b, 'placed': would_bet, 'p': p_side,
                                'win': win, 'pnl': pnl})

        n_rest = restore_results(batch_date, all_actuals)
        try:
            os.remove(save_path)
        except OSError:
            pass
        print(f'  lote {batch_date}: {len(batch_bets)} apuestas, {len(jobs)} jobs, '
              f'masked {n_masked}, restaurados {n_rest} | {time.time()-t0:.0f}s', flush=True)

    pool.close()
    pool.join()

    # ── Resumen ──
    eval_ids = {x['bet'].id for x in results}
    n_eval = len(eval_ids)
    eval_bets = [b for b in bets if b.id in eval_ids]

    real_pnl = sum(
        ((b.stake or 0) / 1000.0 * ((b.played_odds or 1) - 1)) if b.bet_status == 'WON'
        else (-(b.stake or 0) / 1000.0)
        for b in eval_bets)
    real_w = sum(1 for b in eval_bets if b.bet_status == 'WON')
    real_l = sum(1 for b in eval_bets if b.bet_status == 'LOST')

    print('\n' + '=' * 100)
    print(f'RESUMEN 2 SEMANAS (apuestas evaluadas: {n_eval} de {len(bets)})')
    print('=' * 100)
    print(f'REAL (producción): {real_w}W/{real_l}L (WR {real_w/(real_w+real_l)*100:.1f}%) | '
          f'P&L {real_pnl:+.0f} COP\n')
    for tag in ('WEB', 'AUTO', 'VALUE'):
        rs = [x for x in results if x['sys'] == tag]
        placed = [x for x in rs if x['placed']]
        won = [x for x in placed if x['win']]
        pnl = sum(x['pnl'] for x in rs)
        skipped_win = [x for x in rs if not x['placed'] and x['win']]
        skipped_loss = [x for x in rs if not x['placed'] and not x['win']]
        wr = len(won) / len(placed) * 100 if placed else 0
        print(f'{tag:6s}: apuesta {len(placed)}/{len(rs)} | {len(won)}W/{len(placed)-len(won)}L '
              f'(WR {wr:.1f}%) | P&L {pnl:+.0f} COP | no-apostó: {len(skipped_win)}G/{len(skipped_loss)}P')
        agg = defaultdict(lambda: [0, 0, 0.0])
        for x in rs:
            if not x['placed']:
                continue
            b = x['bet']
            m = (b.mercado or '?')[:28]
            a = agg[m]
            a[0] += 1
            if x['win']:
                a[1] += 1
            a[2] += x['pnl']
        for m, (n, w, p) in sorted(agg.items(), key=lambda kv: -kv[1][2]):
            print(f'        {m:30s} n={n:3d} W{w} ({w/n*100 if n else 0:4.1f}%) | P&L {p:+8.0f}')

    if skip:
        print(f'\nNo evaluables: {len(skip)}')
        reasons = Counter(r for _b, r in skip)
        for r, n in reasons.items():
            print(f'   {r}: {n}')


if __name__ == '__main__':
    main()
