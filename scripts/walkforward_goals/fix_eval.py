"""
Walk-forward GOLES O/U — PASO 8: ¿el modelo ARREGLADO (swap_nomult) se vuelve rentable?

Corre la variante con divisores corregidos y sin multiplicadores → λ casi insesgado
(λ_h 1.455 vs 1.459 real; λ_a 1.100 vs 1.116). Luego evalúa ROI con y sin
corrección de nivel walk-forward residual, en avg y max odds.
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
OUT = f'{BASE}/fixed_out.pkl'

WINDOW_DAYS = 730
N_LEAGUE_AVG = 200
N_TEAM = 30
MIN_TEAM = 10


def main():
    df = pd.read_pickle(IN).sort_values(['date', 'div', 'home']).reset_index(drop=True)
    team_home = defaultdict(list); team_away = defaultdict(list)
    league_all = defaultdict(list); league_dates = defaultdict(list)
    rows = []

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

                # FIX: divisores por la escala correcta, sin multiplicadores fijos
                lam_h = (A_i / lgH) * (D_j / lgH) * lgH
                lam_a = (A_j / lgA) * (D_i / lgA) * lgA
                lam_h = max(0.1, lam_h); lam_a = max(0.1, lam_a)
                lam_t = lam_h + lam_a

                imp_o = 1.0 / float(r['o_over']); imp_u = 1.0 / float(r['o_under'])
                fair_o = imp_o / (imp_o + imp_u)

                rows.append({
                    'date': d, 'season': r['season'], 'div': div, 'home': home, 'away': away,
                    'tot': int(r['fthg'] + r['ftag']), 'lam_h': lam_h, 'lam_a': lam_a, 'lam_total': lam_t,
                    'o_over': float(r['o_over']), 'o_under': float(r['o_under']),
                    'o_over_max': float(r['o_over_max']) if pd.notna(r['o_over_max']) else np.nan,
                    'o_under_max': float(r['o_under_max']) if pd.notna(r['o_under_max']) else np.nan,
                    'fair_o': fair_o, 'fair_u': 1 - fair_o,
                })
        if has_g:
            fh, fa = int(r['fthg']), int(r['ftag'])
            if fh >= 0 and fa >= 0:
                team_home[home].append((d, fh, fa))
                team_away[away].append((d, fa, fh))
                league_all[div].append((d, fh, fa))
                league_dates[div].append(d)

    o = pd.DataFrame(rows).sort_values('date').reset_index(drop=True)
    o['over_won'] = o['tot'] > 2.5
    print(f'n={len(o)} | bias λ: {o["tot"].mean() - o["lam_total"].mean():+.4f}')
    print(f'λ_h {o["lam_h"].mean():.3f} | λ_a {o["lam_a"].mean():.3f} | λ_t {o["lam_total"].mean():.3f}')

    # corrección de nivel residual walk-forward
    ratios = np.full(len(o), np.nan)
    lig_sum, lig_lam = {}, {}
    g_sum = g_lam = 0.0; n_g = 0
    for i, (div, tot_, lam_) in enumerate(zip(o['div'].values, o['tot'].values, o['lam_total'].values)):
        if div in lig_sum and lig_sum[div] >= 300 and lig_lam[div] > 0:
            ratios[i] = lig_sum[div] / lig_lam[div]
        elif n_g >= 300 and g_lam > 0:
            ratios[i] = g_sum / g_lam
        lig_sum[div] = lig_sum.get(div, 0.0) + tot_
        lig_lam[div] = lig_lam.get(div, 0.0) + lam_
        g_sum += tot_; g_lam += lam_; n_g += 1
    o['ratio'] = ratios
    o = o[o['ratio'].notna()].copy()
    o['lam_c'] = o['lam_total'] * o['ratio']
    o['p_over'] = 1.0 - poisson.cdf(np.floor(2.5), o['lam_c'])
    o['p_under'] = 1 - o['p_over']
    print(f'ratio medio: {o["ratio"].mean():.5f} | tras corrección bias: {o["tot"].mean() - o["lam_c"].mean():+.4f}')

    y = o['over_won'].astype(int)
    print(f'\nBrier modelo fijo: {brier_score_loss(y, o["p_over"]):.4f} | mercado: {brier_score_loss(y, o["fair_o"]):.4f}')
    print(f'AUC modelo fijo:   {roc_auc_score(y, o["p_over"]):.4f} | mercado: {roc_auc_score(y, o["fair_o"]):.4f}')

    # ROI grid
    def roi(tag, side, edge_min, ev_min=None, price_col='avg'):
        d = o
        if side == 'over':
            p = d['p_over'].values; fair = d['fair_o'].values
            price = (d['o_over_max'].fillna(d['o_over']) if price_col == 'max' else d['o_over']).values
            won = d['over_won'].values
        elif side == 'under':
            p = d['p_under'].values; fair = d['fair_u'].values
            price = (d['o_under_max'].fillna(d['o_under']) if price_col == 'max' else d['o_under']).values
            won = ~d['over_won'].values
        else:
            eo = (d['p_over'] - d['fair_o']).values; eu = (d['p_under'] - d['fair_u']).values
            take_over = eo >= eu
            p = np.where(take_over, d['p_over'], d['p_under'])
            fair = np.where(take_over, d['fair_o'], d['fair_u'])
            if price_col == 'max':
                price = np.where(take_over, d['o_over_max'].fillna(d['o_over']), d['o_under_max'].fillna(d['o_under']))
            else:
                price = np.where(take_over, d['o_over'], d['o_under'])
            won = np.where(take_over, d['over_won'], ~d['over_won'])
        edge = p - fair; ev = p * price - 1.0
        sel = edge >= edge_min
        if ev_min is not None: sel &= (ev >= ev_min)
        if sel.sum() == 0:
            print(f'  {tag:44s} n=0'); return
        w = won[sel]; pr = price[sel]
        pnl = np.where(w, pr - 1.0, -1.0)
        se = pnl.std(ddof=1)/np.sqrt(len(pnl))
        print(f'  {tag:44s} n={len(pnl):5d} WR={w.mean()*100:5.1f}% ROI={pnl.mean()*100:+6.2f}% (z={pnl.mean()/se:+.1f})')

    print('\nROI modelo fijo (avg odds):')
    roi('FIX OVER edge≥0.03', 'over', 0.03, price_col='avg')
    roi('FIX OVER edge≥0.05', 'over', 0.05, price_col='avg')
    roi('FIX UNDER edge≥0.03', 'under', 0.03, price_col='avg')
    roi('FIX UNDER edge≥0.05', 'under', 0.05, price_col='avg')
    roi('FIX ambos edge≥0.05', 'both', 0.05, price_col='avg')
    print('\nROI modelo fijo (max odds):')
    roi('FIX OVER edge≥0.03 (max)', 'over', 0.03, price_col='max')
    roi('FIX UNDER edge≥0.03 (max)', 'under', 0.03, price_col='max')
    roi('FIX ambos edge≥0.03 (max)', 'both', 0.03, price_col='max')
    roi('FIX ambos edge≥0.05 (max)', 'both', 0.05, price_col='max')
    roi('FIX ambos edge≥0.05 (max) & EV≥10%', 'both', 0.05, 0.10, price_col='max')
    roi('FIX ambos EV≥15% (max)', 'both', 0.0, 0.15, price_col='max')

    o.to_pickle(OUT)
    print(f'\nGuardado: {OUT}')


if __name__ == '__main__':
    main()
