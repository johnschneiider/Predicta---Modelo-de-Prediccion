"""
Backtest COMPLETO v2: todas las apuestas de auto_betting (admin) del 30 y 31 Ago 2026
contra los 3 sistemas, sin fuga de datos.
FIX v2: los resultados reales se capturan ANTES del masking (dict en memoria),
no se relee el ORM después de enmascarar.
"""
import math
import os
import sys
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()

from datetime import timedelta

from football_data.models import Match
from value_betting.mapping import fuzzy_match_team

FIELDS = ('fthg', 'ftag', 'hthg', 'htag', 'hst', 'ast', 'hc', 'ac')


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


_engine_cache = {}


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
    except Exception as e:
        print('   [web] goals error:', e)
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
    except Exception as e:
        print('   [web] shots error:', e)
    try:
        c = corners_model.predecir(home, away, league, 'corners_total')
        if c:
            all_preds['corners_total'] = [c]
    except Exception as e:
        print('   [web] corners error:', e)
    try:
        lst = svc.get_all_simple_predictions(home, away, league, 'both_teams_score')
        p = enhanced_both_teams_score_model.predict(home, away, league)
        if p is not None:
            lst.append({'model_name': 'Enhanced Both Teams Score', 'prediction': float(p),
                        'confidence': 0.80, 'total_matches': 100})
        if lst:
            all_preds['both_teams_score'] = lst
    except Exception as e:
        print('   [web] btts error:', e)

    return official_prediction_model.calculate_official_predictions(all_preds)


def autobetting_engine(home, away, league):
    from auto_betting.strategy import get_official_predictions
    return get_official_predictions(home, away, league)


def valuebetting_engine(home, away, league):
    from value_betting.services import generate_full_prediction
    return generate_full_prediction(home, away, league)


ENGINES = {'WEB': web_engine, 'AUTO': autobetting_engine, 'VALUE': valuebetting_engine}


def mask_results(cutoff_date):
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


def restore_results(cutoff_date, actuals):
    n = 0
    for m in Match.objects.filter(date__gte=cutoff_date):
        orig = actuals.get(m.id)
        if not orig:
            continue
        for f, v in orig.items():
            setattr(m, f, v)
        m.save(update_fields=list(FIELDS))
        n += 1
    return n


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


