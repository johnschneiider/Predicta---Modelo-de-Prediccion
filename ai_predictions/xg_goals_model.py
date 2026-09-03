"""
xg_goals_model.py — Modelo de goles basado en Expected Goals (xG) real
═══════════════════════════════════════════════════════════════════════════
Fase 2 (2026-09-03, plan aprobado por John): afinar el λ de goles usando xG
(campo xg_home/xg_away de football_data.Match, ingerido desde Flashscore y
API-Football) en lugar de solo goles crudos (Dixon-Coles).

El xG converge más rápido que los goles (~25 remates/partido vs ~2.6 goles) y
captura mejor la forma actual. Se integra al pipeline web como UN MODELO MÁS
en el ensemble de goals_*; la "Predicción Oficial" (promedio ponderado por
confidence) lo absorbe automáticamente en web, auto_betting y value_betting.

Importante: si no hay datos xG suficientes para el cruce, devuelve None y el
ensemble queda como está (Dixon-Coles puro) — cero riesgo para ligas chicas.

Walk-forward: el parámetro `asof` (fecha) permite validar con datos solo
anteriores al partido; en producción se omite (usa todo lo disponible).
"""
import logging
from datetime import datetime, timedelta

from django.db.models import Avg

from football_data.models import Match, League

logger = logging.getLogger('ai_predictions')

MIN_XG_MATCHES = 5          # mínimo de partidos con xG por equipo para opinar
MAX_WINDOW = 20             # últimos N partidos con xG para promedios
MAX_AGE_DAYS = 400          # no usar xG más viejo que esto


class XGGoalsModel:
    name = "XG Goals Model"

    # ── utilidades ──

    @staticmethod
    def _series(team, league, venue, asof):
        """
        Series de xG a favor y en contra del equipo `team` (venue 'home'|'away'
        | None = todos), estrictamente anteriores a `asof`.
        Devuelve (n, mean_for, mean_against) o None si no hay datos.
        """
        qs = Match.objects.filter(league=league).exclude(xg_home__isnull=True)
        if asof:
            qs = qs.filter(date__lt=asof)
        else:
            qs = qs.filter(date__lt=datetime.now().date())
        qs = qs.filter(date__gte=(asof or datetime.now().date()) - timedelta(days=MAX_AGE_DAYS))

        if venue == 'home':
            qs = qs.filter(home_team=team)
            for_ = 'xg_home'
            against = 'xg_away'
        elif venue == 'away':
            qs = qs.filter(away_team=team)
            for_ = 'xg_away'
            against = 'xg_home'
        else:
            return None

        qs = qs.order_by('-date')[:MAX_WINDOW]
        agg = qs.aggregate(f=Avg(for_), a=Avg(against))
        n = qs.count()
        if n == 0 or agg['f'] is None:
            return None
        return n, float(agg['f']), float(agg['a'])

    @staticmethod
    def _league_avg(league, asof):
        """xG promedio POR EQUIPO por partido en la liga (ventana reciente)."""
        qs = Match.objects.filter(league=league).exclude(xg_home__isnull=True)
        if asof:
            qs = qs.filter(date__lt=asof)
        qs = qs.filter(date__gte=(asof or datetime.now().date()) - timedelta(days=MAX_AGE_DAYS))
        agg = qs.aggregate(f=Avg('xg_home'), a=Avg('xg_away'))
        if agg['f'] is None or agg['a'] is None:
            return None
        return (float(agg['f']) + float(agg['a'])) / 2.0

    # ── API pública ──

    def compute_lambda(self, home_team, away_team, league, asof=None):
        """
        λ_home y λ_away estilo Dixon-Coles pero con xG.
        Devuelve (lam_home, lam_away, n_min, league_avg) o None si faltan datos.
        """
        h = self._series(home_team, league, 'home', asof)
        a = self._series(away_team, league, 'away', asof)
        if not h or not a:
            return None
        if h[0] < MIN_XG_MATCHES or a[0] < MIN_XG_MATCHES:
            return None
        lg_avg = self._league_avg(league, asof)
        if not lg_avg:
            return None

        n_home_for, h_for, h_against = h
        n_away_for, a_for, a_against = a
        # Ratios de ataque/defensa relativos al promedio de la liga
        att_home = h_for / lg_avg
        def_home = h_against / lg_avg
        att_away = a_for / lg_avg
        def_away = a_against / lg_avg
        lam_home = att_home * def_away * lg_avg
        lam_away = att_away * def_home * lg_avg
        return lam_home, lam_away, min(n_home_for, n_away_for), lg_avg

    def predict_match(self, home_team, away_team, league, pred_type='goals_total'):
        if pred_type not in ('goals_total', 'goals_home', 'goals_away'):
            return None
        try:
            r = self.compute_lambda(home_team, away_team, league)
            if not r:
                return None
            lam_home, lam_away, n_min, lg_avg = r
            # confidence crece con la muestra xG (0.4 → 0.7)
            confidence = min(0.7, 0.35 + 0.04 * n_min)
            if pred_type == 'goals_home':
                prediction = lam_home
            elif pred_type == 'goals_away':
                prediction = lam_away
            else:
                prediction = lam_home + lam_away
            return {
                'model_name': self.name,
                'prediction': round(float(prediction), 2),
                'confidence': round(confidence, 2),
                'probabilities': {
                    'lambda_home': round(float(lam_home), 3),
                    'lambda_away': round(float(lam_away), 3),
                    'n_xg_min': n_min,
                    'league_avg_xg': round(float(lg_avg), 3),
                },
                'total_matches': n_min,
            }
        except Exception as e:
            logger.warning(f'XGGoalsModel error para {home_team} vs {away_team}: {e}')
            return None


xg_goals_model = XGGoalsModel()
