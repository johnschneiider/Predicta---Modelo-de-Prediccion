# -*- coding: utf-8 -*-
"""PAPERBET CON FILTRO LLM — mismo pipeline de auto_betting en producción,
pero TODOS los picks que pasan el gate duro se escriben en PaperBet con el
veredicto del LLM (approve/reject + razón). Así podemos medir si el filtro
LLM realmente mejora el ROI comparando aprobados vs rechazados.

Uso: manage.py run_paper_bets_llm [--hours 24] [--dry-run]

Reutiliza TODA la lógica de recolección de `run_paper_bets` (motores
btts_v2/goles_v2/sot_v2/x12_v2, gate duro cuota>=2.00 + edge>=6pp, cuotas
reales de Kambi) y agrega:
  1. Validación LLM (web_search) de cada pick candidato.
  2. TODOS los picks se guardan en PaperBet con llm_verdict (True/False/None).
  3. Dedup: no se repite un pick ya existente (cualquier estado).
"""
from auto_betting.management.commands.run_paper_bets import Command as BaseCommand
from auto_betting import llm_validator
from auto_betting.models import PaperBet


class Command(BaseCommand):
    help = 'Paperbet con filtro LLM (valida cada pick con IA + búsqueda web)'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--dry-run', action='store_true',
                            help='No escribe en PaperBet; solo valida y loguea.')

    def _add(self, m, home_db, away_db, liga, mercado, motor, seleccion,
             linea, cuota, prob, start):
        # Dedup: si ya existe el pick (cualquier estado), skip
        eid = str(m['event_id'])
        if PaperBet.objects.filter(
            evento_id=eid, mercado=mercado, seleccion=seleccion, linea=linea
        ).exists():
            return False

        # Validar con LLM
        bet = {
            'evento_id': eid,
            'home': home_db, 'away': away_db, 'liga': liga.name,
            'mercado': mercado, 'motor': motor, 'seleccion': seleccion,
            'linea': linea, 'cuota': cuota, 'prob': prob,
            'ev': prob * cuota - 1,
            'start_time': str(start),
        }
        approved, reason, meta = llm_validator.validate_bet(bet)
        tag = "LLM APROBADO" if approved else "LLM RECHAZADO"
        self.stdout.write(
            f"  [{tag}] {home_db} vs {away_db} | {mercado}/{seleccion} "
            f"cuota={cuota:.2f} prob={prob:.2%} ev={bet['ev']:+.3f} -> {reason[:120]}"
        )

        if self._opt('dry_run'):
            return True

        # Guardar TODOS los picks, marcando el veredicto LLM
        PaperBet.objects.create(
            evento_id=eid, start_time=start,
            home_team=home_db, away_team=away_db, liga=liga.name,
            mercado=mercado, motor=motor, seleccion=seleccion, linea=linea,
            cuota=cuota, prob=round(prob, 4), ev=round(bet['ev'], 4),
            llm_verdict=approved,
            llm_reason=reason[:500],
            llm_model=meta.get('model', '') if isinstance(meta, dict) else '',
        )
        return True

    def _opt(self, name):
        return getattr(self, '_opts', {}).get(name, False)

    def handle(self, *args, **opts):
        self._opts = opts or {}
        return super().handle(*args, **opts)
