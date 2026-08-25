#!/bin/bash
# Actualización de TODAS las ligas hasta hoy — 2026-08-21
# Objetivo: tener todos los partidos hasta ayer (20-ago) en la BD
# Estrategia: --mode results --current (rápido, solo marcadores) para todas las ligas
# Luego --mode full --current --skip-existing-stats para traer stats de partidos nuevos

cd /var/www/predicta.com.co
VENV=/var/www/predicta.com.co/venv/bin/python
LOGDIR=/var/www/predicta.com.co/logs
mkdir -p "$LOGDIR"

LOGFILE="$LOGDIR/update_all_$(date +%Y%m%d_%H%M%S).log"
echo "=== Actualización TODAS las ligas — $(date) ===" | tee "$LOGFILE"
echo "Estrategia: results --current para todas, luego full --skip-existing-stats" | tee -a "$LOGFILE"

# ── FASE 1: Resultados (marcadores) — temporada actual para todas las ligas ──
# Esto trae los partidos del 17-20 ago que faltan

echo "" | tee -a "$LOGFILE"
echo "=== FASE 1: Resultados (marcadores) — temporada actual ===" | tee -a "$LOGFILE"

# Suramérica
for entry in \
  "Primera A (Colombia)|football/colombia/primera-a" \
  "Primera Division (Argentina)|football/argentina/liga-profesional" \
  "Primera Nacional (Argentina)|football/argentina/primera-nacional" \
  "Serie A (Brasil)|football/brazil/serie-a-betano" \
  "Serie B (Brasil)|football/brazil/serie-b" \
  "Liga MX (Mexico)|football/mexico/liga-mx" \
  "Liga de Expansion MX (Mexico)|football/mexico/liga-de-expansion-mx" \
  "US MLS (USA)|football/usa/mls" \
  "Liga Pro (Ecuador)|football/ecuador/liga-pro" \
  "Serie B (Ecuador)|football/ecuador/serie-b" \
  "Primera B (Colombia)|football/colombia/primera-b" \
  "Primera Division (Chile)|football/chile/liga-de-primera"; do
  IFS='|' read -r league slug <<< "$entry"
  echo "" | tee -a "$LOGFILE"
  echo ">>> $league" | tee -a "$LOGFILE"
  timeout 300 $VENV scripts/flashscore_scrape.py \
    --league "$league" --slug "$slug" \
    --current --mode results --delay 0.5 2>&1 | tee -a "$LOGFILE"
done

# Europa (ligas activas en agosto)
for entry in \
  "Premier League|football/england/premier-league" \
  "Championship|football/england/championship" \
  "League One|football/england/league-one" \
  "League Two|football/england/league-two" \
  "La Liga|football/spain/laliga" \
  "Segunda División|football/spain/laliga2" \
  "2. Bundesliga|football/germany/2-bundesliga" \
  "Serie B|football/italy/serie-b" \
  "Ligue 2|football/france/ligue-2" \
  "Eredivisie|football/netherlands/eredivisie" \
  "Primeira Liga|football/portugal/liga-portugal" \
  "Süper Lig|football/turkey/super-lig" \
  "Jupiler Pro League|football/belgium/jupiler-pro-league" \
  "Scottish Premiership|football/scotland/premiership" \
  "Scottish Championship|football/scotland/championship"; do
  IFS='|' read -r league slug <<< "$entry"
  echo "" | tee -a "$LOGFILE"
  echo ">>> $league" | tee -a "$LOGFILE"
  timeout 300 $VENV scripts/flashscore_scrape.py \
    --league "$league" --slug "$slug" \
    --current --mode results --delay 0.5 2>&1 | tee -a "$LOGFILE"
done

# Ligas europeas menores (las que fallaron en el backfill)
for entry in \
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
  "Urvalsdeild (Islandia)|football/iceland/besta-deild-karla"; do
  IFS='|' read -r league slug <<< "$entry"
  echo "" | tee -a "$LOGFILE"
  echo ">>> $league" | tee -a "$LOGFILE"
  timeout 300 $VENV scripts/flashscore_scrape.py \
    --league "$league" --slug "$slug" \
    --current --mode results --delay 0.5 2>&1 | tee -a "$LOGFILE"
done

# Ligas con temporada terminada (pueden tener jugado en agosto antes del cierre)
for entry in \
  "Bundesliga|football/germany/bundesliga" \
  "Serie A|football/italy/serie-a" \
  "Ligue 1|football/france/ligue-1"; do
  IFS='|' read -r league slug <<< "$entry"
  echo "" | tee -a "$LOGFILE"
  echo ">>> $league (puede tener temporada ya cerrada)" | tee -a "$LOGFILE"
  timeout 300 $VENV scripts/flashscore_scrape.py \
    --league "$league" --slug "$slug" \
    --current --mode results --delay 0.5 2>&1 | tee -a "$LOGFILE"
  # También probar 2026 explícito
  timeout 300 $VENV scripts/flashscore_scrape.py \
    --league "$league" --slug "$slug" \
    --seasons 2026 --mode results --delay 0.5 2>&1 | tee -a "$LOGFILE"
done

echo "" | tee -a "$LOGFILE"
echo "=== FASE 1 COMPLETA — $(date) ===" | tee -a "$LOGFILE"

# ── FASE 2: Stats (córners/remates) para partidos nuevos ──
# Solo para ligas con partidos nuevos que no tienen stats aún

echo "" | tee -a "$LOGFILE"
echo "=== FASE 2: Stats (córners) para partidos nuevos ===" | tee -a "$LOGFILE"
echo "Usando --mode full --current --skip-existing-stats" | tee -a "$LOGFILE"

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
echo "=== ACTUALIZACIÓN COMPLETA — $(date) ===" | tee -a "$LOGFILE"
echo "Revisa cobertura con:" | tee -a "$LOGFILE"
echo "venv/bin/python manage.py shell -c \"from football_data.models import Match, League; [print(f'{l.name}: {Match.objects.filter(league=l).count()} partidos, ultimo: {Match.objects.filter(league=l).order_by(\\\"-date\\\").first().date}') for l in League.objects.all()]\"" | tee -a "$LOGFILE"
