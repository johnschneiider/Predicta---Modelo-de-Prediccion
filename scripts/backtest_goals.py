"""
Backtest mercados de goles del modelo (Over/Under 2.5 y BTTS) vs mercado.
Reproduce lambda_home/away del modelo y evalua:
  - Over/Under 2.5 goles
  - Ambos marcan (BTTS)
Compara contra cuotas Pinnacle de O/U 2.5 (p_over_25/p_under_25) cuando existen.
"""
import sqlite3
import math
from collections import defaultdict
import numpy as np

DB = '/var/www/predicta.com.co/db.sqlite3'

def poisson_pmf(k, lam):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        SELECT m.league_id, m.date, m.home_team, m.away_team,
               m.fthg, m.ftag, m.p_over_25, m.p_under_25
        FROM football_data_match m
        WHERE m.ftr IS NOT NULL AND m.date >= '2013-01-01' AND m.fthg IS NOT NULL
        ORDER BY m.date ASC
    """)
    rows = c.fetchall()
    conn.close()

    hist = defaultdict(lambda: defaultdict(lambda: {'gf':0,'n':0}))

    # O/U 2.5 modelo: P(total>2.5) por Poisson con lambda_total
    ou_total = ou_correct = 0
    ou_mkt_total = ou_mkt_correct = 0
    # BTTS modelo: 1 - P(home=0) - P(away=0) + P(0,0)
    btts_total = btts_correct = 0

    mae_goals = []
    n = 0

    for (lid, date, ht, at, fthg, ftag, po25, pu25) in rows:
        hd = hist[lid][ht]
        ad = hist[lid][at]
        lh = (hd['gf']/hd['n'])*1.15 if hd['n'] else 1.30
        la = (ad['gf']/ad['n'])*0.85 if ad['n'] else 1.10
        lh = max(0.15, min(4.5, lh)); la = max(0.15, min(4.5, la))
        lt = lh + la

        # O/U 2.5 via Poisson
        p_over = 1.0 - sum(poisson_pmf(k, lt) for k in range(3))  # P(total>=3)
        actual_total = (fthg or 0) + (ftag or 0)
        pred_over = p_over >= 0.5
        ou_total += 1
        if (actual_total > 2.5) == pred_over:
            ou_correct += 1

        # BTTS
        p0h = poisson_pmf(0, lh); p0a = poisson_pmf(0, la)
        p_btts = (1 - p0h) * (1 - p0a)
        btts_total += 1
        actual_btts = (fthg > 0 and ftag > 0)
        if (p_btts >= 0.5) == actual_btts:
            btts_correct += 1

        # Mercado O/U 2.5
        if po25 and pu25:
            try:
                o, u = float(po25), float(pu25)
                if o > 1.0 and u > 1.0:
                    mkt_over = (1/o) / (1/o + 1/u) >= 0.5
                    ou_mkt_total += 1
                    if (actual_total > 2.5) == mkt_over:
                        ou_mkt_correct += 1
            except (TypeError, ValueError):
                pass

        mae_goals.append(abs(lt - actual_total))
        n += 1

        hd['gf'] += (fthg or 0); hd['n'] += 1
        ad['gf'] += (ftag or 0); ad['n'] += 1

    print("="*60)
    print("  BACKTEST MERCADOS DE GOLES  (walk-forward 2013+)")
    print("="*60)
    print(f"  Partidos: {n}")
    print(f"  MAE goles totales (modelo): {np.mean(mae_goals):.2f}")
    print()
    print(f"  🎯 OVER/UNDER 2.5 goles")
    print(f"     Modelo  : {ou_correct/ou_total*100:5.1f}%  ({ou_correct}/{ou_total})")
    if ou_mkt_total:
        print(f"     Mercado : {ou_mkt_correct/ou_mkt_total*100:5.1f}%  ({ou_mkt_correct}/{ou_mkt_total})")
    # baseline: siempre OVER (lo mas frecuente en Europa ~52%)
    over_freq = sum(1 for (_,_,_,_,fh,fa,_,_) in rows if (fh or 0)+(fa or 0) > 2.5)/n*100
    print(f"     Baseline siempre-OVER: {over_freq:.1f}%")
    print()
    print(f"  🎯 AMBOS MARCAN (BTTS)")
    print(f"     Modelo : {btts_correct/btts_total*100:5.1f}%  ({btts_correct}/{btts_total})")
    btts_freq = sum(1 for (_,_,_,_,fh,fa,_,_) in rows if (fh or 0)>0 and (fa or 0)>0)/n*100
    print(f"     Baseline siempre-SI : {btts_freq:.1f}%")
    print(f"     Baseline siempre-NO : {100-btts_freq:.1f}%")

if __name__ == '__main__':
    main()
