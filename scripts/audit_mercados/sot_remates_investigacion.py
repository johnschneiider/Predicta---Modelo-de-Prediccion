# -*- coding: utf-8 -*-
"""
Investigación remates totales + remates a puerta (SOT) — read-only.
1) Mismatch audit: valor SOT en BD (API-Football) vs liquidación Kambi/Opta.
2) Cobertura de datos API por liga/modelo.
3) Calibración: backtest del pipeline actual sobre partidos recientes.
Salida a scripts/audit_mercados/inv_out_20260913.txt
"""
import os, sys, django, json, math
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
django.setup()

from collections import defaultdict
from datetime import timedelta
from django.utils import timezone
from django.db.models import Avg, Count, Q
from football_data.models import Match
from auto_betting.models import HistorialApuesta, AutoBet

OUT = open('/var/www/predicta.com.co/scripts/audit_mercados/inv_out_20260913.txt', 'w')

def w(*a):
    s = ' '.join(str(x) for x in a)
    print(s)
    OUT.write(s + '\n')

w('INVESTIGACIÓN REMATES/SOT · generado', timezone.now().isoformat())
w('='*100)

# ────────────────────────────────────────────────────────────
# PARTE 1 — Mismatch: BD (API-Football) vs liquidación Kambi/Opta
# ────────────────────────────────────────────────────────────
w()
w('### PARTE 1: MISMATCH BD(API-Football) vs LIQUIDACIÓN KAMBI/OPTA — SOT ###')
w()

qs = HistorialApuesta.objects.filter(mercado__startswith='Total de tiros a puerta').select_related('usuario')
w(f'Total filas SOT en historial: {qs.count()} (sistema={qs.filter(is_system=True).count()}, manual={qs.filter(is_system=False).count()})')
w()

def find_db_match(home, away, placed):
    """Busca el partido en Match (legacy) por nombres + fecha aproximada."""
    d0 = placed.date() if placed else None
    qs2 = Match.objects.filter(home_team__icontains=home.split()[0][:6], away_team__icontains=away.split()[0][:6])
    if d0:
        qs2 = qs2.filter(date__gte=d0 - timedelta(days=7), date__lte=d0 + timedelta(days=7))
    m = qs2.order_by('date').first()
    if m: return m
    # fallback: contains both tokens
    qs2 = Match.objects.filter(home_team__icontains=home[:6], away_team__icontains=away[:6])
    return qs2.order_by('date').first()

mism = []
match_ok = 0; match_nodata = 0; match_nomatch = 0
n_won = n_lost = 0
for h in qs.order_by('placed_date'):
    if not h.seleccion or h.linea is None: continue
    sel = h.seleccion.lower()
    line = float(h.linea)
    is_under = 'menos' in sel
    m = find_db_match(h.home_team or '', h.away_team or '', h.placed_date)
    if not m:
        match_nomatch += 1
        continue
    if m.hst is None or m.ast is None:
        match_nodata += 1
        continue
    sot_db = m.hst + m.ast
    db_would = (sot_db <= line) if is_under else (sot_db > line)
    kambi_won = (h.bet_status == 'WON')
    kambi_lost = (h.bet_status == 'LOST')
    if h.bet_status not in ('WON', 'LOST'):
        continue
    if kambi_won: n_won += 1
    else: n_lost += 1
    if db_would != kambi_won:
        mism.append((h, m, sot_db, db_would, kambi_won, 'SISTEMA' if h.is_system else 'manual'))
    match_ok += 1

w(f'Partidos encontrados en BD con dato SOT: {match_ok} | sin match: {match_nomatch} | sin dato SOT: {match_nodata}')
w(f'WON={n_won} LOST={n_lost}  ← liquidaciones Kambi')
w(f'MISMATCHES (BD dice una cosa, Kambi liquidó otra): {len(mism)}')
w()
if mism:
    w(f'{"fecha":10s} {"liga":24s} {"partido":40s} {"sel":14s} {"Kambi":5s} {"SOT_BD":6s} {"Δ":4s} sistema')
    for h, m, sot_db, db_would, kambi_won, tag in mism[:80]:
        w(f'{str(h.placed_date.date()):10s} {(h.liga or "")[:24]:24s} {(h.home_team or "")[:18]+" v "+ (h.away_team or "")[:18]:40s} {h.seleccion:14s} {"WON" if kambi_won else "LOST":5s} {sot_db:6d} ')
    w()
    # resumen por dirección
    db_sez = sum(1 for _,_,_,_,_,_ in mism)
