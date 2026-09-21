"""
Walk-forward GOLES O/U — PASO 5: calibración de forma + blend modelo-mercado.

Tests finales:
  A) Isotonic walk-forward (expanding): corrige la FORMA de la distribución
     (el modelo comprime: dice 72% cuando la realidad es 57%).
     ¿Mejora el ROI? ¿Supera al mercado?
  B) Blend logístico: p_blend = f(logit(p_modelo), logit(fair_mercado)).
     Si el blend supera al mercado puro (Brier/AUC), la señal del modelo
     añade información → hay base para edge. Si no, el modelo no aporta.
  C) Regla final: apostar solo si p_iso - fair ≥ θ con cuota max.

Sin lookahead estricto (expanding, refit periódico).
"""
import numpy as np
import pandas as pd
from scipy.stats import poisson
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss, roc_auc_score

BASE = '/var/www/predicta.com.co/scripts/walkforward_goals'
IN = f'{BASE}/wf_engine_out.pkl'
OUT_TXT = f'{BASE}/form_report.txt'

def main():
    df = pd.read_pickle(IN).sort_values('date').reset_index(drop=True)
    out = []
    P = lambda *a: (print(*a), out.append(' '.join(str(x) for x in a)))

    # corrección walk-forward de nivel
    ratios = np.full(len(df), np.nan)
    lig_sum, lig_lam = {}, {}
    g_sum = g_lam = 0.0; n_g = 0
    for i, (div, tot_, lam_) in enumerate(zip(df['div'].values, df['tot'].values, df['lam_total'].values)):
        if div in lig_sum and lig_sum[div] >= 300 and lig_lam[div] > 0:
            ratios[i] = lig_sum[div] / lig_lam[div]
        elif n_g >= 300 and g_lam > 0:
            ratios[i] = g_sum / g_lam
        lig_sum[div] = lig_sum.get(div, 0.0) + tot_
        lig_lam[div] = lig_lam.get(div, 0.0) + lam_
        g_sum += tot_; g_lam += lam_; n_g += 1
    df['ratio'] = ratios
    sub = df[df['ratio'].notna()].copy().reset_index(drop=True)
    sub['lam_corr'] = sub['lam_total'] * sub['ratio']
    sub['p_over_c'] = 1.0 - poisson.cdf(np.floor(2.5), sub['lam_corr'])
    sub['y'] = sub['over_won'].astype(int)

    P('=' * 100)
    P('FORMA + BLEND — tests finales')
    P(f'n={len(sub)}')
    P('=' * 100)

    # ── A) Isotonic walk-forward ──
    P('\n── A) Isotonic walk-forward (expanding, refit cada 2000) ──')
    n = len(sub)
    p_iso = np.full(n, np.nan)
    MIN_TRAIN = 5000
    REFIT = 2000
    iso = None
    last_fit = -REFIT
    for i in range(n):
        if i >= MIN_TRAIN and i - last_fit >= REFIT:
            train = sub.iloc[:i]
            iso = IsotonicRegression(out_of_bounds='clip', y_min=0.01, y_max=0.99)
            iso.fit(train['p_over_c'].values, train['y'].values)
            last_fit = i
        if iso is not None:
            p_iso[i] = float(iso.predict([sub['p_over_c'].iloc[i]])[0])
    sub['p_over_iso'] = p_iso
    sub['p_under_iso'] = 1.0 - sub['p_over_iso']
    have = sub['p_over_iso'].notna()
    P(f'  cobertura isotonic: {have.mean()*100:.1f}%')

    # métricas de forma
    m = sub[have]
    y = m['y']
    P(f'  Brier poisson-corr: {brier_score_loss(y, m["p_over_c"]):.4f}')
    P(f'  Brier isotonic:     {brier_score_loss(y, m["p_over_iso"]):.4f}')
    P(f'  Brier mercado:      {brier_score_loss(y, m["fair_o"]):.4f}')
    P(f'  AUC poisson-corr:   {roc_auc_score(y, m["p_over_c"]):.4f}')
    P(f'  AUC isotonic:       {roc_auc_score(y, m["p_over_iso"]):.4f}')
    P(f'  AUC mercado:        {roc_auc_score(y, m["fair_o"]):.4f}')

    # curva calibración isotonic
    bins = [0, .3, .35, .40, .45, .50, .55, .60, .65, 1.0]
    m2 = m.copy(); m2['b'] = pd.cut(m2['p_over_iso'], bins)
    g = m2.groupby('b', observed=True).agg(n=('y', 'size'), real=('y', 'mean'), pm=('p_over_iso', 'mean'))
    P('\n  Curva calibración isotonic:')
    for b, r in g.iterrows():
        P(f'    {str(b):15s} n={int(r["n"]):6d} p_iso={r["pm"]*100:5.1f}% real={r["real"]*100:5.1f}% gap={(r["real"]-r["pm"])*100:+5.1f}pp')

    # ROI con isotonic + max odds, varios edge
    def roi_iso(tag, side, edge_min, ev_min=None):
        d = m.copy()
        if side == 'over':
            p = d['p_over_iso']; fair = d['fair_o']; price = d['o_over_max'].fillna(d['o_over']); won = d['over_won']
        elif side == 'under':
            p = d['p_under_iso']; fair = d['fair_u']; price = d['o_under_max'].fillna(d['o_under']); won = ~d['over_won']
        else:
            # ambos: elegir el lado con mayor edge
            eo = d['p_over_iso'] - d['fair_o']
            eu = d['p_under_iso'] - d['fair_u']
            take_over = eo >= eu
            p = np.where(take_over, d['p_over_iso'], d['p_under_iso'])
            fair = np.where(take_over, d['fair_o'], d['fair_u'])
            price = np.where(take_over, d['o_over_max'].fillna(d['o_over']), d['o_under_max'].fillna(d['o_under']))
            won = np.where(take_over, d['over_won'], ~d['over_won'])
        d['edge'] = p - fair
        d['ev'] = p * price - 1.0
        sel = d['edge'] >= edge_min
        if ev_min is not None:
            sel &= d['ev'] >= ev_min
        if sel.sum() == 0:
            P(f'  {tag:46s} n=0'); return
        w = won[sel.values] if hasattr(won, 'values') and not isinstance(won, np.ndarray) else won[sel.values]
        pr = price[sel.values] if not isinstance(price, np.ndarray) else price[sel.values]
        pnl = np.where(w, pr - 1.0, -1.0)
        se = pnl.std(ddof=1) / np.sqrt(len(pnl))
        P(f'  {tag:46s} n={len(pnl):5d} WR={w.mean()*100:5.1f}% ROI={pnl.mean()*100:+6.2f}% (z={pnl.mean()/se:+.1f})')
        return pnl

    P('\n  ROI isotonic + cuota max:')
    roi_iso('ISO OVER edge≥0.03', 'over', 0.03)
    roi_iso('ISO OVER edge≥0.05', 'over', 0.05)
    roi_iso('ISO UNDER edge≥0.03', 'under', 0.03)
    roi_iso('ISO UNDER edge≥0.05', 'under', 0.05)
    roi_iso('ISO ambos edge≥0.03', 'both', 0.03)
    roi_iso('ISO ambos edge≥0.05 & EV≥10%', 'both', 0.05, 0.10)
    roi_iso('ISO ambos edge≥0.08 & EV≥15%', 'both', 0.08, 0.15)

    # ── B) blend logístico walk-forward ──
    P('\n── B) Blend logístico walk-forward [logit(p_corr), logit(fair)] ──')
    eps = 1e-6
    X1 = np.log(np.clip(m['p_over_c'].values, eps, 1-eps) / (1 - np.clip(m['p_over_c'].values, eps, 1-eps)))
    X2 = np.log(np.clip(m['fair_o'].values, eps, 1-eps) / (1 - np.clip(m['fair_o'].values, eps, 1-eps)))
    X = np.column_stack([X1, X2])
    yv = m['y'].values
    n_m = len(m)
    p_blend = np.full(n_m, np.nan)
    MIN_TRAIN = 5000
    REFIT = 2000
    clf = None; last = -REFIT
    for i in range(n_m):
        if i >= MIN_TRAIN and i - last >= REFIT:
            clf = LogisticRegression(C=1.0, max_iter=1000)
            clf.fit(X[:i], yv[:i])
            last = i
        if clf is not None:
            p_blend[i] = clf.predict_proba(X[i:i+1])[0, 1]
    m['p_blend'] = p_blend
    hb = m['p_blend'].notna()
    P(f'  cobertura blend: {hb.mean()*100:.1f}%')
    P(f'  Brier blend:  {brier_score_loss(yv[hb.values], m.loc[hb, "p_blend"]):.4f}')
    P(f'  Brier modelo solo: {brier_score_loss(yv[hb.values], m.loc[hb, "p_over_c"]):.4f}')
    # coeficientes del último fit
    P(f'  Últimos coefs: modelo={clf.coef_[0][0]:+.3f}, mercado={clf.coef_[0][1]:+.3f}, intercept={clf.intercept_[0]:+.3f}')
    # AUC comparativa en la misma submuestra
    P(f'  AUC blend:  {roc_auc_score(yv[hb.values], m.loc[hb, "p_blend"]):.4f}')
    P(f'  AUC mercado en submuestra: {roc_auc_score(yv[hb.values], m.loc[hb, "fair_o"]):.4f}')
    P(f'  AUC modelo en submuestra:  {roc_auc_score(yv[hb.values], m.loc[hb, "p_over_c"]):.4f}')

    # ROI blend
    def roi_blend(tag, side, edge_min):
        # edge = p_blend - fair; precio max
        d = m[hb].copy()
        if side == 'both':
            eo = d['p_blend'] - d['fair_o']
            eu = (1 - d['p_blend']) - d['fair_u']
            take_over = eo >= eu
            p = np.where(take_over, d['p_blend'], 1 - d['p_blend'])
            fair = np.where(take_over, d['fair_o'], d['fair_u'])
            price = np.where(take_over, d['o_over_max'].fillna(d['o_over']), d['o_under_max'].fillna(d['o_under']))
            won = np.where(take_over, d['over_won'], ~d['over_won'])
        else:
            return
        edge = p - fair
        sel = edge >= edge_min
        if sel.sum() == 0:
            P(f'  {tag:46s} n=0'); return
        w = won[sel]; pr = price[sel]
        pnl = np.where(w, pr - 1.0, -1.0)
        se = pnl.std(ddof=1) / np.sqrt(len(pnl))
        P(f'  {tag:46s} n={len(pnl):5d} WR={w.mean()*100:5.1f}% ROI={pnl.mean()*100:+6.2f}% (z={pnl.mean()/se:+.1f})')

    P('\n  ROI blend + cuota max (ambos lados):')
    for e in (0.0, 0.03, 0.05, 0.08):
        roi_blend(f'BLEND edge≥{e:.2f}', 'both', e)

    P('\n' + '=' * 100 + '\nFIN')
    with open(OUT_TXT, 'w') as f:
        f.write('\n'.join(out))
    print(f'\nGuardado: {OUT_TXT}')


if __name__ == '__main__':
    main()
