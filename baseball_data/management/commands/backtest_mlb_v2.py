"""
Backtest walking-forward del modelo v2 (Poisson GLM) + simulación de ROI por mercado.

- Calienta con --warm (2025) y recorre --season (2026) sin lookahead.
- Mercado proxy para el ROI: baseline v1 + vig real observado en Kambi
  (totales 4.5%, moneyline 4.2%, run line 4.7%, 1.ª 5 entradas 5.0%).
- Apuesta 1u cuando P(v2) supera la implícita del mercado-proxy en ≥2pp.
- Informe: baseball_data/reports/backtest_v2_latest.json (métricas + ROI por mercado).
"""
import json
import os
from collections import defaultdict

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand

from baseball_data.models import BaseballGame
from baseball_data.baseline import RollingStats, predict_matchup
from baseball_data.v2_model import V2Model, market_probabilities

REPORT_DIR = os.path.join(settings.BASE_DIR, 'baseball_data', 'reports')

TOTAL_LINES = (5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5)
FIRST5_LINES = (2.5, 3.5, 4.5, 5.5)
MIN_EDGE = 0.02
VIG = {'totals': 1.045, 'moneyline': 1.042, 'runline': 1.047, 'first5': 1.050}


class Market:
    """Acumulador de apuestas de un mercado."""

    def __init__(self, name):
        self.name = name
        self.stakes = 0.0
        self.net = 0.0
        self.n = 0
        self.won = 0
        self.edge_sum = 0.0
        self.ev_sum = 0.0

    def settle(self, p_model, p_market, vig, outcome):
        implied = p_market * vig
        if p_model - implied < MIN_EDGE:
            return
        odds = 1.0 / implied
        self.stakes += 1.0
        self.n += 1
        self.edge_sum += p_model - implied
        self.ev_sum += p_model * odds - 1.0
        if outcome:
            self.net += odds - 1.0
            self.won += 1
        else:
            self.net -= 1.0

    def result(self):
        if self.n == 0:
            return None
        return {
            'n': self.n,
            'hit_rate': round(self.won / self.n, 4),
            'roi': round(self.net / self.stakes, 4),
            'avg_edge': round(self.edge_sum / self.n, 4),
            'avg_ev': round(self.ev_sum / self.n, 4),
        }


