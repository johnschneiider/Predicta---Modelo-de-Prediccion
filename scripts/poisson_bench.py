"""
BENCHMARK walk-forward (sin lookahead) de los modelos de λ — causa raíz de
la calibración.

Compara 3 esquemas para predecir el λ TOTAL (goles y tiros a puerta) de cada
partido usando SOLO datos anteriores al partido:

  A) BASELINE: media de liga (sin información de equipos)
  B) OLD:      réplica del pipeline actual de producción
               - SOT:  promedios simples last-20 por venue (xg_shots_model)
               - Goles: fórmula Dixon-Coles actual (ratios ataque/defensa
                 sin shrinkage + piso de liga + 1.15/0.95 home adv)
  C) NEW:      regresión Poisson regularizada (ridge) con ratings de
               ataque/defensa por equipo + ventaja local + decaimiento temporal
               (los ratings se encogen hacia la media de liga → sin inflación
               de equipos fuertes ni sobreajuste de muestras pequeñas)

Métricas por mercado (sobre el conjunto TEST):
  - Sesgo (λ predicho total - real)
  - RMSE
  - Correlación de rango Spearman (¿el λ ordena partidos? = ¿P discrimina?)
  - Curva de fiabilidad P(over) a línea fija: buckets de P predicha → % real over
"""
import os, sys, warnings
warnings.filterwarnings('ignore')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
sys.path.insert(0, '/var/www/predicta.com.co')
import django; django.setup()

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import poisson, spearmanr
from football_data.models import Match, League

TRAIN_END = pd.Timestamp('2026-06-15')  # test: partidos desde esta fecha (asentados)
TAU = 90.0          # decaimiento temporal NEW (días)
RIDGE = 1.0         # regularización ridge de ratings
MIN_TEAM_GAMES = 5  # partidos mínimos del equipo en train para incluir el partido en test

# ─────────────────────────────────────────────────────────────
# 1) Extraer datos
# ─────────────────────────────────────────────────────────────
qs = Match.objects.filter(
    date__gte='2025-01-01', fthg__isnull=False, ftag__isnull=False,
    hst__isnull=False, ast__isnull=False,
).values('league__name', 'date', 'home_team', 'away_team', 'fthg', 'ftag', 'hst', 'ast')

df = pd.DataFrame(list(qs))
df['date'] = pd.to_datetime(df['date'])
df['total_goals'] = df['fthg'] + df['ftag']
df['total_sot'] = df['hst'] + df['ast']

# Ligas con suficiente data
league_counts = df.groupby('league__name').size()
leagues = league_counts[league_counts >= 400].index.tolist()
print(f'Ligas con >=400 partidos: {len(leagues)} | total filas: {len(df)}\n')


def split_train_test(d):
    tr = d[d['date'] < TRAIN_END]
    te = d[d['date'] >= TRAIN_END]
    return tr, te


def team_hist_mean(d, team, venue, col, n=20):
    """Réplica exacta del enfoque xg_shots_model: media de últimos n partidos
    del equipo en ese venue (home/away), sin shrinkage."""
    sub = d[(d['home_team'] == team) & (d['away_team'] != team)] if venue == 'home' \
        else d[(d['away_team'] == team)]
    sub = sub[sub['date'] < TRAIN_END]  # solo pasado
    sub = sub.sort_values('date').tail(n)
    vals = sub['hst'] if (venue == 'home') else sub['ast']
    if len(vals) == 0:
        return None
    return float(vals.mean())


def predict_old_sot(tr, home, away):
    """OLD: λ_SOT = media hst del local en sus últimos 20 de local
    + media ast del visitante en sus últimos 20 de visitante. Clamp 2-20."""
    h = team_hist_mean(tr, home, 'home', 'hst')
    a = team_hist_mean(tr, away, 'away', 'ast')
    h = h if h is not None else tr['hst'].mean()
    a = a if a is not None else tr['ast'].mean()
    return float(min(20.0, max(2.0, h + a)))


