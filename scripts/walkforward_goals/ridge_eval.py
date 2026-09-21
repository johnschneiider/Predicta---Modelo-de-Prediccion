"""
Ridge evaluación (solo lectura del pickle ya generado por ridge_ratings.py).
"""
import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.metrics import brier_score_loss, roc_auc_score
from sklearn.linear_model import LogisticRegression

BASE = '/var/www/predicta.com.co/scripts/walkforward_goals'
IN = f'{BASE}/ridge_out.pkl'
OUT_TXT = f'{BASE}/ridge_report.txt'


def main():
    allp = pd.read_pickle(IN).copy()
    allp['tot'] = allp['fthg'] + allp['ftag']
    allp['over_won'] = allp['tot'] > 2.5
    imp_o = 1.0 / allp['o_over']
    imp_u = 1.0 / allp['o_under']
    allp['fair_o'] = imp_o / (imp_o + imp_u)
    allp['fair_u'] = 1.0 - allp['fair_o']
    out = []
    P = lambda *a: (print(*a), out.append(' '.join(str(x) for x in a)))

    allp['p_over_r'] = 1.0 - poisson.cdf(np.floor(2.5), allp['lam_total_ridge'])
    allp['p_under_r'] = 1.0 - allp['p_over_r']
    y = allp['over_won'].astype(int)

    P('=' * 100)
    P('MODELO RIDGE — evaluación vs mercado (O/U 2.5)')
    P(f'n={len(allp)} | bias λ: {allp["tot"].mean() - allp["lam_total_ridge"].mean():+.3f}')
    P(f'λ_ridge medio: {allp["lam_total_ridge"].mean():.3f} | real: {allp["tot"].mean():.3f}')
    P('=' * 100)
    P(f'Brier ridge:   {brier_score_loss(y, allp["p_over_r"]):.4f}')
    P(f'Brier mercado: {brier_score_loss(y, allp["fair_o"]):.4f}')
    P(f'AUC ridge:   {roc_auc_score(y, allp["p_over_r"]):.4f}')
    P(f'AUC mercado: {roc_auc_score(y, allp["fair_o"]):.4f}')

    # blend
    eps = 1e-6
    X1 = np.log(np.clip(allp['p_over_r'], eps, 1-eps)/(1-np.clip(allp['p_over_r'], eps, 1-eps)))
    X2 = np.log(np.clip(allp['fair_o'], eps, 1-eps)/(1-np.clip(allp['fair_o'], eps, 1-eps)))
    n = len(allp)
    k = int(n * 0.3)
    clf = LogisticRegression(C=1.0, max_iter=1000)
    clf.fit(np.column_stack([X1[:k], X2[:k]]), y[:k])
    P(f'Blend coefs (train 30%): ridge={clf.coef_[0][0]:+.4f}, mercado={clf.coef_[0][1]:+.4f}, intercept={clf.intercept_[0]:+.4f}')

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

    # por división
    P('\nPor división (RIDGE ambos edge≥0.05):')
    for dv, g in dd.groupby('div'):
        if len(g) < 100: continue
        se = g['pnl'].std(ddof=1)/np.sqrt(len(g))
        P(f'  {dv}: n={len(g):4d} WR={g["won"].mean()*100:5.1f}% ROI={g["pnl"].mean()*100:+6.2f}% (z={g["pnl"].mean()/se:+.1f})')

    P('\n' + '=' * 100 + '\nFIN')
    with open(OUT_TXT, 'w') as f:
        f.write('\n'.join(out))
    print(f'\nGuardado: {OUT_TXT}')


if __name__ == '__main__':
    main()
