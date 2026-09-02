"""
Backtest: 10 apuestas perdidas (30-31 Ago 2026) contra los 3 sistemas de predicción.
- WEB (/ai/predict/): pipeline legacy -> official_prediction_model (promedio ponderado)
- AUTO_BETTING: pipeline oficial + override poisson_ratings (ridge) + caps de sanidad
- VALUE_BETTING: pipeline propio (Ensemble por equipo + Poisson bivariado + enhanced BTTS)

SIN FUGA DE DATOS: antes de predecir cada lote se enmascaran (NULL) los resultados
de los partidos con fecha >= fecha del lote, tal como estaba la DB a la hora de apostar.
Al final se restauran los valores originales.
"""
import math
import traceback
import os
import sys
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()
from datetime import timedelta

from django.utils import timezone

from football_data.models import Match
from value_betting.mapping import fuzzy_match_team


# ── Poisson ──
def poisson_cdf(k, lam):
    if lam <= 0:
        return 1.0 if k >= 0 else 0.0
    s = 0.0
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


# ── Motor WEB: replica de PredictionResultView para los 4 mercados ──
def web_engine(home, away, league):
    from ai_predictions.simple_models import SimplePredictionService, ModeloHibridoGeneral
    from ai_predictions.official_prediction_model import official_prediction_model
    from ai_predictions.corners_model import corners_model
    from ai_predictions.enhanced_both_teams_score import enhanced_both_teams_score_model
    from ai_predictions.shots_prediction_model import shots_prediction_model
    from ai_predictions.xg_shots_model import xg_shots_model

    all_preds = {}
    svc = SimplePredictionService()

    # goals_total: 3 simples + híbrido
    try:
        lst = svc.get_all_simple_predictions(home, away, league, 'goals_total')
        hyb = ModeloHibridoGeneral().predecir(home, away, league, 'goals_total')
        if hyb and hyb.get('prediction', 0) > 0:
            lst.append(hyb)
        if lst:
            all_preds['goals_total'] = lst
    except Exception as e:
        print('   [web] goals error:', e)

    # shots_on_target_total: shots_prediction + xg_shots (AMBOS, como la web)
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

    # corners_total: modelo único
    try:
        c = corners_model.predecir(home, away, league, 'corners_total')
        if c:
            all_preds['corners_total'] = [c]
    except Exception as e:
        print('   [web] corners error:', e)

    # both_teams_score: 3 simples + enhanced
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

    off = official_prediction_model.calculate_official_predictions(all_preds)
    return off


# ── Motor AUTO_BETTING ──
def autobetting_engine(home, away, league):
    from auto_betting.strategy import get_official_predictions
    return get_official_predictions(home, away, league)


# ── Motor VALUE_BETTING ──
def valuebetting_engine(home, away, league):
    from value_betting.services import generate_full_prediction
    return generate_full_prediction(home, away, league)


def mask_results(cutoff_date):
    """Pone en NULL los resultados de partidos desde cutoff_date (inclusive)."""
    qs = Match.objects.filter(date__gte=cutoff_date)
    n = 0
    for m in qs:
        changed = False
        for f in ('fthg', 'ftag', 'hthg', 'htag', 'hst', 'ast', 'hc', 'ac'):
            if getattr(m, f) is not None:
                setattr(m, f, None)
                changed = True
        if changed:
            m.save(update_fields=['fthg', 'ftag', 'hthg', 'htag', 'hst', 'ast', 'hc', 'ac'])
            n += 1
    return n


def restore_results(cutoff_date, actuals):
    """Restaura resultados guardados en `actuals` {match_id: {...}}."""
    qs = Match.objects.filter(date__gte=cutoff_date)
    n = 0
    for m in qs:
        orig = actuals.get(m.id)
        if not orig:
            continue
        for f, v in orig.items():
            setattr(m, f, v)
        m.save(update_fields=['fthg', 'ftag', 'hthg', 'htag', 'hst', 'ast', 'hc', 'ac'])
        n += 1
    return n


def get_actuals(cutoff_date):
    out = {}
    for m in Match.objects.filter(date__gte=cutoff_date):
        out[m.id] = {f: getattr(m, f) for f in
                     ('fthg', 'ftag', 'hthg', 'htag', 'hst', 'ast', 'hc', 'ac')}
    return out


