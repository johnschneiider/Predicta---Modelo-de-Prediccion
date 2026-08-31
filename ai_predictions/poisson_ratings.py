"""
Motor de ratings Poisson regularizados (ridge) — SOLUCIÓN DEFINITIVA de λ.

Reemplaza los promedios muestrales sin shrinkage (que causaban:
- inflación de λ de goles para ataques fuertes → la curva de fiabilidad invertida,
- λ de tiros a puerta ruidoso por ventanas de 20 partidos por venue)
por una regresión de Poisson con:
  log λ_home = α + att[home] + def[away] + home_adv
  log λ_away = α + att[away] + def[home]
con regularización ridge sobre att/def (los ratings se encogen hacia la media
de liga, eliminando sobreconfianza) y pesos con decaimiento temporal (τ=90d)
para adaptarse a la forma reciente.

Validado walk-forward (scripts/poisson_bench.py, 26 ligas, 1224 partidos test):
  GOLES:  sesgo +0.36 → −0.10 | RMSE 1.73 → 1.69 | ρ 0.185 → 0.223
  SOT:    RMSE 3.25 → 3.19     | ρ 0.205 → 0.248 (mejor discriminación)
  Curvas de fiabilidad monótonas en ambos mercados.

Uso:
  from ai_predictions.poisson_ratings import poisson_ratings_engine
  res = poisson_ratings_engine.predict_total(home, away, league, 'sot')
  # res = {'lambda': float, 'confidence': float, 'n_matches': int} | None
"""
import logging
import threading
import numpy as np
from datetime import timedelta
from django.utils import timezone
from scipy.optimize import minimize
from scipy.stats import poisson

logger = logging.getLogger(__name__)

TAU_DAYS = 90.0      # decaimiento temporal (días)
RIDGE = 1.0          # fuerza de regularización de ratings
DATA_WINDOW_DAYS = 730
MIN_LEAGUE_MATCHES = 60   # menos que esto → None (fallback al pipeline viejo)
MIN_TEAM_MATCHES = 5

MARKET_COLS = {
    'goals': ('fthg', 'ftag'),
    'sot': ('hst', 'ast'),
    'corners': ('hc', 'ac'),
}


class PoissonRatingsEngine:
    """Ajusta y sirve ratings Poisson por (liga, mercado) con caché diaria."""

    def __init__(self):
        self._cache = {}
        self._lock = threading.Lock()

    # ── ajuste ──────────────────────────────────────────────
    def _fit(self, league_id, market, rows):
        """rows: list of dicts {home, away, yh, ya, age_days}."""
        col_h, col_a = MARKET_COLS[market]
        teams = sorted({r['home'] for r in rows} | {r['away'] for r in rows})
        t2i = {t: i for i, t in enumerate(teams)}
        n = len(teams)
        hh = np.array([t2i[r['home']] for r in rows])
        aa = np.array([t2i[r['away']] for r in rows])
        yh = np.array([r['yh'] for r in rows], dtype=float)
        ya = np.array([r['ya'] for r in rows], dtype=float)
        w = np.exp(-np.array([r['age_days'] for r in rows]) / TAU_DAYS)

        n_params = 2 * n + 2
        x0 = np.zeros(n_params)
        x0[0] = np.log((yh.mean() + ya.mean()) / 2 + 1e-6)

        def nll(x):
            alpha, h_adv = x[0], x[-1]
            att = x[1:1 + n]
            deff = x[1 + n:1 + 2 * n]
            lam_h = np.exp(alpha + att[hh] + deff[aa] + h_adv)
            lam_a = np.exp(alpha + att[aa] + deff[hh])
            ll = -np.sum(w * (poisson.logpmf(yh, lam_h) + poisson.logpmf(ya, lam_a)))
            pen = RIDGE * (np.sum(att ** 2) + np.sum(deff ** 2))
            return ll + pen

        res = minimize(nll, x0, method='L-BFGS-B',
                       options={'maxiter': 2000, 'ftol': 1e-10, 'gtol': 1e-7})
        x = res.x
        model = {
            'alpha': x[0],
            'att': dict(zip(teams, x[1:1 + n])),
            'def': dict(zip(teams, x[1 + n:1 + 2 * n])),
            'home_adv': x[-1],
            'team_counts': {t: 0 for t in teams},
        }
        for r in rows:
            model['team_counts'][r['home']] += 1
            model['team_counts'][r['away']] += 1
        model['n_matches'] = len(rows)
        return model

    # ── API pública ─────────────────────────────────────────
    def predict_total(self, home_team, away_team, league, market):
        """λ total esperado. Devuelve dict o None si no hay modelo."""
        if market not in MARKET_COLS:
            return None
        col_h, col_a = MARKET_COLS[market]
        today = timezone.now().date()
        key = (league.id, market, today)

        with self._lock:
            model = self._cache.get(key)
            if model is None:
                model = self._build_model(league, col_h, col_a)
                if model is not None:
                    self._cache[key] = model
            # cache chica: limpiar entradas viejas
            if len(self._cache) > 60:
                for k in list(self._cache):
                    if k[2] != today:
                        del self._cache[k]

        if model is None:
            return None
        if home_team not in model['att'] or away_team not in model['att']:
            return None

        lam_h = np.exp(model['alpha'] + model['att'][home_team]
                       + model['def'][away_team] + model['home_adv'])
        lam_a = np.exp(model['alpha'] + model['att'][away_team]
                       + model['def'][home_team])
        lam_total = float(lam_h + lam_a)

        min_games = min(model['team_counts'].get(home_team, 0),
                        model['team_counts'].get(away_team, 0))
        confidence = 0.50 + 0.20 * min(1.0, min_games / 15.0)

        return {
            'lambda': lam_total,
            'lambda_home': float(lam_h),
            'lambda_away': float(lam_a),
            'confidence': round(confidence, 3),
            'n_matches': model['n_matches'],
            'method': 'Poisson ratings (ridge, τ=90d)',
        }

    def _build_model(self, league, col_h, col_a):
        market = None
        try:
            from football_data.models import Match
            for mk, cols in MARKET_COLS.items():
                if cols == (col_h, col_a):
                    market = mk
            cutoff = timezone.now().date() - timedelta(days=DATA_WINDOW_DAYS)
            qs = Match.objects.filter(
                league=league, date__gte=cutoff,
                **{f'{col_h}__isnull': False, f'{col_a}__isnull': False},
            ).values('date', 'home_team', 'away_team', col_h, col_a)
            rows = []
            today = timezone.now().date()
            for m in qs:
                yh, ya = m[col_h], m[col_a]
                if yh is None or ya is None:
                    continue
                rows.append({
                    'home': m['home_team'], 'away': m['away_team'],
                    'yh': float(yh), 'ya': float(ya),
                    'age_days': float((today - m['date']).days),
                })
            if len(rows) < MIN_LEAGUE_MATCHES:
                return None
            return self._fit(league.id, market, rows)
        except Exception as e:
            logger.error(f'poisson_ratings._build_model({league.name},{market}): {e}')
            return None


poisson_ratings_engine = PoissonRatingsEngine()
