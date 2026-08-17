"""
LOOCV corners — ligas Suramérica (SQLite corners_scraped.db).

Reproduce FIELMENTE el modelo de corners de la app (corners_model.py):
  ce_local  = ataque_home*0.40 + defensa_para_local*0.30 + forma_home*0.15 + liga_prom*0.15
  ce_visit  = ataque_away*0.40 + defensa_para_visit*0.30 + forma_away*0.15 + liga_prom*0.15
  ce_total  = ce_local + ce_visit

LOOCV estricto: para cada partido, TODAS las stats se recalculan EXCLUYENDO ese partido
(sin leakage). Solo ligas suramericanas.

Inputs (fuente SQLite, como hace la app para SA):
  ataque_home  = AVG(home_corners) donde home_team=local
  ataque_away  = AVG(away_corners) donde away_team=visit
  defensa_para_local     = AVG(home_corners) donde away_team=visit (corners que recibe el visitante)
  defensa_para_visitante = AVG(away_corners) donde home_team=local (corners que recibe el local)
  forma_home/away = media de últimos 5 partidos (por fecha) del equipo
  liga_prom = AVG(total_corners)/2 por liga
"""
import sqlite3
import math
from collections import defaultdict
import numpy as np

DB = '/var/www/predicta.com.co/data/corners_scraped.db'
SA_LEAGUES = ['Primera Division', 'Primera A', 'Serie A', 'Serie B']

# Pesos del modelo de la app
W_ATAQUE, W_DEFENSA, W_FORMA, W_LIGA = 0.40, 0.30, 0.15, 0.15
OVER_THRESHOLDS = [8, 10, 12, 15]

def parse_date(d):
    # formatos DD-MM-YYYY o YYYY-MM-DD
    d = str(d).strip()
    if '-' in d:
        parts = d.split('-')
        if len(parts[0]) == 4:  # YYYY-MM-DD
            return (int(parts[0]), int(parts[1]), int(parts[2]))
        else:  # DD-MM-YYYY
            return (int(parts[2]), int(parts[1]), int(parts[0]))
    return (0, 0, 0)

def poisson_pmf(k, lam):
    if lam <= 0: return 1.0 if k == 0 else 0.0
    return math.exp(-lam) * (lam ** k) / math.factorial(k)

def load():
    conn = sqlite3.connect(DB)
    c = conn.cursor()
    c.execute("""SELECT date, home_team, away_team, home_corners, away_corners, league
                 FROM corners_matches WHERE league IN (?,?,?,?)""", SA_LEAGUES)
    rows = c.fetchall()
    conn.close()
    return rows

