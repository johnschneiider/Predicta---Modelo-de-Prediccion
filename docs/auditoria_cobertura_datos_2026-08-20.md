# Auditoría de Cobertura de Datos — Auto-Betting

> **Fecha:** 2026-08-20
> **Alcance:** Tabla `football_data.Match`, ventana de 730 días, umbral ≥10 partidos por equipo (mismo criterio de `validate_market_data` en `auto_betting/strategy.py`).
> **Objetivo:** Explicar por qué el auto-betting solo colocó apuestas en goles y BTTS, y cuantificar los huecos de datos por equipo y liga.

---

## 1. Contexto del problema

Hoy (2026-08-20) el auto-betting v4 colocó únicamente **2 apuestas**, ambas en mercados de **goles totales** y **BTTS**. El log mostraba sistemáticamente:

```
INFO get_official_predictions: saltando shots_total — datos insuficientes
INFO get_official_predictions: saltando corners_total — datos insuficientes
INFO 🎯 OFICIAL - Predicciones oficiales calculadas: 2 tipos  ← solo goals y BTTS
```

La causa: `validate_market_data()` exige **≥10 partidos por equipo** con datos NO NULL en el campo relevante de cada mercado. Los mercados de **córners** (`hc`/`ac`) y **remates** (`hs`/`as_field`) no alcanzan ese umbral en la mayoría de equipos de las ligas que el bot escanea.

### Mercados y su estado

| Mercado | Campo(s) | Estado | Motivo |
|---|---|---|---|
| Total de goles | `fthg`/`ftag` | ✅ Activo | Cobertura casi universal |
| Ambos Equipos Marcarán (BTTS) | reusa `fthg`/`ftag` | ✅ Activo | Hereda cobertura de goles |
| Total de córners | `hc`/`ac` | ❌ Saltado | Datos insuficientes |
| Remates totales | `hs`/`as_field` | ❌ Saltado | Datos insuficientes |
| Resultado Final (1X2) | — | ❌ Desactivado | No implementado en `_build_market_data()` (Fase 1) |
| Tiros a puerta | `hst`/`ast` | ❌ Desactivado | Fase 1 desactivada |

---

## 2. Hallazgo clave

**Remates y córners siempre fallan juntos.** Las columnas `remates<10` y `córners<10` son idénticas en las 42 ligas. Esto confirma que `hs`/`as_field` y `hc`/`ac` los puebla el **mismo scraper de Flashscore**: o llegan ambos, o ninguno.

→ No son dos problemas de datos, es **un solo hueco de scraping**.

---

## 3. Resultado global

- **471 equipos** con datos insuficientes (en al menos un mercado).
- **42 ligas** afectadas en distinto grado.
- **Goles** sano en casi todas las ligas (solo 0-10 equipos por liga bajan del umbral, normalmente ascendidos recientes).
- **Córners y remates** son el cuello de botella.

---

## 4. Tabla por liga

> `conProb` = equipos con al menos un mercado bajo el umbral. Columnas `remates<10` y `córners<10` = equipos que no alcanzan ≥10 partidos con datos.

| Liga | Equipos | Con problema | Goles <10 | Remates <10 | Córners <10 |
|---|---:|---:|---:|---:|---:|
| 2. Bundesliga | 31 | 9 | 9 | 9 | 9 |
| Allsvenskan (Suecia) | 20 | 4 | 1 | 4 | 4 |
| Bundesliga | 26 | 8 | 2 | 8 | 8 |
| Championship | 35 | 5 | 5 | 5 | 5 |
| Eredivisie | 26 | 5 | 5 | 5 | 5 |
| Jupiler Pro League | 27 | 9 | 9 | 9 | 9 |
| La Liga | 23 | 3 | 3 | 3 | 3 |
| League One | 41 | 10 | 10 | 10 | 10 |
| League Two | 39 | 9 | 9 | 9 | 9 |
| **Liga I (Rumania)** | 21 | **21** | 5 | **21** | **21** |
| **Liga MX (Mexico)** | 19 | **19** | 1 | **19** | **19** |
| Liga Pro (Ecuador) | 20 | 4 | 0 | 4 | 4 |
| **Liga de Expansion MX (Mexico)** | 16 | **16** | 0 | **16** | **16** |
| Ligue 1 | 24 | 6 | 2 | 6 | 6 |
| Ligue 2 | 27 | 3 | 3 | 3 | 3 |
| **NB I (Hungria)** | 15 | **15** | 3 | **15** | **15** |
| **PFL 1 (Bulgaria)** | 19 | **19** | 3 | **19** | **19** |
| Premier League | 26 | 3 | 0 | 3 | 3 |
| **Premier Liga (Azerbaiyan)** | 13 | **13** | 3 | **13** | **13** |
| **Premijer Liga (Bosnia)** | 14 | **14** | 2 | **14** | **14** |
| Primeira Liga | 26 | 6 | 6 | 6 | 6 |
| Primera A (Colombia) | 23 | 5 | 3 | 5 | 5 |
| **Primera B (Colombia)** | 18 | **18** | 0 | **18** | **18** |
| Primera Division (Argentina) | 32 | 30 | 3 | 30 | 30 |
| Primera Division (Chile) | 24 | 8 | 4 | 8 | 8 |
| **Primera Division (Costa Rica)** | 14 | **14** | 2 | **14** | **14** |
| **Primera Nacional (Argentina)** | 45 | **45** | 10 | **45** | **45** |
| Scottish Championship | 18 | 5 | 5 | 5 | 5 |
| Scottish Premiership | 17 | 3 | 3 | 3 | 3 |
| Segunda División | 36 | 7 | 7 | 7 | 7 |
| Serie A | 25 | 5 | 0 | 5 | 5 |
| Serie A (Brasil) | 27 | 8 | 0 | 8 | 8 |
| Serie B | 28 | 1 | 0 | 1 | 1 |
| **Serie B (Brasil)** | 33 | 16 | 0 | 16 | 16 |
| **Serie B (Ecuador)** | 14 | **14** | 0 | **14** | **14** |
| **Super Liga (Serbia)** | 20 | **20** | 4 | **20** | **20** |
| **SuperLiga (Grecia)** | 14 | **14** | 0 | **14** | **14** |
| **Superligaen (Dinamarca)** | 14 | **14** | 2 | **14** | **14** |
| Süper Lig | 22 | 4 | 4 | 4 | 4 |
| **US MLS (USA)** | 32 | **32** | 2 | **32** | **32** |
| Urvalsdeild (Islandia) | 16 | 4 | 2 | 4 | 4 |
| Veikkausliiga (Finlandia) | 15 | 3 | 1 | 3 | 3 |

