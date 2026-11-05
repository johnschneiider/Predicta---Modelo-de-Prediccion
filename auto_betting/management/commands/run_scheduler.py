"""
Dispatcher de tareas programadas — reemplaza las múltiples entradas del crontab.

Se ejecuta cada minuto desde el crontab:
    * * * * * ... manage.py run_scheduler

Lee CronSchedule y ejecuta las tareas que tocan a la hora/minuto actual.
Para tareas con cada_n_minutos > 0, ejecuta cada N minutos.
Para tareas de hora fija, ejecuta solo en el minuto exacto.

Guard anti-concurrencia: cada tarea usa pgrep para evitar duplicados.
"""

import logging
import subprocess
import os
import shutil
from datetime import datetime, timezone as dt_timezone

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings

from auto_betting.models import CronSchedule

logger = logging.getLogger('auto_betting')

# Mapeo tarea → comando shell (igual que el crontab original)
COMANDOS = {
    'api_football_daily': ['scripts/api_football_daily.sh'],
    'sync_bet_history': [
        'venv/bin/python', 'manage.py', 'sync_bet_history',
    ],
    'sync_bet_history_pre': [
        'venv/bin/python', 'manage.py', 'sync_bet_history',
    ],
    'sync_bet_history_vespertino': [
        'venv/bin/python', 'manage.py', 'sync_bet_history',
    ],
    'calibration_report': [
        'venv/bin/python', 'manage.py', 'calibration_report', '--days', '7',
    ],
    'run_auto_bets': ['scripts/run_auto_bets_cron.sh'],
    'capture_closing_odds': [
        'venv/bin/python', 'manage.py', 'capture_closing_odds',
    ],
    'api_football_backfill': ['scripts/api_football_backfill.sh'],
    'check_betplay_tokens': [
        'venv/bin/python', 'manage.py', 'check_betplay_tokens',
    ],
    'build_showcase_pick': [
        'venv/bin/python', 'manage.py', 'build_showcase_pick',
    ],
    'inspect_bets': [
        'venv/bin/python', 'manage.py', 'inspect_bets',
    ],
    'score_paper_bets': [
        'venv/bin/python', 'manage.py', 'score_paper_bets', '--days-back', '3',
    ],
    'run_nba_bets': [
        'venv/bin/python', 'manage.py', 'run_nba_bets', '--real', '--yes',
    ],
    'sync_nba_daily': [
        'venv/bin/python', 'manage.py', 'sync_nba_apisports', '--season', '2026-2027',
    ],
    'run_mlb_under_bets': [
        'venv/bin/python', 'manage.py', 'run_mlb_under_bets', '--real', '--yes',
    ],
    'run_paper_bets_basket': [
        'venv/bin/python', 'manage.py', 'run_paper_bets_basket',
    ],
    'run_paper_bets_basket_gated': [
        'venv/bin/python', 'manage.py', 'run_paper_bets_basket_gated',
    ],
    'run_basket_1q2q_bets': [
        'venv/bin/python', 'manage.py', 'run_basket_1q2q_bets',
        '--real', '--yes',
    ],
    'score_paper_bets_basket': [
        'venv/bin/python', 'manage.py', 'score_paper_bets_basket',
        '--days-back', '10',
    ],
    'train_basket_models': [
        'venv/bin/python', 'manage.py', 'train_basket_models',
    ],
    'run_paper_trades_fx': [
        'venv/bin/python', 'manage.py', 'run_paper_trades_fx',
    ],
    'run_paper_bets_ou': [
        'venv/bin/python', 'manage.py', 'run_paper_bets_ou',
    ],
    'score_paper_bets_ou': [
        'venv/bin/python', 'manage.py', 'score_paper_bets_ou',
        '--days-back', '10',
    ],
    'calibrar_ou': [
        'venv/bin/python', 'manage.py', 'calibrar_ou',
    ],
    'backfill_ou_sharp': [
        'venv/bin/python', 'manage.py', 'backfill_ou_sharp', '--dias', '3',
        '--limite', '6',
    ],
    'reporte_ligas_ou': [
        'venv/bin/python', 'manage.py', 'reporte_ligas_ou',
    ],
    'ask_llm_real_ventana': [
        'venv/bin/python', 'manage.py', 'ask_llm_real', '--ventana',
        '--max', '4',
    ],
    'run_value_scan': [
        'venv/bin/python', 'manage.py', 'run_value_scan',
    ],
    'paperparleys': [
        'scripts/paperparleys_cron.sh',
    ],
    'real_parleys': [
        'venv/bin/python', 'manage.py', 'run_real_parleys',
    ],
}

