"""
LOOCV para ligas suramericanas usando la DB de corners (corners_scraped.db)
+ script para scrapear resultados de flashscore y analizar overfitting
"""
import sqlite3
import numpy as np
from collections import defaultdict
from typing import Dict, List, Tuple


def load_south_american_data():
    """Carga datos de corners para ligas suramericanas"""
    conn = sqlite3.connect('/var/www/predicta.com.co/data/corners_scraped.db')
    c = conn.cursor()

    leagues = {
        'Primera A': 'Colombia',
        'Serie A': 'Brasil A',
        'Primera Division': 'Argentina',
        'Serie B': 'Brasil B',
    }

    results = {}
    for league_name, country in leagues.items():
        c.execute("""
            SELECT date, home_team, away_team, home_corners, away_corners
            FROM corners_matches
            WHERE league = ?
            ORDER BY date DESC
        """, (league_name,))
        rows = c.fetchall()
        if rows:
            results[league_name] = {
                'country': country,
                'matches': rows,
                'count': len(rows),
            }
    conn.close()
    return results


def compute_corner_stats(matches, exclude_idx=None):
    """Estadísticas de corners excluyendo un partido (LOOCV)"""
    teams = defaultdict(lambda: {'home_corners': [], 'away_corners': [], 'total_corners': []})

    for i, m in enumerate(matches):
        if exclude_idx is not None and i == exclude_idx:
            continue
        date, ht, at, hc, ac = m
        teams[ht]['home_corners'].append(hc or 0)
        teams[at]['away_corners'].append(ac or 0)
        teams[ht]['total_corners'].append((hc or 0) + (ac or 0))
        teams[at]['total_corners'].append((hc or 0) + (ac or 0))

    return teams


def predict_total_corners(home_team, away_team, stats):
    """Predice total de corners basado en todos los demás partidos"""
    home = stats.get(home_team, {})
    away = stats.get(away_team, {})

    home_avg_for = np.mean(home.get('home_corners', [8.0]))
    away_avg_for = np.mean(away.get('away_corners', [4.0]))
    home_total_avg = np.mean(home.get('total_corners', [10.0]))
    away_total_avg = np.mean(away.get('total_corners', [10.0]))

    # Predicción: promedio de corners del local en casa + visitante fuera
    predicted = (home_avg_for + away_avg_for)

    # Intervalos de confianza
    n_home = len(home.get('home_corners', []))
    n_away = len(away.get('away_corners', []))

    return predicted, n_home, n_away


def loocv_corners():
    """LOOCV para predicción de corners en ligas suramericanas"""
    data = load_south_american_data()
    all_results = {}

    for league_name, info in data.items():
        matches = info['matches']
        n = len(matches)
        if n < 20:
            continue

        errors = []
        errors_pct = []
        over_under_9_5_correct = 0
        over_under_9_5_total = 0

        print(f"\n{'='*60}")
        print(f"  LOOCV Corners: {league_name} ({info['country']}) — {n} partidos")
        print(f"{'='*60}")

        for i in range(min(n, 150)):  # máx 150 por liga
            date, ht, at, hc, ac = matches[i]

            # LOOCV
            stats = compute_corner_stats(matches, exclude_idx=i)

            predicted, nh, na = predict_total_corners(ht, at, stats)
            actual = (hc or 0) + (ac or 0)

            error = abs(predicted - actual)
            errors.append(error)
            errors_pct.append(error / max(actual, 1) * 100)

            # Over/Under 9.5
            over_under_9_5_total += 1
            if (predicted > 9.5 and actual > 9.5) or (predicted <= 9.5 and actual <= 9.5):
                over_under_9_5_correct += 1

        # Métricas
        mae = np.mean(errors)
        rmse = np.sqrt(np.mean(np.array(errors)**2))
        mape = np.mean(errors_pct)
        ou_acc = over_under_9_5_correct / over_under_9_5_total * 100

        # Ratio de overfitting: std entre equipos vs error
        all_home_corners = [m[3] or 0 for m in matches]
        all_away_corners = [m[4] or 0 for m in matches]
        league_std = np.std(all_home_corners + all_away_corners)

        result = {
            'league': league_name,
            'country': info['country'],
            'n': n,
            'mae': mae,
            'rmse': rmse,
            'mape': mape,
            'ou_9_5_acc': ou_acc,
            'league_std': league_std,
            'overfit_ratio': mae / league_std if league_std > 0 else 0,
        }

        print(f"  📊 MAE: {mae:.2f} corners | RMSE: {rmse:.2f} | MAPE: {mape:.1f}%")
        print(f"  📊 Over/Under 9.5 corners: {ou_acc:.1f}%")
        print(f"  📊 Desviación estándar liga: {league_std:.2f} corners")
        print(f"  📊 Ratio MAE/std: {result['overfit_ratio']:.2f} {'✅ Bueno' if result['overfit_ratio'] < 1.0 else '⚠️ Malo'}")

        all_results[league_name] = result

    # Resumen
    print(f"\n\n{'='*60}")
    print(f"  📋 RESUMEN SUDAMÉRICA — Predicción de Corners (LOOCV)")
    print(f"{'='*60}")
    print(f"  {'Liga':<25} {'Partidos':>8} {'MAE':>6} {'MAPE':>7} {'O/U 9.5':>8} {'Ratio':>6}")
    print(f"  {'─'*65}")
    for name, r in sorted(all_results.items(), key=lambda x: x[1]['mae']):
        rat = '⚠️' if r['overfit_ratio'] > 1.0 else '✅'
        print(f"  {r['country']:<25} {r['n']:>8} {r['mae']:>5.1f} {r['mape']:>6.1f}% {r['ou_9_5_acc']:>7.1f}% {rat}")

    return all_results


if __name__ == '__main__':
    loocv_corners()
