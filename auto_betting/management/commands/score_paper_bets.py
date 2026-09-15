# -*- coding: utf-8 -*-
"""PAPERBET — liquida apuestas paper OPEN con resultados reales (API-Football).
Uso: manage.py score_paper_bets [--days-back 7]
"""
import difflib, unicodedata
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from auto_betting.models import PaperBet
from football_api.client import ApiFootballClient
from football_api.models import ApiLeague
from football_data.models import League

def norm(s):
    s = unicodedata.normalize('NFKD', s)
    return ''.join(x for x in s.lower() if x.isalnum())

class Command(BaseCommand):
    help = 'Liquida apuestas paper OPEN con resultados de API-Football'

    def add_arguments(self, parser):
        parser.add_argument('--days-back', type=int, default=7)

    def handle(self, *args, **opts):
        cutoff = timezone.now() - timedelta(days=opts['days_back'])
        open_bets = PaperBet.objects.filter(estado='OPEN', start_time__gte=cutoff)
        if not open_bets.exists():
            self.stdout.write('Sin apuestas OPEN.')
            return
        # cache: fecha -> fixtures ; fixture_id -> stats SOT
        c = ApiFootballClient()
        fx_cache = {}
        sot_cache = {}
        liga2api = {l.id: a.api_id for a in ApiLeague.objects.filter(predicta_league_id__isnull=False) for l in League.objects.filter(id=a.predicta_league_id)}
        name2lid = {l.name: l.id for l in League.objects.all()}
        n_ok = n_open = 0
        for bet in open_bets:
            day = bet.start_time.strftime('%Y-%m-%d')
            if day not in fx_cache:
                try:
                    fx_cache[day] = c.fixtures(date=day).get('response', [])
                except Exception:
                    fx_cache[day] = None
            fx = fx_cache[day]
            if fx is None:
                continue
            lid = name2lid.get(bet.liga)
            api_lid = liga2api.get(lid) if lid else None
            # buscar fixture por nombres (y liga si está)
            nh, na = norm(bet.home_team), norm(bet.away_team)
            best = None; best_s = 0.0
            for f in fx:
                if api_lid and f['league']['id'] != api_lid:
                    continue
                s1 = difflib.SequenceMatcher(None, nh, norm(f['teams']['home']['name'])).ratio()
                s2 = difflib.SequenceMatcher(None, na, norm(f['teams']['away']['name'])).ratio()
                sc = s1 + s2
                if sc > best_s:
                    best_s = sc; best = f
            if best is None or best_s < 1.4:
                continue
            status = best['fixture']['status']['short']
            if status not in ('FT', 'AET', 'PEN'):
                n_open += 1
                continue
            gh = best['goals']['home']; ga = best['goals']['away']
            if gh is None or ga is None:
                continue
            won = None; resultado = f'{gh}-{ga}'
            mkt = bet.mercado
            if mkt == 'Ambos Equipos Marcarán':
                bts = gh > 0 and ga > 0
                won = bts if bet.seleccion == 'Sí' else (not bts)
            elif mkt == 'Total de goles':
                tot = gh + ga
                if 'Más' in bet.seleccion:
                    won = tot > bet.linea
                else:
                    won = tot < bet.linea
            elif mkt == 'Doble Oportunidad':
                if bet.seleccion == '1X':
                    won = gh >= ga
                elif bet.seleccion == 'X2':
                    won = gh <= ga
                else:  # 12
                    won = gh != ga
            elif mkt == 'Resultado Final':
                r = '1' if gh > ga else ('X' if gh == ga else '2')
                sel = bet.seleccion
                won = (sel in ('1', 'Home', 'OT_1') and r == '1') or (sel in ('X', 'Draw', 'OT_X') and r == 'X') or (sel in ('2', 'Away', 'OT_2') and r == '2')
                resultado = f'{gh}-{ga} ({r})'
            elif 'tiros a puerta' in mkt:
                fid = best['fixture']['id']
                if fid not in sot_cache:
                    try:
                        sd = c.fixtures_statistics(fid)
                        sot_cache[fid] = sd
                    except Exception:
                        sot_cache[fid] = None
                sd = sot_cache[fid]
                tot = None
                if sd:
                    for t in sd.get('response', []):
                        st = {s_['type']: s_['value'] for s_ in (t.get('statistics') or [])}
                        v = st.get('Shots on Goal')
                        if v is None:
                            tot = None; break
                        tot = (tot or 0) + int(v)
                if tot is None:
                    n_open += 1
                    continue
                won = tot > bet.linea if 'Más' in bet.seleccion else tot < bet.linea
                resultado = f'SOT {tot}'
            if won is None:
                continue
            bet.estado = 'WON' if won else 'LOST'
            bet.payout = (bet.stake * bet.cuota) if won else 0
            bet.resultado_real = resultado
            bet.settled_at = timezone.now()
            bet.save(update_fields=['estado', 'payout', 'resultado_real', 'settled_at'])
            n_ok += 1
        self.stdout.write(f'Liquidadas: {n_ok} | Siguen OPEN (sin FT/stats aún): {n_open}')
        self._settle_parlays()

    def _settle_parlays(self):
        """Liquida combinadas cuyas patas (PaperBet) ya están asentadas."""
        from auto_betting.models import PaperParlay
        n = 0
        for p in PaperParlay.objects.filter(estado='OPEN'):
            ids = [l.get('paperbet_id') for l in (p.legs or []) if l.get('paperbet_id')]
            if not ids:
                continue
            legs = list(PaperBet.objects.filter(id__in=ids))
            if len(legs) != len(ids):
                continue  # falta alguna pata
            estados = [b.estado for b in legs]
            if 'OPEN' in estados:
                continue
            if 'VOID' in estados:
                p.estado = 'VOID'; p.resultado_real = f'void en {estados.count("VOID")} pata(s)'; p.payout = p.stake
            elif all(e == 'WON' for e in estados):
                p.estado = 'WON'; p.resultado_real = f'{estados.count("WON")}/{len(legs)}'; p.payout = p.stake * p.cuota
            else:
                p.estado = 'LOST'; p.resultado_real = f'{estados.count("WON")}/{len(legs)}'; p.payout = 0
            p.settled_at = timezone.now()
            p.save(update_fields=['estado', 'resultado_real', 'payout', 'settled_at'])
            n += 1
        self.stdout.write(f'Combinadas liquidadas: {n}')
