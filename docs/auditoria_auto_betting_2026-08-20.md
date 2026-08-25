# Auditoría Auto-Betting — 2026-08-20

> **Alcance:** Revisión del sistema de auto-apuestas (`auto_betting/`) vs. el motor de predicción oficial (`/ai/predict/`).
> **Motivo:** Día de pérdidas el 2026-08-19. Verificación de si se apuesta siguiendo la estadística real de Predicta.
> **Conclusión:** NO se está apostando con la predicción oficial. Se detectaron 5 problemas graves.
> **Estado:** Solo diagnóstico. Sin cambios de código.

---

## 1. Resumen ejecutivo

El sistema de auto-apuestas **no** replica lo que `/ai/predict/` muestra al usuario. Usa modelos individuales crudos (y en algunos casos un mercado que la web no predice), en lugar de la **"Predicción Oficial"** (promedio ponderado por confianza de todos los modelos). El resultado son probabilidades infladas de forma irreal que generan "edges" falsos de +30% a +112%.

**Día 2026-08-19 (lote 05:10 UTC):** 18 apuestas sistema, 2 WON / 7 LOST / 9 OPEN asentadas hasta ahora = **−525 COP** neto.

---

## 2. Problemas detectados

### Problema 1 — Modelo de tiros a puerta ROTO (datos faltantes)

**Causa raíz:** `xg_shots_model.predict_shots_on_target_total()` consulta los campos `hst`/`ast` (tiros a puerta) de la BD. Esos datos **solo existen desde 2026**. Antes, todo es `NULL`.

- 537 partidos MLS en BD → solo 109 con `hst` (y los 109 son de 2026).
- Toronto FC: **1 solo partido** con `hst` (`hst=1`) → promedio = 1.0.
- Charlotte: **2 partidos** con `ast` (`1, 3`) → promedio = 2.0.
- Modelo calcula `home_sot + away_sot = 1.0 + 2.0 = 3.0`.
- Poisson con λ=3.0 → **P(Under 7.5) = 98.8%** (absurdo para la MLS).

**Caso emblemático (Toronto vs Charlotte, Under 7.5 @2.70):**

| Modelo | λ | P(Under 7.5) |
|---|---|---|
| `shots_prediction_model` | 8.4 | ~30% |
| `xg_shots_model` (usado por auto-betting) | 3.0 | **98.8%** |
| **Predicción Oficial** (promedio) | 5.7 | 78.4% |

Resultado: **LOST** (hubo 8+ tiros a puerta).

### Problema 2 — El auto-betting ignora la "Predicción Oficial" y usa UN solo modelo

`/ai/predict/` muestra la **"Predicción Oficial"** = promedio ponderado por confianza de todos los modelos. El auto-betting la ignora y usa modelos individuales crudos:

- **Tiros a puerta:** usa SOLO `xg_shots_model` (ignora `shots_prediction_model`).
- **Goles:** usa SOLO `DixonColesModel.predict_match()` (ignora Simple Average y Ensemble).

Consecuencia: sobreestima sistemáticamente (toma el modelo más extremo).

| Partido | Mercado | P(auto_bet) | P(oficial) | Δ | Resultado |
|---|---|---|---|---|---|
| Toronto Under 7.5 | tiros | 98.8% | 78.4% | +20.4pp | LOST |
| Fortaleza Over 10.5 | tiros | 74.0% | 63.1% | +10.9pp | LOST |
| DC United Over 10.5 | tiros | 65.3% | 57.0% | +8.3pp | LOST |
| Chacarita Over 2.5 | goles | 66.2% | 57.7% | +8.5pp | LOST |
| Columbus Over 3.5 | goles | 63.1% | 56.8% | +6.3pp | LOST |
| Cincinnati Over 3.5 | goles | 53.1% | 67.3% | −14.2pp | LOST |

### Problema 3 — Mercado "Resultado Final" (1X2) NO existe en `/ai/predict/`

`/ai/predict/` predice 11 mercados: remates, tiros a puerta, goles, córners y "ambos marcan". **No predice 1X2.**

El auto-betting apostó **6 apuestas "Resultado Final"** el 19-Ago, usando `DixonColesModel._calculate_match_outcome()` (ruta oculta, no visible en la web). Probabilidades infladas por el multiplicador de ventaja local (×1.15) y el piso de liga:

