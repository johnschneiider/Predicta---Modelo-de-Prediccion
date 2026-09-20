# -*- coding: utf-8 -*-
"""PAPERBET — recolecta picks de los motores independientes (sin dinero real).
Motores: btts_v2, goles_v2, sot_v2, x12_v2. Cuotas reales de Kambi (1 llamada/evento).
Uso: manage.py run_paper_bets [--hours 48]
"""
import pickle, math
from datetime import datetime, timezone, timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone as djtz
from scipy.stats import poisson, nbinom
from auto_betting.services import fetch_upcoming_matches, fetch_market_odds
from auto_betting.management.commands.run_auto_bets import find_predicta_league, map_teams
from auto_betting.models import PaperBet

S = '/var/www/predicta.com.co/scripts'
BTT_S = S + '/btts_v2/btts_state.pkl'
PB = S + '/paperbet'
HALF = 120.0

FEATS = ['h_n','a_n','gf_h','gf_a','ga_h','ga_a','bts_h','bts_a','scored_h','scored_a','cs_h','cs_a','tot_h','tot_a',
         'form_pts_h','form_gf_h','form_ga_h','form_pts_a','form_gf_a','form_ga_a','rest_h','rest_a',
         'lg_n','lg_gf','lg_ga','lg_bts','lg_tot','lg_n90','lg_bts90','lg_tot90',
         'h2h_n','h2h_bts','h2h_gfh','h2h_gfa']

LABELS = ['Total de goles', 'Total de tiros a puerta (Resuelta usando Opta Data)',
          'Resultado Final', 'Ambos Equipos Marcarán']

