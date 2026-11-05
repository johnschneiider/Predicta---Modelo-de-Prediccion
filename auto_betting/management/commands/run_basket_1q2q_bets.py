# -*- coding: utf-8 -*-
"""REAL: motor basket_1q2q — totales de baloncesto (1Q+2Q) en el descanso.

Coloca dinero real en BetPlay para las ligas de la whitelist, usando la misma
señal y los mismos parámetros que el paperbet (modo muestreo, solo UNDER).
El contador diario es propio del motor: no toca DailyCounter ni el cupo de
fútbol/NBA. Dry-run por defecto; dinero real con --real --yes.

Uso: manage.py run_basket_1q2q_bets [--dry-run] [--real --yes] [--email ...]
"""
from collections import Counter

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone as djtz
from django.utils.dateparse import parse_datetime

from auto_betting import basket_1q2q as bk
from auto_betting import services as ab
from auto_betting.management.commands.run_paper_bets_basket import (
    Command as PaperBasketCommand, modelo_de,
)
from auto_betting.models import AutoBet, AutoBetConfig, BasketModel

WHITELIST = frozenset({
    'japan/b2_league',
    'nba',
    'argentina/lnb',
    'austria/obl',
    'philippines/pba',
    'italy/serie_a2',
    'australia/nbl',
    'turkey/super_league',
})


