"""
Walk-forward GOLES O/U — PASO 6: modelo MEJORADO (ratings Poisson ridge) vs mercado.

Motivación: el pipeline actual (DC con medias móviles) NO bate al mercado.
Este test entrena el modelo que poisson_bench ya mostró superior en precisión
(ratings ataque/defensa regularizados + ventaja local + decay temporal) y lo
confronta contra las cuotas reales O/U 2.5 en walk-forward estricto.

Diseño:
  - Por liga; refit cada 90 días (solo datos anteriores).
  - Ratings: intercept + att[i] + def[j] + home_adv, L2 ridge, decay τ=90d.
  - Fit con sklearn PoissonRegressor (soporta sample_weight).
  - Predicción: λ_h + λ_a → p_over Poisson (+ versión NB con φ rolling).
  - Evaluación: ROI edge/EV vs cuotas (avg y max), Brier/AUC vs mercado.

Sin lookahead. NO toca producción. Salida: ridge_report.txt
"""
import sys
import time

import numpy as np
import pandas as pd
from scipy.stats import poisson, nbinom
from sklearn.linear_model import PoissonRegressor
from sklearn.metrics import brier_score_loss, roc_auc_score

BASE = '/var/www/predicta.com.co/scripts/walkforward_goals'
IN = f'{BASE}/wf_goals_full.pkl'
OUT = f'{BASE}/ridge_out.pkl'
OUT_TXT = f'{BASE}/ridge_report.txt'

TAU = 90.0          # decay temporal (días)
HIST_CAP = 1460     # solo últimos 4 años para el fit
REFIT_DAYS = 90     # cadencia de refit por liga
MIN_HIST = 400      # mínimo de partidos con resultado para el primer fit
ALPHA = 1.0         # regularización ridge


def fit_league(hist_df, cutoff):
    """Fit ratings sobre partidos previos a cutoff. Devuelve (predict_fn, info)."""
    h = hist_df[hist_df['date'] < cutoff]
    if len(h) < MIN_HIST:
        return None
    h = h[h['date'] >= cutoff - pd.Timedelta(days=HIST_CAP)]
    teams = pd.Index(sorted(set(h['home']) | set(h['away'])))
    n = len(teams)
    t2i = {t: i for i, t in enumerate(teams)}

    hh = h['home'].map(t2i).values
    aa = h['away'].map(t2i).values
    gh = h['fthg'].values.astype(float)
    ga = h['ftag'].values.astype(float)
    w = np.exp(-(cutoff - h['date']).dt.days.values / TAU)

    # stacked: fila home-goles y fila away-goles
    # diseño: [att_0..att_{n-1}, def_0..def_{n-1}, home_adv]
    rows = 2 * len(h)
    X = np.zeros((rows, 2 * n + 1))
    y = np.zeros(rows)
    sw = np.zeros(rows)
    idx = np.arange(len(h))
    # home rows
    X[idx, hh] = 1.0
    X[idx, n + aa] = 1.0
    X[idx, 2 * n] = 1.0
    y[idx] = gh
    sw[idx] = w
    # away rows
    X[len(h) + idx, aa] = 1.0
    X[len(h) + idx, n + hh] = 1.0
    X[len(h) + idx, 2 * n] = 0.0
    y[len(h) + idx] = ga
    sw[len(h) + idx] = w

    # normalizar peso (PoissonRegressor pondera por sample_weight absoluto)
    sw = sw * (len(sw) / sw.sum())
    clf = PoissonRegressor(alpha=ALPHA, fit_intercept=True, max_iter=200, tol=1e-4)
    clf.fit(X, y, sample_weight=sw)
    coef = clf.coef_
    att = coef[:n]
    deff = coef[n:2 * n]
    home_adv = coef[2 * n]
    b0 = clf.intercept_

    def predict(home, away):
        if home not in t2i or away not in t2i:
            return None, None
        lh = np.exp(b0 + att[t2i[home]] + deff[t2i[away]] + home_adv)
        la = np.exp(b0 + att[t2i[away]] + deff[t2i[home]])
        return float(lh), float(la)

    return predict


