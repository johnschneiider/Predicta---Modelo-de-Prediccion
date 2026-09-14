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
}

# Tareas que NO deben solaparse (pgrep pattern para guard anti-concurrencia)
ANTI_CONCURRENCY = {
    'run_auto_bets': 'manage.py run_auto_bets',
    'api_football_daily': 'manage.py sync_daily',
    'api_football_backfill': 'manage.py backfill',
    'build_showcase_pick': 'manage.py build_showcase_pick',
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
                should_run = (total_minutes % sched.cada_n_minutos) == 0
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

            try:
                with open(log_path, 'a', encoding='utf-8') as lf:
                    subprocess.Popen(
                        cmd,
                        cwd=str(settings.BASE_DIR),
                        env=env,
                        stdout=lf,
                        stderr=subprocess.STDOUT,
                        start_new_session=True,
                    )
            except Exception as e:
                logger.error(f"run_scheduler: error lanzando {sched.tarea}: {e}")
                continue

            sched.ultimo_run = now
            sched.save(update_fields=['ultimo_run'])

            msg = f"run_scheduler: {sched.tarea} lanzado ({now.strftime('%H:%M UTC')})"
            logger.info(msg)
            self.stdout.write(msg)
