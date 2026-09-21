"""
Walk-forward GOLES O/U — PASO 7: test del bug estructural + variantes corregidas.

Hipótesis (del análisis del código): la fórmula de producción normaliza mal los
divisores de referencia:
  actual:  raw_lh = (A_i/lg_H) * (D_j/lg_A) * lg_H * 1.15   ← D_j dividido por lg_A (debería lg_H)
           raw_la = (A_j/lg_A) * (D_i/lg_H) * lg_A * 0.95   ← D_i dividido por lg_H (debería lg_A)
Esto infla λ local ~+26% y desinfla λ visitante ~-21%, total +14~20%.

Variantes simuladas (mismas ventanas/datos que engine.py):
  V0: producción (referencia, del engine ya corrido)
  V1: swap divisors, mantiene 1.15/0.95
  V2: swap divisors, sin multiplicadores (1.0/1.0)
Métricas: sesgo λ_h/λ_a/λ_total vs real; AUC/Brier del p_over vs mercado;
ROI de estrategia edge≥5% (avg y max odds) tras corrección walk-forward de nivel.
"""
import bisect
import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.metrics import brier_score_loss, roc_auc_score
from datetime import timedelta
from collections import defaultdict

BASE = '/var/www/predicta.com.co/scripts/walkforward_goals'
IN = f'{BASE}/wf_goals_full.pkl'

WINDOW_DAYS = 730
N_LEAGUE_AVG = 200
N_TEAM = 30
MIN_TEAM = 10


def run_variant(df, mode):
    """mode: 'swap' o 'swap_nomult'. Devuelve arrays lam_h, lam_a."""
    team_home = defaultdict(list)
    team_away = defaultdict(list)
    league_all = defaultdict(list)
    league_dates = defaultdict(list)
    out_lh = np.full(len(df), np.nan)
    out_la = np.full(len(df), np.nan)

    for i, r in df.iterrows():
        d = r['date']; div = r['div']; home = r['home']; away = r['away']
        has_g = bool(r['has_goal']); has_o = bool(r['has_odds'])
        if has_g and has_o:
            win_start = d - timedelta(days=WINDOW_DAYS)
            lall = league_all[div]; ld = league_dates[div]
            i0 = bisect.bisect_left(ld, win_start); i1 = bisect.bisect_left(ld, d)
            recent = lall[i0:i1]
            if len(recent) >= 50:
                lg_h = [x[1] for x in recent][-N_LEAGUE_AVG:]
                lg_a = [x[2] for x in recent][-N_LEAGUE_AVG:]
                lgH = float(np.mean(lg_h)); lgA = float(np.mean(lg_a))

                th = team_home[home]
                k0 = bisect.bisect_left([x[0] for x in th], win_start)
                k1 = bisect.bisect_left([x[0] for x in th], d)
                hm = th[k0:k1][-N_TEAM:]
                A_i = float(np.mean([x[1] for x in hm])) if len(hm) >= MIN_TEAM else lgH
                D_i = float(np.mean([x[2] for x in hm])) if len(hm) >= MIN_TEAM else lgA

                ta = team_away[away]
                j0 = bisect.bisect_left([x[0] for x in ta], win_start)
                j1 = bisect.bisect_left([x[0] for x in ta], d)
                am = ta[j0:j1][-N_TEAM:]
                A_j = float(np.mean([x[1] for x in am])) if len(am) >= MIN_TEAM else lgA
                D_j = float(np.mean([x[2] for x in am])) if len(am) >= MIN_TEAM else lgH

                if mode == 'swap':
                    h_mult, a_mult = 1.15, 0.95
                else:
                    h_mult, a_mult = 1.0, 1.0
                # divisores correctos: D_j (goles recibidos por visitante = goles local-style) vs lgH; D_i vs lgA
                raw_lh = (A_i / lgH) * (D_j / lgH) * lgH * h_mult
                raw_la = (A_j / lgA) * (D_i / lgA) * lgA * a_mult

                out_lh[i] = raw_lh
                out_la[i] = raw_la

        if has_g:
            fh, fa = int(r['fthg']), int(r['ftag'])
            if fh >= 0 and fa >= 0:
                team_home[home].append((d, fh, fa))
                team_away[away].append((d, fa, fh))
                league_all[div].append((d, fh, fa))
                league_dates[div].append(d)
    return out_lh, out_la


def main():
    df = pd.read_pickle(IN).sort_values(['date', 'div', 'home']).reset_index(drop=True)
    mask = df['has_goal'] & df['has_odds']
    print(f'evaluables: {mask.sum()}')

    # referencia de producción desde el engine ya corrido
    eng = pd.read_pickle(f'{BASE}/wf_engine_out.pkl')

    results = {}
    for mode in ('swap', 'swap_nomult'):
        lh, la = run_variant(df, mode)
        results[mode] = (lh, la)
        sub = df[mask].copy()
        sub['lh'] = lh[mask.values]
        sub['la'] = la[mask.values]
        sub = sub.dropna(subset=['lh', 'la'])
        print(f'\n=== VARIANTE {mode} ===')
        print(f"  λ_h medio: {sub['lh'].mean():.3f} vs real home {sub['fthg'].mean():.3f}")
        print(f"  λ_a medio: {sub['la'].mean():.3f} vs real away {sub['ftag'].mean():.3f}")
        print(f"  λ_total:   {(sub['lh']+sub['la']).mean():.3f} vs real {(sub['fthg']+sub['ftag']).mean():.3f}")

    # comparar con producción (engine)
    print('\n=== PRODUCCIÓN (del engine) ===')
    print(f"  λ_total medio: {eng['lam_total'].mean():.3f} vs real {eng['tot'].mean():.3f}")
    print(f"  λ_h medio: {eng['lam_h'].mean():.3f} | λ_a medio: {eng['lam_a'].mean():.3f}")
    print(f"  real home: {eng['fthg'].mean():.3f} | real away: {eng['ftag'].mean():.3f}")

    # AUC/Brier de variantes vs mercado (sin corrección de nivel, para ver la forma)
    print('\n=== AUC/Brier vs mercado (sin corrección) ===')
    for mode in ('swap', 'swap_nomult'):
        lh, la = results[mode]
        sub = df[mask].copy()
        sub['ln'] = lh[mask.values] + la[mask.values]
        sub = sub.dropna(subset=['ln'])
        p_over = 1.0 - poisson.cdf(np.floor(2.5), sub['ln'])
        y = ((sub['fthg'] + sub['ftag']) > 2.5).astype(int)
        imp_o = 1.0 / sub['o_over']; imp_u = 1.0 / sub['o_under']
        fair_o = (imp_o / (imp_o + imp_u)).values
        print(f"  {mode}: Brier {brier_score_loss(y, p_over):.4f} | AUC {roc_auc_score(y, p_over):.4f} | "
              f"bias {sub['ln'].mean() - (sub['fthg']+sub['ftag']).mean():+.3f}")
        print(f"          mercado: Brier {brier_score_loss(y, fair_o):.4f} | AUC {roc_auc_score(y, fair_o):.4f}")

    # vig de las cuotas max
    imp_max = 1.0 / df.loc[mask, 'o_over_max'].fillna(df['o_over']) + 1.0 / df.loc[mask, 'o_under_max'].fillna(df['o_under'])
    imp_avg = 1.0 / df.loc[mask, 'o_over'] + 1.0 / df.loc[mask, 'o_under']
    print(f"\nVig medio (BbAv): {(imp_avg.mean()-1)*100:.2f}% | Vig medio (BbMx): {(imp_max.mean()-1)*100:.2f}%")


if __name__ == '__main__':
    main()
