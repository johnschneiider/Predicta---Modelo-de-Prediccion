"""
Backtest del modelo Predicta vs el mercado (Pinnacle/Bet365).

Reproduce fielmente el modelo de la app (predictors.py + simple_models.py):
  - lambda_home = avg_goles(local, historico previo) * 1.15
  - lambda_away = avg_goles(visitante, historico previo) * 0.85
  - Poisson -> P(1X2)

Compara contra:
  1. Baselines (siempre local, favorito del mercado)
  2. Probabilidades implicitas de Pinnacle (mercado eficiente)
  3. Simulacion de value-betting (modelo vs mercado)

Walk-forward estricto: para cada partido solo se usa el historico ANTERIOR.
"""
import sqlite3
import math
from collections import defaultdict
import numpy as np

DB = '/var/www/predicta.com.co/db.sqlite3'
MIN_YEAR = 2013  # era Pinnacle

def poisson_pmf(k, lam):
    if lam <= 0:
        return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def poisson_1x2(lh, la, maxg=10):
    pH = pD = pA = 0.0
    for h in range(maxg + 1):
        ph = poisson_pmf(h, lh)
        for a in range(maxg + 1):
            pa = poisson_pmf(a, la)
            j = ph * pa
            if h > a: pH += j
            elif h == a: pD += j
            else: pA += j
    t = pH + pD + pA
    if t > 0:
        pH, pD, pA = pH/t, pD/t, pA/t
    return np.array([pH, pD, pA])

