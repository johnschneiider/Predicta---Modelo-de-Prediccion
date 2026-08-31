"""
Backtest de calibración empírica bayesiana por submercado (READ-ONLY).

Compara 3 esquemas sobre las apuestas históricas reales (P_raw + resultado):
  A) actual (heurística global: shrinkage 0.95/0.50 + cap 0.58)
  B) empírica bayesiana por submercado (WR histórica encogida hacia 0.5)

Para cada esquema calcula, por submercado, cuántas apuestas PASARÍAN el filtro
EV>0 (aprox, cuota real de la apuesta) con la P calibrada, y el P&L real de ese
subconjunto (stake fijo 500 COP, payout = stake*cuota si WON).

No escribe nada. Solo evalúa el impacto.
"""
import os, sys, re, glob
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
sys.path.insert(0, '/var/www/predicta.com.co')
import django; django.setup()

from collections import defaultdict
from auto_betting.models import AutoBet, HistorialApuesta

K = 20          # fuerza de shrinkage bayesiano hacia el prior
PRIOR = 0.50    # prior neutro
STAKE = 500.0

# ---- reconstruir dataset (submarket, p_raw, cuota, win) ----
raw_by_coupon = {}
pat = re.compile(r'raw=([\d.]+)%\).*coupon=(\d+)')
for fn in glob.glob('/var/www/predicta.com.co/logs/auto_betting.log*'):
    for line in open(fn, errors='ignore'):
        m = pat.search(line)
        if m:
            raw_by_coupon[int(m.group(2))] = float(m.group(1)) / 100.0

hist = {h.coupon_ref: h.bet_status
        for h in HistorialApuesta.objects.filter(bet_status__in=['WON', 'LOST'])}

rows = []
for a in AutoBet.objects.exclude(coupon_ref=None):
    st = hist.get(a.coupon_ref)
    if not st:
        continue
    p_raw = raw_by_coupon.get(a.coupon_ref)
    if p_raw is None:
        continue
    lado = (a.seleccion or '').split(' ')[0]
    key = f'{a.mercado} · {lado}'
    rows.append((key, p_raw, a.cuota or 0, 1 if st == 'WON' else 0))

# ---- calibración empírica bayesiana por submercado ----
sub_stats = defaultdict(lambda: {'n': 0, 'w': 0})
for key, p_raw, cu, w in rows:
    s = sub_stats[key]; s['n'] += 1; s['w'] += w

empirical = {}
for key, s in sub_stats.items():
    empirical[key] = (s['w'] + K * PRIOR) / (s['n'] + K)


def calibrate_heuristic(p, cap=0.58):
    if p <= 0.60:
        pc = 0.5 + (p - 0.5) * 0.95
    else:
        pc = min(cap, 0.5 + (p - 0.5) * 0.50)
    return max(0.05, min(0.95, min(cap, pc)))


print(f'K(shrinkage)={K}  prior={PRIOR}  stake={STAKE:.0f} COP\n')
print('CALIBRACIÓN EMPÍRICA BAYESIANA POR SUBMERCADO:')
print(f"{'submercado':40s} {'n':>4s} {'WR_real':>7s} {'p_emp':>6s}")
for key in sorted(empirical):
    s = sub_stats[key]
    print(f'{key:40s} {s["n"]:4d} {s["w"]/s["n"]*100:6.1f}% {empirical[key]*100:5.1f}%')

# ---- evaluar filtro EV>5% (tier cuota baja) con cada esquema ----
def evaluate(label, calib_fn):
    kept = defaultdict(lambda: {'n': 0, 'w': 0, 'pnl': 0.0})
    tot = {'n': 0, 'w': 0, 'pnl': 0.0}
    for key, p_raw, cu, w in rows:
        p_cal = calib_fn(key, p_raw)
        ev = p_cal * cu - 1.0
        if ev <= 0.05:      # mismo umbral base que el tier de cuota baja
            continue
        pnl = (STAKE * cu - STAKE) if w else -STAKE
        k = kept[key]; k['n'] += 1; k['w'] += w; k['pnl'] += pnl
        tot['n'] += 1; tot['w'] += w; tot['pnl'] += pnl
    print(f'\n===== {label} =====')
    print(f"{'submercado':40s} {'n':>4s} {'WR':>6s} {'P&L COP':>10s}")
    for key in sorted(kept):
        k = kept[key]
        print(f'{key:40s} {k["n"]:4d} {k["w"]/k["n"]*100:5.1f}% {k["pnl"]:10,.0f}')
    if tot['n']:
        print(f'{"TOTAL":40s} {tot["n"]:4d} {tot["w"]/tot["n"]*100:5.1f}% {tot["pnl"]:10,.0f}')

evaluate('A) HEURÍSTICA ACTUAL (cap 0.58)', lambda key, p: calibrate_heuristic(p))
evaluate('B) EMPÍRICA BAYESIANA POR SUBMERCADO', lambda key, p: empirical.get(key, calibrate_heuristic(p)))
