# Backfill Córners/Remates — Estado

> **Lanzado:** 2026-08-20 11:47 UTC (06:47 Bogotá)
> **Estimación de finalización:** ~20:00 UTC (~15:00 Bogotá) — ±1 hora
> **Duración estimada:** 8-9 horas

---

## Qué se está haciendo

Backfill de **córners (`hc`/`ac`) y remates (`hs`/`as_field`)** desde Flashscore para 18 ligas que tienen 0% o cobertura parcial de estos datos. Las ligas se scrapearon originalmente con `--mode results` (solo marcadores) y nunca se corrió `--mode full` para traer stats.

## Datos del scraper

| Campo | Valor |
|---|---|
| **Script** | `scripts/flashscore_scrape.py` |
| **Script shell** | `scripts/backfill_corners.sh` |
| **Log** | `logs/backfill_corners_20260820_114729.log` |
| **PID** | 1603605 (proceso Python) / 1603589 (script shell) |
| **Modo** | `--mode full` (visita detalle de cada partido para extraer stats) |
| **Delay** | 1.0s entre partidos |
| **Flag nuevo** | `--skip-existing-stats` (no reescribe partidos que ya tienen córners) |
| **Venv** | `/var/www/predicta.com.co/venv/bin/python` |
| **Chromium** | Playwright Chrome en `/root/.cache/ms-playwright/chromium-1234/` |
| **Usuario** | root (necesario porque Playwright está en `/root/.cache/`) |

## Volumen

- **Total partidos a visitar:** ~6,010
- **Ligas 0% (full scrape):** 4 ligas, ~1,280 partidos
  - Liga de Expansion MX, Primera B Colombia, Serie B Ecuador, SuperLiga Grecia
- **Ligas parciales (con --skip-existing-stats):** 14 ligas, ~4,730 partidos
  - Liga MX, US MLS, Serie A/B Brasil, Argentina (Primera Div + Nacional), Superligaen, Super Liga Serbia, NB I Hungría, PFL Bulgaria, Liga I Rumania, Premier Liga Azerbaiyán, Premijer Bosnia, Costa Rica

## Cómo verificar progreso

```bash
# Ver log en tiempo real
tail -f /var/www/predicta.com.co/logs/backfill_corners_20260820_114729.log

# Ver si el proceso sigue corriendo
ps aux | grep flashscore_scrape

# Ver cobertura actual de córners en DB
cd /var/www/predicta.com.co && venv/bin/python manage.py shell -c "
from football_data.models import Match
total = Match.objects.count()
with_c = Match.objects.filter(hc__isnull=False).count()
print(f'Córners: {with_c:,}/{total:,} ({with_c*100//total}%)')
"
```

## Problema conocido

- El scraper visita TODAS las páginas de partidos (incluso las que ya tienen datos con `--skip-existing-stats`), porque solo sabe si un partido tiene córners después de visitarlo. Optimización futura: pre-filtrar con results listing antes de visitar.

## Después del backfill

Cuando termine, los mercados de **córners** y **remates totales** deberían estar activos en el auto-betting para las 18 ligas afectadas (~471 equipos desbloqueados). Verificar con `validate_market_data()` para un partido de ejemplo.
