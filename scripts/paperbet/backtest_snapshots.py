# -*- coding: utf-8 -*-
"""BACKTEST motores paper contra cuotas Kambi históricas (OddsSnapshot, 18-ago → 15-sep).
Features leak-free desde features_*.csv (cada fila = info anterior al partido). Resultados reales desde Match.
Simula las mismas compuertas de run_paper_bets con stake plano 10k COP. Salida: WR/ROI/net por motor + CLV.
"""
import os, sys, json, pickle, difflib, unicodedata
from collections import defaultdict
import numpy as np, pandas as pd
from scipy.stats import poisson, nbinom
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django; django.setup()
from datetime import date as ddate, timedelta
from auto_betting.models import OddsSnapshot, HistorialApuesta
from value_betting.models import KambiMatch
from football_data.models import Match
from football_api.models import ApiLeague, ApiFixture, TeamFixtureStat

OUT = 'scripts/paperbet'
eng = pickle.load(open(OUT + '/engines.pkl', 'rb'))
FEATS, CFEATS = eng['FEATS'], eng['CFEATS']
PHI_C, PHI_S = eng['PHI_CORNERS'], eng['PHI_SOT']

def norm(s):
    s = unicodedata.normalize('NFKD', str(s))
    return ''.join(c for c in s.lower() if c.isalnum())

# ---- features leak-free ----
btt_df = pd.read_csv('scripts/btts_v2/features_btts.csv', parse_dates=['date'])
btt_df['dkey'] = btt_df['date'].dt.strftime('%Y-%m-%d')
btt_idx = {(r.dkey, r.lid, r.home, r.away): r for r in btt_df.itertuples()}
del btt_df
cor_df = pd.read_csv(OUT + '/features_corners.csv', parse_dates=['date'])
cor_df['dkey'] = cor_df['date'].dt.strftime('%Y-%m-%d')
cor_idx = {(r.dkey, r.lid, r.htid, r.atid): r for r in cor_df.itertuples()}
del cor_df

# ---- eventos → (date, home, away, liga predicta, api lid, htid, atid) ----
snap_events = list(OddsSnapshot.objects.values_list('event_id', flat=True).order_by().distinct())
hist_map = {}
for eid, h, a, lg, st in HistorialApuesta.objects.filter(event_id__in=snap_events).values_list('event_id','home_team','away_team','liga','event_start_date').distinct():
    hist_map.setdefault(eid, (h, a, st.date()))
km_map = {}
for k in KambiMatch.objects.filter(kambi_event_id__in=snap_events).select_related('predicta_league'):
    h = k.mapped_home_team or k.home_team
    a = k.mapped_away_team or k.away_team
    if h and a and k.start_time:
        km_map[k.kambi_event_id] = (h, a, k.start_time.date(), k.predicta_league_id)

# índice Match por (date, home, away) + fuzzy
match_rows = {(m['date'].isoformat(), m['home_team'], m['away_team']): m for m in
              Match.objects.filter(date__gte=ddate(2026, 8, 17)).values('date','home_team','away_team','fthg','ftag','corners_total','league_id')}
match_names = defaultdict(list)
for k_ in match_rows:
    match_names[k_[0]].append(k_[1])
    match_names[k_[0]].append(k_[2])

api_lid_by_pred = dict(ApiLeague.objects.filter(predicta_league_id__isnull=False).values_list('predicta_league_id', 'id'))
api_fix_cache = {}
def find_api_fixture(day, api_lid, home, away):
    key = (day, api_lid, home, away)
    if key in api_fix_cache: return api_fix_cache[key]
    out = None
    qs = ApiFixture.objects.filter(date=day, league_id=api_lid)
    nh, na = norm(home), norm(away)
    best, bs = None, 0.0
    for f in qs.select_related('home_team', 'away_team'):
        s1 = difflib.SequenceMatcher(None, nh, norm(f.home_team.name)).ratio()
        s2 = difflib.SequenceMatcher(None, na, norm(f.away_team.name)).ratio()
        if s1 + s2 > bs:
            bs, best = s1 + s2, f
    if best is not None and bs >= 1.4:
        out = (best.home_team_id, best.away_team_id, best.id)
    api_fix_cache[key] = out
    return out

snaps = OddsSnapshot.objects.all().order_by('captured_at')
by_out = defaultdict(list)
for s in snaps:
    by_out[(s.event_id, s.market, s.seleccion, s.linea)].append(s)

def entry_odds(snaps_):
    return min(snaps_, key=lambda s: s.captured_at).odds_decimal

def closing_odds(snaps_):
    return max(snaps_, key=lambda s: s.captured_at).odds_decimal