def main():
    from auto_betting.models import HistorialApuesta, MarketFilterConfig
    from cuentas.models import Usuario

    admin = Usuario.objects.get(username='admin')
    lost = list(HistorialApuesta.objects.filter(
        usuario=admin, bet_status='LOST', is_system=True,
        placed_date__date__in=['2026-08-30', '2026-08-31']).order_by('-placed_date'))

    # Seleccionar 10 apuestas de partidos distintos (6 del 31 + 4 del 30)
    sel, seen = [], set()
    for h in lost:
        if (h.home_team, h.away_team) in seen:
            continue
        sel.append(h)
        seen.add((h.home_team, h.away_team))
        if len(sel) >= 10:
            break

    # ── Mapear cada apuesta a su Match en football_data ──
    overrides = {
        ('Osasuna', 'Getafe'): 904326,  # La Liga 2026-08-31 (fuzzy falló con otra liga)
    }

    def find_match(h):
        ov = overrides.get((h.home_team, h.away_team))
        if ov:
            return Match.objects.get(id=ov)
        d = h.event_start_date.date()
        best = None
        for delta in (-1, 0, 1):
            day = d + timedelta(days=delta)
            for m in Match.objects.filter(date=day):
                th = fuzzy_match_team(h.home_team, [m.home_team], threshold=0.45)
                ta = fuzzy_match_team(h.away_team, [m.away_team], threshold=0.45)
                if th and ta:
                    return m
        # Fallback: solo home
        for delta in (-1, 0, 1):
            day = d + timedelta(days=delta)
            for m in Match.objects.filter(date=day):
                th = fuzzy_match_team(h.home_team, [m.home_team], threshold=0.45)
                if th and m.league.name == h.liga:
                    return m
        return None

    rows = []
    for h in sel:
        m = find_match(h)
        rows.append({'bet': h, 'match': m})

    # Umbrales por submercado (los del sistema)
    mf = MarketFilterConfig.get_solo().as_market_filters()

    def side_of(sel_):
        s = sel_.strip().lower()
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

    def actual_outcome(h, m):
        """(gana_la_apuesta, descripcion)"""
        side = side_of(h.seleccion)
        if 'ambos' in (h.mercado or '').lower():
            btts = (m.fthg or 0) > 0 and (m.ftag or 0) > 0
            return btts if side == 'si' else (not btts), f"res {m.fthg}-{m.ftag}"
        if 'puerta' in (h.mercado or '').lower():
            tot = (m.hst or 0) + (m.ast or 0)
            if side == 'over':
                return tot > h.linea, f"sot {tot}"
            return tot < h.linea, f"sot {tot}"
        if 'goles' in (h.mercado or '').lower():
            tot = (m.fthg or 0) + (m.ftag or 0)
            if side == 'over':
                return tot > h.linea, f"goles {tot}"
            return tot < h.linea, f"goles {tot}"
        return False, '?'

    # ── Procesar por lotes (fecha de apuesta = cutoff de masking) ──
    print('=' * 100)
    print('BACKTEST: 10 apuestas perdidas vs 3 sistemas (sin fuga de datos)')
    print('=' * 100)

    results = []  # por sistema: lista de dicts
    batches = sorted({r['bet'].placed_date.date() for r in rows}, reverse=True)

    for batch_date in batches:
        first = next(r for r in rows if r['bet'].placed_date.date() == batch_date)
        h, m = first['bet'], first['match']
        if m is None:
            print(f"!! Sin match en DB: {h.home_team} vs {h.away_team}")
            continue
        cutoff = batch_date
        actuals = get_actuals(cutoff)
        n_masked = mask_results(cutoff)
        print(f"\n── Lote {cutoff} (masked: {n_masked} partidos) ──")

        batch_rows = [x for x in rows if x['bet'].placed_date.date() == batch_date]
        for r2 in batch_rows:
            h2, m2 = r2['bet'], r2['match']
            if m2 is None:
                continue
            side = side_of(h2.seleccion)
            thr = threshold(h2)
            actual_win, desc = actual_outcome(h2, m2)
            league = m2.league
            home, away = m2.home_team, m2.away_team

            print(f"\n▶ {home} vs {away} ({league.name}) | apuesta: {h2.seleccion} "
                  f"(linea {h2.linea}) @ {h2.played_odds} | REAL: {desc} → {'GANARÍA' if actual_win else 'PERDIDA'}")

            engines = {}
            try:
                engines['WEB'] = ('web', web_engine(home, away, league))
            except Exception as e:
                print('   WEB error:', e)
            try:
                engines['AUTO'] = ('auto', autobetting_engine(home, away, league))
            except Exception as e:
                print('   AUTO error:', e)
            try:
                engines['VALUE'] = ('value', valuebetting_engine(home, away, league))
            except Exception as e:
                print('   VALUE error:', e)

            for tag, (kind, pred) in engines.items():
                if not pred:
                    print(f'   {tag:6s}: sin predicción → NO apuesta (evita la pérdida)')
                    results.append({'sys': tag, 'bet': h2, 'placed': False, 'p': None,
                                    'win': None, 'pnl': 0.0})
                    continue
                p_side = None
                lam = None
                if kind == 'web':
                    off = pred
                    if 'ambos' in (h2.mercado or '').lower():
                        if 'both_teams_score' in off:
                            p_side = off['both_teams_score']['prediction']
                    elif 'puerta' in (h2.mercado or '').lower():
                        if 'shots_on_target_total' in off:
                            lam = off['shots_on_target_total']['prediction']
                    elif 'goles' in (h2.mercado or '').lower():
                        if 'goals_total' in off:
                            lam = off['goals_total']['prediction']
                    if lam is not None:
                        p_side = p_over(h2.linea, lam) if side == 'over' else p_under(h2.linea, lam)
                elif kind == 'auto':
                    if 'ambos' in (h2.mercado or '').lower():
                        if 'both_teams_score' in pred:
                            p_side = pred['both_teams_score']['yes']
                    elif 'puerta' in (h2.mercado or '').lower():
                        if 'shots_on_target' in pred:
                            lam = pred['shots_on_target']['lambda']
                    elif 'goles' in (h2.mercado or '').lower():
                        if 'goals_total' in pred:
                            lam = pred['goals_total']['lambda']
                    if lam is not None:
                        p_side = p_over(h2.linea, lam) if side == 'over' else p_under(h2.linea, lam)
                elif kind == 'value':
                    if 'ambos' in (h2.mercado or '').lower():
                        p_side = pred.get('p_bts_yes')
                    elif 'puerta' in (h2.mercado or '').lower():
                        p_side = None  # value_betting no tiene tiros a puerta
                    elif 'goles' in (h2.mercado or '').lower():
                        lam = pred.get('lambda_total')
                    if lam is not None:
                        p_side = p_over(h2.linea, lam) if side == 'over' else p_under(h2.linea, lam)

                if p_side is None:
                    print(f'   {tag:6s}: sin dato para este mercado → NO apuesta (evita la pérdida)')
                    results.append({'sys': tag, 'bet': h2, 'placed': False, 'p': None,
                                    'win': None, 'pnl': 0.0})
                    continue

                would_bet = p_side >= thr
                stake_cop = (h2.stake or 0) / 1000.0
                pnl = (stake_cop * ((h2.played_odds or 1) - 1)) if (would_bet and actual_win) else (
                    -stake_cop if would_bet else 0.0)
                lam_str = f'λ={lam:.2f}' if lam is not None else ''
                print(f'   {tag:6s}: {lam_str} P({h2.seleccion})={p_side:.1%} '
                      f'[umbral {thr:.0%}] → {"APUESTA" if would_bet else "NO apuesta"} → '
                      f'{"GANA" if actual_win else "PIERDE"} → P&L {pnl:+.0f} COP')
                results.append({'sys': tag, 'bet': h2, 'placed': would_bet, 'p': p_side,
                                'win': actual_win, 'pnl': pnl})

        # restaurar
        n_rest = restore_results(cutoff, actuals)
        print(f'   (restaurados: {n_rest})')

    # ── Resumen ──
    print('\n' + '=' * 100)
    print('RESUMEN POR SISTEMA')
    print('=' * 100)
    total_stake = sum((r['bet'].stake or 0) / 1000.0 for r in rows)
    print(f'Real (lo que pasó): 10 apuestas PERDIDAS → P&L {-total_stake:+.0f} COP\n')
    for tag in ('WEB', 'AUTO', 'VALUE'):
        rs = [x for x in results if x['sys'] == tag]
        placed = [x for x in rs if x['placed']]
        won = [x for x in placed if x['win']]
        pnl = sum(x['pnl'] for x in rs)
        print(f'{tag:6s}: apuestas {len(placed)}/10 | ganadas {len(won)}/{len(placed) if placed else 0} | '
              f'P&L {pnl:+.0f} COP | pérdidas evitadas {10 - len(placed)}')
        for x in rs:
            if not x['placed']:
                print(f'        evitada: {x["bet"].home_team} vs {x["bet"].away_team} ({x["bet"].seleccion})')


if __name__ == '__main__':
    main()
