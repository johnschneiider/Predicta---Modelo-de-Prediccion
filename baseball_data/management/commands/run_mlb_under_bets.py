"""
Auto-betting MLB: apuesta TOTAL DE CARRERAS — MENOS DE (under) contra BetPlay/Kambi.

Selección:
- Modelo v1 (producción, validado como el mejor): P(under) del baseline Poisson.
- Mercado: "Total de carreras" de Kambi; devig over/under por línea.
- Candidata si edge = P(modelo) − P(fair devigada) >= --min-edge (default 3pp).
- --days (default lun,jue,vie,dom): días en que aplica la estrategia.
  Validado: subset lun/jue/vie/dom OOS 2024-25 +8,5% (p=0,007 corregido por 4-de-7).
- Toma la mejor línea (mayor edge) por partido, hasta --max apuestas.

Modos:
- default: DRY-RUN (no toca BetPlay ni la BD).
- --real --yes: valida y coloca de verdad con el ticket del usuario (stake vía capital).
"""
from datetime import datetime, timedelta, timezone

import requests
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction

from baseball_data.views import _full_stats, KAMBI_BASE, KAMBI_HEADERS, KAMBI_PARAMS
from baseball_data.baseline import predict_matchup
from baseball_data.models import BaseballTeam

TOTAL_LINES = ('5.5', '6.5', '7.5', '8.5', '9.5', '10.5', '11.5')


