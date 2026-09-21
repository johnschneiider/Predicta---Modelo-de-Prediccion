"""
Walk-forward GOLES O/U — PASO 4: búsqueda de nichos rentables (sin lookahead).

Sobre wf_engine_out.pkl + corrección de sesgo walk-forward:
  1) Curva de calibración del modelo corregido
  2) ROI por división (¿mercados menos eficientes?)
  3) Estrategias de cola: |λ-2.5| grande, p extrema
  4) Contrerasian: fade del favorito del mercado (fair≥0.55 → under)
  5) EV altos (10/15/20%) con max odds
  6) Correlación entre dirección de desacuerdo y resultado
"""
import numpy as np
import pandas as pd
from scipy.stats import poisson

BASE = '/var/www/predicta.com.co/scripts/walkforward_goals'
IN = f'{BASE}/wf_engine_out.pkl'
OUT_TXT = f'{BASE}/niche_report.txt'

def main():
    df = pd.read_pickle(IN).sort_values('date').reset_index(drop=True)
    out = []
    P = lambda *a: (print(*a), out.append(' '.join(str(x) for x in a)))

    # ── corrección walk-forward (igual que evaluate.py) ──
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
    sub = df[df['ratio'].notna()].copy()
    sub['lam_corr'] = sub['lam_total'] * sub['ratio']
    sub['p_over_c'] = 1.0 - poisson.cdf(np.floor(2.5), sub['lam_corr'])
    sub['p_under_c'] = 1.0 - sub['p_over_c']
    sub['dist'] = (sub['lam_corr'] - 2.5).abs()

    P('=' * 100)
    P('NICHOS GOLES O/U — corrección walk-forward aplicada')
    P(f'n={len(sub)} | ratio medio {sub["ratio"].mean():.4f}')
    P('=' * 100)

    # ── 1) calibración del corregido ──
    P('\n── 1) Calibración del modelo corregido (p_over_c vs real) ──')
    bins = [0, .25, .35, .40, .45, .50, .55, .60, .65, 1.0]
    sub['b'] = pd.cut(sub['p_over_c'], bins)
    g = sub.groupby('b', observed=True).agg(n=('over_won', 'size'), real=('over_won', 'mean'),
                                            pm=('p_over_c', 'mean'))
    for b, r in g.iterrows():
        P(f'  {str(b):18s} n={int(r["n"]):6d} p_corr={r["pm"]*100:5.1f}% real={r["real"]*100:5.1f}% gap={(r["real"]-r["pm"])*100:+5.1f}pp')

    # ── 2) ROI por división (under edge≥0.05 & EV≥5%, y maxquote) ──
    P('\n── 2) ROI por división — estrategia UNDER edge≥0.05 & EV≥5% (BbAv) ──')
    u = sub[['date', 'season', 'div', 'o_under', 'o_under_max', 'fair_u', 'p_under_c', 'over_won']].copy()
    u['side'] = 'under'
    u['won'] = ~u['over_won']
    u['edge'] = u['p_under_c'] - u['fair_u']
    u['ev'] = u['p_under_c'] * u['o_under'] - 1.0
    uf = u[(u['edge'] >= 0.05) & (u['ev'] >= 0.05)].copy()
    uf['pnl'] = np.where(uf['won'], uf['o_under'] - 1.0, -1.0)
    uf['pnl_max'] = np.where(uf['won'], uf['o_under_max'].fillna(uf['o_under']) - 1.0, -1.0)
    for d, gg in uf.groupby('div'):
        P(f'  {d}: n={len(gg):5d} WR={gg["won"].mean()*100:5.1f}% ROI_av={gg["pnl"].mean()*100:+6.2f}% ROI_max={gg["pnl_max"].mean()*100:+6.2f}%')

    # ── 3) estrategias de cola ──
    P('\n── 3) Colas: distancia |λ_corr-2.5| ──')
    def tail(tag, side, dist_min=None, dist_max=None, p_min=None, p_max=None, ev_min=None):
        rows = []
        d = sub
        if side in ('over', 'both'):
            o = d[['div','date','season','o_over','o_over_max','fair_o','p_over_c','over_won','dist']].copy()
            o['side']='over'; o['p']=o['p_over_c']; o['fair']=o['fair_o']; o['won']=o['over_won']
            rows.append(o)
        if side in ('under', 'both'):
            u2 = d[['div','date','season','o_under','o_under_max','fair_u','p_under_c','over_won','dist']].copy()
            u2['side']='under'; u2['p']=u2['p_under_c']; u2['fair']=u2['fair_u']; u2['won']=~u2['over_won']
            rows.append(u2)
        x = pd.concat(rows, ignore_index=True)
        for c in ('o_over', 'o_under', 'o_over_max', 'o_under_max', 'fair_o', 'fair_u', 'p_over_c', 'p_under_c'):
            if c not in x.columns:
                x[c] = np.nan
        if dist_min is not None: x = x[x['dist'] >= dist_min]
        if dist_max is not None: x = x[x['dist'] <= dist_max]
        if p_min is not None: x = x[x['p'] >= p_min]
        if p_max is not None: x = x[x['p'] <= p_max]
        x['ev'] = x['p'] * np.where(x['side']=='under', x['o_under'], x['o_over']) - 1.0
        if ev_min is not None:
            x = x[x['ev'] >= ev_min]
        x['price'] = np.where(
            x['side']=='under',
            x['o_under_max'].fillna(x['o_under']),
            x['o_over_max'].fillna(x['o_over']),
        )
        if len(x) == 0:
            P(f'  {tag:52s} n=0'); return None
        x['pnl'] = np.where(x['won'], x['price'] - 1.0, -1.0)
        roi = x['pnl'].mean(); se = x['pnl'].std(ddof=1)/np.sqrt(len(x))
        P(f'  {tag:52s} n={len(x):5d} WR={x["won"].mean()*100:5.1f}% ROI={roi*100:+6.2f}% (z={roi/se:+.1f})')
        return x

    tail('UNDER dist≥0.5 (max)', 'under', dist_min=0.5)
    tail('UNDER dist≥0.75 (max)', 'under', dist_min=0.75)
    tail('UNDER dist≥1.0 (max)', 'under', dist_min=1.0)
    tail('OVER dist≥0.5 (max)', 'over', dist_min=0.5)
    tail('OVER dist≥0.75 (max)', 'over', dist_min=0.75)
    tail('OVER dist≥1.0 (max)', 'over', dist_min=1.0)

    P('\n── 3b) p extrema ──')
    tail('UNDER p≥0.55 (max)', 'under', p_min=0.55)
    tail('UNDER p≥0.60 (max)', 'under', p_min=0.60)
    tail('UNDER p≥0.65 (max)', 'under', p_min=0.65)
    tail('OVER p≤0.35 (max)', 'over', p_max=0.35)
    tail('OVER p≤0.30 (max)', 'over', p_max=0.30)
    tail('OVER p≤0.25 (max)', 'over', p_max=0.25)

    # ── 4) contrarian: fade favorito del mercado ──
    P('\n── 4) Contrarian por fair del mercado ──')
    # fair_o ≥ X → under; fair_o ≤ Y → over
    for x0 in (0.52, 0.55, 0.58, 0.60):
        m = sub[sub['fair_o'] >= x0]
        if len(m):
            price = m['o_under_max'].fillna(m['o_under'])
            won = ~m['over_won']
            pnl = np.where(won, price - 1.0, -1.0)
            se = pnl.std(ddof=1)/np.sqrt(len(m))
            P(f'  fair_o≥{x0:.2f} → UNDER (max) n={len(m):5d} WR={won.mean()*100:5.1f}% ROI={pnl.mean()*100:+6.2f}% (z={pnl.mean()/se:+.1f})')
    for x0 in (0.45, 0.42, 0.40):
        m = sub[sub['fair_o'] <= x0]
        if len(m):
            price = m['o_over_max'].fillna(m['o_over'])
            won = m['over_won']
            pnl = np.where(won, price - 1.0, -1.0)
            se = pnl.std(ddof=1)/np.sqrt(len(m))
            P(f'  fair_o≤{x0:.2f} → OVER (max) n={len(m):5d} WR={won.mean()*100:5.1f}% ROI={pnl.mean()*100:+6.2f}% (z={pnl.mean()/se:+.1f})')

    # ── 5) EV altos con max odds ──
    P('\n── 5) EV altos (max odds) ──')
    tail('EV≥10% (max) ambos', 'both', ev_min=0.10)
    tail('EV≥15% (max) ambos', 'both', ev_min=0.15)
    tail('EV≥20% (max) ambos', 'both', ev_min=0.20)
    tail('UNDER EV≥10% (max)', 'under', ev_min=0.10)
    tail('UNDER EV≥15% (max)', 'under', ev_min=0.15)
    tail('OVER EV≥10% (max)', 'over', ev_min=0.10)
    tail('OVER EV≥15% (max)', 'over', ev_min=0.15)

    # ── 6) desacuerdo dirección ──
    P('\n── 6) Modelo vs mercado: desacuerdo ──')
    sub['gap'] = sub['p_over_c'] - sub['fair_o']
    for lo, hi, lab in [(-1, -0.08, 'modelo MUY under vs mercado'), (-0.08, -0.03, 'modelo under'), (-0.03, 0.03, 'acuerdo'), (0.03, 0.08, 'modelo over'), (0.08, 1, 'modelo MUY over vs mercado')]:
        m = sub[(sub['gap'] > lo) & (sub['gap'] <= hi)]
        if len(m) < 50:
            continue
        # En 'modelo over' apostar over; en 'modelo under' apostar under
        over_side = m['gap'] > 0
        price_o = m['o_over_max'].fillna(m['o_over'])
        price_u = m['o_under_max'].fillna(m['o_under'])
        won = np.where(over_side, m['over_won'], ~m['over_won'])
        price = np.where(over_side, price_o, price_u)
        pnl = np.where(won, price - 1.0, -1.0)
        se = pnl.std(ddof=1)/np.sqrt(len(m))
        P(f'  {lab:34s} n={len(m):5d} WR={won.mean()*100:5.1f}% ROI={pnl.mean()*100:+6.2f}% (z={pnl.mean()/se:+.1f})')

    P('\n' + '=' * 100 + '\nFIN')
    with open(OUT_TXT, 'w') as f:
        f.write('\n'.join(out))
    print(f'\nGuardado: {OUT_TXT}')

if __name__ == '__main__':
    main()