def main():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""
        SELECT m.league_id, m.date, m.home_team, m.away_team,
               m.fthg, m.ftag, m.ftr,
               m.psh, m.psd, m.psa
        FROM football_data_match m
        WHERE m.ftr IS NOT NULL
          AND m.date >= '2013-01-01'
          AND m.fthg IS NOT NULL
        ORDER BY m.date ASC
    """)
    rows = c.fetchall()
    conn.close()

    # Acumulador walk-forward por liga
    # league -> team -> {gf, ga, n} (goles totales, no solo local/visit)
    league_hist = defaultdict(lambda: defaultdict(lambda: {'gf': 0, 'ga': 0, 'n': 0}))

    res = {'H': 0, 'D': 1, 'A': 2}
    inv = {0: 'H', 1: 'D', 2: 'A'}

    model_correct = 0
    market_correct = 0
    fav_correct = 0
    n_all = 0
    n_with_pinn = 0

    model_ll = 0.0
    market_ll = 0.0
    n_ll = 0

    # Error por outcome real (modelo)
    err_model = {'H': [0,0], 'D': [0,0], 'A': [0,0]}
    # Confusion modelo
    conf = {'H': {'H':0,'D':0,'A':0}, 'D': {'H':0,'D':0,'A':0}, 'A': {'H':0,'D':0,'A':0}}

    # Value betting ledger
    value_bets = []  # (stake, odds, won)

    for (lid, date, ht, at, fthg, ftag, ftr, psh, psd, psa) in rows:
        if ftr not in ('H', 'D', 'A'):
            continue
        actual = res[ftr]

        hist = league_hist[lid]
        hd = hist[ht]
        ad = hist[at]

        # lambda con historico previo (walk-forward)
        if hd['n'] > 0:
            lambda_h = (hd['gf'] / hd['n']) * 1.15
        else:
            lambda_h = 1.30  # default sin historico

        if ad['n'] > 0:
            lambda_a = (ad['gf'] / ad['n']) * 0.85
        else:
            lambda_a = 1.10

        # clamp razonable
        lambda_h = max(0.15, min(4.5, lambda_h))
        lambda_a = max(0.15, min(4.5, lambda_a))

        pm = poisson_1x2(lambda_h, lambda_a)
        model_pred = int(np.argmax(pm))

        n_all += 1
        if model_pred == actual:
            model_correct += 1
        err_model[ftr][0] += 1
        if model_pred == actual:
            err_model[ftr][1] += 1
        conf[ftr][inv[model_pred]] += 1

        # ---- mercado ----
        if psh and psd and psa:
            try:
                oh, od, oa = float(psh), float(psd), float(psa)
                if oh > 1.0 and od > 1.0 and oa > 1.0:
                    inv_p = np.array([1/oh, 1/od, 1/oa])
                    pmkt = inv_p / inv_p.sum()
                    market_pred = int(np.argmax(pmkt))
                    fav_pred = int(np.argmin([oh, od, oa]))  # favorito (menor cuota)
                    n_with_pinn += 1
                    if market_pred == actual:
                        market_correct += 1
                    if fav_pred == actual:
                        fav_correct += 1

                    # log-loss
                    eps = 1e-9
                    model_ll += -math.log(max(pm[actual], eps))
                    market_ll += -math.log(max(pmkt[actual], eps))
                    n_ll += 1

                    # value betting: apostar si P_modelo > P_mercado * (1+margin)
                    for k in range(3):
                        margin = 0.10
                        if pm[k] > pmkt[k] * (1 + margin):
                            odd = [oh, od, oa][k]
                            stake = 1.0
                            won = (actual == k)
                            value_bets.append((stake, odd, won))
            except (TypeError, ValueError):
                pass

        # ---- actualizar historico con ESTE partido (despues de predecir) ----
        hd['gf'] += (fthg or 0); hd['ga'] += (ftag or 0); hd['n'] += 1
        ad['gf'] += (ftag or 0); ad['ga'] += (fthg or 0); ad['n'] += 1

    print("=" * 66)
    print("  BACKTEST PREDICTA vs MERCADO  (walk-forward, 2013+)")
    print("=" * 66)
    print(f"  Partidos evaluados (modelo): {n_all}")
    print(f"  Partidos con cuota Pinnacle : {n_with_pinn}")
    print()
    print(f"  🎯 ACCURACY 1X2")
    print(f"     Modelo Predicta      : {model_correct/n_all*100:5.1f}%  ({model_correct}/{n_all})")
    if n_with_pinn:
        print(f"     Mercado (Pinnacle)   : {market_correct/n_with_pinn*100:5.1f}%  ({market_correct}/{n_with_pinn})")
        print(f"     Favorito del mercado : {fav_correct/n_with_pinn*100:5.1f}%")
    if n_ll:
        print(f"  📉 LOG-LOSS (menor = mejor)")
        print(f"     Modelo Predicta : {model_ll/n_ll:.4f}")
        print(f"     Mercado Pinnacle: {market_ll/n_ll:.4f}")
    print()
    print(f"  🎯 MODELO — acierto por resultado real:")
    for r, lbl in [('H','Local'), ('D','Empate'), ('A','Visitante')]:
        t, ok = err_model[r]
        if t: print(f"     {lbl:10s}: {ok/t*100:5.1f}%  ({ok}/{t})")
    print()
    print(f"  🔀 MATRIZ DE CONFUSIÓN DEL MODELO (filas=real, col=predicho)")
    print(f"     {'':>16} {'H':>6} {'D':>6} {'A':>6}")
    for r, lbl in [('H','Real Local'), ('D','Real Empate'), ('A','Real Visit')]:
        row = conf[r]
        print(f"     {lbl:>16} {row['H']:>6} {row['D']:>6} {row['A']:>6}")
    print()
    if value_bets:
        total_stake = sum(b[0] for b in value_bets)
        total_ret = sum(b[0]*b[1] if b[2] else 0 for b in value_bets)
        wins = sum(1 for b in value_bets if b[2])
        print(f"  💰 VALUE-BETTING (P_modelo > P_mercado*1.10):")
        print(f"     Apuestas: {len(value_bets)} | Aciertos: {wins} ({wins/len(value_bets)*100:.1f}%)")
        print(f"     Stake total: {total_stake:.0f}u | Retorno: {total_ret:.0f}u | ROI: {(total_ret-total_stake)/total_stake*100:+.1f}%")

if __name__ == '__main__':
    main()
