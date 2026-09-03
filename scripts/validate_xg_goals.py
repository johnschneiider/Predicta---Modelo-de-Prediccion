"""
validate_xg_goals.py — Valida el λ del modelo xG contra la "Predicción Oficial"
actual (Dixon-Coles ensemble) usando partidos ya jugados con resultado.

Fuentes:
  - SavedPrediction (ai_predictions): λ oficial que mostró la web.
  - Match (football_data): resultado real (fthg+ftag) y xG histórico.

Métricas: RMSE, MAE, Brier O/U 2.5, tasa de over real vs P oficial.
Walk-forward estricto: el λ_xg solo usa partidos anteriores al evaluado.
"""
import os
import sys

sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()

import math
from datetime import timedelta
from difflib import SequenceMatcher
from collections import defaultdict

from ai_predictions.models import SavedPrediction
from ai_predictions.xg_goals_model import XGGoalsModel
from football_data.models import Match


def ratio(a, b):
    return SequenceMatcher(None, (a or '').lower(), (b or '').lower()).ratio()


def get_official_lambda(sp):
    try:
        modelos = sp.all_predictions.get('goals_total') or []
    except Exception:
        return None
    for m in modelos:
        if m.get('model_name') in ('Predicción Oficial', 'Predicción oficial'):
            v = m.get('prediction')
            return float(v) if v is not None else None
    return None


def poisson_pmf(k, lam):
    return (math.exp(-lam) * lam ** k) / math.factorial(k)


def poisson_over(line, lam):
    k = int(line) if line == int(line) else None
    # línea 2.5 → over = P(X >= 3) = 1 - P(X <= 2)
    return 1.0 - sum(poisson_pmf(i, lam) for i in range(int(line) + 1))


def main():
    model = XGGoalsModel()
    # dedup por (league_id, home, away) tomando el más reciente
    seen = {}
    for sp in SavedPrediction.objects.select_related('league').order_by('-created_at'):
        key = (sp.league_id, (sp.home_team or '').lower(), (sp.away_team or '').lower())
        if key not in seen:
            seen[key] = sp
    print(f'SavedPredictions únicas: {len(seen)}')

    rows = []
    sin_match = 0
    sin_resultado = 0
    sin_lambda_oficial = 0
    sin_xg = 0

    for sp in seen.values():
        lam_of = get_official_lambda(sp)
        if lam_of is None:
            sin_lambda_oficial += 1
            continue
        # buscar el Match real (resultado)
        qs = Match.objects.filter(league=sp.league)
        cands = list(qs.filter(
            date__gte=sp.created_at.date() - timedelta(days=3),
            date__lte=sp.created_at.date() + timedelta(days=7),
        ))
        best, best_score = None, 0.0
        for m in cands:
            s = ratio(m.home_team, sp.home_team) + ratio(m.away_team, sp.away_team)
            if s > best_score:
                best, best_score = m, s
        if not best or best_score < 1.5:
            sin_match += 1
            continue
        m = best
        if m.fthg is None or m.ftag is None:
            sin_resultado += 1
            continue
        real = m.fthg + m.ftag
        r = model.compute_lambda(sp.home_team, sp.away_team, sp.league, asof=m.date)
        if not r:
            sin_xg += 1
            continue
        lam_home, lam_away, n_min, lg_avg = r
        lam_xg = lam_home + lam_away
        rows.append({
            'match': f'{m.home_team} vs {m.away_team}',
            'liga': sp.league.name,
            'lam_of': lam_of, 'lam_xg': lam_xg,
            'real': real, 'n_xg': n_min,
        })

    print(f'  sin λ oficial: {sin_lambda_oficial} | sin Match: {sin_match} | '
          f'sin resultado: {sin_resultado} | sin datos xG: {sin_xg}')
    n = len(rows)
    print(f'\nEvaluadas (con resultado y xG): {n}\n')

    def rmse(lam_field):
        return math.sqrt(sum((r[lam_field] - r['real']) ** 2 for r in rows) / n)

    def mae(lam_field):
        return sum(abs(r[lam_field] - r['real']) for r in rows) / n

    def brier(lam_field, line=2.5):
        return sum((poisson_over(line, r[lam_field]) - (1.0 if r['real'] > line else 0.0)) ** 2 for r in rows) / n

    print(f"{'métrica':22s} {'OFICIAL':>10s} {'xG':>10s} {'diff':>8s}")
    for nombre, fn in [('RMSE λ vs goles', rmse), ('MAE λ vs goles', mae),
                       ('Brier O/U 2.5', brier)]:
        v_of, v_xg = fn('lam_of'), fn('lam_xg')
        print(f"{nombre:22s} {v_of:10.3f} {v_xg:10.3f} {v_xg - v_of:+8.3f}")

    # blend simple: peso w al xG
    for w in (0.3, 0.5, 0.7):
        rows_b = [{**r, 'lam_b': w * r['lam_xg'] + (1 - w) * r['lam_of']} for r in rows]
        r_b = math.sqrt(sum((x['lam_b'] - x['real']) ** 2 for x in rows_b) / n)
        print(f"  blend w={w}: RMSE {r_b:.3f}")

    # por cobertura xG del partido (n_xg >= 10 vs < 10)
    print()
    for grupo, sub in [('n_xg >= 10', [r for r in rows if r['n_xg'] >= 10]),
                       ('n_xg < 10', [r for r in rows if r['n_xg'] < 10])]:
        if not sub:
            continue
        r_of = math.sqrt(sum((r['lam_of'] - r['real']) ** 2 for r in sub) / len(sub))
        r_xg = math.sqrt(sum((r['lam_xg'] - r['real']) ** 2 for r in sub) / len(sub))
        print(f"  {grupo} (n={len(sub)}): RMSE oficial {r_of:.3f} vs xG {r_xg:.3f}")

    # muestra
    print('\nEjemplos (oficial | xG | real):')
    for r in sorted(rows, key=lambda r: abs(r['lam_xg'] - r['lam_of']), reverse=True)[:8]:
        print(f"  {r['match'][:52]:52s} | {r['lam_of']:5.2f} | {r['lam_xg']:5.2f} | {r['real']} | n={r['n_xg']}")


if __name__ == '__main__':
    main()
