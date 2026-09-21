# -*- coding: utf-8 -*-
"""
Descarga stats post-partido de los partidos FT de HOY (13-sep-2026) en ligas cubiertas.
Ground truth para el test out-of-sample del modelo de remates totales v2.
Guarda en scripts/remates_v2/today_ft_stats.json (no toca la BD).
"""
import os, sys, django, json, time
sys.path.insert(0, '/var/www/predicta.com.co')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
django.setup()
from football_api.client import ApiFootballClient

FT = json.load(open('/tmp/ft_covered.json'))
OUT = '/var/www/predicta.com.co/scripts/remates_v2/today_ft_stats.json'

results = {}
if os.path.exists(OUT):
    results = json.load(open(OUT))
    print(f'resume: {len(results)} ya descargados')

c = ApiFootballClient()
n_new = 0
for f in FT:
    fid = f['fixture']['id']
    if str(fid) in results: continue
    try:
        d = c.fixtures_statistics(fid)
    except Exception as e:
        print(fid, 'ERR', str(e)[:100]); time.sleep(1); continue
    resp = d.get('response', [])
    # extract total_shots per team
    row = {'fixture_id': fid, 'league': f['league']['name'], 'league_id': f['league']['id'],
           'home': f['teams']['home']['name'], 'away': f['teams']['away']['name'],
           'kickoff': f['fixture']['date'], 'teams': []}
    for t in resp:
        stats = {}
        for s in (t.get('statistics') or []):
            if s.get('type') in ('Total Shots', 'Shots on Goal', 'Shots insidebox', 'Shots outsidebox', 'Ball Possession', 'Corner Kicks'):
                stats[s['type']] = s['value']
        row['teams'].append({'team': t['team']['name'], 'home': t['team']['id'] == f['teams']['home']['id'], 'stats': stats})
    row['total_shots'] = None
    if len(row['teams']) == 2 and all(t['stats'].get('Total Shots') is not None for t in row['teams']):
        row['total_shots'] = sum(int(t['stats']['Total Shots']) for t in row['teams'])
        row['total_sot'] = sum(int(t['stats'].get('Shots on Goal') or 0) for t in row['teams'])
    results[str(fid)] = row
    n_new += 1
    if n_new % 25 == 0:
        print(f'{n_new} nuevos... quota remaining={c.daily_remaining}')
        json.dump(results, open(OUT,'w'))
    time.sleep(0.2)

json.dump(results, open(OUT,'w'))
ok = sum(1 for r in results.values() if r.get('total_shots') is not None)
print(f'DONE. {len(results)} partidos, {ok} con total_shots utilizable. quota remaining={c.daily_remaining}')
