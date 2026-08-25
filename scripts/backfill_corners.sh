#!/bin/bash
# Backfill de córners y remates para ligas 100% rotas (0% cobertura)
# Fecha: 2026-08-20
# Ejecutar como www-data para no romper ownership de db.sqlite3

cd /var/www/predicta.com.co
VENV=/var/www/predicta.com.co/venv/bin/python
LOGDIR=/var/www/predicta.com.co/logs
mkdir -p "$LOGDIR"

LOGFILE="$LOGDIR/backfill_corners_$(date +%Y%m%d_%H%M%S).log"
echo "=== Backfill córners/remates — $(date) ===" | tee "$LOGFILE"
echo "Log: $LOGFILE" | tee -a "$LOGFILE"

# ── Ligas 100% rotas (0% córners) ──
# 1. Liga de Expansion MX (Mexico) — formato Apertura/Clausura
echo "" | tee -a "$LOGFILE"
echo ">>> [1/4] Liga de Expansion MX (Mexico) — temporadas 2025-2026 2024-2025" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Liga de Expansion MX (Mexico)" \
    --slug football/mexico/liga-de-expansion-mx \
    --seasons 2025-2026 2024-2025 \
    --mode full --delay 1.0 2>&1 | tee -a "$LOGFILE"

# 2. Primera B (Colombia)
echo "" | tee -a "$LOGFILE"
echo ">>> [2/4] Primera B (Colombia) — temporadas 2025 2024 2023" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Primera B (Colombia)" \
    --slug football/colombia/primera-b \
    --seasons 2025 2024 2023 \
    --mode full --delay 1.0 2>&1 | tee -a "$LOGFILE"

# 3. Serie B (Ecuador)
echo "" | tee -a "$LOGFILE"
echo ">>> [3/4] Serie B (Ecuador) — temporadas 2025 2024 2023" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Serie B (Ecuador)" \
    --slug football/ecuador/serie-b \
    --seasons 2025 2024 2023 \
    --mode full --delay 1.0 2>&1 | tee -a "$LOGFILE"

# 4. SuperLiga (Grecia)
echo "" | tee -a "$LOGFILE"
echo ">>> [4/4] SuperLiga (Grecia) — temporadas 2025 2024 2023" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "SuperLiga (Grecia)" \
    --slug football/greece/super-league \
    --seasons 2025 2024 2023 \
    --mode full --delay 1.0 2>&1 | tee -a "$LOGFILE"

echo "" | tee -a "$LOGFILE"
echo "=== Backfill FASE 1 completado — $(date) ===" | tee -a "$LOGFILE"

# ── FASE 2: Ligas parciales (7-33% cobertura) con --skip-existing-stats ──
# Estas ligas tienen algunos córners pero no completos. Usamos el flag
# para saltar partidos que ya tienen data y solo backfill los faltantes.

echo "" | tee -a "$LOGFILE"
echo "=== Iniciando FASE 2: ligas parciales con --skip-existing-stats ===" | tee -a "$LOGFILE"

# Liga MX (Mexico) — 7% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> Liga MX (Mexico) — temporadas 2025-2026 2024-2025" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Liga MX (Mexico)" \
    --slug football/mexico/liga-mx \
    --seasons 2025-2026 2024-2025 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# US MLS (USA) — 20% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> US MLS (USA) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "US MLS (USA)" \
    --slug football/usa/mls \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# Serie A (Brasil) — 20% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> Serie A (Brasil) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Serie A (Brasil)" \
    --slug football/brazil/serie-a-betano \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# Serie B (Brasil) — 19% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> Serie B (Brasil) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Serie B (Brasil)" \
    --slug football/brazil/serie-b \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# Primera Division (Argentina) — 20% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> Primera Division (Argentina) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Primera Division (Argentina)" \
    --slug football/argentina/liga-profesional \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# Primera Nacional (Argentina) — 33% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> Primera Nacional (Argentina) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Primera Nacional (Argentina)" \
    --slug football/argentina/primera-nacional \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# Superligaen (Dinamarca) — 8% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> Superligaen (Dinamarca) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Superligaen (Dinamarca)" \
    --slug football/denmark/superliga \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# Super Liga (Serbia) — 12% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> Super Liga (Serbia) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Super Liga (Serbia)" \
    --slug football/serbia/mozzart-bet-super-liga \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# NB I (Hungria) — 9% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> NB I (Hungria) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "NB I (Hungria)" \
    --slug football/hungary/nb-i \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# PFL 1 (Bulgaria) — 13% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> PFL 1 (Bulgaria) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "PFL 1 (Bulgaria)" \
    --slug football/bulgaria/efbet-league \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# Liga I (Rumania) — 14% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> Liga I (Rumania) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Liga I (Rumania)" \
    --slug football/romania/superliga \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# Premier Liga (Azerbaiyan) — 1% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> Premier Liga (Azerbaiyan) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Premier Liga (Azerbaiyan)" \
    --slug football/azerbaijan/premier-league \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# Premijer Liga (Bosnia) — 3% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> Premijer Liga (Bosnia) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Premijer Liga (Bosnia)" \
    --slug football/bosnia-and-herzegovina/wwin-liga-bih \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

# Primera Division (Costa Rica) — 7% cobertura
echo "" | tee -a "$LOGFILE"
echo ">>> Primera Division (Costa Rica) — temporadas 2025 2024" | tee -a "$LOGFILE"
$VENV scripts/flashscore_scrape.py \
    --league "Primera Division (Costa Rica)" \
    --slug football/costa-rica/primera-division \
    --seasons 2025 2024 \
    --mode full --delay 1.0 --skip-existing-stats 2>&1 | tee -a "$LOGFILE"

echo "" | tee -a "$LOGFILE"
echo "=== Backfill COMPLETO — $(date) ===" | tee -a "$LOGFILE"
echo "Revisa cobertura con: venv/bin/python manage.py shell -c \"from football_data.models import *; ...\"" | tee -a "$LOGFILE"