**TOTAL:** 42 ligas · 471 equipos con problemas.

---

## 5. Ligas 100% rotas para córners/remates (máximo impacto en el bot)

Estas ligas no tienen datos de córners/remates en **ningún** equipo (o casi). Son las que más golpean al auto-betting porque el bot las escanea activamente vía Kambi:

| Liga | Equipos sin datos | Relevancia para el bot |
|---|---|---|
| Primera Nacional (Argentina) | 45/45 | Alta (liga grande) |
| US MLS (USA) | 32/32 | **Crítica** (el bot ya apostó córners MLS antes) |
| Liga MX (Mexico) | 19/19 | **Crítica** (el bot escanea hoy) |
| Liga de Expansion MX (Mexico) | 16/16 | **Crítica** (el bot escanea hoy) |
| Serie B (Brasil) | 16/33 | Alta (el bot escanea hoy) |
| Serie B (Ecuador) | 14/14 | Alta |
| SuperLiga (Grecia) | 14/14 | Media |
| Superligaen (Dinamarca) | 14/14 | Media |
| Super Liga (Serbia) | 20/20 | Media |
| NB I (Hungria) | 15/15 | Media |
| PFL 1 (Bulgaria) | 19/19 | Media |
| Premier Liga (Azerbaiyan) | 13/13 | Baja |
| Premijer Liga (Bosnia) | 14/14 | Baja |
| Primera B (Colombia) | 18/18 | Media |
| Primera Division (Costa Rica) | 14/14 | Baja |
| Liga I (Rumania) | 21/21 | Media |
| Serie A (Brasil) | 8/27 | Media |

---

## 6. Ligas con cobertura SANA (sin problema de córners/remates)

Championship, League One, League Two, Ligue 2, Segunda División, Primeira Liga, Serie B, Süper Lig, La Liga, Premier League, Eredivisie, Bundesliga, 2. Bundesliga, Scottish Premiership/Championship, Serie A (Italia).

---

## 7. Acciones recomendadas

1. **Backfill de Flashscore** para córners (`hc`/`ac`) y remates (`hs`/`as_field`) en las ~28 ligas rotas → desbloquearía de golpe los 2 mercados más rentables en ~471 equipos.
   - Revisar `FLASHSCORE_SCRAPING.md` y `scripts/` para ver por qué estas ligas no traen estas columnas.
   - Priorizar: Liga MX, Liga de Expansión MX, MLS, Serie A/B Brasil, Argentina (las que el bot escanea hoy).
2. **Activar 1X2**: implementar bloque `x12` en `_build_market_data()` (`auto_betting/management/commands/run_auto_bets.py`). El modelo `predict_x12()` ya existe en `strategy.py` pero no se invoca.
3. **Activar tiros a puerta**: reactivar mercado usando `fetch_shots_on_target_odds()` (ya en `services.py`) + `xg_shots_model`. Requiere datos `hst`/`ast` (verificar cobertura igual que córners).
4. **(Opcional)** Bajar `MIN_MATCHES` (hoy 10) — genera predicciones menos confiables, no recomendado salvo ligas con datos casi completos.

---

## 8. Método de extracción

```bash
cd /var/www/predicta.com.co && venv/bin/python manage.py shell
```

Consulta base (umbral 730 días, ≥10 partidos por equipo):

```python
from football_data.models import Match
from django.utils import timezone
from datetime import timedelta

cutoff = timezone.now().date() - timedelta(days=730)
MIN = 10

# goles
g = (Match.objects.filter(home_team=t, date__gte=cutoff, fthg__isnull=False).count()
     + Match.objects.filter(away_team=t, date__gte=cutoff, ftag__isnull=False).count())
# remates
s = (Match.objects.filter(home_team=t, date__gte=cutoff, hs__isnull=False).count()
     + Match.objects.filter(away_team=t, date__gte=cutoff, as_field__isnull=False).count())
# córners
c = (Match.objects.filter(home_team=t, date__gte=cutoff, hc__isnull=False).count()
     + Match.objects.filter(away_team=t, date__gte=cutoff, ac__isnull=False).count())
```