# Logs por tarea
LOGS = {
    'sync_bet_history': 'logs/sync_history.log',
    'sync_bet_history_pre': 'logs/sync_history.log',
    'sync_bet_history_vespertino': 'logs/sync_history.log',
    'calibration_report': 'logs/auto_betting.log',
    'capture_closing_odds': 'logs/closing_odds.log',
    'check_betplay_tokens': 'logs/notificaciones.log',
    'api_football_daily': 'logs/api_football.log',
    'api_football_backfill': 'logs/api_football.log',
    'run_auto_bets': 'logs/auto_betting.log',
    'build_showcase_pick': 'logs/showcase.log',
    'inspect_bets': 'logs/inspector.log',
    # score_paper_bets tiene log PROPIO a propósito: antes compartía
    # logs/paperbet_llm.log con la tarea de root run_paper_bets_llm, que lo
    # recrea como root:root y dejaba al scheduler (www-data) sin poder abrirlo.
    'score_paper_bets': 'logs/score_paper_bets.log',
    'run_nba_bets': 'logs/nba_betting.log',
    'sync_nba_daily': 'logs/nba_sync.log',
    'run_mlb_under_bets': 'logs/mlb_betting.log',
    'run_paper_bets_basket': 'logs/paperbet_basket.log',
    'run_paper_bets_basket_gated': 'logs/paperbet_basket_gated.log',
    'run_basket_1q2q_bets': 'logs/basket_1q2q_real.log',
    'score_paper_bets_basket': 'logs/score_paper_bets_basket.log',
    'train_basket_models': 'logs/basket_train.log',
    'run_paper_trades_fx': 'logs/papertrading_fx.log',
    'run_paper_bets_ou': 'logs/paperbet_ou.log',
    'score_paper_bets_ou': 'logs/score_paper_bets_ou.log',
    'calibrar_ou': 'logs/basket_ou.log',
    'backfill_ou_sharp': 'logs/backfill_ou.log',
    'reporte_ligas_ou': 'logs/ligas_ou.log',
    'ask_llm_real_ventana': 'logs/llm_real_ventana.log',
    'run_value_scan': 'logs/value_betting.log',
    'paperparleys': 'logs/paperparleys.log',
    'real_parleys': 'logs/real_parleys.log',
}

# Tareas que NO deben solaparse (pgrep pattern para guard anti-concurrencia)
ANTI_CONCURRENCY = {
    'run_auto_bets': 'manage.py run_auto_bets',
    'api_football_daily': 'manage.py sync_daily',
    'api_football_backfill': 'manage.py backfill',
    'build_showcase_pick': 'manage.py build_showcase_pick',
    'inspect_bets': 'manage.py inspect_bets',
    'run_nba_bets': 'manage.py run_nba_bets',
    'run_mlb_under_bets': 'manage.py run_mlb_under_bets',
    'run_paper_bets_basket': 'manage.py run_paper_bets_basket$',
    'run_paper_bets_basket_gated': 'manage.py run_paper_bets_basket_gated$',
    'run_basket_1q2q_bets': 'manage.py run_basket_1q2q_bets',
    'score_paper_bets_basket': 'manage.py score_paper_bets_basket',
    'train_basket_models': 'manage.py train_basket_models',
    'run_paper_trades_fx': 'manage.py run_paper_trades_fx',
    'run_paper_bets_ou': 'manage.py run_paper_bets_ou',
    'score_paper_bets_ou': 'manage.py score_paper_bets_ou',
    'calibrar_ou': 'manage.py calibrar_ou',
    'backfill_ou_sharp': 'manage.py backfill_ou_sharp',
    'reporte_ligas_ou': 'manage.py reporte_ligas_ou',
    'ask_llm_real_ventana': 'manage.py ask_llm_real',
    'run_value_scan': 'manage.py run_value_scan',
    'paperparleys': 'manage.py paperparleys',
    'real_parleys': 'manage.py run_real_parleys',
}


