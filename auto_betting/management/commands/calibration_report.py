"""
Reporte de calibración del auto-betting: compara la probabilidad declarada (P)
contra el win rate real por submercado (mercado+lado), usando AutoBet como
fuente (guarda la P calibrada exacta que vio la estrategia al apostar).

Uso:
    python manage.py calibration_report            # últimos 30 días
    python manage.py calibration_report --days 60
    python manage.py calibration_report --email admin@predicta.com.co

Alertas de descalibración (impresas en stdout y log):
    - FAIL: WR real < P media - 20pp con n >= 5 → la estrategia está mintiendo
      en ese submercado (como goles-over el 23-Ago: P ~55%, WR 13%).
    - WARN: WR real < P media - 10pp con n >= 5.
    - n < 5: se reporta pero sin veredicto (muestra insuficiente).
"""

import logging
from collections import defaultdict

from django.core.management.base import BaseCommand
from django.utils import timezone as django_timezone
from datetime import timedelta

from auto_betting.models import AutoBet, HistorialApuesta

logger = logging.getLogger('auto_betting')

FAIL_GAP_PP = 20.0
WARN_GAP_PP = 10.0
MIN_SAMPLE = 5


def _config_field_for(mercado, lado):
    """Mapea (mercado, lado) del reporte a un campo `*_enabled` de MarketFilterConfig."""
    m = (mercado or '').lower()
    l = (lado or '').lower()
    if 'goles' in m:
        base = 'goals'
    elif 'esquina' in m:
        base = 'corners'
    elif 'tiros' in m and 'puerta' in m:
        base = 'shots_on_target'
    elif m.startswith('total de tiros (resuelta'):
        # Remates totales: 'Total de Tiros (Resuelta usando Opta Data)'
        # (solo el mercado TOTAL; las variantes 'por parte de X' no mapean)
        base = 'remates'
    elif 'marcar' in m or 'ambos' in m:
        base = 'btts'
    else:
        return None
    side = {'over': 'over', 'under': 'under', 'sí': 'si', 'no': 'no'}.get(l)
    if not side:
        return None
    return f'{base}_{side}_enabled'


