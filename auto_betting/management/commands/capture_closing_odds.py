"""
Comando de management para capturar cuotas de cierre (closing odds) y calcular CLV.

Flujo:
1. Fase 1: eventos con apuestas pendientes (HistorialApuesta sin cierre y/o AutoBet
   OPEN, que existe desde la colocación aunque el sync llegue tarde). Se fetchea el
   mercado por su label real de Kambi y se guardan snapshots de TODOS los outcomes:
   el del outcome apostado (con historial) y el resto como referencia actualizable
   (una fila por outcome, útil para el fallback por lado/línea).
2. Fase 2: apuestas con partido ya iniciado. Último snapshot por outcome_id; si no
   existe, fallback por (evento+mercado+lado+línea) o (evento+mercado+selección).
   Sin dato → clv = 0 (irrecuperable, se marca para que la columna tenga valor).
"""

import logging
from datetime import datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting.models import HistorialApuesta, OddsSnapshot, AutoBet
from auto_betting.services import fetch_market_odds

logger = logging.getLogger('auto_betting')


class Command(BaseCommand):
    help = "Captura cuotas de cierre (pre-partido) y calcula CLV para apuestas pendientes."

    def handle(self, *args, **options):
        now = timezone.now()

        # ── Fase 1: Capturar snapshots de eventos con apuestas pendientes ──
        pending = HistorialApuesta.objects.filter(
            closing_odds__isnull=True,
            event_start_date__gt=now,
            outcome_id__isnull=False,
        ).exclude(outcome_id=0)

        by_event = {}
        for ap in pending.only('event_id', 'mercado', 'outcome_id'):
            info = by_event.setdefault(ap.event_id, {'markets': set(), 'outcomes': set()})
            if ap.mercado:
                info['markets'].add(ap.mercado)
            if ap.outcome_id:
                info['outcomes'].add(ap.outcome_id)

        # AutoBet OPEN de partidos aún no iniciados: existe desde la colocación,
        # aunque el sync a HistorialApuesta llegue después del pitido.
        for b in AutoBet.objects.filter(estado='OPEN', start_time__gt=now).only('evento_id', 'mercado'):
            if not b.evento_id or not b.mercado:
                continue
            info = by_event.setdefault(b.evento_id, {'markets': set(), 'outcomes': set()})
            info['markets'].add(b.mercado)

        if by_event:
            self.stdout.write(f"📸 Fase 1: {len(by_event)} eventos con apuestas pendientes...")
            snapshots_creados = referencias = 0
            for ev_id, info in by_event.items():
                for market_label in info['markets']:
                    try:
                        offers = fetch_market_odds(ev_id, market_label)
                    except Exception as e:
                        logger.warning(f"Error fetching odds event={ev_id} market={market_label}: {e}")
                        continue

                    for offer in offers:
                        outcome_id = offer.get('outcome_id')
                        if not outcome_id:
                            continue
                        datos = {
                            'event_id': ev_id,
                            'market': market_label,
                            'seleccion': offer.get('label', ''),
                            'linea': offer.get('line'),
                            'side': '',
                            'odds_decimal': offer.get('odds_decimal', 0),
                        }
                        if outcome_id in info['outcomes']:
                            # Outcome apostado: historial de snapshots (como antes)
                            OddsSnapshot.objects.update_or_create(
                                outcome_id=outcome_id, captured_at=now, defaults=datos)
                            snapshots_creados += 1
                        else:
                            # Referencia: una fila por outcome, actualizada al vuelo
                            upd = OddsSnapshot.objects.filter(outcome_id=outcome_id).update(
                                captured_at=now, **datos)
                            if not upd:
                                OddsSnapshot.objects.create(outcome_id=outcome_id, **datos)
                            referencias += 1

            self.stdout.write(f"  ✅ {snapshots_creados} snapshots de apuestas + {referencias} referencias actualizadas.")
        else:
            self.stdout.write("📸 Fase 1: No hay apuestas pendientes de snapshot.")

        # ── Fase 2: Calcular closing_odds y CLV para apuestas cuyo partido ya empezó ──
        ready = HistorialApuesta.objects.filter(
            closing_odds__isnull=True,
            event_start_date__lte=now,
            outcome_id__isnull=False,
        ).exclude(outcome_id=0)

        if ready.exists():
            self.stdout.write(f"📊 Fase 2: Calculando CLV para {ready.count()} apuestas con partido iniciado...")
            calculados = sin_dato = 0
            for ap in ready:
                # Último snapshot del outcome apostado
                snap = OddsSnapshot.objects.filter(
                    outcome_id=ap.outcome_id
                ).order_by('-captured_at').first()

                if not snap:
                    # Fallback: mismo evento+mercado+lado+línea (o selección exacta)
                    base = OddsSnapshot.objects.filter(
                        event_id=ap.event_id, market=ap.mercado or '')
                    sel = ap.seleccion or ''
                    low = sel.lower()
                    if low.startswith('más de') or low.startswith('menos de'):
                        lado = 'Más de' if low.startswith('más') else 'Menos de'
                        snap = base.filter(
                            seleccion__istartswith=lado, linea=ap.linea
                        ).order_by('-captured_at').first()
                    else:
                        snap = base.filter(seleccion=sel).order_by('-captured_at').first()

                if not snap:
                    # Irrecuperable: se marca 0 para que la columna tenga valor
                    if ap.clv != 0:
                        ap.clv = 0.0
                        ap.save(update_fields=['clv', 'actualizado'])
                    sin_dato += 1
                    continue

                closing = snap.odds_decimal
                played = ap.played_odds

                if closing and closing > 0 and played and played > 0:
                    clv = round((played / closing - 1.0) * 100, 2)
                else:
                    clv = 0.0

                ap.closing_odds = closing
                ap.clv = clv
                ap.save(update_fields=['closing_odds', 'clv', 'actualizado'])
                calculados += 1

            self.stdout.write(f"  ✅ {calculados} CLV calculados | {sin_dato} sin dato → clv=0.")
        else:
            self.stdout.write("📊 Fase 2: No hay apuestas listas para CLV.")

        # Resumen
        total_con_clv = HistorialApuesta.objects.exclude(clv__isnull=True).count()
        total_sin_clv = HistorialApuesta.objects.filter(clv__isnull=True).count()
        self.stdout.write(
            self.style.SUCCESS(
                f"\n🏁 Captura completada: {total_con_clv} con CLV, {total_sin_clv} sin CLV."
            )
        )
