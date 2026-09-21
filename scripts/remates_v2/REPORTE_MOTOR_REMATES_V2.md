# MOTOR REMATES TOTALES v2 — Reporte de diseño y primer test
**Fecha:** 2026-09-13 · **Estado:** standalone, NO en producción (read-only respecto al bot)

## Qué se construyó

Motor independiente de remates totales, desacoplado del pipeline web:

1. **Dataset leak-free** (`build_features.py` → `features_all.csv`):
   37.946 partidos con features por equipo (ventana exponencial, half-life 120d):
   remates for/against por venue, SOT, inside-box, corners, forma L5, descanso, media de liga.
   **Sin leakage**: cada fila usa solo partidos anteriores a su fecha.
2. **Modelo**: HistGradientBoosting (sklearn) + features derivadas A/D (`lamT_a`, ratios) +
   **calibración lineal** (corrige el sesgo del GBM). Artefacto: `gbm_v23.pkl`.
3. **Test out-of-sample pedido por John**: partidos de HOY (13-sep) que la BD NO tenía;
   stats bajadas de la API post-partido (`today_ft_stats.json`, 112 partidos con remates).
4. **Shadow ledger** (`shadow_ledger.jsonl` + `remates_v2_shadow2.py` + `shadow_score.py`):
   registra predicciones + líneas reales de BetPlay PRE-partido y las puntúa al terminar.
   Es la via para "medir edge prospectivamente" sin apostar. Colector automático 2x/día.

## Resultados

### Test de HOY (out-of-sample real, 110 partidos)
| Modelo | MAE | RMSE | bias |
|---|---|---|---|
| **v2.3 (nuevo, calibrado)** | **4.60** | 5.85 | −0.40 |
| Motor viejo (shots+xg) | 5.69 | — | — |
| Baseline media global (25.25) | 5.51 | — | — |
| Baseline media de liga | 4.87 | — | — |
| Baseline last-5 | 6.76 | — | — |

→ **Mejora 19% sobre el motor viejo en idénticos partidos. Gana en 65% de los partidos (72/110).**

### Walk-forward (7.590 partidos, mar–sep 2026)
v2.3: MAE 4.83 · baseline liga 5.04 · baseline global 5.14 → sigue ganando en ventana amplia.

### Distribución de error (HOY)
±3 remates: 40% · ±5: 60%. Cola: 3 partidos con error >15 (K League 4 remates reales vs 20 predichos; MLS 42).
Sesgo residual: subpredicción media de −0.4 (corregida con calibración).

## Requisito de edge (contexto de decisión)
Para batir el vig de ~11% de BetPlay en remates totales se necesita error de λ ≤ ~0.9-1.3 disparos.
Hoy: MAE 4.6 (insuficiente aún), pero ya bate a los baselines y al motor viejo.
El shadow ledger acumula evidencia prospectiva (modelo vs mercado con líneas reales) para decidir
activación solo con evidencia: criterio = MAE_model < MAE_market y P&L hipotético > 0 en ≥50 picks.

## Próximos pasos sugeridos (sin implementar aún)
1. Dejar correr el shadow ledger (job `remates-v2-shadow-collect`, 10:00 y 22:00 UTC).
2. Re-test semanal: cuando haya ≥30 partidos puntuados revisar `shadow_report.md`.
3. Si el modelo bate al mercado en prospectivo, entonces discutir integración a producción.

## Archivos
- Scripts: `scripts/remates_v2/*.py` · Modelos: `gbm_v22.pkl`, `gbm_v23.pkl`
- Datos: `features_all.csv`, `features_v22.csv`, `histories.pkl`, `today_ft_stats.json`
- Evals: `eval_v23.txt`, `compare_final.txt`, `eval_final.txt`, `live_out.txt`
- Shadow: `shadow_ledger.jsonl`, `shadow_scored.jsonl`, `shadow_report.md`

