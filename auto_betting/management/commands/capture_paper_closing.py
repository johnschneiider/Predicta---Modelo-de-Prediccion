# -*- coding: utf-8 -*-
"""PAPERBET — captura cuotas de cierre para apuestas OPEN cuyo partido empieza pronto.
Solo consulta Kambi si hay algo por capturar (barato). Uso: manage.py capture_paper_closing
"""
from datetime import timedelta
from django.core.management.base import BaseCommand
from django.utils import timezone
from auto_betting.models import PaperBet
from auto_betting.services import fetch_market_odds


class Command(BaseCommand):
    help = 'Captura closing odds de apuestas paper OPEN'

    def handle(self, *args, **opts):
        now = timezone.now()
        ventana = now + timedelta(hours=2)
        # partidos que empiezan en <=2h (o ya empezaron hace <=30 min y aún no capturado)
        qs = PaperBet.objects.filter(estado='OPEN', closing_odds__isnull=True,
                                     start_time__isnull=False,
                                     start_time__lte=ventana,
                                     start_time__gte=now - timedelta(minutes=30))
        if not qs.exists():
            self.stdout.write('Nada por capturar.')
            return
        # agrupar por evento
        by_event = {}
        for b in qs:
            by_event.setdefault(b.evento_id, []).append(b)
        n = 0
        for eid, bets in by_event.items():
            markets = set(b.mercado for b in bets)
            all_odds = []
            for mk in markets:
                try:
                    all_odds.extend(fetch_market_odds(eid, mk))
                except Exception:
                    continue
            for b in bets:
                for o in all_odds:
                    sel_match = (o.get('outcome_label') or o.get('label')) == b.seleccion or o.get('label') == b.seleccion
                    linea_match = (o.get('line') == b.linea) if b.linea is not None else o.get('line') is None
                    if sel_match and linea_match:
                        b.closing_odds = o['odds_decimal']
                        b.save(update_fields=['closing_odds'])
                        n += 1
                        break
        self.stdout.write(f'Closing odds capturadas: {n}')
