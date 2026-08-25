#!/bin/bash
# Backfill con espera de cuota — 00:00 UTC (19:00 Colombia) = reset de cuota API-Football.
# backfill_wait hace polling a /status (no consume quota) y reintenta hasta que resetea.
set -u
cd /var/www/predicta.com.co
export DJANGO_SETTINGS_MODULE=betting_bot.settings
LOG=logs/api_football.log

echo "$(date '+%F %T') === backfill_wait (cuota reset) ===" >> "$LOG"
venv/bin/python manage.py backfill_wait >> "$LOG" 2>&1 || echo "$(date '+%F %T') backfill_wait ERROR" >> "$LOG"
