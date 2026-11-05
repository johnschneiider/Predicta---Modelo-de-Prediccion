"""
Backtest walking-forward del baseline MLB.

- Calienta las stats con partidos terminados de --warm (p. ej. 2025).
- Recorre los partidos terminados de --season en orden cronológico.
- Para cada partido predice SOLO con partidos anteriores, registra el resultado
  y recién entonces actualiza las stats (sin lookahead).
- Evalúa: MAE/RMSE, Brier, log-loss y calibración por mercado
  (totales 5.5–11.5, moneyline, run line ±1.5, primeros 5 innings).
- Escribe el informe en baseball_data/reports/backtest_latest.json.

Nota: no existen odds históricas en la API (solo juegos recientes), por lo que el
ROI contra líneas de cierre NO se puede calcular aquí; el valor real se mide en vivo
contra las líneas de Kambi/BetPlay (página "Valor MLB").
"""
import json
import os
import math
from collections import defaultdict

import numpy as np
from django.conf import settings
from django.core.management.base import BaseCommand

from baseball_data.models import BaseballGame
from baseball_data.baseline import RollingStats, predict_matchup

REPORT_DIR = os.path.join(settings.BASE_DIR, 'baseball_data', 'reports')

TOTAL_LINES = (5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5)
FIRST5_LINES = (2.5, 3.5, 4.5, 5.5)


def _logloss(p, y):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return -(y * math.log(p) + (1 - y) * math.log(1 - p))


class MarketEval:
    def __init__(self, name):
        self.name = name
        self.pairs = []  # (p, y)
        self.brier_sum = 0.0
        self.ll_sum = 0.0
        self.n = 0

    def add(self, p, y):
        self.pairs.append((p, y))
        self.brier_sum += (p - y) ** 2
        self.ll_sum += _logloss(p, y)
        self.n += 1

    def summary(self):
        if self.n == 0:
            return None
        freq = sum(y for _, y in self.pairs) / self.n
        # Brier de referencia (climatología)
        brier_ref = freq * (1 - freq)
        return {
            'n': self.n,
            'freq': round(freq, 4),
            'brier': round(self.brier_sum / self.n, 4),
            'brier_ref': round(brier_ref, 4),
            'brier_skill': round(1 - (self.brier_sum / self.n) / brier_ref, 4) if brier_ref > 0 else None,
            'logloss': round(self.ll_sum / self.n, 4),
            'calibration': self._calibration(),
        }

    def _calibration(self):
        bins = [[] for _ in range(10)]
        for p, y in self.pairs:
            idx = min(int(p * 10), 9)
            bins[idx].append((p, y))
        out = []
        for i, b in enumerate(bins):
            if not b:
                continue
            out.append({
                'bin': f"{i * 0.1:.1f}-{i * 0.1 + 0.1:.1f}",
                'n': len(b),
                'mean_p': round(float(np.mean([p for p, _ in b])), 3),
                'actual': round(float(np.mean([y for _, y in b])), 3),
            })
        return out


class Command(BaseCommand):
    help = "Backtest walking-forward del baseline MLB (sin lookahead)"

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, default=2026)
        parser.add_argument('--warm', type=int, default=2025, help='Temporada de calentamiento')
        parser.add_argument('--verbose', action='store_true')

    def handle(self, *args, **options):
        season = options['season']
        warm = options['warm']

        warm_qs = BaseballGame.objects.filter(
            season=warm, home_runs__isnull=False, away_runs__isnull=False,
            status__in=('Game Finished', 'Finished', 'After OT')).order_by('date')
        warm_games = list(warm_qs)
        self.stdout.write(f"Calentamiento {warm}: {len(warm_games)} partidos terminados")

        qs = BaseballGame.objects.filter(
            season=season, home_runs__isnull=False, away_runs__isnull=False,
            status__in=('Game Finished', 'Finished', 'After OT')).order_by('date')
        games = list(qs)
        self.stdout.write(f"Backtest {season}: {len(games)} partidos terminados")
        if not games:
            self.stderr.write("Sin partidos. Corre sync_mlb_data --games primero.")
            return

        stats = RollingStats(warm_games)

        maes = []
        total_mae = []
        evals = {}  # nombre mercado -> MarketEval

        def ev(name):
            if name not in evals:
                evals[name] = MarketEval(name)
            return evals[name]

        for i, g in enumerate(games):
            pred = predict_matchup(stats, g.home_team_id, g.away_team_id,
                                   TOTAL_LINES, FIRST5_LINES)
            hr, ar = g.home_runs, g.away_runs
            total = hr + ar

            # Errores de punto
            maes.append(abs(pred['lam_home'] - hr))
            total_mae.append(abs(pred['pred_total'] - total))

            # Totales
            for line, probs in pred['total_line_probs'].items():
                over = 1 if total > float(line) else 0
                ev(f"total_{line}").add(probs['over'], over)
                ev(f"total_{line}").add(probs['under'], 1 - over)

            # Moneyline
            y_home = 1 if hr > ar else 0
            ev("ml_home").add(pred['p_home_win'], y_home)
            ev("ml_away").add(pred['p_away_win'], 1 - y_home)

            # Run line ±1.5
            home_covers = 1 if hr - ar >= 2 else 0
            ev("rl_home_1.5").add(pred['runline_probs']['1.5']['home'], home_covers)
            ev("rl_away_1.5").add(pred['runline_probs']['1.5']['away'], 1 - home_covers)

            # Primeros 5 innings (si hay datos de entradas)
            if g.innings_home and g.innings_away:
                h5 = sum(float(v) for k, v in g.innings_home.items() if k.isdigit() and int(k) <= 5)
                a5 = sum(float(v) for k, v in g.innings_away.items() if k.isdigit() and int(k) <= 5)
                t5 = h5 + a5
                for line, probs in pred['first5_probs'].items():
                    over5 = 1 if t5 > float(line) else 0
                    ev(f"f5_{line}").add(probs['over'], over5)
                    ev(f"f5_{line}").add(probs['under'], 1 - over5)

            stats.update(g)
            if options['verbose'] and (i + 1) % 500 == 0:
                self.stdout.write(f"  {i + 1}/{len(games)}")

        report = {
            'model': 'baseline_poisson_rolling',
            'warm_season': warm,
            'season': season,
            'n_games': len(games),
            'mae_home_runs': round(float(np.mean(maes)), 3),
            'rmse_home_runs': round(float(np.sqrt(np.mean(np.square(maes)))), 3),
            'mae_total_runs': round(float(np.mean(total_mae)), 3),
            'rmse_total_runs': round(float(np.sqrt(np.mean(np.square(total_mae)))), 3),
            'markets': {},
        }
        for name in sorted(evals):
            s = evals[name].summary()
            if s:
                report['markets'][name] = s

        os.makedirs(REPORT_DIR, exist_ok=True)
        out_path = os.path.join(REPORT_DIR, 'backtest_latest.json')
        with open(out_path, 'w') as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        self.stdout.write(self.style.SUCCESS(f"Informe: {out_path}"))
        self.stdout.write(f"n={report['n_games']} | MAE total {report['mae_total_runs']} | "
                          f"RMSE total {report['rmse_total_runs']}")
        for name in ('total_7.5', 'ml_home', 'rl_home_1.5', 'f5_4.5'):
            s = report['markets'].get(name)
            if s:
                self.stdout.write(
                    f"  {name:<12} n={s['n']:<5} freq={s['freq']} brier={s['brier']} "
                    f"brier_skill={s['brier_skill']} logloss={s['logloss']}")
