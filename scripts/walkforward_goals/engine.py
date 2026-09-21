"""
Walk-forward GOLES O/U — PASO 2: motor de simulación (sin lookahead).

Para cada partido (en orden cronológico), calcula λ_local/λ_visitante replicando
EXACTAMENTE la cadena de producción (dixon_coles.calculate_lambda_parameters):

  1. league_home_avg / league_away_avg: últimos 200 partidos de la liga (730d)
  2. home_attack: media fthg últimos 30 de local del equipo (730d, min 10)
  3. away_attack:  media ftag últimos 30 de visitante (730d, min 10)
  4. home_defense: media ftag recibidos últimos 30 de local (730d, min 10)
  5. away_defense: media fthg recibidos últimos 30 de visitante (730d, min 10)
  6. raw_lh = (home_attack/league_home_avg) * (away_defense/league_away_avg) * league_home_avg * 1.15
     raw_la = (away_attack/league_away_avg) * (home_defense/league_home_avg) *  league_away_avg * 0.95
  7. piso de liga: si total < league_total_avg → escalar
  8. clamp λ a [max(0.1,p05), min(p99,6.0)] (últimos 500 de la liga, 730d)

SOLO datos estrictamente anteriores al partido (fecha < fecha_partido).
Salida: wf_engine_out.pkl con λ, probabilidades (Poisson/NB), cuotas y resultado.

Sin dependencias de Django. No toca producción.
"""
import bisect
import os
import sys
from collections import defaultdict
from datetime import timedelta

import numpy as np
import pandas as pd

IN = '/var/www/predicta.com.co/scripts/walkforward_goals/wf_goals_full.pkl'
OUT = '/var/www/predicta.com.co/scripts/walkforward_goals/wf_engine_out.pkl'

WINDOW_DAYS = 730
N_LEAGUE_AVG = 200      # últimos 200 para medias de liga
N_LEAGUE_LIMITS = 500   # últimos 500 para percentiles
N_TEAM = 30             # últimos 30 por equipo/venue
MIN_TEAM = 10           # mínimo de partidos para usar media del equipo

try:
    from scipy.stats import poisson as _pois
    from scipy.stats import nbinom as _nb
except ImportError:
    print('ERROR: scipy requerido')
    sys.exit(1)