class Command(BaseCommand):
    help = "Reporte de calibración WR real vs P declarada por submercado"

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=30)
        parser.add_argument('--email', type=str, default=None)

    def _auto_disable_submarkets(self, keys):
        """
        P3b (2026-09-03): el monitor no solo alerta — deshabilita los
        submercados 🔴/🟡 en MarketFilterConfig para que la corrida de las
        06:10 no apueste sobre un submercado descalibrado.
        """
        from auto_betting.models import MarketFilterConfig
        try:
            cfg = MarketFilterConfig.get_solo()
        except Exception as e:
            logger.error(f'P3b: no se pudo leer MarketFilterConfig: {e}')
            return
        disabled = []
        for key in keys:
            mercado, _, lado = key.rpartition(' · ')
            field = _config_field_for(mercado, lado)
            if not field:
                logger.warning(f'P3b: sin mapeo de config para "{key}"')
                continue
            if getattr(cfg, field, False):
                setattr(cfg, field, False)
                disabled.append(field)
        if disabled:
            cfg.actualizado_por = (
                f'monitor calibración (P3b): {", ".join(disabled)} descalibrados'
            )
            cfg.save()
            msg = f'🛑 P3b: submercados deshabilitados automáticamente: {", ".join(disabled)}'
            self.stdout.write(self.style.ERROR('\n' + msg))
            logger.error(msg)

    def handle(self, *args, **options):
        days = options['days']
        email = options['email']
        since = django_timezone.now() - timedelta(days=days)

        qs = AutoBet.objects.filter(creado__gte=since)
        if email:
            qs = qs.filter(usuario__email=email)

        # AutoBet.estado nunca se actualiza con resultados (todo queda OPEN).
        # La fuente de verdad de resultados es HistorialApuesta (sincronizada
        # desde coupon/history.json de Kambi). Se enlaza por coupon_ref.
        historial = {}
        for h in HistorialApuesta.objects.filter(
            coupon_ref__in=[c for c in qs.values_list('coupon_ref', flat=True) if c],
            bet_status__in=['WON', 'LOST'],
        ):
            historial[h.coupon_ref] = h.bet_status

        buckets = defaultdict(lambda: {'n': 0, 'wins': 0, 'p_sum': 0.0, 'ev_sum': 0.0})
        matched = 0
        for a in qs:
            status = historial.get(a.coupon_ref)
            if not status:
                continue  # OPEN o sin sync todavía
            matched += 1
            p = a.predicta_prob or 0
            if p > 1:
                p = p / 100.0
            lado = (a.seleccion or '').split(' ')[0]
            key = f'{a.mercado} · {lado}'
            b = buckets[key]
            b['n'] += 1
            b['wins'] += 1 if status == 'WON' else 0
            b['p_sum'] += p
            b['ev_sum'] += a.ev or 0

        self.stdout.write(
            f"\n📊 CALIBRACIÓN AUTO-BETTING — últimos {days} días"
            + (f" — {email}" if email else " — todos los usuarios")
            + f" — {matched} asentadas"
        )
        self.stdout.write(
            f"{'SUBMERCADO':42s} {'n':>3s} {'WR real':>8s} {'P media':>8s} "
            f"{'gap':>7s} {'EV medio':>9s}  VEREDICTO"
        )
        self.stdout.write('-' * 95)

        alerts = []
        warns = []
        for key in sorted(buckets):
            b = buckets[key]
            n = b['n']
            wr = b['wins'] / n * 100
            p_avg = b['p_sum'] / n * 100
            gap = wr - p_avg
            ev_avg = b['ev_sum'] / n * 100

            if n < MIN_SAMPLE:
                verdict = '— (n<5)'
            elif gap <= -FAIL_GAP_PP:
                verdict = '🔴 DESCALIBRADO'
                alerts.append((key, n, wr, p_avg, gap))
            elif gap <= -WARN_GAP_PP:
                verdict = '🟡 SOSPECHOSO'
                warns.append((key, n, wr, p_avg, gap))
            elif gap >= WARN_GAP_PP:
                verdict = '🟢 mejor de lo dicho'
            else:
                verdict = '✅ calibrado'

            self.stdout.write(
                f"{key:42s} {n:3d} {wr:7.1f}% {p_avg:7.1f}% "
                f"{gap:+6.1f}pp {ev_avg:+8.1f}%  {verdict}"
            )

        self.stdout.write('-' * 95)
        total_n = sum(b['n'] for b in buckets.values())
        total_w = sum(b['wins'] for b in buckets.values())
        if total_n:
            self.stdout.write(
                f"{'TOTAL':42s} {total_n:3d} {total_w/total_n*100:7.1f}%"
            )

        if alerts:
            msg_lines = [
                f"🚨 ALERTA DE DESCALIBRACIÓN ({len(alerts)} submercados, "
                f"últimos {days} días):"
            ]
            for key, n, wr, p_avg, gap in alerts:
                msg_lines.append(
                    f"  • {key}: WR {wr:.0f}% vs P {p_avg:.0f}% "
                    f"({gap:+.0f}pp, n={n})"
                )
            if warns:
                msg_lines.append(
                    f"⚠️ Sospechosos (−10 a −20pp, vigilar): {len(warns)} submercados"
                )
                for key, n, wr, p_avg, gap in warns:
                    msg_lines.append(
                        f"  • {key}: WR {wr:.0f}% vs P {p_avg:.0f}% "
                        f"({gap:+.0f}pp, n={n})"
                    )
            msg = "\n".join(msg_lines)
            self.stdout.write(self.style.ERROR("\n" + msg))
            logger.error(msg)
            self._auto_disable_submarkets([x[0] for x in alerts] + [x[0] for x in warns])
        elif warns:
            # FIX 2026-08-31: los 🟡 (−10 a −20pp) también se reportan como
            # WARNING visible en logs (antes pasaban desapercibidos: tiros a
            # puerta sangró −15-18pp durante días sin ninguna alerta).
            msg_lines = [
                f"⚠️ Submercados sospechosos ({len(warns)}, últimos {days} días):"
            ]
            for key, n, wr, p_avg, gap in warns:
                msg_lines.append(
                    f"  • {key}: WR {wr:.0f}% vs P {p_avg:.0f}% "
                    f"({gap:+.0f}pp, n={n})"
                )
            msg = "\n".join(msg_lines)
            self.stdout.write(self.style.WARNING("\n" + msg))
            logger.warning(msg)
            self._auto_disable_submarkets([x[0] for x in warns])
        else:
            self.stdout.write(self.style.SUCCESS(
                "\n✅ Sin alertas de descalibración."
            ))
