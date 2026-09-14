"""
Comando de management para capturar cuotas de cierre (closing odds) y calcular CLV.

Flujo:
1. Encuentra apuestas en HistorialApuesta con closing_odds IS NULL y event_start_date > now (partido no ha empezado).
2. Agrupa por event_id y hace fetch_market_odds() para los mercados relevantes.
3. Guarda OddsSnapshot por cada outcome_id seguido.
4. Para apuestas con event_start_date <= now (partido ya empezó), toma el último snapshot
   de ese outcome_id → lo escribe como closing_odds y calcula clv.
"""

import logging
from datetime import datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting.models import HistorialApuesta, OddsSnapshot
from auto_betting.services import fetch_market_odds

logger = logging.getLogger('auto_betting')

# Mercados prioritarios para snapshot
MERCADOS_PRIORITARIOS = [
    "Total de Tiros de Esquina",
    "Total de goles",
    "Total de tiros a puerta",
    "Total de Tiros (Resuelta usando Opta Data)",
    "Resultado Final",
    "Ambos Equipos Marcarán",
]


class Command(BaseCommand):
    help = "Captura cuotas de cierre (pre-partido) y calcula CLV para apuestas pendientes."

    def handle(self, *args, **options):
        now = timezone.now()

        # ── Fase 1: Capturar snapshots de apuestas cuyo partido aún no empieza ──
        pending = HistorialApuesta.objects.filter(
            closing_odds__isnull=True,
            event_start_date__gt=now,
            outcome_id__isnull=False,
        ).exclude(outcome_id=0)

        if pending.exists():
            self.stdout.write(f"📸 Fase 1: Capturando snapshots para {pending.count()} apuestas con partido pendiente...")
            # Agrupar por event_id para minimizar llamadas API
            by_event = {}
            for ap in pending:
                ev_id = ap.event_id
                if ev_id not in by_event:
                    by_event[ev_id] = []
                by_event[ev_id].append(ap)

            snapshots_creados = 0
            for ev_id, apuestas in by_event.items():
                # Determinar mercados a escanear para este evento
                mercados_a_buscar = set()
                for ap in apuestas:
                    mercado = ap.mercado or ""
                    # Mapear el mercado del historial al label de Kambi
                    for mp in MERCADOS_PRIORITARIOS:
                        if mp.lower() in mercado.lower() or mercado.lower() in mp.lower():
                            mercados_a_buscar.add(mp)
                            break
                    else:
                        # Si no coincide, buscar todos los prioritarios
                        mercados_a_buscar.update(MERCADOS_PRIORITARIOS[:3])

                for market_label in mercados_a_buscar:
                    try:
                        offers = fetch_market_odds(ev_id, market_label)
                    except Exception as e:
                        logger.warning(f"Error fetching odds event={ev_id} market={market_label}: {e}")
                        continue

                    for offer in offers:
                        # Solo guardar si el outcome_id corresponde a una apuesta pendiente
                        outcome_id = offer.get('outcome_id')
                        ap_match = [a for a in apuestas if a.outcome_id == outcome_id]
                        if not ap_match:
                            continue

                        OddsSnapshot.objects.update_or_create(
                            outcome_id=outcome_id,
                            captured_at=now,
                            defaults={
                                'event_id': ev_id,
                                'market': market_label,
                                'seleccion': offer.get('label', ''),
                                'linea': offer.get('line'),
                                'side': '',
                                'odds_decimal': offer.get('odds_decimal', 0),
                            },
                        )
                        snapshots_creados += 1

            self.stdout.write(f"  ✅ {snapshots_creados} snapshots guardados.")
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
            calculados = 0
            for ap in ready:
                # Tomar el último snapshot del outcome_id
                snap = OddsSnapshot.objects.filter(
                    outcome_id=ap.outcome_id
                ).order_by('-captured_at').first()

                if not snap:
                    continue

                closing = snap.odds_decimal
                played = ap.played_odds

                if closing and closing > 0 and played and played > 0:
                    clv = round((played / closing - 1.0) * 100, 2)
                else:
                    clv = None

                ap.closing_odds = closing
                ap.clv = clv
                ap.save(update_fields=['closing_odds', 'clv', 'actualizado'])
                calculados += 1

            self.stdout.write(f"  ✅ {calculados} apuestas con CLV calculado.")
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