| Partido | Cuota | P(modelo) | Implied market | Edge falso | Resultado |
|---|---|---|---|---|---|
| NY Red Bulls | 2.80 | 71.0% | 35.7% | +35% | LOST |
| LA Galaxy | 2.18 | 78.7% | 45.9% | +33% | OPEN |
| Sporting KC | 3.35 | 67.5% | 29.9% | +38% | OPEN |
| Orlando City | 2.75 | 61.4% | 36.4% | +25% | OPEN |
| Philadelphia | 2.43 | 63.6% | 41.2% | +22% | OPEN |
| Cuiabá | 2.20 | 58.3% | 45.5% | +13% | WON |

Un local con 71% a cuota 2.80 no existe en fútbol real.

### Problema 4 — Sobre-confianza generalizada (incluso en la Predicción Oficial)

Aunque se usara la Predicción Oficial, el modelo sigue sobre-confía. Asigna 53–79% a apuestas que en su mayoría pierden:

| Partido | P(oficial) | Resultado |
|---|---|---|
| Toronto Under 7.5 | 78.4% | LOST |
| Cincinnati Over 3.5 | 67.3% | LOST |
| Fortaleza Over 10.5 | 63.1% | LOST |
| Chacarita Over 2.5 | 57.7% | LOST |
| DC United Over 10.5 | 57.0% | LOST |
| Columbus Over 3.5 | 56.8% | LOST |

El EV positivo (+40% a +112%) es una **ilusión**: las probabilidades no reflejan la realidad.

### Problema 5 — Falta de validación de cobertura de datos antes de apostar

`run_auto_bets.py` valida mínimo 10 partidos por equipo **para goles** (`analyze_team_statistics(..., 'goals')`), pero **NO valida la cobertura de `hst`/`ast`** para el mercado de tiros a puerta. Toronto tiene 18 partidos (pasa el filtro de goles) pero solo 1 con `hst`.

---

## 3. Ligas/equipos en riesgo de datos basura

### Ligas con 0% de datos `hst` (el modelo produce basura SIEMPRE)

| Liga | Partidos 2026 | % con hst |
|---|---|---|
| Bundesliga | 104 | 0% |
| Ligue 1 | 106 | 0% |
| Premier League | 108 | 0% |
| Serie A (Italia) | 106 | 0% |
| Serie B (Italia) | 109 | 0% |
| SuperLiga (Grecia) | 105 | 0% |

Equipos afectados: Arsenal, AC Milan, Nice, Freiburg, Olympiacos, Panathinaikos, etc.

### Equipos en riesgo dentro de ligas con datos (pocos partidos 2026)

- Primera Nacional (Argentina): 27 equipos con 3–5 partidos `hst`.
- Primera División (Argentina): 24 equipos.
- US MLS: 23 equipos (Toronto solo 1 con `hst`).
- Serie B (Brasil): 20 equipos.
- La Liga: 18 equipos (7–9 partidos).

---

## 4. Análisis contrafactual (¿qué habría pasado con la predicción oficial?)

Ejecutado el motor real de `/ai/predict/` (3 modelos de goles + 2 de tiros + córners, promediados) para las 18 apuestas del 19-Ago.

| Escenario | Apuestas | Asentadas | Net COP |
|---|---|---|---|
| **REAL** (lo que pasó) | 18 | 2W / 7L (+9 OPEN) | **−525** |
| **OFICIAL** (predicción real) | 12 (6 menos: todas 1X2) | 1W / 6L (+5 OPEN) | **−625** |

**Conclusión:** usar la predicción oficial NO habría salvado el día. Habría evitado el 1X2 (bien), pero las Over/Under habrían perdido igual. El problema de fondo es la **sobre-confianza + datos basura**, no solo "el modelo equivocado".

---

## 5. Plan de corrección (por prioridad)

### Fase 1 — Cortafuegos inmediato (bloquear el sangrado) 🔴

1. **Desactivar el mercado 1X2** en `auto_betting/strategy.py` / `run_auto_bets.py`.
   - El mercado no existe en `/ai/predict/` y tiene probabilidades infladas.
   - Quitar `predict_x12()` de `_build_market_data()` (o gatearlo con `feature flag = False`).