class Command(BaseCommand):
    help = "Dispatcher de tareas programadas (reemplaza crontab individual)."

    def handle(self, *args, **options):
        now = timezone.now()
        if now.tzinfo is None:
            now = now.replace(tzinfo=dt_timezone.utc)

        current_hour = now.hour
        current_minute = now.minute

        for sched in CronSchedule.objects.filter(enabled=True):
            should_run = False

            if sched.cada_n_minutos > 0:
                # Tarea recurrente (ej. cada 15 min)
                total_minutes = current_hour * 60 + current_minute
                # Ancla horaria (2026-09-20, decisión John): run_auto_bets usa
                # hora_utc/minuto_utc como offset para conservar el barrido
                # histórico de las 03:00 UTC (cada_n_minutos=720 → 03:00 y
                # 15:00 UTC, dos barridos/día). Las demás tareas recurrentes
                # mantienen el ancla en medianoche UTC (offset 0).
                offset = (sched.hora_utc * 60 + sched.minuto_utc) if sched.tarea == 'run_auto_bets' else 0
                should_run = ((total_minutes - offset) % sched.cada_n_minutos) == 0
            else:
                # Tarea de hora fija
                should_run = (current_hour == sched.hora_utc and current_minute == sched.minuto_utc)

            if not should_run:
                continue

            # Guard anti-concurrencia
            pattern = ANTI_CONCURRENCY.get(sched.tarea)
            if pattern:
                try:
                    check = subprocess.run(
                        ['pgrep', '-f', pattern],
                        capture_output=True, text=True, timeout=10,
                    )
                    if check.returncode == 0:
                        logger.info(f"run_scheduler: {sched.tarea} SKIP (ya corriendo)")
                        continue
                except Exception:
                    pass

            # Ejecutar
            cmd = COMANDOS.get(sched.tarea)
            if not cmd:
                logger.warning(f"run_scheduler: {sched.tarea} sin comando configurado")
                continue

            log_file = LOGS.get(sched.tarea, 'logs/scheduler.log')
            log_path = settings.BASE_DIR / log_file

            env = dict(os.environ)
            env['DJANGO_SETTINGS_MODULE'] = 'betting_bot.settings'

            # --- Blindaje del log -------------------------------------------
            # Un archivo de log a nombre de OTRO usuario hacía que open() fallara
            # con Permission denied y la tarea NUNCA se lanzaba: fallaba en
            # silencio, una y otra vez, durante días. Se auto-repara antes de abrir.
            try:
                log_path.parent.mkdir(parents=True, exist_ok=True)
                if log_path.exists() and not os.access(log_path, os.W_OK):
                    os.chmod(log_path, 0o664)
                    try:
                        shutil.chown(log_path, user='www-data', group='www-data')
                    except (LookupError, PermissionError):
                        pass
                    logger.warning(
                        f"run_scheduler: {log_file} no era escribible; propiedad reparada"
                    )
            except Exception as e:
                logger.warning(f"run_scheduler: no se pudo revisar {log_file}: {e}")

            # Abrir el log NUNCA debe impedir lanzar la tarea: si falla, se lanza
            # igual sin redirección. Perder el log es aceptable; perder el trabajo no.
            lf = None
            try:
                lf = open(log_path, 'a', encoding='utf-8')
            except Exception as e:
                logger.error(
                    f"run_scheduler: {sched.tarea} sin log escribible en {log_file}: {e} "
                    f"(se lanza igual)"
                )

            try:
                subprocess.Popen(
                    cmd,
                    cwd=str(settings.BASE_DIR),
                    env=env,
                    stdout=lf if lf is not None else subprocess.DEVNULL,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
            except Exception as e:
                if lf is not None:
                    lf.close()
                logger.error(f"run_scheduler: error lanzando {sched.tarea}: {e}")
                continue
            finally:
                # El hijo ya heredó el descriptor; el padre puede cerrar el suyo.
                if lf is not None:
                    lf.close()

            sched.ultimo_run = now
            sched.save(update_fields=['ultimo_run'])

            msg = f"run_scheduler: {sched.tarea} lanzado ({now.strftime('%H:%M UTC')})"
            logger.info(msg)
            self.stdout.write(msg)