class Command(BaseCommand):
    help = ('REAL: apuestas de totales de baloncesto en el descanso 2Q→3Q '
            '(motor basket_1q2q, solo ligas whitelist). Dry-run por defecto.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Simula sin colocar (comportamiento por defecto)')
        parser.add_argument('--real', action='store_true',
                            help='Colocar apuestas reales')
        parser.add_argument('--yes', action='store_true',
                            help='Confirmación doble para dinero real')
        parser.add_argument('--validate-only', action='store_true',
                            help='Valida el cupón con la cuenta real, sin colocar')
        parser.add_argument('--max-bets', type=int, default=0,
                            help='Tope de apuestas en esta corrida (0=sin tope)')
        parser.add_argument('--email', type=str, default=None,
                            help='Solo este usuario (email)')

    def handle(self, *args, **options):
        real = options['real'] and not options['dry_run']
        if real and not options['yes']:
            self.stderr.write('⛔ Para dinero real se requieren --real y --yes.')
            return
        validate_only = options['validate_only']
        if validate_only and not real:
            self.stderr.write('⛔ --validate-only requiere --real --yes.')
            return
        max_bets = max(0, int(options['max_bets'] or 0))
        self.stdout.write(
            f"\n{'🧪 DRY-RUN' if not real else '💵 REAL'} — "
            f"Basket 1Q+2Q (motor {bk.MOTOR})"
            f"{' · SOLO VALIDACIÓN' if validate_only else ''}")

        try:
            partidos = bk.fetch_live_partidos()
        except bk.ErrorBasket as exc:
            self.stderr.write(f'Kambi: {exc}')
            return

        en_ventana = [
            p for p in partidos
            if bk.en_ventana_descanso(p)
            and p.clave_liga not in bk.NO_SON_LIGAS
            and p.clave_liga in WHITELIST
        ]
        self.stdout.write(f'Partidos en ventana whitelist: {len(en_ventana)}')
        if not en_ventana:
            return

        modelos = {m.liga: modelo_de(m) for m in BasketModel.objects.all()}
        global_m = modelos.pop(bk.CLAVE_GLOBAL, None)
        cache_modelos = {}
        candidatos = []
        motivos = Counter()
        for p in en_ventana:
            modelo = PaperBasketCommand._modelo_para(
                p.clave_liga, modelos, global_m, cache_modelos)
            ev = bk.evaluar(p, modelo)
            if not ev['ok']:
                motivos[ev['motivo']] += 1
                continue
            if ev['lado'] not in bk.LADOS_PAPER_ACTIVOS:
                motivos[f"lado {ev['lado']} no activo"] += 1
                continue
            if not p.betoffer_id or not p.outcome_under_id:
                motivos['sin IDs de oferta/outcome'] += 1
                continue
            if p.outcome_under_status != 'OPEN':
                motivos['UNDER no OPEN'] += 1
                continue
            candidatos.append((p, ev))

        self.stdout.write(f'Candidatos: {len(candidatos)}')
        for motivo, n in motivos.most_common():
            self.stdout.write(f'  · {motivo}: {n}')
        for p, ev in candidatos:
            self.stdout.write(
                f"  · {p.clave_liga}: {p.local} vs {p.visitante} — "
                f"{bk.SEL_UNDER} {p.linea:g} @ {ev['cuota']:.2f} "
                f"(P={ev['prob'] * 100:.1f}% EV={ev['ev'] * 100:+.1f}% "
                f"Δ={ev['diferencia']:+.1f})")
        if not candidatos:
            return

        configs = AutoBetConfig.objects.filter(activo=True).select_related('usuario')
        if options['email']:
            configs = configs.filter(usuario__email=options['email'])
        if not configs:
            self.stdout.write('Sin configuraciones activas.')
            return

        from capital.services import resolve_stake

        colocadas_total = 0
        validadas_total = 0
        for config in configs:
            if max_bets and colocadas_total >= max_bets:
                break
            owner = config.usuario
            hoy = djtz.localdate()
            usadas = AutoBet.objects.filter(
                usuario=owner, mercado=bk.MERCADO, creado__date=hoy).count()
            disponibles = config.max_apuestas_diarias - usadas
            if disponibles <= 0:
                self.stdout.write(
                    f"⛔ {owner.email}: cupo basket alcanzado "
                    f"({usadas}/{config.max_apuestas_diarias}).")
                continue
            stake, motivo = resolve_stake(config)
            if stake is None:
                self.stdout.write(f"⛔ {owner.email}: sin stake ({motivo}).")
                continue
            self.stdout.write(
                f"\n👤 {owner.email} | stake {stake / 1000:,.0f} COP [{motivo}] "
                f"| cupo basket {usadas}/{config.max_apuestas_diarias}")

            if not real:
                for p, ev in candidatos:
                    if disponibles <= 0:
                        break
                    self.stdout.write(
                        f"🧪 [DRY-RUN] Apostaría: {p.local} vs {p.visitante} — "
                        f"{bk.SEL_UNDER} {p.linea:g} @ {ev['cuota']:.2f} "
                        f"| outcome_id={p.outcome_under_id} "
                        f"betoffer_id={p.betoffer_id}")
                    disponibles -= 1
                continue

            token, _routing = ab.login(config.ticket, config.punter_id or '2585240')
            if not token:
                self.stderr.write(f"❌ Login BetPlay falló ({owner.email}).")
                continue

            hechas = []
            for p, ev in candidatos:
                if disponibles <= 0:
                    break
                if AutoBet.objects.filter(
                        usuario=owner, evento_id=p.evento_id, mercado=bk.MERCADO,
                        estado__in=['OPEN', 'WIN', 'LOSE', 'VOID']).exists():
                    continue
                inicio = parse_datetime((p.inicio or '').replace('Z', '+00:00'))
                if inicio is None:
                    self.stderr.write(
                        f"⚠️ Sin start_time: {p.local} vs {p.visitante}")
                    continue
                outcome = {
                    'betoffer_id': p.betoffer_id,
                    'outcome_id': p.outcome_under_id,
                    'label': (p.outcome_under_label
                              or f'{bk.SEL_UNDER} {p.linea:g}'),
                    'odds': p.outcome_under_odds,
                    'odds_decimal': ev['cuota'],
                    'line': p.linea,
                    'type': 'OT_UNDER',
                    'status': p.outcome_under_status,
                    'cashout_status': p.outcome_under_cashout,
                    'display_order': p.outcome_under_display_order,
                    'criterion': p.criterion,
                    'betoffer_tags': p.betoffer_tags,
                    'event_id': p.evento_id,
                    'is_live': True,
                }
                if not outcome['odds']:
                    self.stderr.write(
                        f"⚠️ Sin odds raw: {p.local} vs {p.visitante}")
                    continue
                event_data = {'event_id': p.evento_id, 'path': p.event_path}
                ok, val = ab.validate_coupon(token, outcome, event_data, stake)
                if not ok:
                    self.stderr.write(
                        f"⚠️ Validate falló ({owner.email} · "
                        f"{p.local} vs {p.visitante}): {str(val)[:120]}")
                    continue
                if validate_only:
                    validadas_total += 1
                    self.stdout.write(self.style.SUCCESS(
                        f"✅ Validación OK (sin colocar): {p.local} vs "
                        f"{p.visitante} | {bk.SEL_UNDER} {p.linea:g} "
                        f"@ {ev['cuota']:.2f}"))
                    break
                ok, resp = ab.place_bet(token, outcome, event_data, stake)
                if not ok:
                    self.stderr.write(
                        f"❌ Place falló ({owner.email} · "
                        f"{p.local} vs {p.visitante}): {str(resp)[:120]}")
                    continue
                try:
                    fair = None
                    if p.cuota_over and p.cuota_under:
                        io = 1.0 / p.cuota_over
                        iu = 1.0 / p.cuota_under
                        fair = iu / (io + iu)
                    edge = ((ev['prob'] - fair) * 100) if fair else (ev['ev'] * 100)
                    with transaction.atomic():
                        AutoBet.objects.create(
                            usuario=owner,
                            evento_id=p.evento_id,
                            home_team=p.local,
                            away_team=p.visitante,
                            liga=p.liga_nombre or p.clave_liga,
                            start_time=inicio,
                            mercado=bk.MERCADO,
                            seleccion=bk.SEL_UNDER,
                            linea=p.linea,
                            cuota=ev['cuota'],
                            corners_predichos=round(ev['prob'] * 100, 2),
                            predicta_prob=round(ev['prob'] * 100, 2),
                            predicta_prob_raw=round(ev['prob'] * 100, 2),
                            edge=round(edge, 2),
                            ev=round(ev['ev'], 4),
                            coupon_ref=resp.get('coupon_ref'),
                            bet_ref=resp.get('bet_ref'),
                            stake=stake,
                            potential_payout=resp.get('potential_payout'),
                            estado='OPEN',
                        )
                        disponibles -= 1
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(
                        f"⚠️ Apuesta colocada pero NO registrada ({owner.email} · "
                        f"{p.local} vs {p.visitante}): {exc}. "
                        f"coupon={resp.get('coupon_ref')} — detengo la corrida.")
                    break
                colocadas_total += 1
                delay = ' ⏳ delay' if resp.get('delay_pending') else ''
                self.stdout.write(self.style.SUCCESS(
                    f"✅ {p.local} vs {p.visitante} | {bk.MERCADO} "
                    f"{bk.SEL_UNDER} {p.linea:g} @ {ev['cuota']:.2f} | "
                    f"coupon={resp.get('coupon_ref')}{delay}"))
                hechas.append({
                    'partido': f"{p.local} vs {p.visitante}",
                    'mercado': bk.MERCADO,
                    'seleccion': f"{bk.SEL_UNDER} {p.linea:g}",
                    'cuota': ev['cuota'],
                    'stake_cop': stake / 1000,
                })
                if max_bets and colocadas_total >= max_bets:
                    self.stdout.write(
                        f"Tope de corrida alcanzado ({max_bets}).")
                    break

            if hechas:
                try:
                    from notificaciones.services import notificar_apuestas
                    wa = notificar_apuestas(owner, hechas, 'Basket 1Q+2Q')
                    self.stdout.write(
                        f"📱 WhatsApp resumen a {owner.email}: {wa}")
                except Exception as exc:  # noqa: BLE001
                    self.stderr.write(
                        f"⚠️ WhatsApp resumen basket falló: {exc}")

        if validate_only:
            self.stdout.write(self.style.SUCCESS(
                f"\n🏁 Basket 1Q+2Q: {validadas_total} validación(es) OK; "
                f"no se colocó dinero."))
        else:
            self.stdout.write(self.style.SUCCESS(
                f"\n🏁 Basket 1Q+2Q completado: {colocadas_total} "
                f"{'simuladas [DRY-RUN]' if not real else 'colocadas'}."))