2. **Apagar el mercado "tiros a puerta"** mientras no haya datos fiables.
   - Desactivar `fetch_shots_on_target_odds` / `predict_shots_on_target` hasta el Fix de datos.
   - Es el mercado con el caso Toronto (98.8% → LOST).

3. **Pausar el cron** del auto-betting hasta aplicar Fase 1 y 2.
   - `crontab www-data`: comentar la línea `10 5 * * *` (o el cron actual).

### Fase 2 — Conectar al motor oficial 🟠

4. **Usar la "Predicción Oficial"** en lugar de modelos individuales.
   - En `strategy.py`, reemplazar `predict_corners/goals/shots` por una llamada a `official_prediction_model` (el mismo promedio que muestra `/ai/predict/`).
   - Evita el sesgo de "tomar el modelo más extremo".

5. **Unificar el flujo de predicción.**
   - Crear una función única `get_official_prediction(home, away, league)` que consuma el pipeline completo (SimplePredictionService + shots_prediction_model + xg_shots_model + corners_model + enhanced_both_teams_score) y devuelva solo la predicción oficial por mercado.

### Fase 3 — Validación de datos 🟡

6. **Validar cobertura de datos antes de apostar.**
   - Para tiros a puerta: exigir ≥10 partidos con `hst`/`ast` por equipo (no solo partidos totales).
   - Para goles/córners: mantener el filtro actual pero extenderlo a cada mercado específico.
   - Si un equipo tiene <N partidos con datos del mercado, **saltar el partido** (no usar fallback silencioso).

7. **Arreglar `xg_shots_model`.**
   - Cuando un equipo tenga <10 partidos con `hst`, hacer fallback al **promedio de liga** (no a `_default_team_data()` con λ=4.0 fija).
   - Alternativa: si no hay datos, devolver `None` y que el auto-betting salte ese mercado.

8. **Completar/verificar los datos `hst`/`ast`.**
   - Identificar por qué Bundesliga, Ligue 1, Premier League, Serie A, Serie B, SuperLiga (Grecia) no tienen `hst`.
   - Revisar el scraper Flashscore (`scripts/scrape_corners.py` / FLASHSCORE_SCRAPING.md) y ampliar cobertura.

### Fase 4 — Recalibración del modelo 🟢

9. **Calibrar las probabilidades (Platt scaling / isotonic regression).**
   - El modelo asigna 53–79% a apuestas que en su mayoría pierden. Hay que calibrar contra resultados históricos reales.
   - Backtest: comparar P predicha vs frecuencia real de acierto por rango de probabilidad.

10. **Revisar la inflación de Dixon-Coles.**
    - El multiplicador ×1.15 (ventaja local) y el piso de liga inflan las lambdas.
    - Evaluar eliminar/ajustar ambos, o calibrar rho (τ) de Dixon-Coles con datos reales.

11. **Revisar el cálculo de EV.**
    - El EV positivo actual es ilusión porque P no está calibrada.
    - Considerar margen de seguridad: solo apostar si `P_modelo > implied + buffer` (ej. buffer de 5–10pp), o usar Kelly fraccional.

### Fase 5 — Monitoreo y validación 🟣

12. **CLV como métrica de salud.**
    - Ya existe `capture_closing_odds`. Usarlo como señal de edge real: CLV > 0 sostenido = edge, CLV ≈ 0 = sin edge.
    - Si CLV medio < 0 durante N apuestas, pausar el sistema.

13. **Definir umbrales de stop-loss.**
    - Límite diario de pérdida (ej. 10 stakes) y límite semanal.

14. **Reporte diario.**
    - Resumen automático (WR, P&L, CLV, por mercado) al final del día.

---

## 6. Referencias

- `auto_betting/strategy.py` — lógica de selección (EV, tier thresholds, modelos individuales).
- `auto_betting/management/commands/run_auto_bets.py` — flujo principal.
- `ai_predictions/views.py` — endpoint `/ai/predict/` (11 mercados, sin 1X2).
- `ai_predictions/official_prediction_model.py` — "Predicción Oficial" (promedio ponderado).
- `ai_predictions/xg_shots_model.py` — modelo de tiros a puerta (roto por datos faltantes).
- `ai_predictions/dixon_coles.py` — modelo de goles/1X2 (inflación por ×1.15 y piso de liga).
- `auto_betting/models.py` — `AutoBet`, `HistorialApuesta`, `AutoBetConfig`.

