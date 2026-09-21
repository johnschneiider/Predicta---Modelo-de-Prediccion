#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Auditoría READ-ONLY de mercados — 2026-09-13. No modifica datos.
Uso: cd /var/www/predicta.com.co && venv/bin/python scripts/audit_mercados/audit_mercados_20260913.py
"""
import os, sys, datetime as dt, statistics as st
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django
django.setup()
import logging
logging.disable(logging.CRITICAL)

from django.utils import timezone
from auto_betting.models import HistorialApuesta
from auto_betting.strategy import submarket_clv_health

now = timezone.now()
print('AUDITORÍA MERCADOS · generado', now.isoformat())
print('=' * 100)

def cop(x):
    # unidad de display: raw/1000 = COP
    return x / 1000.0

def stats(rows):
    rows = list(rows)
    n = len(rows)
    if n == 0:
        return None
    won = sum(1 for r in rows if r.bet_status == 'WON')
    stake = sum(r.stake for r in rows)
    payout = sum((r.payout or 0) for r in rows)
    net = payout - stake
    roi = (net / stake * 100) if stake else 0.0
    wr = won / n * 100
    odds = [r.bet_odds for r in rows if r.bet_odds]
    avg_odds = sum(odds) / len(odds) if odds else None
    be = (sum(1.0 / o for o in odds) / len(odds) * 100) if odds else None
    clvs = [r.clv for r in rows if r.clv is not None]
    avg_clv = sum(clvs) / len(clvs) if clvs else None
    pnls = [((r.payout or 0) - r.stake) for r in rows]
    mean = sum(pnls) / n
    sd = st.stdev(pnls) if n > 1 else 0.0
    z = (mean / (sd / (n ** 0.5))) if sd > 0 else None
    events = len(set((r.event_id, r.mercado, r.seleccion, r.linea) for r in rows))
    return dict(n=n, won=won, wr=wr, stake=stake, net=net, roi=roi, avg_odds=avg_odds,
                be=be, avg_clv=avg_clv, clv_n=len(clvs), z=z, events=events)

BASE = HistorialApuesta.objects.filter(is_system=True).exclude(bet_status__in=['OPEN', 'VOID'])

def show(tag, s):
    if not s:
        print(f'  {tag}: sin datos')
        return
    z = f'{s["z"]:+.2f}' if s['z'] is not None else 'n/a'
    oc = f'{s["avg_odds"]:.2f}' if s['avg_odds'] else 'n/a'
    be = f'{s["be"]:.1f}%' if s['be'] else 'n/a'
    clv = f'{s["avg_clv"]:+.2f} (n={s["clv_n"]})' if s['avg_clv'] is not None else 'n/a'
    print(f'  {tag}: n={s["n"]} (eventos={s["events"]}) WR={s["wr"]:.1f}% stake={cop(s["stake"]):,.0f} net={cop(s["net"]):+,.0f} COP ROI={s["roi"]:+.1f}% avgOdds={oc} BE={be} CLV={clv} z={z}')

MARKETS = [
    ('Total de goles', 'GOLES'),
    ('Ambos Equipos Marcarán', 'BTTS'),
    ('Total de Tiros de Esquina', 'CÓRNERS'),
    ('Total de tiros a puerta (Resuelta usando Opta Data)', 'SOT'),
    ('Resultado Final', '1X2'),
]

print()
print('### 1. SISTEMA (is_system=True) POR MERCADO — histórico completo ###')
for mk, tag in MARKETS:
    s = stats(BASE.filter(mercado__icontains=mk))
    show(tag, s)

print()
print('### 2. VENTANAS 30d / 7d — CÓRNERS, BTTS, GOLES ###')
for mk, tag in MARKETS[:3]:
    for days, dtag in [(30, '30d'), (7, '7d')]:
        cutoff = now - dt.timedelta(days=days)
        s = stats(BASE.filter(mercado__icontains=mk, placed_date__gte=cutoff))
        show(f'{tag} {dtag}', s)

print()
print('### 3. CÓRNERS por lado+línea ###')
for side, slabel in [('Menos', 'UNDER'), ('Más', 'OVER')]:
    for linev in [7.5, 8.5, 9.5, 10.5, 11.5, 12.5, 13.5]:
        sel = f'{side} de {linev}'
        s = stats(BASE.filter(mercado__icontains='Tiros de Esquina', seleccion=sel))
        if s:
            show(f'{slabel} {linev}', s)

print()
print('### 4. BTTS por selección ###')
for sel in ['Sí', 'No']:
    s = stats(BASE.filter(mercado__icontains='Ambos Equipos', seleccion=sel))
    show(sel, s)

print()
print('### 5. GOLES por línea ###')
for sel in ['Más de 1.5', 'Más de 2.5', 'Más de 3.5', 'Menos de 2.5', 'Menos de 3.5']:
    s = stats(BASE.filter(mercado__icontains='Total de goles', seleccion=sel))
    if s:
        show(sel, s)

print()
print('### 6. CLV HEALTH (función viva del motor) ###')
for label in ['Tiros de Esquina', 'Ambos Equipos Marcarán', 'Total de goles']:
    ok, avg, n = submarket_clv_health(label)
    print(f'  {label}: ok={ok} avg_clv={avg} n={n}')

print()
print('### 7. POR USUARIO (sistema, settled) ###')
uids = sorted(set(BASE.values_list('usuario_id', flat=True)))
for uid in uids:
    s = stats(BASE.filter(usuario_id=uid))
    show(f'user {uid}', s)

print()
print('### 8. RECONCILIACIÓN: liquidaciones últimas 30h vs antes ###')
cut = now - dt.timedelta(hours=30)
newrows = list(BASE.filter(actualizado__gte=cut))
old = list(BASE.filter(actualizado__lt=cut))
for tag, rows in [('ANTES (30h+)', old), ('ÚLTIMAS 30h', newrows)]:
    for mk in ['Tiros de Esquina', 'Ambos Equipos', 'Total de goles']:
        s = stats([r for r in rows if mk.lower() in (r.mercado or '').lower()])
        if s:
            show(f'{tag} {mk[:12]}', s)
print()
print('  -- filas liquidadas en últimas 30h (todas) --')
net30 = 0
for r in sorted(newrows, key=lambda x: x.actualizado):
    net30 += (r.payout or 0) - r.stake
    print(f'  [{r.actualizado.strftime("%m-%d %H:%M")}] {r.mercado[:28]:28s} {r.seleccion[:12]:12s} {r.bet_status:4s} {r.home_team[:18]:18s} vs {r.away_team[:18]:18s} st={cop(r.stake):>7,.0f} net={cop((r.payout or 0)-r.stake):>+9,.0f} clv={r.clv}')
print(f'  >> NETO TOTAL últimas 30h (sistema): {cop(net30):+,.0f} COP · filas={len(newrows)}')

print()
print('### 9. ABIERTAS (exposición actual) ###')
tot_exp = 0
for r in HistorialApuesta.objects.filter(bet_status='OPEN'):
    tot_exp += r.stake
    print(f'  sys={r.is_system} {r.mercado[:40]:40s} {r.seleccion[:12]:12s} {r.home_team[:20]:20s} vs {r.away_team[:20]:20s} stake={cop(r.stake):,.0f} inicio={r.event_start_date}')
print(f'  >> exposición abierta total: {cop(tot_exp):,.0f} COP')

print()
print('### 10. CHEQUEOS DE ANOMALÍA ###')
print('  WON con payout 0:', HistorialApuesta.objects.filter(bet_status='WON', payout=0).count())
print('  LOST con payout >0:', HistorialApuesta.objects.filter(bet_status='LOST', payout__gt=0).count())
print('  stake<=0:', HistorialApuesta.objects.filter(stake__lte=0).count())
print('  sin bet_odds (settled sys):', BASE.filter(bet_odds__isnull=True).count(), 'de', BASE.count())
print('  sin clv (settled sys):', BASE.filter(clv__isnull=True).count(), 'de', BASE.count())
