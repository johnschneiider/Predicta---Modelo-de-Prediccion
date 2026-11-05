"""
Baseline MLB: Poisson rodante por equipo (splits home/away).

- λ_local  = (off_home_de_local + def_away_del_visitante) / 2
- λ_visit  = (off_away_del_visitante + def_home_del_local) / 2
- Probabilidades de todos los mercados por convolución de Poissons:
  * Total de carreras (líneas 5.5 a 11.5)
  * Moneyline (ganador, con desempate 50/50 en extra innings)
  * Run line ±1.5
  * Primeros 5 innings (λ escalada 5/9, aproximación de baseline)

Sin lookahead: las stats usan SOLO partidos terminados antes del partido a predecir.
"""
import math
import numpy as np

MAX_RUNS = 24  # truncamiento del soporte de la Poisson


def _poisson_pmf(lam, n=MAX_RUNS):
    if lam <= 0:
        lam = 0.1
    k = np.arange(n + 1)
    with np.errstate(under='ignore'):
        p = np.exp(-lam) * np.power(lam, k) / np.array([math.factorial(int(x)) for x in k])
    p = p / p.sum()
    return p


def _skellam_pmf(lam_h, lam_a, n=MAX_RUNS):
    """PMF de la diferencia (local - visitante) de dos Poisson independientes."""
    ph = _poisson_pmf(lam_h, n)
    pa = _poisson_pmf(lam_a, n)
    diff = np.convolve(ph, pa[::-1])
    # diff[i] = P(H - A = i - n)
    max_abs = n
    pmf = np.zeros(2 * max_abs + 1)
    pmf = diff  # índice i corresponde a diferencia i - n
    return pmf, n  # pmf[d + n] = P(diff = d)


class RollingStats:
    """Estadísticas rodantes por equipo (sin lookahead)."""

    def __init__(self, warm_games=None):
        self.t = {}  # team_id -> dict
        if warm_games:
            for g in warm_games:
                self.update(g)

    def _entry(self, tid):
        if tid not in self.t:
            self.t[tid] = {
                'gp_h': 0, 'rs_h': 0, 'ra_h': 0,   # como local
                'gp_a': 0, 'rs_a': 0, 'ra_a': 0,   # como visitante
            }
        return self.t[tid]

    def update(self, game):
        """Incorpora un partido terminado (home_runs/away_runs no nulos)."""
        if game.home_runs is None or game.away_runs is None:
            return
        h = self._entry(game.home_team_id)
        a = self._entry(game.away_team_id)
        h['gp_h'] += 1
        h['rs_h'] += game.home_runs
        h['ra_h'] += game.away_runs
        a['gp_a'] += 1
        a['rs_a'] += game.away_runs
        a['ra_a'] += game.home_runs

    def lambdas(self, home_id, away_id):
        h = self._entry(home_id)
        a = self._entry(away_id)

        league = 4.4  # promedio histórico de carreras por equipo y juego (MLB ~4.4)

        off_h = (h['rs_h'] / h['gp_h']) if h['gp_h'] else league
        def_h = (h['ra_h'] / h['gp_h']) if h['gp_h'] else league
        off_a = (a['rs_a'] / a['gp_a']) if a['gp_a'] else league
        def_a = (a['ra_a'] / a['gp_a']) if a['gp_a'] else league

        # suavizado hacia la media de la liga (encogimiento del baseline)
        shrink = 8  # pseudo-juegos
        off_h = (off_h * h['gp_h'] + league * shrink) / (h['gp_h'] + shrink)
        def_h = (def_h * h['gp_h'] + league * shrink) / (h['gp_h'] + shrink)
        off_a = (off_a * a['gp_a'] + league * shrink) / (a['gp_a'] + shrink)
        def_a = (def_a * a['gp_a'] + league * shrink) / (a['gp_a'] + shrink)

        lam_h = (off_h + def_a) / 2
        lam_a = (off_a + def_h) / 2
        return lam_h, lam_a


def predict_matchup(stats: RollingStats, home_id, away_id, total_lines=(5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5),
                    first5_lines=(2.5, 3.5, 4.5, 5.5), runline=1.5):
    lam_h, lam_a = stats.lambdas(home_id, away_id)
    ph = _poisson_pmf(lam_h)
    pa = _poisson_pmf(lam_a)

    total_pmf = np.convolve(ph, pa)[:2 * MAX_RUNS + 1]  # P(H+A = k)

    total_probs = {}
    for line in total_lines:
        threshold = int(line) + 1  # Over X.5 ⇒ P(total ≥ X+1)
        over = float(total_pmf[threshold:].sum())
        total_probs[str(line)] = {'over': round(over, 4), 'under': round(1 - over, 4)}

    diff_pmf, shift = _skellam_pmf(lam_h, lam_a)
    p_tie = float(diff_pmf[shift])
    p_home_gt = float(diff_pmf[shift + 1:].sum())
    p_away_gt = float(diff_pmf[:shift].sum())
    p_home_win = p_home_gt + 0.5 * p_tie
    p_away_win = p_away_gt + 0.5 * p_tie

    # Run line: local -1.5 cubre si gana por 2+ → P(diff >= 2)
    p_home_cover = float(diff_pmf[shift + 2:].sum())
    runline_probs = {str(runline): {'home': round(p_home_cover, 4),
                                    'away': round(1 - p_home_cover, 4)}}

    # Primeros 5 innings: λ escalada (baseline aproximado)
    lam5_h, lam5_a = lam_h * (5 / 9), lam_a * (5 / 9)
    ph5 = _poisson_pmf(lam5_h)
    pa5 = _poisson_pmf(lam5_a)
    total5_pmf = np.convolve(ph5, pa5)[:2 * MAX_RUNS + 1]
    first5_probs = {}
    for line in first5_lines:
        threshold = int(line) + 1
        over = float(total5_pmf[threshold:].sum())
        first5_probs[str(line)] = {'over': round(over, 4), 'under': round(1 - over, 4)}

    return {
        'lam_home': round(lam_h, 3),
        'lam_away': round(lam_a, 3),
        'pred_total': round(lam_h + lam_a, 2),
        'p_home_win': round(p_home_win, 4),
        'p_away_win': round(p_away_win, 4),
        'total_line_probs': total_probs,
        'runline_probs': runline_probs,
        'first5_probs': first5_probs,
    }