---

*Documento generado por auditoría. Sin cambios de código aplicados.*

---

## 7. Ejecución Fase 1 — Cortafuegos (2026-08-20 02:31 UTC)

**Estado:** ✅ APLICADO. Sin pausar cron (se aplicará Fase 2 hoy mismo).

### Cambios realizados

**Archivo:** `auto_betting/management/commands/run_auto_bets.py`

1. **Mercado 1X2 (Resultado Final) DESACTIVADO**
   - Comentado el bloque `x12 = predict_x12(...)` + `fetch_x12_odds(...)` en `_build_market_data()`.
   - Motivo: no existe en `/ai/predict/`; probabilidades infladas por Dixon-Coles (×1.15 ventaja local + piso de liga).
   - 6 apuestas con edges falsos de +25% a +38% eliminadas.

2. **Mercado Tiros a Puerta DESACTIVADO**
   - Comentado el bloque `shots = predict_shots_on_target(...)` + `fetch_shots_on_target_odds(...)` en `_build_market_data()`.
   - Motivo: `xg_shots_model` roto por datos `hst`/`ast` faltantes en 2026 para ligas top (Bundesliga, Ligue 1, Premier League, Serie A, Serie B Italia, SuperLiga Grecia = 0% cobertura). Fallback a `_default_team_data()` con λ=4.0 fija produce probabilidades absurdas (caso Toronto: P(Under 7.5)=98.8% → LOST).

3. **Docstring actualizado** para reflejar 4 mercados activos (córners, goles, remates totales, BTTS) en lugar de 6.

### Mercados que siguen ACTIVOS

| Mercado | Modelo usado | Estado |
|---|---|---|
| Córners | `corners_model.predecir()` | ✅ Activo |
| Goles totales | `DixonColesModel.predict_match()` | ✅ Activo |
| Remates totales | `xg_shots_model.predict_shots_total()` | ✅ Activo |
| Ambos marcan | `enhanced_both_teams_score_model` | ✅ Activo |

### Mercados DESACTIVADOS

| Mercado | Motivo |
|---|---|
| Tiros a puerta | Datos `hst`/`ast` rotos en 2026 → modelo produce basura |
| 1X2 (Resultado Final) | No existe en `/ai/predict/`; probs infladas por Dixon-Coles |

### Verificación

- Import del módulo: ✅ sin errores de sintaxis.
- Dry-run de `_build_market_data`: confirma que solo se llaman `predict_corners`, `predict_goals`, `predict_total_shots`, `predict_btts`. Los bloques de `predict_shots_on_target` y `predict_x12` están comentados.
- Cron NO pausado (instrucción de John: se aplicará Fase 2 hoy mismo).

### Próximos pasos

- **Fase 2** (conectar al motor oficial): pendiente aprobación de John.
- **Fase 3** (validación de datos): pendiente.
- **Fase 4** (calibración): pendiente.

---

## 8. Ejecución Fase 2 — Conectar al motor oficial (2026-08-20 02:33 UTC)

**Estado:** ✅ APLICADO.

### Objetivo

Reemplazar el uso de modelos individuales crudos (que tomaban el modelo más extremo) por la **Predicción Oficial** = promedio ponderado por confianza de todos los modelos, igual que muestra `/ai/predict/`.

### Cambios realizados

**Archivo: `auto_betting/strategy.py`**

- **Nueva función `get_official_predictions(home_team, away_team, league)`** que ejecuta el pipeline completo:
  - **Goles:** Dixon-Coles + Simple Average + Ensemble + Híbrido General → promedio oficial (4 modelos)
  - **Remates totales:** shots_prediction_model + xg_shots_model → promedio oficial (2 modelos)
  - **Córners:** corners_model (modelo único, ya alineado)
  - **BTTS:** enhanced_both_teams_score_model (modelo único, ya alineado)
  - Usa `official_prediction_model.calculate_official_predictions()` para promediar.
  - Devuelve dict con `lambda`/`yes` y `confidence` por mercado.