class Command(BaseCommand):
    help = "Auto-betting MLB: under de total de carreras (dry-run por defecto)"

    def add_arguments(self, parser):
        parser.add_argument('--real', action='store_true', help='Colocar apuestas reales')
        parser.add_argument('--yes', action='store_true', help='Confirmación doble para dinero real')
        parser.add_argument('--user', type=str, default='admin', help='Usuario (username o email)')
        parser.add_argument('--min-edge', type=float, default=0.03, help='Edge mínimo (default 0.03)')
        parser.add_argument('--max', type=int, default=3, help='Máximo de apuestas a colocar')
        parser.add_argument('--only-thursday', action='store_true', help='Solo jueves (alias de --days jue)')
        parser.add_argument('--days', type=str, default='lun,jue,vie,dom',
                            help="Días activos (default: lun,jue,vie,dom; usar 'all' para todos)")
        parser.add_argument('--horas', type=int, default=24,
                            help='Horizonte máximo en horas para apostar (default 24)')

    def handle(self, *args, **options):
        from auto_betting import services as ab

        real = options['real']
        if real and not options['yes']:
            self.stderr.write("⛔ Para dinero real se requieren --real y --yes.")
            return

        day_names = ['lun', 'mar', 'mié', 'jue', 'vie', 'sáb', 'dom']
        if options['only_thursday']:
            active_days = {3}
        elif options['days'].strip().lower() == 'all':
            active_days = set(range(7))
        else:
            active_days = set()
            for part in options['days'].lower().replace(';', ',').split(','):
                part = part.strip()
                if part in day_names:
                    active_days.add(day_names.index(part))
                elif part.isdigit() and 0 <= int(part) <= 6:
                    active_days.add(int(part))
                else:
                    self.stderr.write(f"Día no reconocido: '{part}'")
                    return
        today_wd = datetime.now(timezone.utc).astimezone().weekday()
        if today_wd not in active_days:
            self.stdout.write(self.style.WARNING(
                f"⏸️  Hoy es {day_names[today_wd]}: fuera de los días activos "
                f"({', '.join(day_names[d] for d in sorted(active_days))}) → sin apuestas."))
            return

        # 1) partidos MLB próximos en BetPlay
        r = requests.get(f"{KAMBI_BASE}/listView/baseball.json", params=KAMBI_PARAMS,
                         headers=KAMBI_HEADERS, timeout=20)
        r.raise_for_status()
        events = []
        descartados = 0
        horizonte = datetime.now(timezone.utc) + timedelta(hours=options['horas'])
        for e in r.json().get('events', []):
            ev = e.get('event', {})
            keys = [p.get('termKey', '') for p in ev.get('path', [])]
            if 'mlb' in keys and ev.get('state') == 'NOT_STARTED':
                try:
                    _start = datetime.fromisoformat(str(ev.get('start', '')).replace('Z', '+00:00'))
                except Exception:
                    continue
                if _start > horizonte:
                    descartados += 1
                    continue
                events.append(ev)
        self.stdout.write(f"Partidos MLB próximos: {len(events)} "
                          f"(descartados >{options['horas']}h: {descartados})")
        if not events:
            self.stdout.write("No hay partidos MLB próximos en BetPlay.")
            return

        teams = {t.name: t for t in BaseballTeam.objects.all()}
        stats = _full_stats()

        picks = []
        for ev in events:
            ht = teams.get(ev.get('homeName', ''))
            at = teams.get(ev.get('awayName', ''))
            if not ht or not at:
                continue
            pred = predict_matchup(stats, ht.id, at.id)
            offers = ab.fetch_market_odds(ev['id'], ["Total de carreras"])
            by_line = {}
            for o in offers:
                if o.get('line') is None:
                    continue
                by_line.setdefault(round(float(o['line']), 1), {})[o.get('type')] = o
            for line, sides in by_line.items():
                key = f"{line:.1f}"
                if key not in pred['total_line_probs']:
                    continue
                over, under = sides.get('OT_OVER'), sides.get('OT_UNDER')
                if not over or not under:
                    continue
                do, du = over['odds_decimal'], under['odds_decimal']
                fair_u = (1 / du) / (1 / du + 1 / do)
                p_u = pred['total_line_probs'][key]['under']
                edge = p_u - fair_u
                if edge >= options['min_edge']:
                    picks.append({
                        'event_id': ev['id'], 'path': ev.get('path', []),
                        'home': ev.get('homeName'), 'away': ev.get('awayName'),
                        'start': ev.get('start'),
                        'line': line, 'odds': du, 'p': p_u, 'fair': fair_u,
                        'edge': edge, 'ev': p_u * du - 1,
                        'outcome': under,
                    })

        picks.sort(key=lambda x: -x['edge'])
        picks = picks[:options['max']]

        self.stdout.write(f"\n{'🧪 DRY-RUN' if not real else '💵 REAL'} — MLB under de totales "
                          f"| edge>= {options['min_edge']:.0%} | {len(events)} partidos en BetPlay\n")
        for i, p in enumerate(picks, 1):
            self.stdout.write(
                f"{i}. {p['away']} @ {p['home']} | Menos de {p['line']} @{p['odds']:.2f} "
                f"| P={p['p']*100:.1f}% fair={p['fair']*100:.1f}% edge={p['edge']*100:+.1f}pp "
                f"EV={p['ev']*100:+.1f}% | inicio {p['start']}")

        if not picks:
            self.stdout.write("Sin candidatas con ese edge.")
            return
        if not real:
            self.stdout.write(self.style.WARNING(
                "\n🧪 DRY-RUN: no se tocó BetPlay. Para ejecutar de verdad: --real --yes"))
            return

        # ── ejecución real ──
        from auto_betting.models import AutoBet, AutoBetConfig, DailyCounter
        from capital.services import resolve_stake

        User = get_user_model()
        user = User.objects.filter(username=options['user']).first() or \
            User.objects.filter(email=options['user']).first()
        if not user:
            self.stderr.write(f"Usuario {options['user']} no encontrado.")
            return
        config = AutoBetConfig.objects.filter(usuario=user).first()
        if not config or not config.ticket:
            self.stderr.write(f"Sin AutoBetConfig/ticket para {user}.")
            return

        stake_kambi, motivo = resolve_stake(config)
        if stake_kambi is None:
            self.stderr.write(f"⛔ Sin stake disponible ({motivo}).")
            return
        self.stdout.write(f"Usuario {user} | stake {stake_kambi/1000:,.0f} COP [{motivo}]")

        token, routing = ab.login(config.ticket, config.punter_id or "2585240")
        if not token:
            self.stderr.write("❌ Login BetPlay falló (ticket vencido?).")
            return

        colocadas = 0
        hechas = []
        # Opinión IA real (informativa): tope de llamadas por corrida.
        ai_calls = 0
        ai_max = int(getattr(settings, 'LLM_REAL_MAX_CALLS', 8) or 8)
        for p in picks:
            # Dedup (2026-10-03): no repetir la misma apuesta en corridas
            # sucesivas (el cron corre cada 4h; la cuota puede cambiar pero la
            # apuesta ya colocada para ese evento+mercado no se repite).
            existe = AutoBet.objects.filter(
                usuario=user, evento_id=p['event_id'], mercado='Total de carreras',
                estado__in=['OPEN', 'WIN', 'LOSE', 'VOID']).exists()
            if existe:
                self.stdout.write(
                    f"⏭️ Ya apostado: {p['away']} @ {p['home']} — Total de carreras (skip)")
                continue
            event_data = {'event_id': p['event_id'], 'path': p['path']}
            ok, val = ab.validate_coupon(token, p['outcome'], event_data, stake_kambi)
            if not ok:
                logger_msg = val.get('message') if isinstance(val, dict) else val
                self.stderr.write(f"⚠️ Validate falló ({p['home']}): {str(logger_msg)[:120]}")
                continue
            ok, resp = ab.place_bet(token, p['outcome'], event_data, stake_kambi)
            if not ok:
                self.stderr.write(f"❌ Place falló ({p['home']}): {str(resp)[:120]}")
                continue
            with transaction.atomic():
                nueva = AutoBet.objects.create(
                    usuario=user, evento_id=p['event_id'],
                    home_team=p['home'], away_team=p['away'], liga='MLB',
                    start_time=p['start'], mercado='Total de carreras',
                    seleccion=f"Menos de {p['line']}", linea=p['line'],
                    cuota=p['odds'], corners_predichos=p['p'] * 100,
                    predicta_prob=round(p['p'] * 100, 2), predicta_prob_raw=round(p['p'] * 100, 2),
                    edge=round(p['edge'] * 100, 2), ev=round(p['ev'], 4),
                    coupon_ref=resp.get('coupon_ref'), bet_ref=resp.get('bet_ref'),
                    stake=stake_kambi, potential_payout=resp.get('potential_payout'),
                    estado='OPEN')
                counter, _ = DailyCounter.objects.get_or_create(usuario=user, fecha=datetime.now(timezone.utc).date())
                counter.apuestas_colocadas += 1
                counter.save()

            # Opinión IA INFORMATIVA (LLM_MODEL_REAL) — no bloquea ni filtra.
            # Sola si el partido ya está en la ventana T-X (config web); si no,
            # la pide después ask_llm_real_ventana.
            from auto_betting.llm_validator import llm_ventana_alcanzada
            if ai_calls < ai_max and llm_ventana_alcanzada(nueva.start_time):
                ai_calls += 1
                try:
                    from auto_betting.llm_validator import opinar_apuesta
                    ok_ia, why_ia = opinar_apuesta(nueva, {
                        'home': p['home'], 'away': p['away'], 'liga': 'MLB',
                        'mercado': 'Total de carreras', 'motor': 'mlb',
                        'seleccion': f"Menos de {p['line']}", 'linea': p['line'],
                        'cuota': p['odds'], 'prob': p['p'], 'ev': p['ev'],
                        'edge_pp': p['edge'] * 100, 'start_time': p['start'],
                    })
                    _tag_ia = ('🧠 IA APROBÓ' if ok_ia is True else
                               ('🧠 IA RECHAZÓ' if ok_ia is False else '🧠 IA SIN RESPUESTA'))
                    self.stdout.write(
                        f"  {_tag_ia}: {p['away']} @ {p['home']} "
                        f"[Menos de {p['line']}] — {(why_ia or '')[:110]}"
                    )
                except Exception as e:
                    self.stderr.write(f"  (Opinión IA falló, no afecta la apuesta: {e})")

            colocadas += 1
            self.stdout.write(self.style.SUCCESS(
                f"✅ {p['away']} @ {p['home']} Menos de {p['line']} @{p['odds']:.2f} "
                f"| coupon={resp.get('coupon_ref')}"))
            hechas.append({
                'partido': f"{p['away']} @ {p['home']}",
                'mercado': 'Total de carreras',
                'seleccion': f"Menos de {p['line']}",
                'cuota': p['odds'],
                'stake_cop': stake_kambi / 1000,
            })
        self.stdout.write(self.style.SUCCESS(f"\n🏁 {colocadas} apuestas colocadas."))
        if hechas:
            try:
                from notificaciones.services import notificar_apuestas
                wa = notificar_apuestas(user, hechas, 'MLB')
                self.stdout.write(f"📱 WhatsApp resumen a {user.email}: {wa}")
            except Exception as e:
                self.stderr.write(f"⚠️ WhatsApp resumen MLB falló: {e}")
