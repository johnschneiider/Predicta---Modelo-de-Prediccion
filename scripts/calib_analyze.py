"""
Análisis de calibración empírica por submercado (READ-ONLY).
Reconstruye (P_cruda -> resultado real) uniendo:
  - logs/auto_betting.log  (P cruda 'raw=' por coupon)
  - AutoBet                (submercado, cuota, linea, P calibrada)
  - HistorialApuesta       (resultado real WON/LOST por coupon_ref)

No escribe nada. Solo imprime la relación P_raw -> WR real por submercado
para decidir el método de calibración.
"""
import os, sys, re, glob
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
sys.path.insert(0, '/var/www/predicta.com.co')
import django; django.setup()

from collections import defaultdict
from auto_betting.models import AutoBet, HistorialApuesta

# 1) P cruda por coupon desde logs
raw_by_coupon = {}
pat = re.compile(r'raw=([\d.]+)%\).*coupon=(\d+)')
for fn in glob.glob('/var/www/predicta.com.co/logs/auto_betting.log*'):
    for line in open(fn, errors='ignore'):
        m = pat.search(line)
        if m:
            raw_by_coupon[int(m.group(2))] = float(m.group(1)) / 100.0

# 2) resultado real por coupon
hist = {h.coupon_ref: h.bet_status
        for h in HistorialApuesta.objects.filter(bet_status__in=['WON', 'LOST'])}

# 3) triple join
rows = []  # (submarket_key, p_raw, p_cal, cuota, win)
for a in AutoBet.objects.exclude(coupon_ref=None):
    st = hist.get(a.coupon_ref)
    if not st:
        continue
    p_raw = raw_by_coupon.get(a.coupon_ref)
    if p_raw is None:
        continue
    p_cal = (a.predicta_prob or 0)
    if p_cal > 1:
        p_cal /= 100.0
    lado = (a.seleccion or '').split(' ')[0]
    key = f'{a.mercado} · {lado}'
    rows.append((key, p_raw, p_cal, a.cuota or 0, 1 if st == 'WON' else 0))

print(f'Muestras con P_raw + resultado: {len(rows)}\n')

# Curva de fiabilidad por submercado: bins de P_raw
def bin_label(p):
    lo = int(p * 20) * 5  # bins de 5pp
    return f'{lo:2d}-{lo+5}%'

by_sub = defaultdict(list)
for key, p_raw, p_cal, cu, w in rows:
    by_sub[key].append((p_raw, p_cal, cu, w))

for key in sorted(by_sub):
    data = by_sub[key]
    n = len(data)
    wr = sum(d[3] for d in data) / n
    praw = sum(d[0] for d in data) / n
    pcal = sum(d[1] for d in data) / n
    print(f'=== {key}  (n={n}) ===')
    print(f'    P_raw media {praw*100:5.1f}%  |  P_cal media {pcal*100:5.1f}%  |  WR real {wr*100:5.1f}%')
    # bins
    bins = defaultdict(lambda: {'n': 0, 'w': 0, 'praw': 0.0})
    for p_raw, p_cal, cu, w in data:
        b = bins[bin_label(p_raw)]
        b['n'] += 1; b['w'] += w; b['praw'] += p_raw
    for bl in sorted(bins):
        b = bins[bl]
        print(f'      raw {bl}:  n={b["n"]:3d}  WR={b["w"]/b["n"]*100:5.1f}%')
    print()