- Las funciones individuales (`predict_goals`, `predict_total_shots`, etc.) se conservan en el archivo pero **ya no se usan** en `run_auto_bets.py`.

**Archivo: `auto_betting/management/commands/run_auto_bets.py`**

- `_build_market_data()` **reescrita**: ahora llama a `get_official_predictions()` una vez por partido y construye los datos de mercado desde el resultado oficial.
- Imports actualizados: `get_official_predictions` reemplaza a las 6 funciones individuales.
- Imports de servicios limpiados: `fetch_shots_on_target_odds` y `fetch_x12_odds` eliminados (mercados desactivados en Fase 1).
- Docstring actualizado a v5.

### Verificación

- **Compilación:** imports y sintaxis verificados sin errores.
- **Test funcional** (West Ham vs Leeds, Premier League):

| Mercado | Viejo (individual) | Nuevo (oficial) | Δ |
|---|---|---|---|
| Goles | λ=3.57 (solo Dixon-Coles) | λ=3.29 (4 modelos promediados) | −0.28 |
| Remates | λ=20.60 (solo xg_shots_model) | λ=24.15 (2 modelos promediados) | +3.55 |
| Córners | λ=10.52 (sin cambio) | λ=10.52 | 0 |
| BTTS | P=0.64 (sin cambio) | P=0.64 | 0 |

- **Modelos usados por mercado (oficial):**
  - Goles: Dixon-Coles Poisson, Simple Average, Ensemble Average, Modelo Híbrido General
  - Remates: Shots Prediction Model, XG Shots Model
  - Córners: Corners Avanzado (40/30/15/15)
  - BTTS: Enhanced Both Teams Score

### Impacto esperado

1. **Goles:** la predicción ya no toma Dixon-Coles solo (el más extremo, con ×1.15 ventaja local). Ahora promedia 4 modelos, reduciendo la sobre-confianza.
2. **Remates:** la predicción ya no toma xg_shots_model solo (que usa datos `hst`/`ast` rotos para tiros a puerta, pero SÍ funciona para remates totales con datos `hs`/`as`). Ahora promedia ambos modelos.
3. **Córners y BTTS:** sin cambio (ya usaban el modelo único correcto).

### Próximos pasos

- **Fase 3** (validación de datos): pendiente.
- **Fase 4** (calibración): pendiente.
- **Fase 5** (monitoreo): pendiente.

---

## 9. Ejecución Fase 3 — Validación de datos (2026-08-20 02:41 UTC)

**Estado:** ✅ APLICADO.

### Objetivo

Validar la cobertura de datos por mercado antes de apostar, para que el sistema no use modelos con datos insuficientes que producen probabilidades basura.

### Diagnóstico de cobertura

Se ejecutó un análisis de cobertura de datos por campo y liga (ventana 730 días):

| Campo | Cobertura global | Problema |
|---|---|---|
| `fthg`/`ftag` (goles) | 100% en todas las ligas | ✅ Ninguno |
| `hs`/`as_field` (remates) | 64.6% total | ⚠️ Variable por liga |
| `hst`/`ast` (tiros a puerta) | 64.1% total | ⚠️ Mismo patrón que remates |
| `hc`/`ac` (córners) | 64.3% total | ⚠️ Mismo patrón que remates |

**Ligas con datos insuficientes** (recientes 730 días):

| Liga | Partidos | % con hs/hst/hc |
|---|---|---|
| SuperLiga (Grecia) | 105 | 0% |
| Premier Liga (Azerbaiyan) | 109 | 4% |
| Premijer Liga (Bosnia) | 112 | 7% |
| Liga MX (Mexico) | 134 | 23% |
| NB I (Hungria) | 128 | 17% |
| PFL 1 (Bulgaria) | 134 | 24% |
| Super Liga (Serbia) | 134 | 22% |
| Superligaen (Dinamarca) | 129 | 16% |
| Serie A (Brasil) | 321 | 34% |
| Serie B (Brasil) | 315 | 32% |
| US MLS (USA) | 322 | 34% |
| Primera Division (Argentina) | 317 | 34% |
| Liga I (Rumania) | 139 | 26% |

**Ligas con datos completos** (≥80%):

