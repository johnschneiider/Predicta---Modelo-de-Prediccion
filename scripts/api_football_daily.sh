#!/bin/bash
# API-Football daily pipeline — 01:00 Colombia (06:00 UTC).
# 1) sync_daily: fixtures próximos + stats de finalizados recientes.
# 2) backfill_leagues: continúa el backfill de 2 temporadas hasta completar.
# Ambos pausan solos al tocar el límite diario (7500 req) y reanudan al día siguiente.
set -u
cd /var/www/predicta.com.co
export DJANGO_SETTINGS_MODULE=betting_bot.settings
LOG=logs/api_football.log

# Guard 2026-08-27: esperar a que termine cualquier backfill antes del sync_daily
# (evita 'database is locked' cuando el backfill de las 00:00 UTC aún escribe en SQLite).
BACKFILL_MAX_WAIT=1800  # 30 min
BACKFILL_WAITED=0
while pgrep -f "manage.py backfill" >/dev/null 2>&1; do
  if [ "$BACKFILL_WAITED" -ge "$BACKFILL_MAX_WAIT" ]; then
    echo "$(date '+%F %T') sync_daily ABORT: backfill sigue corriendo tras ${BACKFILL_MAX_WAIT}s" >> "$LOG"
    exit 1
  fi
  echo "$(date '+%F %T') esperando backfill (${BACKFILL_WAITED}s) antes de sync_daily" >> "$LOG"
  sleep 30
  BACKFILL_WAITED=$((BACKFILL_WAITED + 30))
done

echo "$(date '+%F %T') === sync_daily ===" >> "$LOG"
venv/bin/python manage.py sync_daily >> "$LOG" 2>&1 || echo "$(date '+%F %T') sync_daily ERROR" >> "$LOG"

echo "$(date '+%F %T') === backfill_leagues ===" >> "$LOG"
# Guard 2026-08-25: no arrancar un segundo backfill si ya hay uno corriendo
# (evita doble procesamiento y quemar cuota en la misma liga).
if pgrep -f "manage.py backfill_leagues" >/dev/null 2>&1; then
  echo "$(date '+%F %T') backfill_leagues SKIP: ya hay un backfill corriendo" >> "$LOG"
else
  venv/bin/python manage.py backfill_leagues >> "$LOG" 2>&1 || echo "$(date '+%F %T') backfill_leagues ERROR" >> "$LOG"
fi

echo "$(date '+%F %T') === populate_legacy (Match <- API) ===" >> "$LOG"
venv/bin/python manage.py populate_legacy --clear >> "$LOG" 2>&1 || echo "$(date '+%F %T') populate_legacy ERROR" >> "$LOG"

echo "$(date '+%F %T') === done ===" >> "$LOG"
