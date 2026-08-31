"""
Evaluación de REAPERTURA de submercados (READ-ONLY, walk-forward sin lookahead).

Con el motor Poisson ridge (poisson_ratings), calcula sobre los partidos TEST
(>= 2026-06-15) la P(over/under) predicha por línea para goles, tiros a puerta
y córners, y BTTS derivado de λ_home/λ_away. Compara P predicha vs WR real.

Regla de lectura: si P ≈ WR real en un (mercado, línea, lado) → el submercado
está honesto y puede reabrirse. Si P >> WR → sigue descalibrado (no abrir).

También calcula la cuota mínima justa (1/P) para apostar con EV>0: si el
mercado real no ofrece esa cuota, el gate de EV lo filtra solo.
"""
import os, sys, warnings
warnings.filterwarnings('ignore')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
sys.path.insert(0, '/var/www/predicta.com.co')
import django; django.setup()

import numpy as np
import pandas as pd
from scipy.stats import poisson
from football_data.models import Match

TRAIN_END = pd.Timestamp('2026-06-15')

qs = Match.objects.filter(
    date__gte='2025-01-01', fthg__isnull=False, ftag__isnull=False,
).values('league__name', 'date', 'home_team', 'away_team', 'fthg', 'ftag', 'hst', 'ast', 'hc', 'ac')
df = pd.DataFrame(list(qs))
df['date'] = pd.to_datetime(df['date'])

# ── engine: importar y parchear caché para ajustar por liga con train ──
from ai_predictions.poisson_ratings import PoissonRatingsEngine, MARKET_COLS
engine = PoissonRatingsEngine()

MARKETS = {
    'goals': {'cols': ('fthg', 'ftag'), 'lines': [1.5, 2.5, 3.5]},
    'sot':   {'cols': ('hst', 'ast'),   'lines': [6.5, 7.5, 8.5, 9.5, 10.5]},
    'corners': {'cols': ('hc', 'ac'),   'lines': [7.5, 8.5, 9.5, 10.5]},
}

# acumuladores: (mercado, línea, lado) -> {n, p_sum, wins}
acc = {}
btts_acc = {'n': 0, 'p_sum': 0.0, 'wins': 0}

leagues = df.groupby('league__name').size()
leagues = leagues[leagues >= 400].index.tolist()
n_test = 0

for lg in leagues:
    d = df[df['league__name'] == lg]
    tr, te = d[d['date'] < TRAIN_END], d[d['date'] >= TRAIN_END]
    if len(tr) < 100 or len(te) < 20:
        continue
    # fit por mercado usando SOLO train (sin lookahead)
    models = {}
    for mk, spec in MARKETS.items():
        ch, ca = spec['cols']
        if te[ch].notna().mean() < 0.8:
            continue
        sub = tr[tr[ch].notna() & tr[ca].notna()]
        if len(sub) < 60:
            continue
        rows = [{'home': r['home_team'], 'away': r['away_team'],
                 'yh': float(r[ch]), 'ya': float(r[ca]),
                 'age_days': float((TRAIN_END - r['date']).days)}
                for _, r in sub.iterrows()]
        try:
            models[mk] = engine._fit(lg if isinstance(lg, int) else None, mk, rows)
        except Exception:
            continue

    for _, row in te.iterrows():
        for mk, spec in MARKETS.items():
            m = models.get(mk)
            if m is None:
                continue
            ch, ca = spec['cols']
            yh, ya = row[ch], row[ca]
            if pd.isna(yh) or pd.isna(ya):
                continue
            if row['home_team'] not in m['att'] or row['away_team'] not in m['att']:
                continue
            lam_h = np.exp(m['alpha'] + m['att'][row['home_team']]
                           + m['def'][row['away_team']] + m['home_adv'])
            lam_a = np.exp(m['alpha'] + m['att'][row['away_team']]
                           + m['def'][row['home_team']])
            total = yh + ya
            for line in spec['lines']:
                p_over = 1.0 - poisson.cdf(int(np.floor(line)), lam_h + lam_a)
                for side, p, won in [('over', p_over, total > line),
                                     ('under', 1 - p_over, total < line)]:
                    key = (mk, line, side)
                    b = acc.setdefault(key, {'n': 0, 'p_sum': 0.0, 'wins': 0})
                    b['n'] += 1; b['p_sum'] += p; b['wins'] += won
            # BTTS derivado de λ (independencia Poisson)
            p_btts = (1 - np.exp(-lam_h)) * (1 - np.exp(-lam_a))
            btts_acc['n'] += 1
            btts_acc['p_sum'] += p_btts
            btts_acc['wins'] += 1 if (yh >= 1 and ya >= 1) else 0
            n_test += 1

print(f'Partidos evaluados (test, walk-forward): {n_test}\n')
print(f'{"SUBMERCADO":38s} {"n":>5s} {"P pred":>7s} {"WR real":>8s} {"gap":>7s} {"cuota justa":>11s}  veredicto')
print('-' * 90)
for key in sorted(acc):
    mk, line, side = key
    b = acc[key]
    if b['n'] < 20:
        continue
    p = b['p_sum'] / b['n']
    wr = b['wins'] / b['n']
    gap = wr - p
    fair = 1.0 / p if p > 0 else 99
    name = {'goals': 'Goles', 'sot': 'Tiros a puerta', 'corners': 'Córners'}[mk]
    if abs(gap) <= 0.06 and p >= 0.35:
        v = '✅ puede reabrirse'
    elif gap <= -0.08:
        v = '🔴 sigue descalibrado'
    elif p < 0.35:
        v = '⚪ P baja (solo EV>0 con cuota alta)'
    else:
        v = '🟡 revisar'
    print(f'{name} {side} {line:>5.1f}'.ljust(38) + f'{b["n"]:5d} {p*100:6.1f}% {wr*100:7.1f}% {gap*100:+6.1f}pp {fair:10.2f}  {v}')

# BTTS
print('-' * 90)
p = btts_acc['p_sum'] / btts_acc['n']
wr = btts_acc['wins'] / btts_acc['n']
gap = wr - p
v = '✅ calibrado' if abs(gap) <= 0.06 else ('🔴 descalibrado' if gap <= -0.08 else '🟡 revisar')
print(f"{'BTTS Sí (derivado de λ motor)':38s} {btts_acc['n']:5d} {p*100:6.1f}% {wr*100:7.1f}% {gap*100:+6.1f}pp {1.0/p:10.2f}  {v}")
print(f"{'BTTS No (1-P)':38s} {btts_acc['n']:5d} {(1-p)*100:6.1f}% {(1-wr)*100:7.1f}% {-gap*100:+6.1f}pp {1.0/(1-p):10.2f}  {'✅ calibrado' if abs(gap)<=0.06 else ('🔴' if -gap<=-0.08 else '🟡 revisar')}")