Championship, League One, League Two, Scottish Premiership, Scottish Championship, Eredivisie, Jupiler Pro League, Ligue 2, Primeira Liga, Segunda División, Süper Lig, 2. Bundesliga, La Liga, Bundesliga, Premier League, Serie A (Italia), Serie B (Italia), Ligue 1.

### Causa raíz de los datos faltantes

Se analizó la fuente de datos por liga:

1. **CSVs de football-data.co.uk** (formato estándar): Tienen `hs`, `hst`, `hc` completos. Ej: Premier League, Bundesliga, Championship.
2. **Scraper de Flashscore** (`source_file='unknown'`): Solo importan marcadores (fthg, ftag, ftr). Las estadísticas (`hs`, `hst`, `hc`) solo se extraen para algunos partidos, no para todos.
3. **CSVs recientes (2025-2026)**: Algunos no incluyen las columnas de estadísticas. Ej: `E0 (26).csv` (Premier League 2025-26) tiene 380 partidos pero 0 con hs/hst/hc.

**Conclusión:** El scraper de Flashscore no está extrayendo estadísticas para todas las ligas. Requiere ejecutar backfill con `scripts/flashscore_scrape.py` en modo `stats` para las ligas afectadas.

### Cambios realizados

#### Punto 6 — Validación de cobertura por mercado

**Archivo: `auto_betting/strategy.py`**

- **Nueva función `validate_market_data(home_team, away_team, league)`** que verifica:
  - **Goles:** ≥10 partidos con `fthg`/`ftag` por equipo (suma local+visitante, ventana 730 días).
  - **Remates:** ≥10 partidos con `hs`/`as_field` por equipo.
  - **Córners:** ≥10 partidos con `hc`/`ac` por equipo.
  - **BTTS:** Usa la misma validación de goles.
- Devuelve `{market: True/False}` por cada mercado.
- Si un equipo tiene <10 partidos con datos del mercado, ese mercado se omite (no fallback silencioso).
- Log de mercados saltados con datos de cobertura para debugging.

**Archivo: `auto_betting/management/commands/run_auto_bets.py`**

- El filtro de datos insuficientes ahora usa `validate_market_data()` en lugar de `analyze_team_statistics('goals')`.
- Si ni siquiera hay datos de goles, el partido se salta entero (igual que antes).
- Si hay datos de goles pero no de remates/córners, solo se saltan esos mercados.

**Integración en `get_official_predictions()`:**
- Antes de ejecutar cualquier modelo, se llama a `validate_market_data()`.
- Solo se ejecutan los modelos para mercados con datos suficientes.
- Los mercados sin datos se saltan con un log informativo.

#### Punto 7 — Fallback al promedio de liga en modelos de remates

**Archivo: `ai_predictions/xg_shots_model.py`**

- **Nuevo método `_get_league_average_data(league)`** que calcula los promedios de la liga (shots, SOT, goals) a partir de los últimos 100 partidos con datos.
- `_get_team_xg_data()` ahora usa `_get_league_average_data()` como fallback cuando un equipo no tiene partidos con `hst`/`ast`, en lugar de `_default_team_data()` con λ=4.0 fija.
- `_default_team_data()` se mantiene como último recurso (si la liga entera no tiene datos).
- Esto también mejora el promedio oficial de remates: si un modelo no tiene datos del equipo, usa el promedio de liga (más realista) en lugar de un valor fijo.

**Archivo: `ai_predictions/shots_prediction_model.py`**

- **Nuevos métodos `_get_league_avg_shots(league, home_away)` y `_get_league_avg_sot(league, home_away)`.**
- `_get_team_shots_average()`, `_get_team_shots_conceded_average()`, `_get_team_shots_on_target_average()` ahora usan fallback al promedio de liga en lugar de valores fijos (12.0/10.0/4.5/4.0).
- Si la liga entera no tiene datos, usa el valor fijo como último recurso.

#### Punto 8 — Diagnóstico de datos faltantes

Se identificó la causa raíz (ver sección "Causa raíz" arriba):
- El scraper de Flashscore no extrae estadísticas (hs, hst, hc) para todas las ligas.
- Los CSVs recientes de algunas ligas no incluyen las columnas de estadísticas.
- **Pendiente:** ejecutar backfill con `scripts/flashscore_scrape.py --mode stats` para las ligas afectadas.