def edge_pair(by_out, eid, market, linea, side, p):
    """edge del modelo vs fair devigged; si falta la otra pata, fallback EV nominal."""
    pair = [(sl, entry_odds(s3)) for (e3, mk, sl, ln), s3 in by_out.items()
            if e3 == eid and mk == market and ln == linea]
    inv = {sl: 1.0 / o for sl, o in pair if o}
    if len(inv) == 2:
        s = sum(inv.values())
        return p - inv.get(side, 0) / s
    # fallback: EV nominal
    for sl, o in pair:
        if sl == side:
            return p * o - 1
    return None

# ---- simulación ----
results = defaultdict(lambda: {'n': 0, 'won': 0, 'stake': 0, 'payout': 0, 'clv': [], 'cuotas': []})
events_ok = 0
for eid in snap_events:
    src = hist_map.get(eid) or km_map.get(eid)
    if not src: continue
    if len(src) == 4:
        h, a, day, pred_lid = src
    else:
        h, a, day = src; pred_lid = None
    dkey = day.isoformat()
    # match real
    m = match_rows.get((dkey, h, a))
    if m is None:
        # fuzzy dentro del día
        cands = [k for k in match_rows if k[0] == dkey]
        nh, na = norm(h), norm(a)
        best, bs = None, 0.0
        for k in cands:
            sc = difflib.SequenceMatcher(None, nh, norm(k[1])).ratio() + difflib.SequenceMatcher(None, na, norm(k[2])).ratio()
            if sc > bs: bs, best = sc, k
        if bs < 1.5: continue
        m = match_rows[best]
    if m['fthg'] is None or m['ftag'] is None: continue
    lid = m['league_id']
    gh, ga = m['fthg'], m['ftag']
    tot = gh + ga
    bts = 1 if (gh > 0 and ga > 0) else 0
    res = 0 if gh > ga else (1 if gh == ga else 2)
    feat = btt_idx.get((dkey, lid, h, a))
    if feat is None: feat = btt_idx.get((dkey, lid, m['home_team'], m['away_team']))
    if feat is None: continue
    events_ok += 1
    X = pd.DataFrame([[getattr(feat, k_) for k_ in FEATS]], columns=FEATS).astype(float)
    # motores goals-based
    art = pickle.load(open('scripts/btts_v2/gbm_btts.pkl', 'rb'))
    p_btts = float(art['iso'].predict(art['model'].predict_proba(X)[:, 1])[0])
    lam_g = float(eng['goles'].predict(X)[0])
    p_x = eng['x12'].predict_proba(X)[0]
    p_home = float(eng['x12_iso_h'].predict([p_x[0]])[0])
    # corners/sot si hay features por ids
    lam_c = lam_s = None
    api_lid = api_lid_by_pred.get(lid)
    if api_lid:
        fx = find_api_fixture(day, api_lid, m['home_team'], m['away_team'])
        if fx:
            htid, atid, _ = fx
            fr = cor_idx.get((dkey, api_lid, htid, atid))
            if fr is not None:
                lam_c = float(eng['corners'].predict(pd.DataFrame([[getattr(fr, k_) for k_ in CFEATS]], columns=CFEATS).astype(float))[0])
    # apuestas por mercado
    for (eid2, market, sel, linea), sn in by_out.items():
        if eid2 != eid: continue
        cuota = entry_odds(sn); cierre = closing_odds(sn)
        if not cuota or cuota < 1.05: continue
        bet = None  # (motor, p, payout_factor)
        if market == 'Ambos Equipos Marcarán':
            if sel == 'Sí':
                e_ = edge_pair(by_out, eid, market, None, 'Sí', p_btts)
                if e_ is not None and p_btts >= 0.50 and e_ >= 0.03:
                    bet = ('btts_v2', p_btts, 1.0 if bts else 0.0)
            elif sel == 'No':
                p_no = 1 - p_btts
                e_ = edge_pair(by_out, eid, market, None, 'No', p_no)
                if e_ is not None and p_no >= 0.50 and e_ >= 0.03:
                    bet = ('btts_v2', p_no, 0.0 if bts else 1.0)
        elif market == 'Total de goles' and linea is not None:
            if cuota < 1.5 or linea < 2.0 or linea > 4.5: continue
            if sel.startswith('Más'):
                p = 1 - poisson.cdf(linea, lam_g)
                e_ = edge_pair(by_out, eid, market, linea, sel, p)
                if p >= 0.50 and abs(lam_g - linea) >= 0.4 and e_ is not None and e_ >= 0.03:
                    bet = ('goles_v2', p, 1.0 if tot > linea else 0.0)
            elif sel.startswith('Menos'):
                p = poisson.cdf(linea, lam_g)
                e_ = edge_pair(by_out, eid, market, linea, sel, p)
                if p >= 0.50 and abs(lam_g - linea) >= 0.4 and e_ is not None and e_ >= 0.03:
                    bet = ('goles_v2', p, 1.0 if tot < linea else 0.0)
        elif market == 'Resultado Final':
            fair3 = {}
            for (e3, mk, sl, ln), s3 in by_out.items():
                if e3 == eid and mk == market:
                    o = entry_odds(s3)
                    if o: fair3[sl] = 1.0 / o
            if len(fair3) == 3:
                s = sum(fair3.values())
                f1, fX, f2 = fair3.get('1', 0) / s, fair3.get('X', 0) / s, fair3.get('2', 0) / s
                if sel == '1' and p_home >= 0.42 and (p_home - f1) >= 0.05 and cuota >= 1.6:
                    bet = ('x12_v2', p_home, 1.0 if res == 0 else 0.0)
                elif sel == 'X' and p_x[1] >= 0.42 and (p_x[1] - fX) >= 0.05 and cuota >= 1.6:
                    bet = ('x12_v2', float(p_x[1]), 1.0 if res == 1 else 0.0)
                elif sel == '2' and p_x[2] >= 0.42 and (p_x[2] - f2) >= 0.05 and cuota >= 1.6:
                    bet = ('x12_v2', float(p_x[2]), 1.0 if res == 2 else 0.0)
            elif len(fair3) == 1:
                if sel == '1' and p_home >= 0.42 and p_home * cuota - 1 >= 0.05 and cuota >= 1.6:
                    bet = ('x12_v2', p_home, 1.0 if res == 0 else 0.0)
                elif sel == 'X' and p_x[1] >= 0.42 and p_x[1] * cuota - 1 >= 0.05 and cuota >= 1.6:
                    bet = ('x12_v2', float(p_x[1]), 1.0 if res == 1 else 0.0)
                elif sel == '2' and p_x[2] >= 0.42 and p_x[2] * cuota - 1 >= 0.05 and cuota >= 1.6:
                    bet = ('x12_v2', float(p_x[2]), 1.0 if res == 2 else 0.0)
        elif market == 'Total de Tiros de Esquina' and linea is not None and lam_c is not None:
            if cuota < 1.5 or linea < 8.5 or linea > 11.5: continue
            ct = m['corners_total']
            if ct is None:
                # fallback: suma de corner_kicks en TeamFixtureStat
                if fx and fx[2]:
                    sts = TeamFixtureStat.objects.filter(fixture_id=fx[2]).values_list('corner_kicks', flat=True)
                    sts = [v for v in sts if v is not None]
                    if len(sts) == 2:
                        ct = sum(sts)
            if ct is None: continue
            if sel.startswith('Más'):
                p = 1 - nbinom.cdf(linea, PHI_C, PHI_C / (PHI_C + lam_c))
                e_ = edge_pair(by_out, eid, market, linea, sel, p)
                if p >= 0.50 and abs(lam_c - linea) >= 0.75 and e_ is not None and e_ >= 0.03:
                    bet = ('corners_v2', p, 1.0 if ct > linea else 0.0)
            elif sel.startswith('Menos'):
                p = nbinom.cdf(linea, PHI_C, PHI_C / (PHI_C + lam_c))
                e_ = edge_pair(by_out, eid, market, linea, sel, p)
                if p >= 0.50 and abs(lam_c - linea) >= 0.75 and e_ is not None and e_ >= 0.03:
                    bet = ('corners_v2', p, 1.0 if ct < linea else 0.0)
        if bet is None: continue
        motor, p_, won = bet
        stake = 10000
        payout = stake * cuota if won else 0
        r = results[motor]
        r['n'] += 1; r['won'] += won; r['stake'] += stake; r['payout'] += payout
        r['cuotas'].append(cuota)
        if cierre:
            r['clv'].append((cuota - cierre) / cierre * 100)

print(f'Eventos simulables: {events_ok} | apuestas: {sum(r["n"] for r in results.values())}\n')
print(f'{"Motor":12} {"n":>4} {"WR":>6} {"ROI":>7} {"Net COP":>10} {"Cuota med":>9} {"CLV med":>8}')
for motor in ['btts_v2', 'goles_v2', 'x12_v2', 'corners_v2', 'sot_v2']:
    r = results.get(motor)
    if not r or r['n'] == 0:
        print(f'{motor:12}    0'); continue
    wr = r['won'] / r['n'] * 100
    roi = (r['payout'] - r['stake']) / r['stake'] * 100
    net = r['payout'] - r['stake']
    cq = np.mean(r['cuotas'])
    clv = np.mean(r['clv']) if r['clv'] else 0
    print(f'{motor:12} {r["n"]:4d} {wr:5.1f}% {roi:+6.1f}% {net:+10.0f} {cq:8.2f} {clv:+7.2f}%')
json.dump({k: {'n': v['n'], 'won': v['won'], 'stake': v['stake'], 'payout': v['payout'], 'clv': v['clv']}
           for k, v in results.items()}, open(OUT + '/backtest_snapshots_result.json', 'w'))
print('\nguardado backtest_snapshots_result.json')
