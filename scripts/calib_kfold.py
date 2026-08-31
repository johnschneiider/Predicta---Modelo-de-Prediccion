"""
K-fold CV (READ-ONLY) para estimar de forma robusta si la calibración empírica
por submercado supera a la heurística actual, promediando sobre folds para
neutralizar la suerte de una sola ventana.
"""
import os, sys, re, glob, random
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
sys.path.insert(0, '/var/www/predicta.com.co')
import django; django.setup()

from collections import defaultdict
from auto_betting.models import AutoBet, HistorialApuesta

K = 20; PRIOR = 0.50; STAKE = 500.0; FOLDS = 5; SEED = 42

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
    if not st: continue
    p_raw = raw_by_coupon.get(a.coupon_ref)
    if p_raw is None: continue
    lado = (a.seleccion or '').split(' ')[0]
    rows.append((f'{a.mercado} · {lado}', p_raw, a.cuota or 0, 1 if st == 'WON' else 0))

def heur(p, cap=0.58):
    pc = 0.5 + (p - 0.5) * (0.95 if p <= 0.60 else 0.50)
    return max(0.05, min(0.95, min(cap, pc)))

random.seed(SEED)
idx = list(range(len(rows))); random.shuffle(idx)
folds = [idx[i::FOLDS] for i in range(FOLDS)]

accA = {'n':0,'w':0,'pnl':0.0}; accB = {'n':0,'w':0,'pnl':0.0}
for f in range(FOLDS):
    test_ids = set(folds[f])
    train = [rows[i] for i in range(len(rows)) if i not in test_ids]
    test  = [rows[i] for i in folds[f]]
    st_tr = defaultdict(lambda: {'n':0,'w':0})
    for key,p,cu,w in train:
        s=st_tr[key]; s['n']+=1; s['w']+=w
    emp = {k:(s['w']+K*PRIOR)/(s['n']+K) for k,s in st_tr.items()}
    for key,p_raw,cu,w in test:
        # A
        if heur(p_raw)*cu-1.0 > 0.05:
            pnl=(STAKE*cu-STAKE) if w else -STAKE
            accA['n']+=1; accA['w']+=w; accA['pnl']+=pnl
        # B
        pc=emp.get(key, heur(p_raw))
        if pc*cu-1.0 > 0.05:
            pnl=(STAKE*cu-STAKE) if w else -STAKE
            accB['n']+=1; accB['w']+=w; accB['pnl']+=pnl

for lbl,acc in [('A) heurística actual',accA),('B) empírica bayesiana',accB)]:
    wr=acc['w']/acc['n']*100 if acc['n'] else 0
    roi=acc['pnl']/(acc['n']*STAKE)*100 if acc['n'] else 0
    print(f"{lbl:35s} n={acc['n']:4d}  WR={wr:5.1f}%  P&L={acc['pnl']:9,.0f}  ROI={roi:+5.1f}%")