class Command(BaseCommand):
    help = 'Recolecta apuestas paper de los motores independientes'

    def add_arguments(self, parser):
        parser.add_argument('--hours', type=int, default=48)

    def handle(self, *args, **opts):
        btt_state = pickle.load(open(BTT_S, 'rb'))
        eng = pickle.load(open(PB + '/engines.pkl', 'rb'))
        sot_state = pickle.load(open(PB + '/sot_state.pkl', 'rb'))
        cor_state = pickle.load(open(PB + '/corners_state.pkl', 'rb'))
        TEAM_KEYS = btt_state['TEAM_KEYS']; hists = btt_state['hists']
        LSTATE = btt_state['LSTATE']; PAIR = btt_state['PAIR']

        matches = fetch_upcoming_matches(hours_ahead=opts['hours'])
        self.stdout.write(f'Partidos próximos: {len(matches)}')
        n_new = 0
        for m in matches:
            league = find_predicta_league(m)
            if league is None:
                continue
            home_db, away_db = map_teams(m, league)
            if not home_db or not away_db or home_db == away_db:
                continue
            lid = league.id
            hk = TEAM_KEYS.get(f'{lid}|{home_db}'); ak = TEAM_KEYS.get(f'{lid}|{away_db}')
            start = m['start_time']
            if hk is not None and ak is not None:
                row = self._goals_feats(btt_state, hk, ak, lid, start)
                X = [[row[k] for k in FEATS]]
                import pandas as pd
                Xd = pd.DataFrame(X, columns=FEATS).astype(float)
                art = pickle.load(open(S + '/btts_v2/gbm_btts.pkl', 'rb'))
                p_btts = float(art['iso'].predict(art['model'].predict_proba(Xd)[:, 1])[0])
                lam_g = float(eng['goles'].predict(Xd)[0])
                p_x = eng['x12'].predict_proba(Xd)[0]
                p_home = float(eng['x12_iso_h'].predict([p_x[0]])[0])
                self._paper_btts(m, home_db, away_db, league, p_btts, fetch_market_odds(m['event_id'], 'Ambos Equipos Marcarán'), start)
                self._paper_goals(m, home_db, away_db, league, lam_g, fetch_market_odds(m['event_id'], 'Total de goles'), start)
                self._paper_x12(m, home_db, away_db, league, p_x, p_home, fetch_market_odds(m['event_id'], 'Resultado Final'), start)
            self._paper_sot(m, home_db, away_db, league, sot_state, fetch_market_odds(m['event_id'], 'Total de tiros a puerta (Resuelta usando Opta Data)'), start)
            self._paper_corners(m, home_db, away_db, league, fetch_market_odds(m['event_id'], 'Total de Tiros de Esquina'), start)
            self._paper_do(m, home_db, away_db, league, p_x, fetch_market_odds(m['event_id'], 'Doble Oportunidad'), start)
        self._build_parlays()
        self.stdout.write(f'Recolección finalizada.')

    # ---------- features (replicadas de btts_v2) ----------
    def _goals_feats(self, st, hk, ak, lid, start):
        ORD = start.toordinal()
        def tf(t):
            h = st['hists'][t]
            out = {}
            for v, vn in ((0, 'h'), (1, 'a')):
                d = h['s'][v]; sw = d['sw']
                if sw >= 1e-6:
                    out[f'{vn}_n'] = sw
                    out[f'gf_{vn}'] = d['gf']/sw; out[f'ga_{vn}'] = d['ga']/sw
                    out[f'bts_{vn}'] = d['bts']/sw; out[f'scored_{vn}'] = d['scored']/sw
                    out[f'cs_{vn}'] = d['cs']/sw; out[f'tot_{vn}'] = d['tot']/sw
                else:
                    out[f'{vn}_n'] = None
                    for kk in ('gf','ga','bts','scored','cs','tot'): out[f'{kk}_{vn}'] = None
            last = list(h['last'])
            if last:
                pts=0; gf=0; ga=0
                for o,g,c,b,vv in last[-6:]:
                    gf+=g; ga+=c; pts += 3 if g>c else (1 if g==c else 0)
                out['form_pts']=pts/max(1,len(last[-6:])); out['form_gf']=gf/max(1,len(last[-6:])); out['form_ga']=ga/max(1,len(last[-6:]))
                out['rest']=ORD-last[-1][0]
            else:
                out['form_pts']=out['form_gf']=out['form_ga']=None; out['rest']=None
            return out
        fh = tf(hk); fa = tf(ak)
        lf = st['LSTATE'].get(lid)
        if lf:
            f = 0.5 ** ((ORD - lf['last'])/HALF)
            lg_n = lf['sw']*f
            lg_gf = lf['gf']*f/lg_n if lg_n>1e-6 else None
            lg_ga = lf['ga']*f/lg_n if lg_n>1e-6 else None
            lg_bts = lf['bts']*f/lg_n if lg_n>1e-6 else None
            lg_tot = lf['tot']*f/lg_n if lg_n>1e-6 else None
            w90 = [o for o in lf['last90'] if o > ORD-90]
            lg_n90 = len(w90)
            lg_bts90 = lf['bts90_sum']/lg_n90 if w90 else None
            lg_tot90 = lf['tot90_sum']/lg_n90 if w90 else None
        else:
            lg_n=lg_gf=lg_ga=lg_bts=lg_tot=lg_n90=lg_bts90=lg_tot90=None
        pl = st['PAIR'].get(f'{lid}|{hk}|{ak}', [])
        h2h = [x for x in pl if x[0] > ORD-1095][-10:]
        if h2h:
            h2h_n=len(h2h); h2h_bts=sum(x[1] for x in h2h)/h2h_n
            h2h_gfh=sum(x[2] for x in h2h)/h2h_n; h2h_gfa=sum(x[3] for x in h2h)/h2h_n
        else:
            h2h_n=0; h2h_bts=h2h_gfh=h2h_gfa=None
        return {'h_n':fh['h_n'],'a_n':fa['a_n'],'gf_h':fh['gf_h'],'gf_a':fa['gf_a'],'ga_h':fh['ga_h'],'ga_a':fa['ga_a'],
                'bts_h':fh['bts_h'],'bts_a':fa['bts_a'],'scored_h':fh['scored_h'],'scored_a':fa['scored_a'],
                'cs_h':fh['cs_h'],'cs_a':fa['cs_a'],'tot_h':fh['tot_h'],'tot_a':fa['tot_a'],
                'form_pts_h':fh['form_pts'],'form_gf_h':fh['form_gf'],'form_ga_h':fh['form_ga'],
                'form_pts_a':fa['form_pts'],'form_gf_a':fa['form_gf'],'form_ga_a':fa['form_ga'],
                'rest_h':fh['rest'],'rest_a':fa['rest'],'lg_n':lg_n,'lg_gf':lg_gf,'lg_ga':lg_ga,'lg_bts':lg_bts,
                'lg_tot':lg_tot,'lg_n90':lg_n90,'lg_bts90':lg_bts90,'lg_tot90':lg_tot90,
                'h2h_n':h2h_n,'h2h_bts':h2h_bts,'h2h_gfh':h2h_gfh,'h2h_gfa':h2h_gfa}

    # ---------- decisores ----------
    def _devig2(self, odds):
        """Fair probs desde par over/under o Sí/No (2-way)."""
        inv = {o.get('type'): 1.0/o['odds_decimal'] for o in odds if o.get('odds_decimal')}
        if 'OT_OVER' in inv and 'OT_UNDER' in inv:
            s = inv['OT_OVER'] + inv['OT_UNDER']
            return {'OT_OVER': inv['OT_OVER']/s, 'OT_UNDER': inv['OT_UNDER']/s} if s > 0 else None
        if 'OT_YES' in inv and 'OT_NO' in inv:
            s = inv['OT_YES'] + inv['OT_NO']
            return {'OT_YES': inv['OT_YES']/s, 'OT_NO': inv['OT_NO']/s} if s > 0 else None
        return None

    def _devig3(self, odds):
        """Fair probs 3-way (Resultado Final)."""
        inv = {}
        for o in odds:
            t = o.get('type')
            if t in ('OT_ONE', 'OT_CROSS', 'OT_TWO') and o.get('odds_decimal'):
                inv[t] = 1.0/o['odds_decimal']
        if len(inv) != 3:
            return None
        s = sum(inv.values())
        return {k: v/s for k, v in inv.items()} if s > 0 else None

    def _paper_corners(self, m, h, a, lg, odds, start):
        """Córners v2: NegBin(phi=49) sobre features por team id (corners_state)."""
        if not odds:
            return
        from football_api.models import ApiLeague
        api_league_id = ApiLeague.objects.filter(predicta_league_id=lg.id).values_list('api_id', flat=True).first()
        if not api_league_id:
            return
        from football_api.client import ApiFootballClient
        import difflib, unicodedata
        def norm(s):
            s = unicodedata.normalize('NFKD', s)
            return ''.join(x for x in s.lower() if x.isalnum())
        c = ApiFootballClient()
        day = start.strftime('%Y-%m-%d')
        try:
            fx = c.fixtures(date=day).get('response', [])
        except Exception:
            return
        nh, na = norm(h), norm(a)
        best = None; best_s = 0.0
        for f in fx:
            if f['league']['id'] != api_league_id:
                continue
            s1 = difflib.SequenceMatcher(None, nh, norm(f['teams']['home']['name'])).ratio()
            s2 = difflib.SequenceMatcher(None, na, norm(f['teams']['away']['name'])).ratio()
            if s1 + s2 > best_s:
                best_s, best = s1 + s2, f
        if best is None or best_s < 1.4:
            return
        htid, atid = best['teams']['home']['id'], best['teams']['away']['id']
        st = pickle.load(open(PB + '/corners_state.pkl', 'rb'))
        ORD = start.toordinal()
        def tfc(tid):
            hh = st['hist'].get(tid)
            out = {}
            if hh is None:
                return {k: None for k in ('h_n','a_n','corn_f_h','corn_a_h','sot_f_h','ibox_f_h','xg_f_h','poss_f_h',
                                          'corn_f_a','corn_a_a','sot_f_a','ibox_f_a','xg_f_a','poss_f_a')}
            for v, vn in ((0,'h'),(1,'a')):
                dd = hh.get(v, {'sw':0.0}); sw = dd['sw']
                out[f'{vn}_n'] = sw
                for k in ('corn_f','corn_a','sot_f','ibox_f','xg_f','poss_f'):
                    out[f'{k}_{vn}'] = dd.get(k,0.0)/sw if sw>1e-6 else None
            return out
        fh = tfc(htid); fa = tfc(atid)
        lf = st['LSTATE'].get(api_league_id)
        if lf:
            f = 0.5 ** ((ORD - lf['last'])/HALF)
            lg_n = lf['sw']*f
            lg_corn = lf['corn']*f/lg_n if lg_n>1e-6 else None
            lg_xg = lf['xg']*f/lg_n if lg_n>1e-6 else None
        else:
            lg_n = lg_corn = lg_xg = None
        CFEATS = ['h_n','a_n','corn_f_h','corn_a_h','sot_f_h','ibox_f_h','xg_f_h','poss_f_h',
                  'corn_f_a','corn_a_a','sot_f_a','ibox_f_a','xg_f_a','poss_f_a','lg_n','lg_corn','lg_xg']
        row = {**fh, **fa, 'lg_n': lg_n, 'lg_corn': lg_corn, 'lg_xg': lg_xg}
        import pandas as pd
        X = pd.DataFrame([[row[k] for k in CFEATS]], columns=CFEATS).astype(float)
        eng = pickle.load(open(PB + '/engines.pkl', 'rb'))
        lam_c = float(eng['corners'].predict(X)[0])
        PHI = eng['PHI_CORNERS']
        fair = self._devig2(odds)
        if not fair:
            return
        for o in odds:
            if o.get('line') is None:
                continue
            line = o['line']; cuota = o['odds_decimal']; t = o.get('type')
            if cuota < 1.75 or line < 8.5 or line > 11.5:
                continue
            if t == 'OT_OVER':
                p = 1 - nbinom.cdf(line, PHI, PHI/(PHI + lam_c))
                if p >= 0.50 and (p - fair['OT_OVER']) >= 0.06 and abs(lam_c - line) >= 0.75:
                    self._add(m, h, a, lg, 'Total de Tiros de Esquina', 'corners_v2', 'Más de', line, cuota, p, start)
            elif t == 'OT_UNDER':
                p = nbinom.cdf(line, PHI, PHI/(PHI + lam_c))
                if p >= 0.50 and (p - fair['OT_UNDER']) >= 0.06 and abs(lam_c - line) >= 0.75:
                    self._add(m, h, a, lg, 'Total de Tiros de Esquina', 'corners_v2', 'Menos de', line, cuota, p, start)

    def _paper_do(self, m, h, a, lg, p_x, odds, start):
        """Doble Oportunidad derivada del x12_v2 (1X/X2/12)."""
        p1, pX, p2 = float(p_x[0]), float(p_x[1]), float(p_x[2])
        probs = {'1X': p1 + pX, 'X2': pX + p2, '12': p1 + p2}
        tipos = {'1X': 'OT_ONE_OR_CROSS', 'X2': 'OT_CROSS_OR_TWO', '12': 'OT_ONE_OR_TWO'}
        fair = {}
        for o in odds:
            t = o.get('type')
            if t in tipos.values() and o.get('odds_decimal'):
                fair[t] = 1.0 / o['odds_decimal']
        if len(fair) < 2:
            return
        s = sum(fair.values())
        for o in odds:
            t = o.get('type'); cuota = o['odds_decimal']
            sel = next((k for k, v in tipos.items() if v == t), None)
            if sel is None or cuota < 1.75:
                continue
            p = probs[sel]
            if p >= 0.60 and (p - fair[t] / s) >= 0.06:
                self._add(m, h, a, lg, 'Doble Oportunidad', 'x12_v2', sel, None, cuota, p, start)

    def _build_parlays(self):
        """Arma dobles con cuota objetivo ~2.0 desde singles OPEN con EV>=0.
        Patas de eventos distintos, cada par de eventos una sola vez, máx 10/día.
        """
        from auto_betting.models import PaperParlay
        singles = list(PaperBet.objects.filter(estado='OPEN').exclude(motor=''))
        legs = [s for s in singles if s.ev is not None and s.ev >= -0.05 and s.prob and s.prob >= 0.52 and s.cuota and s.cuota >= 1.35]
        # dedupe por par de evento_id
        usados = set()
        for p in PaperParlay.objects.filter(estado='OPEN'):
            evs = sorted([l.get('evento_id') for l in (p.legs or []) if l.get('evento_id')])
            if len(evs) == 2:
                usados.add(tuple(evs))
        cands = []
        for i in range(len(legs)):
            for j in range(i + 1, len(legs)):
                a, b = legs[i], legs[j]
                if a.evento_id == b.evento_id:
                    continue
                par = tuple(sorted([a.evento_id, b.evento_id]))
                if par in usados:
                    continue
                cuota = a.cuota * b.cuota
                if not (1.80 <= cuota <= 2.40):
                    continue
                prob = a.prob * b.prob
                ev = prob * cuota - 1
                cands.append((ev, a, b))
        cands.sort(key=lambda x: -x[0])
        creadas = 0
        for ev, a, b in cands:
            if creadas >= 10:
                break
            par = tuple(sorted([a.evento_id, b.evento_id]))
            if par in usados:
                continue
            leg_lst = [
                {'paperbet_id': a.id, 'evento_id': a.evento_id, 'home': a.home_team, 'away': a.away_team,
                 'mercado': a.mercado, 'seleccion': a.seleccion, 'linea': a.linea, 'cuota': a.cuota,
                 'prob': a.prob, 'motor': a.motor},
                {'paperbet_id': b.id, 'evento_id': b.evento_id, 'home': b.home_team, 'away': b.away_team,
                 'mercado': b.mercado, 'seleccion': b.seleccion, 'linea': b.linea, 'cuota': b.cuota,
                 'prob': b.prob, 'motor': b.motor},
            ]
            PaperParlay.objects.create(legs=leg_lst, cuota=round(a.cuota * b.cuota, 4),
                                       prob=round(a.prob * b.prob, 4), ev=round(ev, 4))
            usados.add(par)
            creadas += 1
        self.stdout.write(f'Combinadas creadas: {creadas}')

    def _add(self, m, home_db, away_db, liga, mercado, motor, seleccion, linea, cuota, prob, start):
        ev = prob*cuota - 1
        dup = PaperBet.objects.filter(evento_id=str(m['event_id']), mercado=mercado,
                                      seleccion=seleccion, linea=linea, estado='OPEN').exists()
        if dup:
            return False
        PaperBet.objects.create(evento_id=str(m['event_id']), start_time=start,
                                home_team=home_db, away_team=away_db, liga=liga.name,
                                mercado=mercado, motor=motor, seleccion=seleccion, linea=linea,
                                cuota=cuota, prob=round(prob, 4), ev=round(ev, 4))
        return True

    def _paper_btts(self, m, h, a, lg, p, odds, start):
        fair = self._devig2(odds)
        if not fair:
            return
        p_mkt_si = fair.get('OT_YES')
        if p_mkt_si is None:
            return
        for o in odds:
            cuota = o['odds_decimal']
            t = o.get('type')
            if t == 'OT_YES':
                if p >= 0.50 and cuota >= 1.75 and (p - p_mkt_si) >= 0.06:
                    self._add(m, h, a, lg, 'Ambos Equipos Marcarán', 'btts_v2', 'Sí', None, cuota, p, start)
            elif t == 'OT_NO':
                p_no = 1 - p
                if p_no >= 0.50 and cuota >= 1.75 and (p_no - (1 - p_mkt_si)) >= 0.06:
                    self._add(m, h, a, lg, 'Ambos Equipos Marcarán', 'btts_v2', 'No', None, cuota, p_no, start)

    def _paper_goals(self, m, h, a, lg, lam, odds, start):
        fair = self._devig2(odds)
        if not fair:
            return
        for o in odds:
            if o.get('line') is None:
                continue
            line = o['line']; cuota = o['odds_decimal']; t = o.get('type')
            if cuota < 1.75 or line < 2.0 or line > 4.5:
                continue
            if t == 'OT_OVER':
                p = 1 - poisson.cdf(line, lam)
                if p >= 0.50 and (p - fair['OT_OVER']) >= 0.06 and abs(lam - line) >= 0.4:
                    self._add(m, h, a, lg, 'Total de goles', 'goles_v2', 'Más de', line, cuota, p, start)
            elif t == 'OT_UNDER':
                p = poisson.cdf(line, lam)
                if p >= 0.50 and (p - fair['OT_UNDER']) >= 0.06 and abs(lam - line) >= 0.4:
                    self._add(m, h, a, lg, 'Total de goles', 'goles_v2', 'Menos de', line, cuota, p, start)

    def _paper_x12(self, m, h, a, lg, p_x, p_home, odds, start):
        fair = self._devig3(odds)
        if not fair:
            return
        for o in odds:
            t = o.get('type'); cuota = o['odds_decimal']
            if t == 'OT_ONE':
                p = p_home; sel = '1'
            elif t == 'OT_CROSS':
                p = float(p_x[1]); sel = 'X'
            elif t == 'OT_TWO':
                p = float(p_x[2]); sel = '2'
            else:
                continue
            if p >= 0.42 and (p - fair[t]) >= 0.08 and cuota >= 1.75:
                self._add(m, h, a, lg, 'Resultado Final', 'x12_v2', sel, None, cuota, p, start)

    def _paper_sot(self, m, h, a, lg, sot_state, odds, start):
        # resolución de ids: busca el fixture en la API por liga+fecha+equipos
        from football_api.models import ApiLeague
        api_league_id = ApiLeague.objects.filter(predicta_league_id=lg.id).values_list('api_id', flat=True).first()
        if not api_league_id:
            return
        from football_api.client import ApiFootballClient
        c = ApiFootballClient()
        day = start.strftime('%Y-%m-%d')
        try:
            fx = c.fixtures(date=day).get('response', [])
        except Exception:
            return
        import difflib, unicodedata
        def norm(s):
            s = unicodedata.normalize('NFKD', s)
            return ''.join(x for x in s.lower() if x.isalnum())
        nh, na = norm(h), norm(a)
        best = None; best_s = 0.0
        for f in fx:
            if f['league']['id'] != api_league_id:
                continue
            s1 = difflib.SequenceMatcher(None, nh, norm(f['teams']['home']['name'])).ratio()
            s2 = difflib.SequenceMatcher(None, na, norm(f['teams']['away']['name'])).ratio()
            sc = s1 + s2
            if sc > best_s:
                best_s = sc; best = f
        if best is None or best_s < 1.4:
            return
        htid, atid = best['teams']['home']['id'], best['teams']['away']['id']
        st = sot_state
        ORD = start.toordinal()
        def tfsot(tid, venue):
            hh = st['hist'].get(tid)
            out = {}
            if hh is None:
                return {k: None for k in ('h_n','a_n','sot_f_h','sot_a_h','ibox_f_h','xg_f_h','corn_f_h','poss_f_h',
                                          'sot_f_a','sot_a_a','ibox_f_a','xg_f_a','corn_f_a','poss_f_a')}
            for v, vn in ((0,'h'),(1,'a')):
                dd = hh.get(v, {'sw':0.0}); sw = dd['sw']
                out[f'{vn}_n'] = sw
                for k in ('sot_f','sot_a','ibox_f','xg_f','corn_f','poss_f'):
                    out[f'{k}_{vn}'] = dd.get(k,0.0)/sw if sw>1e-6 else None
            return out
        fh = tfsot(htid, 0); fa = tfsot(atid, 1)
        lf = st['LSTATE'].get(api_league_id)
        if lf:
            f = 0.5 ** ((ORD - lf['last'])/HALF)
            lg_n = lf['sw']*f
            lg_sot = lf['sot']*f/lg_n if lg_n>1e-6 else None
            lg_xg = lf['xg']*f/lg_n if lg_n>1e-6 else None
        else:
            lg_n = lg_sot = lg_xg = None
        SFEATS = ['h_n','a_n','sot_f_h','sot_a_h','ibox_f_h','xg_f_h','corn_f_h','poss_f_h',
                  'sot_f_a','sot_a_a','ibox_f_a','xg_f_a','corn_f_a','poss_f_a','lg_n','lg_sot','lg_xg']
        row = {**fh, **fa, 'lg_n': lg_n, 'lg_sot': lg_sot, 'lg_xg': lg_xg}
        import pandas as pd
        X = pd.DataFrame([[row[k] for k in SFEATS]], columns=SFEATS).astype(float)
        eng = pickle.load(open(PB + '/engines.pkl', 'rb'))
        lam_s = float(eng['sot'].predict(X)[0])
        PHI = eng['PHI_SOT']
        fair = self._devig2(odds)
        if not fair:
            return
        for o in odds:
            if o.get('line') is None:
                continue
            line = o['line']; cuota = o['odds_decimal']; t = o.get('type')
            if cuota < 1.75 or line < 6.5 or line > 9.5:
                continue
            if t == 'OT_OVER':
                p = 1 - nbinom.cdf(line, PHI, PHI/(PHI + lam_s))
                if p >= 0.50 and (p - fair['OT_OVER']) >= 0.06 and abs(lam_s - line) >= 1.0:
                    self._add(m, h, a, lg, 'Total de tiros a puerta (Resuelta usando Opta Data)', 'sot_v2', 'Más de', line, cuota, p, start)
            elif t == 'OT_UNDER':
                p = nbinom.cdf(line, PHI, PHI/(PHI + lam_s))
                if p >= 0.50 and (p - fair['OT_UNDER']) >= 0.06 and abs(lam_s - line) >= 1.0:
                    self._add(m, h, a, lg, 'Total de tiros a puerta (Resuelta usando Opta Data)', 'sot_v2', 'Menos de', line, cuota, p, start)
