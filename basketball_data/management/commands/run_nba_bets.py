# -*- coding: utf-8 -*-
"""
Auto-betting NBA (baloncesto) — dinero real, filtrado por Filtro V2.

Modelo: baseline rodante (Marcador ~ Normal, basketball_data/baseline_nba.py),
el mismo del estudio ROI por mercado/día/temporada.

Mercados y días permitidos (Filtro V2, claves nba_*):
  nba_ml_home       → lun
  nba_ml_away       → lun, sáb
  nba_spread_home   → lun
  nba_spread_away   → lun, jue, sáb
  nba_total_over    → mié
  nba_total_under   → dom

Compuerta por apuesta: P(modelo) − P(fair devigada) ≥ 3pp (misma del estudio).
Dry-run por defecto; dinero real con --real --yes.
"""
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone as djtz

from auto_betting import services as ab
from auto_betting.models import AutoBet, AutoBetConfig, DailyCounter
from auto_betting.v2_filter import is_allowed as v2_is_allowed, v2_activo
from basketball_data.baseline_nba import predict_game
from basketball_data.models import NBATeam

KAMBI_BASE = "https://us.offering-api.kambicdn.com/offering/v2018/betplay"
KAMBI_HEADERS = {"Accept": "application/json",
                 "Origin": "https://betplay.com.co",
                 "Referer": "https://betplay.com.co/"}
KAMBI_PARAMS = {"channel_id": 1, "client_id": 200, "lang": "es_CO", "market": "CO",
                "useCombined": "true", "useCombinedLive": "true"}
MIN_EDGE = 0.03
LABELS = ['Ganador - Prórroga incluida', 'Hándicap de Puntos - Prórroga incluida',
          'Total de puntos - Prórroga incluida']


def _devig(odds_a, odds_b):
    ia, ib = 1 / odds_a, 1 / odds_b
    s = ia + ib
    return ia / s, ib / s


