# -*- coding: utf-8 -*-
"""PAPERBET CON FILTRO LLM — mismo pipeline de auto_betting en producción,
pero cada pick candidato pasa por validación de un LLM con búsqueda web antes
de escribirse en PaperBet. Solo los picks aprobados por el LLM quedan.

Uso: manage.py run_paper_bets_llm [--hours 48] [--dry-run]

Reutiliza TODA la lógica de recolección (motores btts_v2/goles_v2/sot_v2/x12_v2,
gate duro cuota>=1.75 + edge>=6pp, cuotas reales de Kambi) de `run_paper_bets`
y agrega un único filtro extra: `auto_betting.llm_validator.validate_bet`.
"""
from auto_betting.management.commands.run_paper_bets import Command as BaseCommand
from auto_betting import llm_validator


class Command(BaseCommand):
    help = 'Paperbet con filtro LLM (valida cada pick con IA + búsqueda web)'

    def add_arguments(self, parser):
        super().add_arguments(parser)
        parser.add_argument('--dry-run', action='store_true',
                            help='No escribe en PaperBet; solo valida y loguea.')

    def _add(self, m, home_db, away_db, liga, mercado, motor, seleccion,
             linea, cuota, prob, start):
        bet = {
            'evento_id': str(m.get('event_id')),
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
            f"cuota={cuota:.2f} prob={prob:.2%} ev={bet['ev']:+.3f} -> {reason}"
        )
        if not approved:
            return False
        if self._opt('dry_run'):
            return True
        return super()._add(m, home_db, away_db, liga, mercado, motor,
                            seleccion, linea, cuota, prob, start)

    def _opt(self, name):
        # BaseCommand.handle recibe **opts; guardamos en self para uso en _add
        return getattr(self, '_opts', {}).get(name, False)

    def handle(self, *args, **opts):
        self._opts = opts or {}
        return super().handle(*args, **opts)
