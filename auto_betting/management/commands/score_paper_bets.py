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

# Horas tras el inicio a partir de las cuales una apuesta que NO se puede
# liquidar (partido aplazado, sin estadísticas, equipo con nombre que no
# coincide con la API) se anula y se devuelve el stake. Sin este tope, esas
# apuestas se quedaban en OPEN indefinidamente y el paperbet nunca cuadraba.
STALE_VOID_HOURS = 40

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
        # Fases de la API que mapean a cada liga de Predicta. Puede haber más de
        # una (Apertura/Clausura): ver auto_betting/fixture_match.py.
        from auto_betting.fixture_match import match_fixture
        ligas_api = list(ApiLeague.objects.filter(predicta_league_id__isnull=False))
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
            # Varias ligas de la API pueden apuntar a la misma liga de Predicta
            # (Apertura y Clausura). Se prueban todas, no solo la primera.
            candidatas = [a for a in ligas_api if a.predicta_league_id == lid] if lid else []
            best = None; best_s = 0.0; best_motivo = ''
            for al in candidatas:
                cand, motivo = match_fixture(fx, al.api_id, al.name,
                                             bet.home_team, bet.away_team)
                if cand is None:
                    if not best_motivo:
                        best_motivo = motivo
                    continue
                s1 = difflib.SequenceMatcher(None, norm(bet.home_team),
                                             norm(cand['teams']['home']['name'])).ratio()
                s2 = difflib.SequenceMatcher(None, norm(bet.away_team),
                                             norm(cand['teams']['away']['name'])).ratio()
                if s1 + s2 > best_s:
                    best_s = s1 + s2; best = cand; best_motivo = motivo
            if best is None and not candidatas:
                # Liga sin equivalencia en la API: se prueba el emparejamiento
                # sin filtro de liga como último recurso (y así se reporta).
                best, best_motivo = match_fixture(fx, None, None,
                                                  bet.home_team, bet.away_team)
                if best is not None:
                    s1 = difflib.SequenceMatcher(None, norm(bet.home_team),
                                                 norm(best['teams']['home']['name'])).ratio()
                    s2 = difflib.SequenceMatcher(None, norm(bet.away_team),
                                                 norm(best['teams']['away']['name'])).ratio()
                    best_s = s1 + s2
            # match_fixture ya aplica el umbral (0.7 por equipo) y admite fases
            # hermanas, así que basta con comprobar que encontró algo.
            if best is None:
                # Partido sin fixture en API (liga fuera de cobertura del plan).
                # Pasadas 40h del start_time sin poder liquidar → VOID (stake devuelto).
                if timezone.now() - bet.start_time > timedelta(hours=STALE_VOID_HOURS):
                    bet.estado = 'VOID'
                    bet.resultado_real = 'sin cobertura API'
                    bet.payout = bet.stake
                    bet.settled_at = timezone.now()
                    bet.save(update_fields=['estado', 'resultado_real', 'payout', 'settled_at'])
                    n_ok += 1
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
            elif 'tiros a puerta' in mkt or mkt == 'Total de Tiros de Esquina':
                fid = best['fixture']['id']
                stat_key = 'Shots on Goal' if 'tiros a puerta' in mkt else 'Corner Kicks'
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
                        v = st.get(stat_key)
                        if v is None:
                            tot = None; break
                        tot = (tot or 0) + int(v)
                if tot is None:
                    n_open += 1
                    continue
                won = tot > bet.linea if 'Más' in bet.seleccion else tot < bet.linea
                resultado = f'{stat_key} {tot}'
            if won is None:
                continue
            bet.estado = 'WON' if won else 'LOST'
            bet.payout = (bet.stake * bet.cuota) if won else 0
            bet.resultado_real = resultado
            bet.settled_at = timezone.now()
            bet.save(update_fields=['estado', 'payout', 'resultado_real', 'settled_at'])
            n_ok += 1
        # --- Barrido final: ninguna apuesta queda OPEN para siempre --------
        # Red de seguridad: pase lo que pase dentro del bucle (rama que hace
        # `continue`, estadística ausente, estado raro de la API), una apuesta
        # más vieja que STALE_VOID_HOURS sin resultado se anula con su stake
        # devuelto. Así el paperbet no acumula OPEN eternos.
        stale_cutoff = timezone.now() - timedelta(hours=STALE_VOID_HOURS)
        n_void = 0
        for bet in PaperBet.objects.filter(estado='OPEN', start_time__lt=stale_cutoff):
            bet.estado = 'VOID'
            bet.resultado_real = f'sin resultado >{STALE_VOID_HOURS}h'
            bet.payout = bet.stake
            bet.settled_at = timezone.now()
            bet.save(update_fields=['estado', 'resultado_real', 'payout', 'settled_at'])
            n_void += 1

        self.stdout.write(
            f'Liquidadas: {n_ok} | Anuladas por antigüedad: {n_void} | '
            f'Siguen OPEN (aún no liquidables): {n_open}'
        )
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
