#!/bin/bash
# Backfill de córners para partidos recientes (17-20 ago) sin stats
# Sin --skip-existing-stats: visita todos los partidos de la temporada actual
# pero solo procesa los que no tienen córners aún

cd /var/www/predicta.com.co
VENV=/var/www/predicta.com.co/venv/bin/python
LOGDIR=/var/www/predicta.com.co/logs
mkdir -p "$LOGDIR"

LOGFILE="$LOGDIR/backfill_recent_$(date +%Y%m%d_%H%M%S).log"
echo "=== Backfill córners partidos recientes — $(date) ===" | tee "$LOGFILE"

for entry in \
  "La Liga|football/spain/laliga" \
  "Süper Lig|football/turkey/super-lig" \
  "Primeira Liga|football/portugal/liga-portugal" \
  "Championship|football/england/championship" \
  "League One|football/england/league-one" \
  "Segunda División|football/spain/laliga2" \
  "Primera Division (Argentina)|football/argentina/liga-profesional" \
  "Primera Division (Chile)|football/chile/liga-de-primera" \
  "Primera Division (Costa Rica)|football/costa-rica/primera-division" \
  "Primera B (Colombia)|football/colombia/primera-b" \
  "Liga Pro (Ecuador)|football/ecuador/liga-pro" \
  "Liga MX (Mexico)|football/mexico/liga-mx" \
  "Serie B (Brasil)|football/brazil/serie-b" \
  "US MLS (USA)|football/usa/mls"; do
  IFS='|' read -r league slug <<< "$entry"
  echo "" | tee -a "$LOGFILE"
  echo ">>> $league" | tee -a "$LOGFILE"
  timeout 600 $VENV scripts/flashscore_scrape.py \
    --league "$league" --slug "$slug" \
    --current --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"
done

echo "" | tee -a "$LOGFILE"
echo "=== Backfill recientes COMPLETO — $(date) ===" | tee -a "$LOGFILE"
