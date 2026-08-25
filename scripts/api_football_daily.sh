#!/bin/bash
# API-Football daily pipeline — 01:00 Colombia (06:00 UTC).
# 1) sync_daily: fixtures próximos + stats de finalizados recientes.
# 2) backfill_leagues: continúa el backfill de 2 temporadas hasta completar.
# Ambos pausan solos al tocar el límite diario (7500 req) y reanudan al día siguiente.
set -u
cd /var/www/predicta.com.co
export DJANGO_SETTINGS_MODULE=betting_bot.settings
LOG=logs/api_football.log

echo "$(date '+%F %T') === sync_daily ===" >> "$LOG"
venv/bin/python manage.py sync_daily >> "$LOG" 2>&1 || echo "$(date '+%F %T') sync_daily ERROR" >> "$LOG"

echo "$(date '+%F %T') === backfill_leagues ===" >> "$LOG"
venv/bin/python manage.py backfill_leagues >> "$LOG" 2>&1 || echo "$(date '+%F %T') backfill_leagues ERROR" >> "$LOG"

echo "$(date '+%F %T') === populate_legacy (Match <- API) ===" >> "$LOG"
venv/bin/python manage.py populate_legacy --clear >> "$LOG" 2>&1 || echo "$(date '+%F %T') populate_legacy ERROR" >> "$LOG"

echo "$(date '+%F %T') === done ===" >> "$LOG"