def main():
    t0 = time.time()
    df = pd.read_pickle(IN).sort_values(['date', 'div']).reset_index(drop=True)
    df = df[df['has_goal']].copy()
    print(f'partidos con resultado: {len(df)}')

    leagues = sorted(df['div'].unique())
    print(f'ligas: {leagues}')

    out_rows = []
    for li, lg in enumerate(leagues):
        d = df[df['div'] == lg].sort_values('date').reset_index(drop=True)
        if len(d) < MIN_HIST:
            print(f'[{lg}] skip (n={len(d)})')
            continue
        first = d['date'].iloc[0] + pd.Timedelta(days=365 * 2)
        # ventanas de refit
        cutoffs = []
        c = first
        end = d['date'].max()
        while c < end:
            cutoffs.append(c)
            c = c + pd.Timedelta(days=REFIT_DAYS)
        pf = None
        preds = np.full(len(d), np.nan)
        preds_a = np.full(len(d), np.nan)
        co = 0
        t_l = time.time()
        for i, r in d.iterrows():
            dt = r['date']
            while co < len(cutoffs) and cutoffs[co] <= dt:
                pf = fit_league(d, cutoffs[co])
                co += 1
            if pf is not None:
                lh, la = pf(r['home'], r['away'])
                if lh is not None:
                    preds[i] = lh
                    preds_a[i] = la
        d['lam_h_ridge'] = preds
        d['lam_a_ridge'] = preds_a
        d['lam_total_ridge'] = preds + preds_a
        ok = d['lam_total_ridge'].notna()
        print(f'[{lg}] n={len(d)} predichos={ok.sum()} ({time.time()-t_l:.0f}s)')
        out_rows.append(d)

    allp = pd.concat(out_rows, ignore_index=True)
    allp = allp[allp['lam_total_ridge'].notna() & allp['has_odds']].copy()
    print(f'\nTotal evaluable con cuotas: {len(allp)} | {time.time()-t0:.0f}s')
    allp.to_pickle(OUT)

    # ── evaluación ──
    out = []
    P = lambda *a: (print(*a), out.append(' '.join(str(x) for x in a)))

    allp['p_over_r'] = 1.0 - poisson.cdf(np.floor(2.5), allp['lam_total_ridge'])
    allp['p_under_r'] = 1.0 - allp['p_over_r']
    y = allp['over_won'].astype(int)

    P('=' * 100)
    P('MODELO RIDGE — evaluación vs mercado (O/U 2.5)')
    P(f'n={len(allp)} | bias λ: {allp["tot"].mean() - allp["lam_total_ridge"].mean():+.3f}')
    P('=' * 100)
    P(f'Brier ridge:  {brier_score_loss(y, allp["p_over_r"]):.4f}')
    P(f'Brier mercado: {brier_score_loss(y, allp["fair_o"]):.4f}')
    P(f'AUC ridge:  {roc_auc_score(y, allp["p_over_r"]):.4f}')
    P(f'AUC mercado: {roc_auc_score(y, allp["fair_o"]):.4f}')

    # blend: ¿el ridge aporta?
    from sklearn.linear_model import LogisticRegression
    eps = 1e-6
    X1 = np.log(np.clip(allp['p_over_r'], eps, 1-eps)/(1-np.clip(allp['p_over_r'], eps, 1-eps)))
    X2 = np.log(np.clip(allp['fair_o'], eps, 1-eps)/(1-np.clip(allp['fair_o'], eps, 1-eps)))
    # walk-forward ligero: primer 30% train, resto eval (aprox)
    n = len(allp)
    k = int(n * 0.3)
    clf = LogisticRegression(C=1.0, max_iter=1000)
    clf.fit(np.column_stack([X1[:k], X2[:k]]), y[:k])
    P(f'Blend coefs (train 30%): ridge={clf.coef_[0][0]:+.3f}, mercado={clf.coef_[0][1]:+.3f}')

    # ROI
    def roi(tag, side, edge_min, ev_min=None):
        d = allp
        if side == 'over':
            p = d['p_over_r'].values; fair = d['fair_o'].values
            price = d['o_over_max'].fillna(d['o_over']).values; won = d['over_won'].values
        elif side == 'under':
            p = d['p_under_r'].values; fair = d['fair_u'].values
            price = d['o_under_max'].fillna(d['o_under']).values; won = ~d['over_won'].values
        else:
            eo = (d['p_over_r'] - d['fair_o']).values
            eu = (d['p_under_r'] - d['fair_u']).values
            take_over = eo >= eu
            p = np.where(take_over, d['p_over_r'], d['p_under_r'])
            fair = np.where(take_over, d['fair_o'], d['fair_u'])
            price = np.where(take_over, d['o_over_max'].fillna(d['o_over']), d['o_under_max'].fillna(d['o_under']))
            won = np.where(take_over, d['over_won'], ~d['over_won'])
        edge = p - fair
        ev = p * price - 1.0
        sel = edge >= edge_min
        if ev_min is not None:
            sel &= (ev >= ev_min)
        if sel.sum() == 0:
            P(f'  {tag:44s} n=0'); return
        w = won[sel]; pr = price[sel]
        pnl = np.where(w, pr - 1.0, -1.0)
        se = pnl.std(ddof=1)/np.sqrt(len(pnl))
        P(f'  {tag:44s} n={len(pnl):5d} WR={w.mean()*100:5.1f}% ROI={pnl.mean()*100:+6.2f}% (z={pnl.mean()/se:+.1f})')

    P('\nROI ridge (cuota max):')
    roi('RIDGE OVER edge≥0.03', 'over', 0.03)
    roi('RIDGE OVER edge≥0.05', 'over', 0.05)
    roi('RIDGE UNDER edge≥0.03', 'under', 0.03)
    roi('RIDGE UNDER edge≥0.05', 'under', 0.05)
    roi('RIDGE ambos edge≥0.03', 'both', 0.03)
    roi('RIDGE ambos edge≥0.05 & EV≥5%', 'both', 0.05, 0.05)
    roi('RIDGE ambos edge≥0.05 & EV≥10%', 'both', 0.05, 0.10)
    roi('RIDGE ambos EV≥15%', 'both', 0.0, 0.15)

    # por temporada de la mejor
    P('\nPor temporada (RIDGE ambos edge≥0.05):')
    d = allp
    eo = (d['p_over_r'] - d['fair_o']).values
    eu = (d['p_under_r'] - d['fair_u']).values
    take_over = eo >= eu
    p = np.where(take_over, d['p_over_r'], d['p_under_r'])
    fair = np.where(take_over, d['fair_o'], d['fair_u'])
    price = np.where(take_over, d['o_over_max'].fillna(d['o_over']), d['o_under_max'].fillna(d['o_under']))
    won = np.where(take_over, d['over_won'], ~d['over_won'])
    sel = (p - fair) >= 0.05
    dd = d[sel].copy()
    dd['won'] = won[sel]; dd['price'] = price[sel]
    dd['pnl'] = np.where(dd['won'], dd['price'] - 1.0, -1.0)
    for s, g in dd.groupby('season'):
        P(f'  {int(s)}: n={len(g):4d} WR={g["won"].mean()*100:5.1f}% ROI={g["pnl"].mean()*100:+6.2f}%')
    if len(dd):
        se = dd['pnl'].std(ddof=1)/np.sqrt(len(dd))
        P(f'  GLOBAL: n={len(dd)} ROI={dd["pnl"].mean()*100:+6.2f}% (z={dd["pnl"].mean()/se:+.2f})')

    P('\n' + '=' * 100 + '\nFIN')
    with open(OUT_TXT, 'w') as f:
        f.write('\n'.join(out))
    print(f'\nGuardado: {OUT_TXT} | total {time.time()-t0:.0f}s')


if __name__ == '__main__':
    main()