## Addendum 2026-09-13 21:25 UTC — test extra pedido por John (partidos de HOY que la BD aún no tenía)
- Se bajaron stats post-partido (API directa, sin tocar BD/bot) de los FT de hoy en ligas cubiertas: 20 partidos nuevos, 7 usables → test OOS adicional: `eval_newft_20260913.txt`.
- v2.3 en esos 7: MAE 4.21 / RMSE 5.20 (viejo 5.29) → gana 5/7. Ej.: Sassuolo–Juventus 26.8 vs 28 real (err −1.2); Real Sociedad–Atlético 26.4 vs 21 (+5.4).
- **Combinado hoy: n=117 → v2.3 MAE 4.58 vs viejo 5.66 (mejora 19.1%, gana 77/117).** `eval_combined_20260913.txt`.
- Fix aplicado al colector shadow (`remates_v2_shadow2.py`): tokenización de nombres normalizada (NFKD + separadores) — resolvía mal nombres con guiones ("Flamengo-RJ"). Ya no aplica a los fixtures actuales (esos corren solo por job). Sin cambios al modelo.
- Scripts: `fetch_today_stats_extra.py`, `eval_newft.py`, `eval_combined_today.py`.

## Addendum 3 — Bet-sim sin cuotas (pedido John)
- 118 partidos de hoy. Regla sin odds: OVER si λ≥25.5+0.75, UNDER si λ≤25.5−0.75 (también probado margen 0, ±1.0, ±1.5 y línea=media de liga).
- **Principal: 93 apuestas → 67 ganadas / 26 perdidas (72.0%).** ε=0: 80/38. B: 53/29 (64.6%).
- Archivo: `betsim_no_odds_20260913.txt` (incluye las 26 pérdidas listadas). Script: `betsim_no_odds.py`.
- Caveat: winrate no es ROI; las ganadas suelen ser favoritas a cuota baja y las pérdidas colas largas — sin cuotas no hay juicio de rentabilidad.

## INTEGRACIÓN A PRODUCCIÓN (2026-09-14 ~00:40 UTC, orden de John)
Motor v2.3 LIVE en el bot, como un mercado más ("remates"), con el mismo embudo de edge y filtros por usuario.

**Qué se implementó:**
- `auto_betting/remates_engine.py`: λ v2.3 en vivo desde la BD (features leak-free: half-life 120d, ventana 400d, n≥3 por equipo), anclaje por IDs de API-Football (sin fuzzy de clubes) + NegBin phi=42.36 para probabilidades.
- `MarketFilterConfig` + UI `/auto-betting/configuracion/umbrales/`: nuevo grupo **"Remates totales"** (Over/Under: activo, P mín, conf, EV mín, cuota mín, línea mín/máx). Editables por admin.
- Embudo compartido `select_bets`: devig, edge ≥5pp vs cuota justa, tiers por cuota, EV, distancia línea-λ (0.75), CLV breaker, dedup por evento+mercado, tope de exposición, anti-movimiento de línea. Todo idéntico a los demás mercados.
- `services.fetch_total_shots_odds`: label REAL corregido ("Total de Tiros (Resuelta usando Opta Data)" — era BUG A del audit) + 1 sola llamada HTTP.
- `capture_closing_odds` y snapshots ahora incluyen el label de remates (CLV funcionará).
- `calibration_report` (P3b): des-calibración de remates auto-deshabilita `remates_over/under_enabled`.
- Bonus fix: `min_line/max_line` por submercado ahora SÍ se aplica (antes se pasaba y se ignoraba; afecta SOT si se reactiva).

**Validación:**
- λ en vivo reproduce el ledger shadow ±0.45 (dif. = definición l5 training vs venue).
- Funnel real: Inter-Udinese genera 2 candidatos (over 27.5 @1.71 EV+10.2%, over 28.5 @1.92 EV+13.5%) para cuentas con cuota mín 1.7; ninguna otra pasó los filtros (conservador).
- Dry-run admin/admin2 OK; comandos sin errores; servicio reiniciado OK.

**Estado de umbrales al lanzar:** remates_over/under activos, P≥0.50, EV≥0, línea sin tope. Los demás mercados conservan su estado previo.

## Primera corrida EN VIVO (14-sep 03:00 UTC) — VERIFICADA
- Motor ejecutó en los 5 fixtures con mercado (λ estables, sin errores en `logs/auto_betting.log`).
- **3 apuestas reales colocadas** — Inter vs Udinese, Over 28.5 @1.92 (P=53.3%, EV=+13.5%):
  admin2 (2.2M Kambi u.), carlosantoniom051 (13M), carlos3 (40M). Todas OPEN; partido 18:45 UTC.
- Nota operativa: el job de verificación programado (cb1f7c04) sufrió timeout 2x por contexto de sesión pesado (600s) y fue eliminado; verificación hecha manualmente. El job de winrate (5fc76171) fue endurecido (timeout 1800s + light-context).