class Command(BaseCommand):
    help = "Auto-betting NBA (baseline + Filtro V2). Dry-run por defecto."

    def add_arguments(self, parser):
        parser.add_argument('--real', action='store_true', help='Colocar apuestas reales')
        parser.add_argument('--yes', action='store_true', help='Confirmación doble para dinero real')
        parser.add_argument('--email', type=str, default=None, help='Solo este usuario (email)')
        parser.add_argument('--horas', type=int, default=24,
                            help='Horizonte máximo en horas para apostar (default 24)')

    def handle(self, *args, **options):
        real = options['real']
        if real and not options['yes']:
            self.stderr.write("⛔ Para dinero real se requieren --real y --yes.")
            return
        self.stdout.write(f"\n{'🧪 DRY-RUN' if not real else '💵 REAL'} — Auto-betting NBA")

        # 1) eventos NBA próximos en BetPlay/Kambi
        try:
            r = requests.get(f"{KAMBI_BASE}/listView/basketball.json", params=KAMBI_PARAMS,
                             headers=KAMBI_HEADERS, timeout=20)
            r.raise_for_status()
        except Exception as e:
            self.stderr.write(f"Error Kambi: {e}")
            return
        events = []
        descartados = 0
        horizonte = djtz.now() + timedelta(hours=options['horas'])
        for e in r.json().get('events', []):
            ev = e.get('event', {})
            keys = [p.get('termKey', '') for p in ev.get('path', [])]
            if ('nba' in keys or 'nba_preseason' in keys) and ev.get('state') == 'NOT_STARTED':
                try:
                    _start = datetime.fromisoformat(ev['start'].replace('Z', '+00:00'))
                except Exception:
                    continue
                if _start > horizonte:
                    descartados += 1
                    continue
                events.append(ev)
        self.stdout.write(f"Partidos NBA próximos: {len(events)} "
                          f"(descartados >{options['horas']}h: {descartados})")
        if not events:
            return

        teams = {t.full_name: t for t in NBATeam.objects.all()}

        # 2) candidatos por evento (una sola vez, no por usuario)
        candidates = []
        for ev in events:
            home = teams.get(ev.get('homeName', ''))
            away = teams.get(ev.get('awayName', ''))
            if not home or not away:
                continue
            # parseo de fecha de inicio
            try:
                start = datetime.fromisoformat(ev['start'].replace('Z', '+00:00'))
            except Exception:
                continue
            local_dt = djtz.localtime(start)

            offers = ab.fetch_market_odds(ev['id'], LABELS)
            if not offers:
                continue

            # ── Ganador (moneyline) ──
            ml = [o for o in offers if 'Ganador' in (o.get('criterion', {}).get('label') or '')
                  and o.get('odds_decimal')]
            if len(ml) >= 2:
                by_name = {o.get('label'): o for o in ml}
                oh, oa = by_name.get(home.full_name), by_name.get(away.full_name)
                if oh and oa:
                    pred = predict_game(home, away)
                    fh, fa = _devig(oh['odds_decimal'], oa['odds_decimal'])
                    for key, o, p, fair in (
                            ('nba_ml_home', oh, pred['p_home_win'], fh),
                            ('nba_ml_away', oa, pred['p_away_win'], fa)):
                        edge = p - fair
                        if edge < MIN_EDGE:
                            continue
                        if v2_activo() and not v2_is_allowed('NBA', key, local_dt):
                            continue
                        candidates.append({
                            'event_id': ev['id'], 'home': home, 'away': away, 'start': start,
                            'market_label': 'Ganador', 'key': key, 'outcome': o,
                            'p': p, 'fair': fair, 'edge': edge,
                            'ev': p * o['odds_decimal'] - 1,
                            'seleccion': (home.full_name if key.endswith('home') else away.full_name),
                            'linea': None,
                        })

            # ── Hándicap de puntos (spread) — línea principal (más balanceada) ──
            sp = [o for o in offers if 'Hándicap' in (o.get('criterion', {}).get('label') or '')
                  and o.get('odds_decimal') and o.get('line') is not None]
            pairs = {}
            for o in sp:
                pairs.setdefault(round(o['line'], 1), {})[o.get('type')] = o
            pair_opts = []
            for line, d in pairs.items():
                if 'OT_ONE' in d and 'OT_TWO' in d:
                    o1, o2 = d['OT_ONE'], d['OT_TWO']
                    pair_opts.append((abs(o1['odds_decimal'] - o2['odds_decimal']), line, o1, o2))
            if pair_opts:
                pair_opts.sort()
                _, line, o1, o2 = pair_opts[0]
                home_o = o1 if o1.get('label') == home.full_name else o2
                away_o = o2 if home_o is o1 else o1
                pred = predict_game(home, away, spread_home_line=home_o['line'])
                fh, fa = _devig(home_o['odds_decimal'], away_o['odds_decimal'])
                for key, o, p, fair in (
                        ('nba_spread_home', home_o, pred['p_spread_home'], fh),
                        ('nba_spread_away', away_o, pred['p_spread_away'], fa)):
                    edge = p - fair
                    if edge < MIN_EDGE:
                        continue
                    if v2_activo() and not v2_is_allowed('NBA', key, local_dt):
                        continue
                    candidates.append({
                        'event_id': ev['id'], 'home': home, 'away': away, 'start': start,
                        'market_label': 'Hándicap', 'key': key, 'outcome': o,
                        'p': p, 'fair': fair, 'edge': edge,
                        'ev': p * o['odds_decimal'] - 1,
                        'seleccion': f"{o.get('label')} {o['line']:+}",
                        'linea': o['line'],
                    })

            # ── Total de puntos — línea principal (más balanceada) ──
            tt = [o for o in offers if 'Total de puntos' in (o.get('criterion', {}).get('label') or '')
                  and o.get('odds_decimal') and o.get('line') is not None]
            lpair = {}
            for o in tt:
                lpair.setdefault(round(o['line'], 1), {})[o.get('type')] = o
            topts = []
            for line, d in lpair.items():
                if 'OT_OVER' in d and 'OT_UNDER' in d:
                    oo, ou = d['OT_OVER'], d['OT_UNDER']
                    topts.append((abs(oo['odds_decimal'] - ou['odds_decimal']), line, oo, ou))
            if topts:
                topts.sort()
                _, line, oo, ou = topts[0]
                pred = predict_game(home, away, total_line=line)
                fo, fu = _devig(oo['odds_decimal'], ou['odds_decimal'])
                for key, o, p, fair in (
                        ('nba_total_over', oo, pred['p_total_over'], fo),
                        ('nba_total_under', ou, pred['p_total_under'], fu)):
                    edge = p - fair
                    if edge < MIN_EDGE:
                        continue
                    if v2_activo() and not v2_is_allowed('NBA', key, local_dt):
                        continue
                    candidates.append({
                        'event_id': ev['id'], 'home': home, 'away': away, 'start': start,
                        'market_label': 'Total de puntos', 'key': key, 'outcome': o,
                        'p': p, 'fair': fair, 'edge': edge,
                        'ev': p * o['odds_decimal'] - 1,
                        'seleccion': f"{'Más de' if key.endswith('over') else 'Menos de'} {line}",
                        'linea': line,
                    })

        self.stdout.write(f"Candidatas que pasan Filtro V2: {len(candidates)}")
        for c in candidates:
            self.stdout.write(
                f"  [{c['key']}] {c['away'].full_name} @ {c['home'].full_name} | {c['seleccion']} "
                f"@{c['outcome']['odds_decimal']:.2f} | P={c['p']*100:.1f}% fair={c['fair']*100:.1f}% "
                f"edge={c['edge']*100:+.1f}pp EV={c['ev']*100:+.1f}%")
        if not candidates:
            return

        # 3) usuarios
        User = get_user_model()
        configs = AutoBetConfig.objects.filter(activo=True).select_related('usuario')
        if options['email']:
            configs = configs.filter(usuario__email=options['email'])
        from capital.services import resolve_stake

        colocadas_total = 0
        for config in configs:
            owner = config.usuario
            hoy = djtz.localdate()
            counter, _ = DailyCounter.objects.get_or_create(usuario=owner, fecha=hoy)
            disponibles = config.max_apuestas_diarias - counter.apuestas_colocadas
            if disponibles <= 0:
                self.stdout.write(f"⛔ {owner.email}: límite diario alcanzado.")
                continue
            stake, motivo = resolve_stake(config)
            if stake is None:
                self.stdout.write(f"⛔ {owner.email}: sin stake ({motivo}).")
                continue
            self.stdout.write(f"\n👤 {owner.email} | stake {stake/1000:,.0f} COP [{motivo}]")
            if not real:
                for c in candidates:
                    ok_v2 = v2_is_allowed('NBA', c['key'], djtz.localtime(c['start']))
                    self.stdout.write(
                        f"🧪 [DRY-RUN] Apostaría: {c['away'].full_name} @ {c['home'].full_name} | "
                        f"{c['market_label']} {c['seleccion']} @{c['outcome']['odds_decimal']:.2f} "
                        f"| edge={c['edge']*100:+.1f}pp")
                continue
            token, _routing = ab.login(config.ticket, config.punter_id or "2585240")
            if not token:
                self.stderr.write(f"❌ Login BetPlay falló ({owner.email}).")
                continue
            hechas = []
            # Opinión IA real (informativa): tope de llamadas por corrida/cuenta.
            ai_calls = 0
            ai_max = int(getattr(settings, 'LLM_REAL_MAX_CALLS', 8) or 8)
            for c in candidates:
                if disponibles <= 0:
                    break
                existe = AutoBet.objects.filter(
                    usuario=owner, evento_id=c['event_id'], mercado=c['market_label'],
                    estado__in=['OPEN', 'WIN', 'LOSE', 'VOID']).exists()
                if existe:
                    continue
                event_data = {'event_id': c['event_id'], 'path': []}
                ok, val = ab.validate_coupon(token, c['outcome'], event_data, stake)
                if not ok:
                    self.stderr.write(f"⚠️ Validate falló ({owner.email} · {c['seleccion']}): {str(val)[:100]}")
                    continue
                ok, resp = ab.place_bet(token, c['outcome'], event_data, stake)
                if not ok:
                    self.stderr.write(f"❌ Place falló ({owner.email} · {c['seleccion']}): {str(resp)[:100]}")
                    continue
                try:
                    with transaction.atomic():
                        nueva = AutoBet.objects.create(
                            usuario=owner, evento_id=c['event_id'],
                            home_team=c['home'].full_name, away_team=c['away'].full_name, liga='NBA',
                            start_time=c['start'], mercado=c['market_label'], seleccion=c['seleccion'],
                            linea=c['linea'], cuota=c['outcome']['odds_decimal'],
                            predicta_prob=round(c['p'] * 100, 2), predicta_prob_raw=round(c['p'] * 100, 2),
                            corners_predichos=round(c['p'] * 100, 2),
                            edge=round(c['edge'] * 100, 2), ev=round(c['ev'], 4),
                            coupon_ref=resp.get('coupon_ref'), bet_ref=resp.get('bet_ref'),
                            stake=stake, potential_payout=resp.get('potential_payout'),
                            estado='OPEN')
                        counter.apuestas_colocadas += 1
                        counter.save()
                        disponibles -= 1
                except Exception as e:
                    self.stderr.write(
                        f"⚠️ Apuesta colocada pero NO registrada ({owner.email} · {c['seleccion']}): {e}. "
                        f"coupon={resp.get('coupon_ref')} — detengo la corrida para evitar más duplicados."
                    )
                    break

                # Opinión IA INFORMATIVA (LLM_MODEL_REAL) — no bloquea ni filtra.
                # Sola si el partido ya está en la ventana T-X (config web);
                # si no, la pide después ask_llm_real_ventana.
                from auto_betting.llm_validator import llm_ventana_alcanzada
                if ai_calls < ai_max and llm_ventana_alcanzada(nueva.start_time):
                    ai_calls += 1
                    try:
                        from auto_betting.llm_validator import opinar_apuesta
                        ok_ia, why_ia = opinar_apuesta(nueva, {
                            'home': c['home'].full_name, 'away': c['away'].full_name,
                            'liga': 'NBA', 'mercado': c['market_label'], 'motor': 'nba',
                            'seleccion': c['seleccion'], 'linea': c['linea'],
                            'cuota': c['outcome']['odds_decimal'], 'prob': c['p'],
                            'ev': c['ev'], 'edge_pp': c['edge'] * 100,
                            'start_time': c['start'],
                        })
                        _tag_ia = ('🧠 IA APROBÓ' if ok_ia is True else
                                   ('🧠 IA RECHAZÓ' if ok_ia is False else '🧠 IA SIN RESPUESTA'))
                        self.stdout.write(
                            f"  {_tag_ia}: {c['away'].full_name} @ {c['home'].full_name} "
                            f"[{c['seleccion']}] — {(why_ia or '')[:110]}"
                        )
                    except Exception as e:
                        self.stderr.write(f"  (Opinión IA falló, no afecta la apuesta: {e})")

                colocadas_total += 1
                self.stdout.write(self.style.SUCCESS(
                    f"✅ {c['away'].full_name} @ {c['home'].full_name} | {c['market_label']} "
                    f"{c['seleccion']} @{c['outcome']['odds_decimal']:.2f} | coupon={resp.get('coupon_ref')}"))
                hechas.append({
                    'partido': f"{c['away'].full_name} @ {c['home'].full_name}",
                    'mercado': c['market_label'],
                    'seleccion': c['seleccion'],
                    'cuota': c['outcome']['odds_decimal'],
                    'stake_cop': stake / 1000,
                })
            if hechas:
                try:
                    from notificaciones.services import notificar_apuestas
                    wa = notificar_apuestas(owner, hechas, 'NBA')
                    self.stdout.write(f"📱 WhatsApp resumen a {owner.email}: {wa}")
                except Exception as e:
                    self.stderr.write(f"⚠️ WhatsApp resumen NBA falló: {e}")
        self.stdout.write(self.style.SUCCESS(
            f"\n🏁 NBA completado: {colocadas_total} "
            f"{'simuladas [DRY-RUN]' if not real else 'colocadas'}."))