### Verificación

- **Imports:** todos los módulos compilan sin errores.
- **Test funcional (Championship — datos completos):**
  - `validate_market_data`: todos los mercados True.
  - `get_official_predictions`: devuelve 4 mercados (goals, shots, corners, btts).
  - Predicción oficial: goals λ=3.18, shots λ=25.9, corners λ=10.98, btts P=0.54.

- **Test funcional (Liga MX — datos parciales):**
  - `validate_market_data`: goals=True, shots=False, corners=False, btts=True.
  - `get_official_predictions`: devuelve solo 2 mercados (goals, btts).
  - Mercados de remates y córners saltados automáticamente.

- **Test funcional (Serie B Brasil — dry run):**
  - Log: `get_official_predictions: saltando shots_total — datos insuficientes`
  - Log: `get_official_predictions: saltando corners_total — datos insuficientes`
  - Solo se ejecutan models de goals y btts.

- **Test xg_shots_model fallback (SuperLiga Grecia — 0% datos):**
  - `_get_team_xg_data` → fallback a `_get_league_average_data` → fallback a `_default_team_data` (la liga no tiene datos).
  - Esto es esperado: `validate_market_data` salta el mercado antes de que el modelo se ejecute.

### Impacto esperado

1. **Adiós a las predicciones basura:** El sistema ya no intentará predecir córners o remates para ligas donde no hay datos (SuperLiga Grecia, Liga MX, MLS, Serie A Brasil, etc.).
2. **Predicciones más realistas cuando hay datos parciales:** Si un equipo no tiene datos pero la liga sí, el modelo usa el promedio de liga en lugar de un valor fijo.
3. **Menos apuestas, pero de mayor calidad:** Se saltan partidos donde no se puede predecir con confianza, reduciendo el ruido.
4. **Transparencia:** Cada mercado saltado se registra en el log con la razón.

### Próximos pasos

- **Fase 4** (calibración): pendiente.
- **Fase 5** (monitoreo): pendiente.
- **Backfill de datos:** ejecutar `scripts/flashscore_scrape.py --mode stats` para las ligas con datos faltantes (Liga MX, MLS, Serie A Brasil, etc.).

---

## 10. Ejecución Fase 4 — Calibración de probabilidades (2026-08-20 02:55 UTC)

**Estado:** ✅ APLICADO.

### Objetivo

El modelo asigna probabilidades infladas que no reflejan la realidad. Se realizó un backtest con 45 apuestas asentadas y se implementó una función de calibración.

### Backtest (45 apuestas asentadas)

#### Calibración por rango de probabilidad

| Rango P | N | P media | WR real | Gap |
|---|---|---|---|---|
| 0-30% | 9 | 9.9% | 11.1% | +1.2 |
| 40-50% | 5 | 45.2% | 40.0% | -5.2 |
| 50-60% | 13 | 53.9% | 69.2% | +15.3 |
| 60-70% | 9 | 64.3% | 11.1% | **-53.2** |
| 70-80% | 3 | 74.0% | 0.0% | **-74.0** |
| 80-100% | 6 | 86.7% | 66.7% | -20.0 |

**General:** P media 51.9%, WR real 37.8%, Gap = -14.1 puntos.

#### Por mercado

| Mercado | N | P media | WR real | Gap |
|---|---|---|---|---|
| Resultado Final | 12 | 60.6% | 33.3% | -27.2 |
| Total de tiros a puerta | 13 | 64.7% | 46.2% | -18.5 |
| Total de goles | 11 | 50.9% | 36.4% | -14.5 |
| Total de Tiros de Esquina | 8 | 18.8% | 25.0% | +6.2 |
| Ambos Equipos Marcarán | 1 | 58.6% | 100.0% | +41.4 |

**Conclusión:** El modelo sobre-confía masivamente en P>60%. Los mercados de 1X2 y tiros a puerta (ya desactivados en Fase 1) eran los peores. Goles tiene un gap de -14.5pp. Córners está ligeramente sub-predicho.

### Cambios realizados

#### Punto 9 — Calibración de probabilidades