def main():
    from auto_betting.models import HistorialApuesta, MarketFilterConfig
    from cuentas.models import Usuario

    admin = Usuario.objects.get(username='admin')
    bets = list(HistorialApuesta.objects.filter(
        usuario=admin, is_system=True,
        placed_date__date__in=['2026-08-30', '2026-08-31']).order_by('placed_date'))

    print(f'Apuestas del sistema (admin) 30-31 Ago: {len(bets)}')
    from collections import Counter
    print('Estados BetPlay:', dict(Counter(b.bet_status for b in bets)))

    mf = MarketFilterConfig.get_solo().as_market_filters()

    def side_of(s):
        s = s.strip().lower()
        if s.startswith('más') or s.startswith('mas'):
            return 'over'
        if s.startswith('menos'):
            return 'under'
        if s in ('sí', 'si'):
            return 'si'
        return 'no'

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
        """stats = dict pre-mask con valores reales. Devuelve (gana, desc, evaluable)."""
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
                return None, 'sin sot en DB', False
            tot = hs + as_
            if side == 'over':
                return tot > h.linea, f"sot {tot}", True
            return tot < h.linea, f"sot {tot}", True
        if 'goles' in (h.mercado or '').lower():
            fh, fa = stats.get('fthg'), stats.get('ftag')
            if fh is None or fa is None:
                return None, 'sin resultado', False
            tot = fh + fa
            if side == 'over':
                return tot > h.linea, f"goles {tot}", True
            return tot < h.linea, f"goles {tot}", True
        return None, 'mercado no soportado', False

    print('=' * 110)
    results = []
    skip = []
    mismatches = []

    batches = sorted({b.placed_date.date() for b in bets}, reverse=True)
    for batch_date in batches:
        batch_bets = [b for b in bets if b.placed_date.date() == batch_date]

        # 1) PRE-MASK: ubicar matches y capturar valores reales
        rows = []
        for b in batch_bets:
            m = find_match(b)
            if m is None:
                skip.append((b, 'sin match en DB'))
                continue
            stats = {f: getattr(m, f) for f in FIELDS}
            rows.append((b, m, stats))

        # 2) MASK
        all_actuals = {m.id: {f: getattr(m, f) for f in FIELDS}
                       for m in Match.objects.filter(date__gte=batch_date)}
        n_masked = mask_results(batch_date)
        print(f'\n── Lote {batch_date} (masked: {n_masked}) ──')

        # 3) EVALUAR + PREDECIR con datos enmascarados
        for b, m, stats in rows:
            win, desc, evaluable = actual_outcome(b, stats)
            if not evaluable:
                skip.append((b, desc))
                continue

            real_won = b.bet_status == 'WON'
            if win != real_won:
                mismatches.append((b, desc, win, real_won))

            home, away, league = m.home_team, m.away_team, m.league
            side = side_of(b.seleccion)
            thr = threshold(b)
            stake_cop = (b.stake or 0) / 1000.0

            print(f'\n▶ {home} vs {away} ({league.name}) | {b.seleccion} (linea {b.linea}) '
                  f'@ {b.played_odds} stake {stake_cop:.0f} | REAL: {desc} → '
                  f'{"GANÓ" if win else "PERDIÓ"}')

            for tag, fn in ENGINES.items():
                key = (batch_date, home, away, league.id, tag)
                pred = _engine_cache.get(key)
                if pred is None:
                    try:
                        pred = fn(home, away, league)
                    except Exception as e:
                        print(f'   {tag:6s}: error {e}')
                        pred = 'ERR'
                    _engine_cache[key] = pred
                if pred in (None, 'ERR'):
                    print(f'   {tag:6s}: sin predicción → NO apuesta → P&L +0')
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
                    print(f'   {tag:6s}: sin dato mercado → NO apuesta → P&L +0')
                    results.append({'sys': tag, 'bet': b, 'placed': False, 'p': None,
                                    'win': win, 'pnl': 0.0})
                    continue

                would_bet = p_side >= thr
                pnl = (stake_cop * ((b.played_odds or 1) - 1)) if (would_bet and win) else (
                    -stake_cop if would_bet else 0.0)
                lam_str = f'λ={lam:.2f}' if lam is not None else ''
                print(f'   {tag:6s}: {lam_str} P({b.seleccion})={p_side:.1%} '
                      f'[umbral {thr:.0%}] → {"APUESTA" if would_bet else "NO apuesta"} → '
                      f'{"GANA" if win else "PIERDE"} → P&L {pnl:+.0f}')
                results.append({'sys': tag, 'bet': b, 'placed': would_bet, 'p': p_side,
                                'win': win, 'pnl': pnl})

        # 4) RESTAURAR
        n_rest = restore_results(batch_date, all_actuals)
        print(f'\n   (restaurados: {n_rest})')

    # ── Resumen ──
    eval_ids = {x['bet'].id for x in results} if results else set()
    skip_ids = {s[0].id for s in skip}
    n_eval = len(eval_ids)
    eval_bets = [b for b in bets if b.id in eval_ids]

    real_pnl = sum(
        ((b.stake or 0) / 1000.0 * ((b.played_odds or 1) - 1)) if b.bet_status == 'WON'
        else (-(b.stake or 0) / 1000.0) if b.bet_status == 'LOST'
        else 0.0
        for b in eval_bets)
    real_w = sum(1 for b in eval_bets if b.bet_status == 'WON')
    real_l = sum(1 for b in eval_bets if b.bet_status == 'LOST')

    print('\n' + '=' * 110)
    print(f'RESUMEN FINAL (apuestas evaluadas: {n_eval})')
    print('=' * 110)
    print(f'REAL (producción): {real_w}W/{real_l}L | P&L {real_pnl:+.0f} COP\n')
    for tag in ('WEB', 'AUTO', 'VALUE'):
        rs = [x for x in results if x['sys'] == tag]
        placed = [x for x in rs if x['placed']]
        won = [x for x in placed if x['win']]
        lost = [x for x in placed if not x['win']]
        pnl = sum(x['pnl'] for x in rs)
        skipped_win = [x for x in rs if not x['placed'] and x['win']]
        skipped_loss = [x for x in rs if not x['placed'] and not x['win']]
        print(f'{tag:6s}: apuesta {len(placed)}/{len(rs)} | {len(won)}W/{len(lost)}L | '
              f'P&L {pnl:+.0f} COP | no-apostó: {len(skipped_win)} ganadoras, '
              f'{len(skipped_loss)} perdedoras')
        for x in skipped_win:
            print(f'        evitó GANADORA: {x["bet"].home_team} vs {x["bet"].away_team} '
                  f'({x["bet"].seleccion})')

    if skip:
        print('\nNo evaluables (sin match/resultado en DB):')
        for b, reason in skip:
            print(f'   - {b.home_team} vs {b.away_team} | {b.seleccion} | {b.bet_status} | {reason}')
    if mismatches:
        print('\n⚠️ Discrepancias stats DB vs BetPlay:')
        for b, desc, win, real_won in mismatches:
            print(f'   - {b.home_team} vs {b.away_team}: stats={desc} (ganaría={win}), '
                  f'BetPlay={b.bet_status} (ganó={real_won})')


if __name__ == '__main__':
    main()
