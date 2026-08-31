"""
Validación OUT-OF-SAMPLE (temporal) de la calibración empírica (READ-ONLY).
Calibra la base rate por submercado con las apuestas ANTERIORES a un punto de
corte y evalúa sobre las POSTERIORES. Compara vs heurística actual.
"""
import os, sys, re, glob
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
sys.path.insert(0, '/var/www/predicta.com.co')
import django; django.setup()

from collections import defaultdict
from auto_betting.models import AutoBet, HistorialApuesta

K = 20; PRIOR = 0.50; STAKE = 500.0

raw_by_coupon = {}
pat = re.compile(r'raw=([\d.]+)%\).*coupon=(\d+)')
for fn in glob.glob('/var/www/predicta.com.co/logs/auto_betting.log*'):
    for line in open(fn, errors='ignore'):
        m = pat.search(line)
        if m:
            raw_by_coupon[int(m.group(2))] = float(m.group(1)) / 100.0

hist = {h.coupon_ref: h.bet_status
        for h in HistorialApuesta.objects.filter(bet_status__in=['WON', 'LOST'])}

rows = []  # (fecha, key, p_raw, cuota, win)
for a in AutoBet.objects.exclude(coupon_ref=None):
    st = hist.get(a.coupon_ref)
    if not st:
        continue
    p_raw = raw_by_coupon.get(a.coupon_ref)
    if p_raw is None:
        continue
    lado = (a.seleccion or '').split(' ')[0]
    key = f'{a.mercado} · {lado}'
    rows.append((a.creado, key, p_raw, a.cuota or 0, 1 if st == 'WON' else 0))

rows.sort(key=lambda r: r[0])
cut = int(len(rows) * 0.5)
train, test = rows[:cut], rows[cut:]
print(f'train={len(train)}  test={len(test)}  corte={train[-1][0].date()}\n')

# base rate por submercado con TRAIN
st_tr = defaultdict(lambda: {'n': 0, 'w': 0})
for _, key, p, cu, w in train:
    s = st_tr[key]; s['n'] += 1; s['w'] += w
emp = {k: (s['w'] + K * PRIOR) / (s['n'] + K) for k, s in st_tr.items()}


def heur(p, cap=0.58):
    pc = 0.5 + (p - 0.5) * (0.95 if p <= 0.60 else 0.50)
    return max(0.05, min(0.95, min(cap, pc)))


def ev_eval(label, calib):
    tot = {'n': 0, 'w': 0, 'pnl': 0.0}
    for _, key, p_raw, cu, w in test:
        p_cal = calib(key, p_raw)
        if p_cal * cu - 1.0 <= 0.05:
            continue
        pnl = (STAKE * cu - STAKE) if w else -STAKE
        tot['n'] += 1; tot['w'] += w; tot['pnl'] += pnl
    wr = tot['w'] / tot['n'] * 100 if tot['n'] else 0
    print(f'{label:45s} n={tot["n"]:4d}  WR={wr:5.1f}%  P&L={tot["pnl"]:9,.0f} COP')


print('EVALUACIÓN SOBRE TEST (out-of-sample):')
ev_eval('A) heurística actual', lambda k, p: heur(p))
ev_eval('B) empírica bayesiana (base rate train)', lambda k, p: emp.get(k, heur(p)))
