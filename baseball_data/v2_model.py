"""
Modelo v2 MLB: Poisson GLM (PoissonRegressor, link log) con features rodantes
derivadas 100% de datos de juego (sin lookahead, sin depender de endpoints bloqueados).

Features por equipo-juego:
- off30 / def30: carreras anotadas / permitidas por juego (ventana 30 juegos, split home/away)
- hits_for30 / hits_against30
- starter_def30: carreras permitidas en entradas 1-6 (proxy de calidad del abridor rival)
- bullpen_def30: carreras permitidas en entradas 7+ (proxy de bullpen rival)
- starter_off30 / bullpen_off30: lo mismo del lado ofensivo
- rest: días de descanso
- park: factor del parque del local (total carreras en juegos de casa / media de liga)
- is_home

Refit cada REFIT_EVERY juegos con todos los datos previos (walking-forward).
Las probabilidades de mercados salen de la convolución de Poissons con λ del GLM.
"""
import math
import numpy as np
from sklearn.linear_model import PoissonRegressor

MAX_RUNS = 24
REFIT_EVERY = 40

FEATURES = [
    'off30', 'def30', 'hits_for30', 'hits_against30',
    'starter_def30', 'bullpen_def30', 'starter_off30', 'bullpen_off30',
    'rest', 'park', 'is_home',
]


def _poisson_pmf(lam, n=MAX_RUNS):
    if lam <= 0:
        lam = 0.1
    k = np.arange(n + 1)
    fact = np.array([math.factorial(int(x)) for x in k], dtype=float)
    with np.errstate(under='ignore'):
        p = np.exp(-lam) * np.power(lam, k) / fact
    p = p / p.sum()
    return p


def _skellam_pmf(lam_h, lam_a, n=MAX_RUNS):
    ph = _poisson_pmf(lam_h, n)
    pa = _poisson_pmf(lam_a, n)
    return np.convolve(ph, pa[::-1]), n  # pmf[d + n] = P(diff = d)


def _split_innings(innings):
    """(carreras 1-6, carreras 7+) desde el dict de innings."""
    r16 = r7 = 0.0
    for k, v in innings.items():
        if not str(k).isdigit():
            continue
        if int(k) <= 6:
            r16 += float(v or 0)
        else:
            r7 += float(v or 0)
    return r16, r7


class V2State:
    """Estado rodante por equipo + buffer de filas de entrenamiento."""

    def __init__(self, warm_games=None):
        self.games = {}  # team_id -> list de dicts por juego (cronológico)
        self.rows = []   # filas de entrenamiento (features, y, team_id, game_id)
        self._park = {}  # team_id -> (suma_total_casa, n_casa)
        self.league_total = []  # totales de todos los juegos para el parque
        if warm_games:
            for g in warm_games:
                self.update(g)

    def _entry(self, tid):
        if tid not in self.games:
            self.games[tid] = []
        return self.games[tid]

    def _avg(self, tid, key, n=30, default=None):
        hist = self.games.get(tid, [])
        vals = [h[key] for h in hist[-n:] if h.get(key) is not None]
        if not vals:
            return default
        return float(np.mean(vals))

    def _rest_days(self, tid, date):
        hist = self.games.get(tid, [])
        if not hist:
            return 4.0
        last = hist[-1]['date']
        days = (date - last).total_seconds() / 86400.0
        return max(0.0, min(days, 10.0))

    def park_factor(self, home_id):
        if home_id not in self._park or self._park[home_id][1] == 0:
            return 1.0
        total, n = self._park[home_id]
        league_avg = float(np.mean(self.league_total[-1000:])) if self.league_total else 9.0
        pf = (total / n) / league_avg
        return float(np.clip(pf, 0.85, 1.15))

    def update(self, g):
        hr, ar = g.home_runs, g.away_runs
        if hr is None or ar is None:
            return
        h16, h7 = _split_innings(g.innings_home)
        a16, a7 = _split_innings(g.innings_away)

        h_entry = {
            'date': g.date, 'is_home': 1, 'runs_for': hr, 'runs_against': ar,
            'hits_for': g.home_hits or 0, 'hits_against': g.away_hits or 0,
            'starter_for': h16, 'starter_against': a16,
            'bullpen_for': h7, 'bullpen_against': a7,
        }
        a_entry = {
            'date': g.date, 'is_home': 0, 'runs_for': ar, 'runs_against': hr,
            'hits_for': g.away_hits or 0, 'hits_against': g.home_hits or 0,
            'starter_for': a16, 'starter_against': h16,
            'bullpen_for': a7, 'bullpen_against': h7,
        }
        self._entry(g.home_team_id).append(h_entry)
        self._entry(g.away_team_id).append(a_entry)

        if home_id := g.home_team_id:
            self._park.setdefault(home_id, [0, 0])
            self._park[home_id][0] += hr + ar
            self._park[home_id][1] += 1
            self.league_total.append(hr + ar)

    def _features(self, tid, opp_id, is_home, date):
        off30 = self._avg(tid, 'runs_for')
        def30 = self._avg(tid, 'runs_against')
        hits_for30 = self._avg(tid, 'hits_for')
        hits_against30 = self._avg(tid, 'hits_against')
        starter_def30 = self._avg(tid, 'starter_against')
        bullpen_def30 = self._avg(tid, 'bullpen_against')
        starter_off30 = self._avg(tid, 'starter_for')
        bullpen_off30 = self._avg(tid, 'bullpen_for')
        defaults = [4.4, 4.4, 8.5, 8.5, 2.6, 1.8, 2.6, 1.8]
        vals = [off30, def30, hits_for30, hits_against30,
                starter_def30, bullpen_def30, starter_off30, bullpen_off30]
        vals = [d if v is None else v for v, d in zip(vals, defaults)]
        return [*vals, self._rest_days(tid, date), self.park_factor(opp_id if is_home else tid), is_home]

    def add_training_rows(self, g):
        hr, ar = g.home_runs, g.away_runs
        if hr is None or ar is None:
            return
        fh = self._features(g.home_team_id, g.away_team_id, 1, g.date)
        fa = self._features(g.away_team_id, g.home_team_id, 0, g.date)
        self.rows.append((fh, hr))
        self.rows.append((fa, ar))