class Command(BaseCommand):
    help = "Backtest walking-forward del modelo v2 con ROI por mercado"

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, default=2026)
        parser.add_argument('--warm', type=int, default=2025)

    def handle(self, *args, **options):
        season, warm = options['season'], options['warm']

        warm_games = list(BaseballGame.objects.filter(
            season=warm, home_runs__isnull=False, away_runs__isnull=False,
            status__in=('Game Finished', 'Finished', 'After OT')).order_by('date'))
        games = list(BaseballGame.objects.filter(
            season=season, home_runs__isnull=False, away_runs__isnull=False,
            status__in=('Game Finished', 'Finished', 'After OT')).order_by('date'))
        self.stdout.write(f"warm={len(warm_games)} juegos | backtest={len(games)} juegos")

        v1 = RollingStats(warm_games)
        v2 = V2Model(warm_games)

        maes_v1 = []
        maes_v2 = []
        markets = {}
        mkt_by_name = {}

        def get_market(name):
            if name not in markets:
                m = Market(name)
                markets[name] = m
                mkt_by_name[name] = m
            return markets[name]

        brier = defaultdict(lambda: [0.0, 0])
        brier_v1 = defaultdict(lambda: [0.0, 0])

        for g in games:
            hr, ar = g.home_runs, g.away_runs
            total = hr + ar

            p1 = predict_matchup(v1, g.home_team_id, g.away_team_id, TOTAL_LINES, FIRST5_LINES)
            lam_h2, lam_a2 = v2.predict(g)
            p2 = market_probabilities(lam_h2, lam_a2, TOTAL_LINES, FIRST5_LINES)

            maes_v1.append(abs(p1['pred_total'] - total))
            maes_v2.append(abs(p2['pred_total'] - total))

            # Totales (todas las líneas)
            for line in TOTAL_LINES:
                key = str(line)
                over = 1 if total > float(key) else 0
                brier[f"total_{key}"][0] += (p2['total_line_probs'][key]['over'] - over) ** 2
                brier[f"total_{key}"][1] += 1
                brier_v1[f"total_{key}"][0] += (p1['total_line_probs'][key]['over'] - over) ** 2
                brier_v1[f"total_{key}"][1] += 1
                m1 = p1['total_line_probs'][key]
                m2 = p2['total_line_probs'][key]
                get_market('totals').settle(m2['over'], m1['over'], VIG['totals'], over)
                get_market('totals').settle(m2['under'], m1['under'], VIG['totals'], 1 - over)

            # Moneyline
            y_home = 1 if hr > ar else 0
            brier['ml'][0] += (p2['p_home_win'] - y_home) ** 2
            brier['ml'][1] += 1
            brier_v1['ml'][0] += (p1['p_home_win'] - y_home) ** 2
            brier_v1['ml'][1] += 1
            get_market('moneyline').settle(p2['p_home_win'], p1['p_home_win'], VIG['moneyline'], y_home)
            get_market('moneyline').settle(p2['p_away_win'], p1['p_away_win'], VIG['moneyline'], 1 - y_home)

            # Run line ±1.5
            home_covers = 1 if hr - ar >= 2 else 0
            brier['rl'][0] += (p2['runline_probs']['1.5']['home'] - home_covers) ** 2
            brier['rl'][1] += 1
            brier_v1['rl'][0] += (p1['runline_probs']['1.5']['home'] - home_covers) ** 2
            brier_v1['rl'][1] += 1
            get_market('runline').settle(p2['runline_probs']['1.5']['home'],
                                         p1['runline_probs']['1.5']['home'],
                                         VIG['runline'], home_covers)
            get_market('runline').settle(p2['runline_probs']['1.5']['away'],
                                         p1['runline_probs']['1.5']['away'],
                                         VIG['runline'], 1 - home_covers)

            # Primeros 5 innings
            if g.innings_home and g.innings_away:
                h5 = sum(float(v) for k, v in g.innings_home.items() if k.isdigit() and int(k) <= 5)
                a5 = sum(float(v) for k, v in g.innings_away.items() if k.isdigit() and int(k) <= 5)
                t5 = h5 + a5
                for line in FIRST5_LINES:
                    key = str(line)
                    over5 = 1 if t5 > float(key) else 0
                    brier[f"f5_{key}"][0] += (p2['first5_probs'][key]['over'] - over5) ** 2
                    brier[f"f5_{key}"][1] += 1
                    m1 = p1['first5_probs'][key]
                    m2 = p2['first5_probs'][key]
                    get_market('first5').settle(m2['over'], m1['over'], VIG['first5'], over5)
                    get_market('first5').settle(m2['under'], m1['under'], VIG['first5'], 1 - over5)

            v1.update(g)
            v2.update(g)

        report = {
            'model': 'poisson_glm_v2',
            'warm_season': warm,
            'season': season,
            'n_games': len(games),
            'mae_total_v1': round(float(np.mean(maes_v1)), 3),
            'mae_total_v2': round(float(np.mean(maes_v2)), 3),
            'rmse_total_v1': round(float(np.sqrt(np.mean(np.square(maes_v1)))), 3),
            'rmse_total_v2': round(float(np.sqrt(np.mean(np.square(maes_v2)))), 3),
            'brier': {k: round(v[0] / v[1], 4) for k, v in brier.items()},
            'brier_v1': {k: round(v[0] / v[1], 4) for k, v in brier_v1.items()},
            'roi': {},
            'bet_rule': f'P(v2) - P(implied) >= {MIN_EDGE}pp, vig Kambi observada',
        }
        for name in ('totals', 'moneyline', 'runline', 'first5'):
            r = markets[name].result()
            if r:
                report['roi'][name] = r

        os.makedirs(REPORT_DIR, exist_ok=True)
        out = os.path.join(REPORT_DIR, 'backtest_v2_latest.json')
        with open(out, 'w') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS(f"Informe: {out}"))
        self.stdout.write(f"MAE total: v1 {report['mae_total_v1']} → v2 {report['mae_total_v2']}")
        for name, r in report['roi'].items():
            self.stdout.write(
                f"  {name:<10} n={r['n']:<5} hit={r['hit_rate']} ROI={r['roi']} avg_edge={r['avg_edge']} avg_ev={r['avg_ev']}")