w()
w('Resumen mismatch por resultado Kambi:')
dir_counts = defaultdict(int)
for h, m, sot_db, db_would, kambi_won, tag in mism:
    is_under = 'menos' in h.seleccion.lower()
    kambi_over = (not is_under and kambi_won) or (is_under and not kambi_won)
    db_over = (sot_db > h.linea)
    dir_counts[(f'BD_dice={"OVER" if db_over else "UNDER"}', f'Kambi={"OVER" if kambi_over else "UNDER"}')] += 1
for k, v in sorted(dir_counts.items()):
    w(f'  {k[0]}  vs {k[1]}: {v}')

OUT.flush()

# ────────────────────────────────────────────────────────────
# PARTE 2 — Cobertura de datos API-Football para remates
# ────────────────────────────────────────────────────────────
w()
w('='*100)
w('### PARTE 2: COBERTURA DE DATOS API-FOOTBALL (BD) PARA REMATES ###')
w()
from football_api.models import TeamFixtureStat, ApiFixture, ApiLeague

cutoff = timezone.now() - timedelta(days=730)
tot = TeamFixtureStat.objects.filter(fixture__date__gte=cutoff, total_shots__isnull=False).count()
sot = TeamFixtureStat.objects.filter(fixture__date__gte=cutoff, shots_on_goal__isnull=False).count()
w(f'Filas equipo-partido con remates (730d): total_shots={tot} shots_on_goal={sot}')

# por liga activa: partidos con stats y si mercado Kambi existe (inferido de apuestas + manual)
leagues_with_market = {
 'Serie A': 'Serie A (Italia)', 'La Liga': 'La Liga', 'Ligue 1': 'Ligue 1',
 'Brasileirao Serie A': 'Brasileirao A', 'Brasileirao Serie B': 'Brasileirao B',
 'Liga Profesional Argentina': 'Argentina', 'Liga MX': 'Liga MX', 'MLS': 'MLS',
 'Superligaen': 'Dinamarca',
}
w()
w('Cobertura de remates por liga relevante (fixtures con stats, 730d):')
for lg in ApiLeague.objects.filter(active=True).order_by('-priority','name'):
    n = ApiFixture.objects.filter(league=lg, stats__isnull=False, date__gte=cutoff).distinct().count()
    if n == 0: continue
    tag = ''
    name = lg.name
    for k, v in leagues_with_market.items():
        if k.lower() in name.lower(): tag = f'  ← mercado Kambi: {v}'
    w(f'  {name:42s} ({lg.country[:14]:14s}) n={n:5d}{tag}')

OUT.flush()

# ────────────────────────────────────────────────────────────
# PARTE 3 — Overdispersion: Poisson vs NegBin para remates totales
# ────────────────────────────────────────────────────────────
w()
w('='*100)
w('### PARTE 3: MODELO ESTADÍSTICO — POISSON vs NEGBIN ###')
w()
import numpy as np
for label, fld in [('REMATES TOTALES (hs+as)', 'total_shots'), ('SOT (hst+ast)', 'shots_on_goal')]:
    vals = []
    for s in TeamFixtureStat.objects.filter(fixture__date__gte=cutoff, **{fld: None} if False else {}).filter(**{}):
        pass
    # agrupar por fixture: sumar home+away
    from collections import defaultdict as dd
    per = dd(int)
    for s in TeamFixtureStat.objects.filter(fixture__date__gte=cutoff).only('fixture_id', fld).iterator():
        v = getattr(s, fld)
        if v is not None:
            per[s.fixture_id] += v
    vals = np.array([v for v in per.values()])
    mu, var = vals.mean(), vals.var()
    phi = mu*mu/(var-mu)
    w(f'{label}: n={len(vals)} media={mu:.2f} var={var:.2f} var/media={var/mu:.3f} -> phi NegBin={phi:.1f}')
    # comparación P(over) por línea real
    from scipy.stats import poisson as P, nbinom as NB
    lines = [6.5,7.5,8.5,9.5,10.5,11.5,12.5] if 'SOT' in label else [21.5,22.5,23.5,24.5,25.5,26.5,27.5,28.5,29.5]
    w('  línea | real P(over) | Poisson | NegBin')
    for line in lines:
        k = int(line)
        real_p = (vals > line).mean()
        p_po = 1 - P.cdf(k, mu)
        n_ = max(1.0, phi); pg = n_/(n_+mu)
        p_nb = 1 - NB.cdf(k, n_, pg)
        w(f'   {line:5.1f} | {real_p:.4f} | {p_po:.4f} | {p_nb:.4f}')

