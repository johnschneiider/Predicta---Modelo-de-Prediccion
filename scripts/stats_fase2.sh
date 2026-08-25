#!/bin/bash
# FASE 2 optimizada: Stats (córners/remates) solo para partidos nuevos
# Pre-filtra del DOM antes de visitar páginas — ~526 visitas en vez de ~2400
# Lanzado: 2026-08-21

cd /var/www/predicta.com.co
VENV=/var/www/predicta.com.co/venv/bin/python
LOGDIR=/var/www/predicta.com.co/logs
mkdir -p "$LOGDIR"

LOGFILE="$LOGDIR/stats_fase2_$(date +%Y%m%d_%H%M%S).log"
echo "=== FASE 2 Stats (optimizada) — $(date) ===" | tee "$LOGFILE"
echo "Pre-filtro DOM: solo visita partidos sin stats" | tee -a "$LOGFILE"

for entry in \
  "Primera A (Colombia)|football/colombia/primera-a" \
  "Primera Division (Argentina)|football/argentina/liga-profesional" \
  "Serie A (Brasil)|football/brazil/serie-a-betano" \
  "Serie B (Brasil)|football/brazil/serie-b" \
  "Liga MX (Mexico)|football/mexico/liga-mx" \
  "US MLS (USA)|football/usa/mls" \
  "Liga Pro (Ecuador)|football/ecuador/liga-pro" \
  "Primera Division (Chile)|football/chile/liga-de-primera" \
  "SuperLiga (Grecia)|football/greece/super-league" \
  "Superligaen (Dinamarca)|football/denmark/superliga" \
  "Super Liga (Serbia)|football/serbia/mozzart-bet-super-liga" \
  "NB I (Hungria)|football/hungary/nb-i" \
  "PFL 1 (Bulgaria)|football/bulgaria/efbet-league" \
  "Liga I (Rumania)|football/romania/superliga" \
  "Premier Liga (Azerbaijan)|football/azerbaijan/premier-league" \
  "Premijer Liga (Bosnia)|football/bosnia-and-herzegovina/wwin-liga-bih" \
  "Primera Division (Costa Rica)|football/costa-rica/primera-division" \
  "Allsvenskan (Suecia)|football/sweden/allsvenskan" \
  "Veikkausliiga (Finlandia)|football/finland/veikkausliiga" \
  "Urvalsdeild (Islandia)|football/iceland/besta-deild-karla" \
  "Liga de Expansion MX (Mexico)|football/mexico/liga-de-expansion-mx" \
  "Primera B (Colombia)|football/colombia/primera-b" \
  "Serie B (Ecuador)|football/ecuador/serie-b" \
  "Primera Nacional (Argentina)|football/argentina/primera-nacional"; do
  IFS='|' read -r league slug <<< "$entry"
  echo "" | tee -a "$LOGFILE"
  echo ">>> $league (stats)" | tee -a "$LOGFILE"
  timeout 600 $VENV scripts/flashscore_scrape.py \
    --league "$league" --slug "$slug" \
    --current --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"
done

echo "" | tee -a "$LOGFILE"
echo "=== FASE 2 COMPLETA — $(date) ===" | tee -a "$LOGFILE"
