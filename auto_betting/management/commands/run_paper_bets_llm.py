# -*- coding: utf-8 -*-
"""PAPERBET CON OPINIÓN IA — mismo pipeline de auto_betting en producción,
pero TODOS los picks que pasan el gate duro se escriben en PaperBet con la
OPINIÓN CRUDA de la IA (approve/reject + confidence + razón). Así podemos medir
si la opinión de la IA mejora el ROI comparando aprobados vs rechazados.

Uso: manage.py run_paper_bets_llm [--hours 24] [--dry-run]

Reutiliza TODA la lógica de recolección de `run_paper_bets` (motores
btts_v2/goles_v2/sot_v2/x12_v2/corners_v2, gate duro por motor, cuotas reales de
Kambi) y agrega:
  1. Opinión IA (búsqueda web) de cada pick con el SYSTEM PROMPT DE SU MERCADO
     (auto_betting/llm_validator.py) y modelo Luna (settings.LLM_MODEL_PAPER).
  2. TODOS los picks se guardan en PaperBet con la opinión cruda:
     llm_verdict (True/False/None), llm_confidence, llm_reason, llm_model.
     Sin filtros: la opinión se registra tal cual para analizarla después.
  3. Dedup: no se repite un pick ya existente (cualquier estado).
"""
from django.conf import settings

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
             linea, cuota, prob, start, extra=None):
        # Dedup: si ya existe el pick (cualquier estado), skip
        eid = str(m['event_id'])
        if PaperBet.objects.filter(
            evento_id=eid, mercado=mercado, seleccion=seleccion, linea=linea
        ).exists():
            return False

        extra = extra or {}
        bet = {
            'evento_id': eid,
            'home': home_db, 'away': away_db, 'liga': liga.name,
            'mercado': mercado, 'motor': motor, 'seleccion': seleccion,
            'linea': linea, 'cuota': cuota, 'prob': prob,
            'ev': prob * cuota - 1,
            'start_time': str(start),
            'lambda': extra.get('lambda'),
        }
        fair = extra.get('fair')
        bet['edge_pp'] = ((prob - fair) * 100 if fair
                          else ((prob - 1.0 / cuota) * 100 if cuota else None))

        # OPINIÓN CRUDA de la IA (sistema de prompts por mercado, modelo Luna).
        # Sin filtros todavía: se guarda tal cual (sí/no + confianza + razón).
        # Kill-switch 2026-10-13 (pedido John): por defecto DESACTIVADA para
        # ahorrar tokens; el pick se registra igual, con llm_verdict=None.
        ia_activa = getattr(settings, 'LLM_PAPER_ENABLED', False)
        if ia_activa:
            approved, reason, meta = llm_validator.validate_market(bet)
        else:
            approved, reason, meta = None, 'IA desactivada (LLM_PAPER_ENABLED=false)', {}
        mkey = (meta or {}).get('market') or 'genérico'
        if not ia_activa:
            tag = 'IA DESACTIVADA'
        elif approved is True:
            tag = f"IA APROBÓ [{mkey}]"
        elif approved is False:
            tag = f"IA RECHAZÓ [{mkey}]"
        else:
            tag = f"IA SIN RESPUESTA [{mkey}]"
        self.stdout.write(
            f"  [{tag}] {home_db} vs {away_db} | {mercado}/{seleccion} "
            f"cuota={cuota:.2f} prob={prob:.2%} edge={(bet['edge_pp'] or 0):+.1f}pp "
            f"-> {reason[:120]}"
        )

        if self._opt('dry_run'):
            return True

        # Guardar TODOS los picks, marcando la opinión de la IA
        PaperBet.objects.create(
            evento_id=eid, start_time=start,
            home_team=home_db, away_team=away_db, liga=liga.name,
            mercado=mercado, motor=motor, seleccion=seleccion, linea=linea,
            cuota=cuota, prob=round(prob, 4), ev=round(bet['ev'], 4),
            llm_verdict=approved,
            llm_reason=reason[:500],
            llm_model=(meta or {}).get('llm_model', ''),
            llm_confidence=(meta or {}).get('llm_confidence'),
        )
        return True

    def _opt(self, name):
        return getattr(self, '_opts', {}).get(name, False)

    def handle(self, *args, **opts):
        self._opts = opts or {}
        return super().handle(*args, **opts)
