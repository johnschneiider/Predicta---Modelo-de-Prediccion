# -*- coding: utf-8 -*-
"""
Modelo base NBA para apuestas reales (baseline rodante Marcador ~ Normal).

Es EXACTAMENTE el modelo del estudio de ROI por mercado/día/temporada
(2026-10-03): splits casa/visita, shrinkage 6 a media 112, σ=17.
Produce probabilidades para:
  - Total de puntos (over/under) a cualquier línea
  - Ganador (moneyline)
  - Hándicap (spread) a cualquier línea
"""
from scipy.stats import norm

from .models import NBAGame

SIGMA = 17.0
MEAN = 112.0
SHRINK = 6


def _team_stats(team_id):
    """(off_home, def_home, off_away, def_away) con shrinkage."""
    qs = NBAGame.objects.filter(home_points__isnull=False, away_points__isnull=False)
    h = qs.filter(home_team_id=team_id)
    a = qs.filter(away_team_id=team_id)
    gp_h = h.count()
    gp_a = a.count()
    gf_h = sum(h.values_list('home_points', flat=True))
    ga_h = sum(h.values_list('away_points', flat=True))
    gf_a = sum(a.values_list('away_points', flat=True))
    ga_a = sum(a.values_list('home_points', flat=True))
    off_h = (gf_h + MEAN * SHRINK) / (gp_h + SHRINK)
    def_h = (ga_h + MEAN * SHRINK) / (gp_h + SHRINK)
    off_a = (gf_a + MEAN * SHRINK) / (gp_a + SHRINK)
    def_a = (ga_a + MEAN * SHRINK) / (gp_a + SHRINK)
    return off_h, def_h, off_a, def_a


def predict_game(home_team, away_team, total_line=None, spread_home_line=None):
    """Probabilidades del baseline para un partido. Líneas opcionales."""
    off_hh, def_hh, _, _ = _team_stats(home_team.id)
    _, _, off_aa, def_aa = _team_stats(away_team.id)
    mu_h = (off_hh + def_aa) / 2
    mu_a = (off_aa + def_hh) / 2
    out = {
        'mu_home': round(mu_h, 1),
        'mu_away': round(mu_a, 1),
        'pred_total': round(mu_h + mu_a, 1),
        'p_home_win': float(norm.cdf((mu_h - mu_a) / SIGMA)),
        'p_away_win': float(1 - norm.cdf((mu_h - mu_a) / SIGMA)),
    }
    if total_line is not None:
        p_over = float(1 - norm.cdf((float(total_line) - (mu_h + mu_a)) / SIGMA))
        out['p_total_over'] = p_over
        out['p_total_under'] = 1 - p_over
    if spread_home_line is not None:
        # home cubre si margen > - línea_local (línea -1.5 → margen > 1.5)
        p_cover_h = float(1 - norm.cdf((-float(spread_home_line) - (mu_h - mu_a)) / SIGMA))
        out['p_spread_home'] = p_cover_h
        out['p_spread_away'] = 1 - p_cover_h
    return out