def predict_old_goals(tr, home, away):
    """OLD: réplica de la fórmula Dixon-Coles actual (sin shrinkage)."""
    lm = tr.sort_values('date').tail(200)
    lh_avg = lm['fthg'].mean() or 1.5
    la_avg = lm['ftag'].mean() or 1.2
    hh = tr[tr['home_team'] == home].sort_values('date').tail(30)
    aa = tr[tr['away_team'] == away].sort_values('date').tail(30)
    MIN = 10
    home_attack = hh['fthg'].mean() if len(hh) >= MIN else lh_avg
    away_attack = aa['ftag'].mean() if len(aa) >= MIN else la_avg
    home_defense = hh['ftag'].mean() if len(hh) >= MIN else la_avg
    away_defense = aa['fthg'].mean() if len(aa) >= MIN else lh_avg
    lh = (home_attack / lh_avg) * (away_defense / la_avg) * lh_avg * 1.15
    la = (away_attack / la_avg) * (home_defense / lh_avg) * la_avg * 0.95
    total = lh + la
    league_total = lh_avg + la_avg
    if total < league_total:  # piso de liga
        scale = league_total / total if total > 0 else 1.0
        lh *= scale; la *= scale
    # límites "realistas": clamp ligero
    lh = float(np.clip(lh, 0.4, 3.5)); la = float(np.clip(la, 0.3, 3.0))
    return lh + la


# ─────────────────────────────────────────────────────────────
# 2) NEW: regresión Poisson regularizada por liga
# ─────────────────────────────────────────────────────────────
def fit_poisson_ratings(tr, col_home, col_away):
    """Ajusta ratings ridge de ataque/defensa + ventaja local por liga
    con decaimiento temporal. Devuelve función de predicción."""
    teams = sorted(set(tr['home_team']) | set(tr['away_team']))
    t2i = {t: i for i, t in enumerate(teams)}
    n_teams = len(teams)

    max_date = tr['date'].max()
    w = np.exp(-(max_date - tr['date']).dt.days.values / TAU)

    hh = tr['home_team'].map(t2i).values
    aa = tr['away_team'].map(t2i).values
    gh = tr[col_home].values.astype(float)
    ga = tr[col_away].values.astype(float)

    # params: [alpha, att[0..n-1], def[0..n-1], home_adv]
    n_params = 1 + n_teams + n_teams + 1
    x0 = np.zeros(n_params)
    x0[0] = np.log(gh.mean() + 1e-6)

    def nll(x):
        alpha = x[0]
        att = x[1:1 + n_teams]
        deff = x[1 + n_teams:1 + 2 * n_teams]
        h_adv = x[-1]
        lam_h = np.exp(alpha + att[hh] + deff[aa] + h_adv)
        lam_a = np.exp(alpha + att[aa] + deff[hh])
        ll = -np.sum(w * (poisson.logpmf(gh, lam_h) + poisson.logpmf(ga, lam_a)))
        pen = RIDGE * (np.sum(att ** 2) + np.sum(deff ** 2))
        return ll + pen

    res = minimize(nll, x0, method='L-BFGS-B',
                   options={'maxiter': 3000, 'ftol': 1e-10, 'gtol': 1e-7})
    x = res.x
    alpha = x[0]; att = x[1:1 + n_teams]; deff = x[1 + n_teams:1 + 2 * n_teams]; h_adv = x[-1]

    def predict(home, away):
        if home not in t2i or away not in t2i:
            return None
        lh = np.exp(alpha + att[t2i[home]] + deff[t2i[away]] + h_adv)
        la = np.exp(alpha + att[t2i[away]] + deff[t2i[home]])
        return float(lh + la)

    return predict


