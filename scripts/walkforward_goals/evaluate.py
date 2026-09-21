"""
Walk-forward GOLES O/U — PASO 3: evaluación de estrategias (sin lookahead).

Usa wf_engine_out.pkl (λ + cuotas + resultado, cronológico). Evalúa:

  A) Diagnóstico del sesgo: real vs λ por temporada/liga — ¿es estable?
  B) Corrección de sesgo WALK-FORWARD (expanding/rolling, solo pasado):
       ratio_t = mean(real) / mean(λ) sobre partidos anteriores
       λ_corr = λ * ratio_t  → p_corr (Poisson)
  C) Estrategias de apuesta sobre p_corr:
       - edge vs devig ≥ [0.0, 0.02, 0.03, 0.05]
       - EV ≥ [0, 0.05, 0.10]
       - subconjuntos: over / under / ambos
     Cuota usada: BbAv (conservadora) y BbMx (techo).
  D) Baselines: over siempre, under siempre.
  E) Estabilidad por temporada de la mejor estrategia.

Sin lookahead en ningún cálculo de decisión.
"""
import numpy as np
import pandas as pd

BASE = '/var/www/predicta.com.co/scripts/walkforward_goals'
IN = f'{BASE}/wf_engine_out.pkl'
OUT_TXT = f'{BASE}/evaluation_report.txt'

pd.set_option('display.width', 200)
pd.set_option('display.max_columns', 50)


def poisson_cdf(k, lam):
    # Poisson CDF via recurrencia (vectorizable si necesario)
    from scipy.stats import poisson
    return poisson.cdf(k, lam)