def main():
    rows = load()
    # Agrupar por liga
    by_league = defaultdict(list)
    for r in rows:
        by_league[r[5]].append(r)

    print("=" * 70)
    print("  LOOCV CORNERS — Suramérica (modelo 40/30/15/15 de la app)")
    print("=" * 70)

    total_err = []
    total_n = 0
    ou_stats = {t: [0, 0] for t in OVER_THRESHOLDS}  # [correct, total]
    # baseline liga para O/U (siempre over/under segun la media historica)
    ou_baseline = {t: [0, 0] for t in OVER_THRESHOLDS}
    home_dir = [0, 0]  # acierto direccional home>away

    for lg, matches in sorted(by_league.items()):
        n = len(matches)
        if n < 15:
            print(f"\n  [{lg}] n={n} — demasiado pocos partidos, omitida")
            continue

        errs = []
        for i in range(n):
            date, ht, at, hc, ac, lg2 = matches[i]
            total_actual = hc + ac

            # ---- Reconstruir stats EXCLUYENDO el partido i (LOOCV) ----
            others = [m for j, m in enumerate(matches) if j != i]

            # acumuladores
            home_c = defaultdict(list)   # home_team -> lista de home_corners (local)
            away_c = defaultdict(list)   # away_team -> lista de away_corners (visit)
            home_conceded = defaultdict(list)  # home_team -> away_corners (lo que recibe de local)
            away_conceded = defaultdict(list)  # away_team -> home_corners (lo que recibe de visit)
            team_all = defaultdict(list)  # team -> lista de (fecha, corners) para forma5
            tot = []

            for m in others:
                d, h, a, hc2, ac2, _ = m
                home_c[h].append(hc2)
                away_c[a].append(ac2)
                home_conceded[h].append(ac2)
                away_conceded[a].append(hc2)
                team_all[h].append((parse_date(d), hc2))
                team_all[a].append((parse_date(d), ac2))
                tot.append(hc2 + ac2)

            def mean(x):
                return float(np.mean(x)) if x else None

            # Inputs
            ataque_home = mean(home_c[ht]) or 5.0
            ataque_away = mean(away_c[at]) or 4.5
            defensa_local = mean(away_conceded[at]) or 5.0   # corners que recibe visitante fuera
            defensa_visit = mean(home_conceded[ht]) or 4.5   # corners que recibe local en casa
            liga_prom = (mean(tot) or 10.0) / 2.0

            # forma5 (últimos 5 por fecha)
            def forma5(team):
                arr = sorted(team_all[team], key=lambda x: x[0], reverse=True)[:5]
                vals = [v for _, v in arr]
                return float(np.mean(vals)) if vals else None

            forma_home = forma5(ht)
            forma_away = forma5(at)
            if forma_home is None: forma_home = ataque_home
            if forma_away is None: forma_away = ataque_away

            # ---- Modelo 40/30/15/15 ----
            ce_local = ataque_home*W_ATAQUE + defensa_local*W_DEFENSA + forma_home*W_FORMA + liga_prom*W_LIGA
            ce_visit = ataque_away*W_ATAQUE + defensa_visit*W_DEFENSA + forma_away*W_FORMA + liga_prom*W_LIGA
            ce_total = ce_local + ce_visit

            # ---- Métricas ----
            errs.append(abs(ce_total - total_actual))
            total_n += 1

            # O/U en cada threshold
            for t in OVER_THRESHOLDS:
                pred_over = ce_total > t
                actual_over = total_actual > t
                if pred_over == actual_over:
                    ou_stats[t][0] += 1
                ou_stats[t][1] += 1
                # baseline: usar la media histórica de la liga (sin este partido)
                base_over = (mean(tot) or 10.0) > t
                if base_over == actual_over:
                    ou_baseline[t][0] += 1
                ou_baseline[t][1] += 1

            # direccional
            if (ce_local >= ce_visit) == (hc >= ac):
                home_dir[0] += 1
            home_dir[1] += 1

        mae = np.mean(errs)
        rmse = np.sqrt(np.mean(np.array(errs)**2))
        print(f"\n  [{lg}] n={n}")
        print(f"    MAE corners totales: {mae:.2f}  RMSE: {rmse:.2f}")
        print(f"    (media real total: {np.mean([m[3]+m[4] for m in matches]):.2f})")
        total_err.extend(errs)

    print()
    print("=" * 70)
    print("  RESUMEN GLOBAL SUAMÉRICA")
    print("=" * 70)
    print(f"  Partidos LOOCV: {total_n}")
    print(f"  MAE corners totales: {np.mean(total_err):.2f}")
    print(f"  RMSE: {np.sqrt(np.mean(np.array(total_err)**2)):.2f}")
    print(f"  Acierto direccional (home vs away corners): {home_dir[0]/home_dir[1]*100:.1f}%  ({home_dir[0]}/{home_dir[1]})")
    print()
    print(f"  {'Over/Under':<12} {'Modelo':>9} {'Baseline media liga':>20}")
    for t in OVER_THRESHOLDS:
        mo = ou_stats[t][0]/ou_stats[t][1]*100
        bo = ou_baseline[t][0]/ou_baseline[t][1]*100
        print(f"  O/U {t:>3}      {mo:>8.1f}%  {bo:>19.1f}%")

if __name__ == '__main__':
    main()