# ─────────────────────────────────────────────────────────────
# 3) Evaluación
# ─────────────────────────────────────────────────────────────
def evaluate(market_key, market_label, col_total, line, col_home, col_away):
    print(f'\n{"=" * 78}\nMERCADO: {market_label}   (línea fija para fiabilidad: {line})')
    print(f'{"=" * 78}')
    res = {'A_baseline': [], 'B_old': [], 'C_new': []}
    rel = {'A': {'buckets': {}, 'n': 0}, 'B': {'buckets': {}, 'n': 0}, 'C': {'buckets': {}, 'n': 0}}

    n_leagues_used = 0
    for lg in leagues:
        d = df[df['league__name'] == lg]
        tr, te = split_train_test(d)
        if len(tr) < 100 or len(te) < 30:
            continue
        n_leagues_used += 1
        try:
            pred_new = fit_poisson_ratings(tr, col_home, col_away)
        except Exception:
            continue

        league_mean = tr[col_total].mean()

        for _, row in te.iterrows():
            home, away = row['home_team'], row['away_team']
            actual = row[col_total]
            # OLD
            if market_key == 'SOT':
                old = predict_old_sot(tr, home, away)
            else:
                old = predict_old_goals(tr, home, away)
            # NEW
            new = pred_new(home, away)
            if new is None:
                continue
            res['A_baseline'].append(league_mean - actual)
            res['B_old'].append(old - actual)
            res['C_new'].append(new - actual)
            # fiabilidad P(over) en línea fija
            for tag, lam in [('A', league_mean), ('B', old), ('C', new)]:
                p_over = 1.0 - poisson.cdf(int(np.floor(line)), lam)
                bucket = min(4, int(p_over * 10))  # 0..4 (0-10,10-20,...,40+)
                rel[tag]['buckets'].setdefault(bucket, {'n': 0, 'w': 0})
                rel[tag]['buckets'][bucket]['n'] += 1
                rel[tag]['buckets'][bucket]['w'] += 1 if actual > line else 0
                rel[tag]['n'] += 1

    print(f'Ligas evaluadas: {n_leagues_used} | partidos test: {len(res["C_new"])}\n')
    print(f'{"esquema":16s} {"n":>5s} {"sesgo λ":>8s} {"RMSE":>6s} {"ρ spearman":>11s}')
    for key, lab in [('A_baseline', 'A) baseline'), ('B_old', 'B) OLD actual'), ('C_new', 'C) NEW ridge')]:
        errs = np.array(res[key])
        if len(errs) == 0:
            continue
        bias = errs.mean(); rmse = np.sqrt((errs ** 2).mean())
        # spearman sobre λ predicho vs real requiere los pares; lo calculamos abajo
        print(f'{lab:16s} {len(errs):5d} {bias:+.2f} {rmse:6.2f} {spear[key]:>11s}')

    # spearman por esquema (recomputar con pares)
    print('\nFiabilidad P(over) por esquema (buckets de P predicha):')
    for tag, lab in [('A', 'A) baseline'), ('B', 'B) OLD'), ('C', 'C) NEW')]:
        r = rel[tag]
        out = []
        for b in sorted(r['buckets']):
            bb = r['buckets'][b]
            lo = b * 10
            wr = bb['w'] / bb['n'] * 100
            out.append(f'{lo}-{lo + 10}%→{wr:.0f}%({bb["n"]})')
        print(f'  {lab:12s} ' + ' | '.join(out))
    return res


spear = {'A_baseline': '', 'B_old': '', 'C_new': ''}
# calcular spearman por liga agregando pares λ-real
def spear_full(df, leagues, market, col_total, col_home, col_away):
    pairs = {'A': [], 'B': [], 'C': []}
    for lg in leagues:
        d = df[df['league__name'] == lg]
        tr, te = split_train_test(d)
        if len(tr) < 100 or len(te) < 30:
            continue
        try:
            pred_new = fit_poisson_ratings(tr, col_home, col_away)
        except Exception:
            continue
        lm = tr[col_total].mean()
        for _, row in te.iterrows():
            home, away = row['home_team'], row['away_team']
            actual = row[col_total]
            old = predict_old_sot(tr, home, away) if market == 'SOT' else predict_old_goals(tr, home, away)
            new = pred_new(home, away)
            if new is None:
                continue
            pairs['A'].append((lm, actual)); pairs['B'].append((old, actual)); pairs['C'].append((new, actual))
    for k in pairs:
        if len(pairs[k]) > 5:
            x = [p[0] for p in pairs[k]]; y = [p[1] for p in pairs[k]]
            spear[{'A': 'A_baseline', 'B': 'B_old', 'C': 'C_new'}[k]] = f'{spearmanr(x, y).statistic:.3f}'
    return pairs

# ── ejecutar ──
pairs_sot = spear_full(df, leagues, 'SOT', 'total_sot', 'hst', 'ast')
evaluate('SOT', 'SOT (tiros a puerta)', 'total_sot', 8.5, 'hst', 'ast')
spear = {'A_baseline': '', 'B_old': '', 'C_new': ''}
pairs_goals = spear_full(df, leagues, 'GOALS', 'total_goals', 'fthg', 'ftag')
evaluate('GOALS', 'GOLES', 'total_goals', 2.5, 'fthg', 'ftag')