def main():
    from scipy.stats import poisson

    df = pd.read_pickle(IN)
    df = df.sort_values('date').reset_index(drop=True)
    out = []
    P = lambda *a: (print(*a), out.append(' '.join(str(x) for x in a)))

    P('=' * 100)
    P('WALK-FORWARD GOLES O/U — EVALUACIÓN')
    P(f'Partidos: {len(df)} | {df["date"].min().date()} → {df["date"].max().date()}')
    P('=' * 100)

    # ── A) Diagnóstico del sesgo ──
    P('\n── A) SESGO real - λ (total goles) ──')
    df['bias'] = df['tot'] - df['lam_total']
    P(f'  Sesgo global: {df["bias"].mean():+.3f} goles | λ medio {df["lam_total"].mean():.3f} vs real {df["tot"].mean():.3f}')
    P('\n  Por temporada:')
    t = df.groupby('season').agg(n=('tot', 'size'), lam=('lam_total', 'mean'), real=('tot', 'mean'))
    t['bias'] = t['real'] - t['lam']
    for s, r in t.iterrows():
        P(f'    {int(s)}: n={int(r["n"]):5d} λ={r["lam"]:.3f} real={r["real"]:.3f} bias={r["bias"]:+.3f}')
    P('\n  Por liga:')
    t = df.groupby('div').agg(n=('tot', 'size'), lam=('lam_total', 'mean'), real=('tot', 'mean'))
    t['bias'] = t['real'] - t['lam']
    for s, r in t.iterrows():
        P(f'    {s}: n={int(r["n"]):5d} λ={r["lam"]:.3f} real={r["real"]:.3f} bias={r["bias"]:+.3f}')

    # ── B) Corrección walk-forward del sesgo ──
    # expanding por liga: ratio = mean(real) / mean(lam) con todos los previos.
    # Mínimo 300 partidos previos de liga; si no, usa ratio global previo.
    P('\n── B) Corrección walk-forward (expanding por liga) ──')
    df['ratio_lig'] = np.nan
    df['ratio_glo'] = np.nan
    # expanding stats
    g_sum = g_lam = 0.0
    lig_sum = {}
    lig_lam = {}
    n_g = 0
    ratios_lig = np.full(len(df), np.nan)
    ratios_glo = np.full(len(df), np.nan)
    for i, (div, tot_, lam_) in enumerate(zip(df['div'].values, df['tot'].values, df['lam_total'].values)):
        # ratio ANTES de añadir este partido
        if (div in lig_sum) and lig_sum[div] >= 300 and lig_lam[div] > 0:
            ratios_lig[i] = lig_sum[div] / lig_lam[div]
        if n_g >= 300 and g_lam > 0:
            ratios_glo[i] = g_sum / g_lam
        # añadir este partido
        lig_sum[div] = lig_sum.get(div, 0.0) + tot_
        lig_lam[div] = lig_lam.get(div, 0.0) + lam_
        g_sum += tot_; g_lam += lam_; n_g += 1
    df['ratio_lig'] = ratios_lig
    df['ratio_glo'] = ratios_glo
    # ratio efectivo: liga si hay, global si no
    df['ratio'] = df['ratio_lig'].fillna(df['ratio_glo'])
    cov = df['ratio'].notna().mean()
    P(f'  Cobertura corrección: {cov*100:.1f}% de {len(df)} partidos')
    P(f'  Ratio liga: media {df["ratio_lig"].mean():.4f} | rango [{df["ratio_lig"].min():.3f}, {df["ratio_lig"].max():.3f}]')
    sub = df[df['ratio'].notna()].copy()
    sub['lam_corr'] = sub['lam_total'] * sub['ratio']

    # recalcular p_over corregido
    sub['p_over_c'] = 1.0 - poisson.cdf(np.floor(2.5), sub['lam_corr'])
    sub['p_under_c'] = 1.0 - sub['p_over_c']

    P(f'  Tras corrección: λ_corr medio {sub["lam_corr"].mean():.3f} vs real {sub["tot"].mean():.3f} (sesgo {sub["tot"].mean()-sub["lam_corr"].mean():+.3f})')
    P(f'  p_over_c medio: {sub["p_over_c"].mean()*100:.2f}% | fair_o medio: {sub["fair_o"].mean()*100:.2f}%')

    # ── C) Estrategias ──
    P('\n── C) ESTRATEGIAS (cuota BbAv, la conservadora) ──')
    P('  Reglas: edge = p_corr - fair ≥ umbral; EV = p_corr * cuota - 1 ≥ umbral')

    def run_strategy(d, side_filter='both', edge_min=0.0, ev_min=0.0, min_odds=1.5, p_min=0.0):
        """Simula apuestas a stake plano=1. Devuelve métricas."""
        rows = []
        d = d.copy()
        # over: apostar OT_OVER con p_over_c, cuota o_over
        # under: apostar OT_UNDER con p_under_c, cuota o_under
        if side_filter in ('both', 'over'):
            o = d[['date', 'season', 'div', 'o_over', 'fair_o', 'p_over_c', 'over_won']].copy()
            o['side'] = 'over'
            o['p'] = o['p_over_c']; o['fair'] = o['fair_o']; o['odds'] = o['o_over']
            o['won'] = o['over_won']
            rows.append(o)
        if side_filter in ('both', 'under'):
            u = d[['date', 'season', 'div', 'o_under', 'fair_u', 'p_under_c', 'over_won']].copy()
            u['side'] = 'under'
            u['p'] = u['p_under_c']; u['fair'] = u['fair_u']; u['odds'] = u['o_under']
            u['won'] = ~u['over_won']
            rows.append(u)
        x = pd.concat(rows, ignore_index=True)
        x['edge'] = x['p'] - x['fair']
        x['ev'] = x['p'] * x['odds'] - 1.0
        x = x[(x['edge'] >= edge_min) & (x['ev'] >= ev_min) & (x['odds'] >= min_odds) & (x['p'] >= p_min)]
        if len(x) == 0:
            return None
        x['pnl'] = np.where(x['won'], x['odds'] - 1.0, -1.0)
        roi = x['pnl'].mean()
        wr = x['won'].mean()
        # error estándar del ROI
        se = x['pnl'].std(ddof=1) / np.sqrt(len(x)) if len(x) > 1 else np.nan
        return {
            'n': len(x), 'wr': wr, 'roi': roi, 'se': se,
            'z': roi / se if se and se > 0 else np.nan,
            'avg_odds': x['odds'].mean(), 'avg_edge': x['edge'].mean(),
            'n_over': (x['side'] == 'over').sum(), 'n_under': (x['side'] == 'under').sum(),
            'pnl_sum': x['pnl'].sum(),
        }

    def fmt(tag, m):
        if m is None:
            P(f'  {tag:44s} n=0')
            return
        P(f'  {tag:44s} n={m["n"]:5d} WR={m["wr"]*100:5.1f}% ROI={m["roi"]*100:+6.2f}% (z={m["z"]:+.1f}) '
          f'odds~{m["avg_odds"]:.2f} edge~{m["avg_edge"]*100:+.1f}pp [{m["n_over"]}O/{m["n_under"]}U]')

    # Baselines
    P('\n  -- Baselines --')
    base_over = run_strategy(sub, 'over')
    base_under = run_strategy(sub, 'under')
    fmt('Over siempre', base_over)
    fmt('Under siempre', base_under)

    # Estrategia 1: edge devig (como sistema actual pero corregido), varios umbrales
    P('\n  -- E1: edge vs devig (θ) — ambos lados --')
    for e in (0.0, 0.02, 0.03, 0.04, 0.05):
        fmt(f'edge≥{e:.2f}', run_strategy(sub, 'both', edge_min=e))

    P('\n  -- E1o: SOLO OVER con edge --')
    for e in (0.0, 0.02, 0.03, 0.04, 0.05):
        fmt(f'OVER edge≥{e:.2f}', run_strategy(sub, 'over', edge_min=e))

    P('\n  -- E1u: SOLO UNDER con edge --')
    for e in (0.0, 0.02, 0.03, 0.04, 0.05):
        fmt(f'UNDER edge≥{e:.2f}', run_strategy(sub, 'under', edge_min=e))

    P('\n  -- E2: edge + EV≥5% --')
    for e in (0.0, 0.02, 0.03, 0.05):
        fmt(f'edge≥{e:.2f} & EV≥5% (ambos)', run_strategy(sub, 'both', edge_min=e, ev_min=0.05))
    for e in (0.0, 0.03, 0.05):
        fmt(f'OVER edge≥{e:.2f} & EV≥5%', run_strategy(sub, 'over', edge_min=e, ev_min=0.05))
        fmt(f'UNDER edge≥{e:.2f} & EV≥5%', run_strategy(sub, 'under', edge_min=e, ev_min=0.05))

    P('\n  -- E3: edge + EV≥5% + cuota≥2.0 --')
    for e in (0.02, 0.03, 0.05):
        fmt(f'edge≥{e:.2f} & EV≥5% & odds≥2', run_strategy(sub, 'both', edge_min=e, ev_min=0.05, min_odds=2.0))

    # ── Evaluación alternativa: con cuota máxima (techo) ──
    P('\n── C2) Igual con cuota BbMx (máxima del mercado) ──')
    sub2 = sub.copy()
    sub2['o_over'] = sub2['o_over_max'].fillna(sub2['o_over'])
    sub2['o_under'] = sub2['o_under_max'].fillna(sub2['o_under'])
    sub2['fair_o'] = sub2['fair_o']  # fair sigue del avg (referencia del mercado)
    P('  (fair se mantiene con avg; la cuota ejecutable mejora)')
    for e in (0.0, 0.03, 0.05):
        fmt(f'MAXQUOTE edge≥{e:.2f}', run_strategy(sub2, 'both', edge_min=e))
    for e in (0.0, 0.03):
        fmt(f'MAXQUOTE OVER edge≥{e:.2f}', run_strategy(sub2, 'over', edge_min=e))
        fmt(f'MAXQUOTE UNDER edge≥{e:.2f}', run_strategy(sub2, 'under', edge_min=e))

    # ── E) Estabilidad por temporada de la mejor estrategia ──
    P('\n── E) ESTABILIDAD POR TEMPORADA ──')

    def season_breakdown(tag, side_filter, edge_min, ev_min=0.05, min_odds=1.5, d=None):
        d = d if d is not None else sub
        rows = []
        if side_filter in ('both', 'over'):
            o = d[['date', 'season', 'o_over', 'fair_o', 'p_over_c', 'over_won']].copy()
            o['side'] = 'over'; o['p'] = o['p_over_c']; o['fair'] = o['fair_o']; o['odds'] = o['o_over']; o['won'] = o['over_won']
            rows.append(o)
        if side_filter in ('both', 'under'):
            u = d[['date', 'season', 'o_under', 'fair_u', 'p_under_c', 'over_won']].copy()
            u['side'] = 'under'; u['p'] = u['p_under_c']; u['fair'] = u['fair_u']; u['odds'] = u['o_under']; u['won'] = ~u['over_won']
            rows.append(u)
        x = pd.concat(rows, ignore_index=True)
        x['edge'] = x['p'] - x['fair']
        x['ev'] = x['p'] * x['odds'] - 1.0
        x = x[(x['edge'] >= edge_min) & (x['ev'] >= ev_min) & (x['odds'] >= min_odds)]
        if len(x) == 0:
            return
        x['pnl'] = np.where(x['won'], x['odds'] - 1.0, -1.0)
        P(f'\n  {tag}:')
        for s, g in x.groupby('season'):
            P(f'    {int(s)}: n={len(g):4d} WR={g["won"].mean()*100:5.1f}% ROI={g["pnl"].mean()*100:+6.2f}%')

    season_breakdown('UNDER edge≥0.03 & EV≥5%', 'under', 0.03)
    season_breakdown('UNDER edge≥0.05 & EV≥5%', 'under', 0.05)
    season_breakdown('OVER edge≥0.05 & EV≥5%', 'over', 0.05)

    # ── F) ¿Coincide el modelo con el mercado? Correlación p_corr vs fair ──
    P('\n── F) Correlación modelo vs mercado ──')
    c1 = sub['p_over_c'].corr(sub['fair_o'])
    P(f'  corr(p_over_c, fair_o) = {c1:.4f}')
    # ¿Cuánta info añade? regresión logística simple no; usar AUC aproximada por buckets
    # comparar Brier score de modelo vs mercado
    from sklearn.metrics import brier_score_loss, roc_auc_score
    y = sub['over_won'].astype(int)
    bs_m = brier_score_loss(y, sub['p_over_c'])
    bs_k = brier_score_loss(y, sub['fair_o'])
    auc_m = roc_auc_score(y, sub['p_over_c'])
    auc_k = roc_auc_score(y, sub['fair_o'])
    P(f'  Brier modelo: {bs_m:.4f} | Brier mercado: {bs_k:.4f} (menor=mejor)')
    P(f'  AUC modelo: {auc_m:.4f} | AUC mercado: {auc_k:.4f}')

    P('\n' + '=' * 100)
    P('FIN')

    with open(OUT_TXT, 'w') as f:
        f.write('\n'.join(out))
    print(f'\nGuardado: {OUT_TXT}')


if __name__ == '__main__':
    main()