OUT.flush()

# ────────────────────────────────────────────────────────────
# PARTE 4 — Calibración del pipeline SOT actual (backtest reciente)
# ────────────────────────────────────────────────────────────
w()
w('='*100)
w('### PARTE 4: CALIBRACIÓN DEL PIPELINE SOT ACTUAL (backtest ~120 partidos recientes) ###')
w()
from ai_predictions.web_pipeline import build_web_predictions, get_official_prediction

# replicar shrinkage del strategy
def league_mean_sot(league):
    cut = timezone.now().date() - timedelta(days=730)
    agg = Match.objects.filter(league=league, date__gte=cut, hst__isnull=False, ast__isnull=False).aggregate(
        avg=Avg('hst') )  # noqa
    # usar total (hst+ast)
    qs2 = Match.objects.filter(league=league, date__gte=cut, hst__isnull=False, ast__isnull=False).only('hst','ast')
    tot = 0; n = 0
    for m in qs2.iterator():
        tot += m.hst + m.ast; n += 1
    return (tot/n) if n else 8.608

SOT_SHRINK = 0.5
sot_errors = []; shots_errors = []
samples = []
cut = timezone.now() - timedelta(days=45)
ms = list(Match.objects.filter(date__gte=cut, hs__isnull=False, as_field__isnull=False, hst__isnull=False, ast__isnull=False).order_by('-date')[:120])
lm_cache = {}
for m in ms:
    key = m.league_id
    if key not in lm_cache:
        lm_cache[key] = league_mean_sot(m.league)
    try:
        preds = build_web_predictions(m.home_team, m.away_team, m.league, prediction_types=['shots_total','shots_on_target_total'])
        off_sot = get_official_prediction(preds, 'shots_on_target_total')
        off_shots = get_official_prediction(preds, 'shots_total')
        sot_real = m.hst + m.ast
        shots_real = m.hs + m.as_field
        if off_sot:
            lam_raw = off_sot['prediction']
            lm = lm_cache[key]
            lam = (1-SOT_SHRINK)*lam_raw + SOT_SHRINK*lm
            sot_errors.append((lam_raw, lam, lm, sot_real))
        if off_shots:
            shots_errors.append((off_shots['prediction'], shots_real))
    except Exception as e:
        pass

if sot_errors:
    raw = np.array([e[0]-e[3] for e in sot_errors])
    shr = np.array([e[1]-e[3] for e in sot_errors])
    w(f'SOT n={len(raw)}')
    w(f'  λ crudo:  bias={raw.mean():+.2f} MAE={np.abs(raw).mean():.2f} RMSE={np.sqrt((raw**2).mean()):.2f}')
    w(f'  λ shrunk: bias={shr.mean():+.2f} MAE={np.abs(shr).mean():.2f} RMSE={np.sqrt((shr**2).mean()):.2f}')
    # dirección: sobreestima/Subestima por deciles
    w('  Sesgo por magnitud de λ (crudo):')
    for lo, hi in [(5,7),(7,8),(8,9),(9,10),(10,12),(12,16)]:
        sel = [(l, r) for (_, l, _, r) in sot_errors if lo <= l < hi]
        if sel:
            b = np.mean([l - r for l, r in sel])
            w(f'    λ∈[{lo},{hi}): n={len(sel)} bias={b:+.2f}')

if shots_errors:
    arr = np.array([e[0]-e[1] for e in shots_errors])
    w(f'REMATES TOTALES n={len(arr)}: bias={arr.mean():+.2f} MAE={np.abs(arr).mean():.2f} RMSE={np.sqrt((arr**2).mean()):.2f}')

OUT.flush()
OUT.close()
print('OUTPUT -> /var/www/predicta.com.co/scripts/audit_mercados/inv_out_20260913.txt')