def main():
    df = pd.read_pickle(IN)
    df = df.sort_values(['date', 'div', 'home']).reset_index(drop=True)
    print(f'Filas: {len(df)} | con cuotas+resultado: {(df["has_odds"] & df["has_goal"]).sum()}')

    # estructuras incrementales
    team_home = defaultdict(list)   # team -> [(date, gf, ga)]
    team_away = defaultdict(list)
    league_all = defaultdict(list)  # div -> [(date, fthg, ftag)]
    league_dates = defaultdict(list)  # para bisect

    rows = []
    n_skip_hist = 0

    # Serie por equipo para φ rolling de goles (por liga): sum y sumsq de goles/equipo
    # (los goles por equipo de todos los partidos jugados: d hg y ag)
    for i, r in df.iterrows():
        d = r['date']
        div = r['div']
        home = r['home']
        away = r['away']

        has_g = bool(r['has_goal'])
        has_o = bool(r['has_odds'])

        if has_g and has_o:
            # ── calcular λ con historia previa ──
            win_start = d - timedelta(days=WINDOW_DAYS)
            lall = league_all[div]
            ld = league_dates[div]
            i0 = bisect.bisect_left(ld, win_start)
            i1 = bisect.bisect_left(ld, d)  # estricto: < fecha partido
            recent = lall[i0:i1]

            if len(recent) >= 50:
                lg_h = [x[1] for x in recent]
                lg_a = [x[2] for x in recent]
                lg_h200 = lg_h[-N_LEAGUE_AVG:]
                lg_a200 = lg_a[-N_LEAGUE_AVG:]
                league_home_avg = float(np.mean(lg_h200)) if lg_h200 else 1.5
                league_away_avg = float(np.mean(lg_a200)) if lg_a200 else 1.2

                # equipo local
                th = team_home[home]
                k0 = bisect.bisect_left([x[0] for x in th], win_start)
                k1 = bisect.bisect_left([x[0] for x in th], d)
                hm = th[k0:k1][-N_TEAM:]
                home_attack = float(np.mean([x[1] for x in hm])) if len(hm) >= MIN_TEAM else league_home_avg
                home_defense = float(np.mean([x[2] for x in hm])) if len(hm) >= MIN_TEAM else league_away_avg

                # equipo visitante
                ta = team_away[away]
                j0 = bisect.bisect_left([x[0] for x in ta], win_start)
                j1 = bisect.bisect_left([x[0] for x in ta], d)
                am = ta[j0:j1][-N_TEAM:]
                away_attack = float(np.mean([x[1] for x in am])) if len(am) >= MIN_TEAM else league_away_avg
                away_defense = float(np.mean([x[2] for x in am])) if len(am) >= MIN_TEAM else league_home_avg

                raw_lh = (home_attack / league_home_avg) * (away_defense / league_away_avg) * league_home_avg * 1.15
                raw_la = (away_attack / league_away_avg) * (home_defense / league_home_avg) * league_away_avg * 0.95

                league_total_avg = league_home_avg + league_away_avg
                tot_raw = raw_lh + raw_la
                if tot_raw < league_total_avg and tot_raw > 0:
                    scale = league_total_avg / tot_raw
                    raw_lh *= scale
                    raw_la *= scale

                # límites p05/p99 últimos 500
                lim_slice = recent[-N_LEAGUE_LIMITS:]
                all_vals = [x[1] for x in lim_slice] + [x[2] for x in lim_slice]
                if len(all_vals) >= 50:
                    p05 = float(np.percentile(all_vals, 5))
                    p99 = float(np.percentile(all_vals, 99))
                    lmin = max(0.1, p05)
                    lmax = min(p99, 6.0)
                else:
                    lmin, lmax = 0.1, 4.0
                lam_h = max(lmin, min(lmax, raw_lh))
                lam_a = max(lmin, min(lmax, raw_la))
                lam_total = lam_h + lam_a

                # probabilidades
                p_over = float(1.0 - _pois.cdf(np.floor(2.5), lam_total))
                p_under = 1.0 - p_over

                # φ rolling de liga (NB): var/mean de goles por equipo
                # usar goles/equipo acumulados (hg y ag) dentro de ventana
                g_vals = lg_h + lg_a
                mu = float(np.mean(g_vals))
                var_ = float(np.var(g_vals))
                phi = (mu * mu / (var_ - mu)) if var_ > mu else 1000.0
                phi = float(min(max(phi, 5.0), 500.0))
                n_nb = phi
                pg = n_nb / (n_nb + lam_total)
                p_over_nb = float(1.0 - _nb.cdf(int(np.floor(2.5)), n_nb, pg))
                p_under_nb = 1.0 - p_over_nb

                # devig
                oo, ou = float(r['o_over']), float(r['o_under'])
                imp_o, imp_u = 1.0 / oo, 1.0 / ou
                fair_o = imp_o / (imp_o + imp_u)
                fair_u = 1.0 - fair_o

                rows.append({
                    'date': d, 'season': r['season'], 'div': div, 'home': home, 'away': away,
                    'fthg': int(r['fthg']), 'ftag': int(r['ftag']), 'tot': int(r['fthg'] + r['ftag']),
                    'lam_h': lam_h, 'lam_a': lam_a, 'lam_total': lam_total,
                    'league_total_avg': league_total_avg,
                    'p_over': p_over, 'p_under': p_under,
                    'p_over_nb': p_over_nb, 'p_under_nb': p_under_nb, 'phi': phi,
                    'o_over': oo, 'o_under': ou,
                    'o_over_max': float(r['o_over_max']) if pd.notna(r['o_over_max']) else np.nan,
                    'o_under_max': float(r['o_under_max']) if pd.notna(r['o_under_max']) else np.nan,
                    'fair_o': fair_o, 'fair_u': fair_u,
                    'over_won': bool(r['fthg'] + r['ftag'] > 2.5),
                })
            else:
                n_skip_hist += 1

        # ── actualizar historia (después de predecir) ──
        if has_g:
            fh, fa = int(r['fthg']), int(r['ftag'])
            if fh >= 0 and fa >= 0:
                team_home[home].append((d, fh, fa))
                team_away[away].append((d, fa, fh))
                league_all[div].append((d, fh, fa))
                league_dates[div].append(d)

        if (i + 1) % 10000 == 0:
            print(f'  ...{i+1} filas procesadas ({len(rows)} simuladas)', flush=True)

    out = pd.DataFrame(rows)
    print(f'\nSimulados: {len(out)} | skip por historia insuficiente: {n_skip_hist}')
    if len(out):
        print(f'Rango: {out["date"].min().date()} → {out["date"].max().date()}')
        print(f'Over rate real: {out["over_won"].mean()*100:.2f}%')
        print(f'λ_total medio: {out["lam_total"].mean():.3f} | real medio: {out["tot"].mean():.3f}')
        print(f'p_over medio: {out["p_over"].mean()*100:.2f}% | fair_o medio: {out["fair_o"].mean()*100:.2f}%')
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    out.to_pickle(OUT)
    print(f'Guardado: {OUT}')


if __name__ == '__main__':
    main()
