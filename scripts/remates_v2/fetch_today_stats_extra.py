# -*- coding: utf-8 -*-
"""Amplía el ground truth de HOY (13-sep) para el test del motor de remates v2.
- Baja fixtures FT de hoy en ligas cubiertas que aún no estén en el overlay (today_ft_stats.json + newft_stats_20260913.json).
- --recheck: reintenta los que quedaron sin total_shots (stats tardías).
No toca la BD. Reanudable.
Uso: python scripts/remates_v2/fetch_today_stats_extra.py [--recheck]
"""
import os, sys, json, time, argparse
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
import django; django.setup()
from datetime import datetime, timezone as dtz
from football_api.client import ApiFootballClient

R = '/var/www/predicta.com.co/scripts/remates_v2'
ap = argparse.ArgumentParser(); ap.add_argument('--recheck', action='store_true')
args = ap.parse_args()

base = json.load(open(R + '/today_ft_stats.json'))
extra_p = R + '/newft_stats_20260913.json'
extra = json.load(open(extra_p)) if os.path.exists(extra_p) else {}
cov = {f['league']['id'] for f in json.load(open(R + '/ft_covered.json'))}
c = ApiFootballClient()

today = '2026-09-13'
d = c.fixtures(date=today)
resp = d.get('response', [])
FT = [f for f in resp if f['fixture']['status']['short'] in ('FT','AET','PEN')]
print(f'FT hoy: {len(FT)} | quota: {c.daily_remaining}')

n_new = 0
for f in FT:
    fid = str(f['fixture']['id'])
    if fid in base or (fid in extra and extra[fid].get('total_shots') is not None):
        continue
    if f['league']['id'] not in cov:
        continue
    try:
        sd = c.fixtures_statistics(f['fixture']['id'])
    except Exception as e:
        print(fid, 'ERR', str(e)[:80]); time.sleep(1); continue
    teams = []
    for t in sd.get('response', []):
        st = {}
        for s_ in (t.get('statistics') or []):
            if s_['type'] in ('Total Shots','Shots on Goal'):
                st[s_['type']] = s_['value']
        teams.append({'team': t['team']['name'], 'home': t['team']['id']==f['teams']['home']['id'], 'stats': st})
    tot = None
    if len(teams)==2 and all(t['stats'].get('Total Shots') is not None for t in teams):
        tot = sum(int(t['stats']['Total Shots']) for t in teams)
    extra[fid] = {'fixture_id': int(fid), 'league': f['league']['name'], 'league_id': f['league']['id'],
                  'home': f['teams']['home']['name'], 'away': f['teams']['away']['name'],
                  'kickoff': f['fixture']['date'], 'teams': teams, 'total_shots': tot}
    n_new += 1
    if n_new % 10 == 0:
        json.dump(extra, open(extra_p,'w'), ensure_ascii=False)
        print(f'{n_new} nuevas... quota={c.daily_remaining}')
    time.sleep(0.2)

if args.recheck:
    for fid, r in list(extra.items()):
        if r.get('total_shots') is not None: continue
        try:
            sd = c.fixtures_statistics(int(fid))
        except Exception:
            time.sleep(0.5); continue
        teams = []
        for t in sd.get('response', []):
            st = {}
            for s_ in (t.get('statistics') or []):
                if s_['type'] in ('Total Shots','Shots on Goal'):
                    st[s_['type']] = s_['value']
            teams.append({'team': t['team']['name'], 'home': None, 'stats': st})
        tot = None
        if len(teams)==2 and all(t['stats'].get('Total Shots') is not None for t in teams):
            tot = sum(int(t['stats']['Total Shots']) for t in teams)
        if tot is not None:
            r['teams'] = teams; r['total_shots'] = tot
            print(f'  recheck {fid}: recuperado total={tot}')
        time.sleep(0.2)

json.dump(extra, open(extra_p,'w'), ensure_ascii=False)
ok = sum(1 for r in extra.values() if r.get('total_shots') is not None)
print(f'DONE. extra file: {len(extra)} partidos | usables: {ok} | quota={c.daily_remaining}')
