# -*- coding: utf-8 -*-
"""Pide la opinión IA (LLM_MODEL_REAL, gpt-5.6-luna) a apuestas reales AutoBet
que aún no tienen veredicto.

Replica lo que hacen run_auto_bets/run_nba_bets/run_mlb_under_bets al colocar:
llama a `auto_betting.llm_validator.opinar_apuesta` por cada fila. Fail-closed:
si el LLM falla, la fila queda sin veredicto (llm_verdict=None) y se reporta.

Uso:
  manage.py ask_llm_real --ventana               # programado (cada 5 min): una
                                                 # sola consulta por partido al
                                                 # alcanzar T-X (LlmRealConfig)
  manage.py ask_llm_real --dry-run                # solo listar objetivos
  manage.py ask_llm_real --max 8                 # opinar sobre las 8 próximas
  manage.py ask_llm_real --ids 1640,1641,1642    # filas concretas
  manage.py ask_llm_real --include-past --max 50 # incluye partidos ya iniciados
"""
import time
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting.llm_validator import opinar_apuesta
from auto_betting.models import AutoBet, LlmRealConfig


def _motor_de(liga):
    l = (liga or '').upper()
    if 'NBA' in l:
        return 'nba'
    if 'MLB' in l:
        return 'mlb'
    return ''


class Command(BaseCommand):
    help = ("Pide opinión IA (LLM_MODEL_REAL) a apuestas reales pendientes "
            "que no tienen veredicto IA. No bloquea ni filtra: solo registra.")

    def add_arguments(self, parser):
        parser.add_argument('--ids', help='IDs AutoBet concretos, separados por coma')
        parser.add_argument('--max', type=int, default=None,
                            help='Tope de llamadas en esta corrida (default LLM_REAL_MAX_CALLS)')
        parser.add_argument('--include-past', action='store_true',
                            help='Incluir apuestas cuyo partido ya inició (default: solo futuras)')
        parser.add_argument('--re-ask', action='store_true',
                            help='Re-consultar también filas que YA tienen veredicto (lo sobreescribe)')
        parser.add_argument('--dry-run', action='store_true', help='Solo listar objetivos')
        parser.add_argument('--sleep', type=float, default=2.0,
                            help='Segundos de pausa entre llamadas (default 2)')
        parser.add_argument('--ventana', action='store_true',
                            help='Modo programado (cada 5 min): apuestas reales '
                                 'OPEN sin opinión que ya entraron en la ventana '
                                 'T-X de LlmRealConfig. Ignora --ids/--re-ask.')

    def handle(self, *args, **opts):
        max_calls = opts['max']
        if max_calls is None:
            max_calls = int(getattr(settings, 'LLM_REAL_MAX_CALLS', 8) or 8)

        if opts['ventana']:
            # Una sola consulta por partido: solo filas aún sin opinión que ya
            # alcanzaron el T-X configurado en la página de umbrales.
            cfg = LlmRealConfig.get_solo()
            if not cfg.enabled:
                self.stdout.write(
                    'ask_llm_real: opinión IA desactivada en umbrales — nada que hacer.')
                return
            ahora = timezone.now()
            qs = (AutoBet.objects
                  .filter(estado='OPEN', llm_asked_at__isnull=True,
                          start_time__gt=ahora,
                          start_time__lte=ahora + timedelta(
                              minutes=cfg.anticipacion_min))
                  .order_by('start_time', 'id'))
            self.stdout.write(
                f"Modo ventana: T-{cfg.anticipacion_min} · objetivos {qs.count()}")
        else:
            qs = AutoBet.objects.filter(estado='OPEN')
            if not opts['re_ask']:
                qs = qs.filter(llm_verdict__isnull=True)
            if opts['ids']:
                ids = [int(x) for x in str(opts['ids']).split(',') if x.strip().isdigit()]
                qs = qs.filter(id__in=ids)
            if not opts['include_past']:
                qs = qs.filter(start_time__gte=timezone.now())
            qs = qs.order_by('start_time', 'id')

        total = qs.count()
        self.stdout.write(f"Objetivos: {total} | tope de llamadas: {max_calls}")

        if opts['dry_run']:
            for b in qs:
                self.stdout.write(f"  #{b.id} {b.start_time} | {b.home_team} vs {b.away_team}"
                                  f" | {b.mercado} | {b.seleccion} | {b.usuario.email}")
            self.stdout.write(self.style.WARNING("DRY-RUN: no se llamó al LLM."))
            return

        calls = ok_n = no_n = err_n = 0
        for b in qs:
            if calls >= max_calls:
                self.stdout.write(self.style.WARNING(
                    f"Tope de {max_calls} llamadas alcanzado; quedaron objetivos sin opinar."))
                break
            calls += 1
            bet = {
                'home': b.home_team, 'away': b.away_team, 'liga': b.liga,
                'mercado': b.mercado, 'motor': _motor_de(b.liga),
                'seleccion': b.seleccion, 'linea': b.linea,
                'cuota': b.cuota, 'prob': (b.predicta_prob or 0) / 100.0,
                'ev': b.ev, 'edge_pp': b.edge,
                'start_time': b.start_time,
            }
            ok, why = opinar_apuesta(b, bet)
            if ok is True:
                ok_n += 1
                tag = 'IA APROBÓ'
            elif ok is False:
                no_n += 1
                tag = 'IA RECHAZÓ'
            else:
                err_n += 1
                tag = 'IA SIN RESPUESTA'
            conf = b.llm_confidence if b.llm_confidence is not None else '-'
            self.stdout.write(
                f"[{calls}] #{b.id} {tag} (conf {conf}) | {b.home_team} vs {b.away_team}"
                f" | {b.mercado} {b.seleccion} — {(why or '')[:140]}")
            if calls < max_calls and calls < total:
                time.sleep(opts['sleep'])

        self.stdout.write(self.style.SUCCESS(
            f"Listo: {calls} llamadas | aprobadas {ok_n} | rechazadas {no_n} | sin respuesta {err_n}"))
