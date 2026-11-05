#!/usr/bin/env bash
set -euo pipefail

cd /var/www/predicta.com.co

LOCK=/var/www/predicta.com.co/logs/paperparleys.lock
exec 9>"$LOCK"
flock -n 9 || { echo "paperparleys: ya hay una ejecucion en curso"; exit 0; }

export DJANGO_SETTINGS_MODULE=betting_bot.settings
export PYTHONDONTWRITEBYTECODE=1

for _ in $(seq 1 20); do
  if ! pgrep -f 'manage.py run_auto_bets' >/dev/null 2>&1; then
    break
  fi
  echo "paperparleys: esperando run_auto_bets ($(date -u +%H:%M:%S))"
  sleep 30
done

if pgrep -f 'manage.py run_auto_bets' >/dev/null 2>&1; then
  echo "paperparleys: run_auto_bets sigue activo; se ejecuta con prioridad baja"
fi

exec nice -n 10 ionice -c2 -n7 timeout --signal=TERM --kill-after=30 900 \
  bash -c 'ulimit -c 0; ulimit -v 2097152; exec venv/bin/python manage.py paperparleys --usuario 1 --min-legs 2 --max-legs 2 "$@"' _ "$@"