class V2Model:
    def __init__(self, warm_games=None):
        self.state = V2State(warm_games)
        self.model = None
        self._n_since_refit = 0

    def _refit(self):
        if len(self.state.rows) < 200:
            return
        X = np.array([r[0] for r in self.state.rows], dtype=float)
        y = np.array([r[1] for r in self.state.rows], dtype=float)
        self.model = PoissonRegressor(alpha=0.5, max_iter=2000, fit_intercept=True)
        self.model.fit(X, y)

    def predict(self, g):
        """Predice λ home/away usando el GLM actual (fallback al baseline si no hay modelo)."""
        self._refit_if_needed()
        fh = np.array([self.state._features(g.home_team_id, g.away_team_id, 1, g.date)], dtype=float)
        fa = np.array([self.state._features(g.away_team_id, g.home_team_id, 0, g.date)], dtype=float)
        if self.model is not None:
            lam_h = float(self.model.predict(fh)[0])
            lam_a = float(self.model.predict(fa)[0])
        else:
            lam_h, lam_a = self._fallback_lambdas(g)
        return max(lam_h, 0.5), max(lam_a, 0.5)

    def _refit_if_needed(self):
        self._n_since_refit += 1
        if self.model is None or self._n_since_refit >= REFIT_EVERY:
            self._refit()
            self._n_since_refit = 0

    def _fallback_lambdas(self, g):
        off_h = self.state._avg(g.home_team_id, 'runs_for', default=4.4)
        def_a = self.state._avg(g.away_team_id, 'runs_against', default=4.4)
        off_a = self.state._avg(g.away_team_id, 'runs_for', default=4.4)
        def_h = self.state._avg(g.home_team_id, 'runs_against', default=4.4)
        return (off_h + def_a) / 2, (off_a + def_h) / 2

    def update(self, g):
        """Registra el resultado y las filas de entrenamiento ANTES de actualizar el estado."""
        self.state.add_training_rows(g)
        self.state.update(g)


def market_probabilities(lam_h, lam_a, total_lines=(5.5, 6.5, 7.5, 8.5, 9.5, 10.5, 11.5),
                         first5_lines=(2.5, 3.5, 4.5, 5.5)):
    ph = _poisson_pmf(lam_h)
    pa = _poisson_pmf(lam_a)
    total_pmf = np.convolve(ph, pa)[:2 * MAX_RUNS + 1]

    total_probs = {}
    for line in total_lines:
        threshold = int(line) + 1
        over = float(total_pmf[threshold:].sum())
        total_probs[str(line)] = {'over': round(over, 4), 'under': round(1 - over, 4)}

    diff_pmf, shift = _skellam_pmf(lam_h, lam_a)
    p_tie = float(diff_pmf[shift])
    p_home_win = float(diff_pmf[shift + 1:].sum()) + 0.5 * p_tie
    p_home_cover = float(diff_pmf[shift + 2:].sum())

    lam5_h, lam5_a = lam_h * (5 / 9), lam_a * (5 / 9)
    total5_pmf = np.convolve(_poisson_pmf(lam5_h), _poisson_pmf(lam5_a))[:2 * MAX_RUNS + 1]
    first5_probs = {}
    for line in first5_lines:
        threshold = int(line) + 1
        over = float(total5_pmf[threshold:].sum())
        first5_probs[str(line)] = {'over': round(over, 4), 'under': round(1 - over, 4)}

    return {
        'lam_home': round(lam_h, 3), 'lam_away': round(lam_a, 3),
        'pred_total': round(lam_h + lam_a, 2),
        'p_home_win': round(p_home_win, 4), 'p_away_win': round(1 - p_home_win, 4),
        'total_line_probs': total_probs,
        'runline_probs': {'1.5': {'home': round(p_home_cover, 4), 'away': round(1 - p_home_cover, 4)}},
        'first5_probs': first5_probs,
    }