**Archivo: `auto_betting/strategy.py`**

- **Nueva función `calibrate_probability(p)`** que aplica shrinkage hacia 50%:
  - **P ≤ 60%:** shrinkage ligero (factor 0.95). Ej: P=55% → 54.8%.
  - **P > 60%:** shrinkage fuerte (factor 0.50) + cap en 65%. Ej: P=70% → 60%, P=80% → 65%.
  - **Rango válido:** [5%, 95%].
- La calibración se aplica en `_add_candidate()` antes de calcular EV.
- Se guarda tanto `p` (calibrada) como `p_raw` (original) para logging.

#### Punto 10 — Revisión de inflación de Dixon-Coles

No se modificó Dixon-Coles directamente (eso afectaría también la web `/ai/predict/`). En su lugar:
- La Fase 2 ya promedia Dixon-Coles con otros 3 modelos (Simple Average, Ensemble, Híbrido General), reduciendo su impacto.
- La calibración de la Fase 4 corrige el sesgo residual del promedio.
- El multiplicador ×1.15 de ventaja local y el piso de liga siguen presentes pero diluidos por el promedio.

#### Punto 11 — Revisión del cálculo de EV

- El EV ahora se calcula con la **P calibrada**, no la cruda.
- Los umbrales escalonados por cuota (tiers) ya exigen EV mínimo de 5-20% según rango.
- Esto funciona como un **buffer de seguridad natural**: solo apuesta si el EV calibrado supera el umbral.

### Tabla de calibración

| P raw | P calibrada | Δ |
|---|---|---|
| 10% | 12.0% | +2.0 |
| 25% | 26.2% | +1.3 |
| 40% | 40.5% | +0.5 |
| 50% | 50.0% | 0.0 |
| 55% | 54.8% | -0.2 |
| 60% | 59.5% | -0.5 |
| 65% | 57.5% | -7.5 |
| 70% | 60.0% | -10.0 |
| 75% | 62.5% | -12.5 |
| 80% | 65.0% | -15.0 |
| 90% | 65.0% | -25.0 |
| 95% | 65.0% | -30.0 |

### Verificación — Test real con dinero (2026-08-20 02:59 UTC)

Se ejecutó `run_auto_bets --email admin@predicta.com.co` con cuota mínima temporal de 1.50:

| Partido | Mercado | Selección | Cuota | P raw | P cal | EV cal | Coupon | Estado |
|---|---|---|---|---|---|---|---|---|
| Athletic Club vs CRB | BTTS | Sí | 1.80 | 59.0% | 58.5% | +5.4% | 13017053800 | OPEN |
| Novorizontino vs América MG | Goles | Under 2.5 | 1.81 | 58.5% | 58.1% | +5.2% | 13017052906 | OPEN |

**Total apostado:** 1.000 COP (~$0.25 USD). Ambas en Serie B Brasil, partidos a las 22:30 y 23:30 UTC.

Observaciones del test real:
- **41 partidos escaneados**, solo 4 mapeados a ligas de Predicta.
- 2 saltados por datos insuficientes (Sheffield Wed y Rayo Vallecano con 1 solo partido en BD).
- 2 apuestas colocadas con EV calibrado marginal pero positivo (+5.2% y +5.4%).
- Sin la calibración, las P habrían sido 59% (sin cambio, están en rango bien calibrado). La calibración no afectó estas apuestas porque están en el rango <60%.
- **Cron de monitoreo** configurado para las 23:00 UTC (post-partido) para verificar resultados.

### Limitaciones

- **45 muestras** es poco para calibración estadística formal (Platt scaling / isotonic regression requieren >200).
- La calibración actual es **simple y conservadora**: shrinkage lineal + cap.
- Con más datos (Fase 5), se puede implementar calibración más fina por mercado y rango.
- No se modificó Dixon-Coles directamente para no afectar la web.

### Próximos pasos

- **Fase 5** (monitoreo): pendiente — CLV como métrica de salud, stop-loss, reporte diario.
- **Backfill de datos:** ejecutar `scripts/flashscore_scrape.py --mode stats` para las ligas con datos faltantes.
- **Calibración avanzada:** cuando se acumulen >200 apuestas asentadas, implementar Platt scaling o isotonic regression por mercado.
