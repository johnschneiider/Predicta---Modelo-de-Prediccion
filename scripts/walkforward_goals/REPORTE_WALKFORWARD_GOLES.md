# Walk-Forward GOLES Over/Under — Informe completo
**Fecha:** 2026-09-12 · **Estado:** investigación concluida (NADA implementado en producción)
**Petición:** estudiar cómo hacer rentable el mercado de goles O/U habilitado y sellado.

---

## 0) Resumen ejecutivo

1. **Bug estructural encontrado en la fórmula λ de producción** (`dixon_coles.py:173-174`):
   los divisores de normalización están invertidos entre local/visitante. Resultado:
   **λ total +20.5% inflado** (3.10 vs 2.58 real), estable en las 13 temporadas y 15 ligas.
2. **Por eso goles perdía siempre**: P(over) del modelo 58.6% vs real 47.4% (+11pp de sesgo).
   Es la causa raíz de las pérdidas históricas (−93K COP en 386 apuestas, WR 44.6%).
3. **Pero arreglar el bug NO lo hace rentable.** Con el fix, λ queda casi perfecto
   (2.555 vs 2.575; ±0.02) — y aun así **el modelo no bate al mercado**:
   AUC modelo 0.548 vs AUC mercado 0.577. El blend le da peso 0.07 al modelo y 1.0 al mercado.
   Incluso el modelo ridge "mejorado" (AUC 0.545) no bate al mercado.
4. **ROI con modelo arreglado, cuota máxima, edge≥5%: −0.44% (z=−0.9)** ≈ cero.
   Con cuota promedio: −4.8% a −5.9% (≈ el vig de 7%). Ningún subconjunto probado
   (líneas, colas, p extremas, contrarian, EV hasta 20%, por liga, por temporada)
   da ROI positivo estadísticamente significativo.
5. **Veredicto:** con datos de nivel de equipo (medias/ratings), el mercado de goles O/U 2.5
   es demasiado eficiente; no hay edge extraíble. Para hacerlo rentable se necesita
   información que el mercado no tenga (alineaciones/bajas/xG fresco) o un libro más barato.

---

## 1) Metodología (sin lookahead)

- **Datos:** 749 CSV football-data.co.uk (histórico en `media/excel_files/`) →
  84,565 partidos deduplicados, de los cuales **62,864 con cuotas reales O/U 2.5** (2005–2018, 15 ligas).
  Cuotas: `BbAv` (promedio del mercado, vig 7.16%) y `BbMx` (máxima, vig 1.88%).
- **Motor walk-forward** (`engine.py`): replica EXACTA de la cadena de producción
  (dixon_coles.calculate_lambda_parameters: ventanas 730d, últimos 30/200/500, piso de liga,
  límites p05/p99, Poisson) usando **solo partidos estrictamente anteriores** (bisect por fecha).
- **Corrección de nivel walk-forward** (`evaluate.py`): ratio expanding = Σreal/Σλ por liga
  (mín 300 partidos previos) → λ_corr. Simula recalibración honesta.
- **Evaluaciones:** ROI a stake plano vs cuotas avg/max, Brier/AUC vs mercado,
  isotonic expanding, blend logístico walk-forward, ratings Poisson ridge con decay τ=90d
  refit cada 90 días (`ridge_ratings.py`).

Artefactos: `scripts/walkforward_goals/` (8 scripts, 4 reportes TXT, 4 pickles).
Referencia de contraste: outputs reales de producción (AutoBet/HistorialApuesta 2026).

---

## 2) Hallazgo central: el bug de la fórmula λ

### 2.1 El defecto (código de producción)

```python
# dixon_coles.py:173-174 (ACTUAL — mal)
raw_lambda_home = (home_attack / league_home_avg) * (away_defense / league_away_avg) * league_home_avg
raw_lambda_away = (away_attack / league_away_avg) * (home_defense / league_home_avg) * league_away_avg
# líneas 177-178: *1.15 y *0.95 (multiplicadores fijos) + piso de liga (185-190)
```

**Problema:** `away_defense` se mide en goles de local (fthg) pero se divide por
`league_away_avg`; `home_defense` se mide en goles de visitante pero se divide por
`league_home_avg`. Los divisores están **cruzados**. Con lgH≈1.46 y lgA≈1.12:
λ_h queda inflado ≈ ×1.53 y λ_a desinflado ≈ ×0.71. Los multiplicadores fijos
1.15/0.95 agravan. El piso de liga termina de escalar todo hacia arriba.

### 2.2 Evidencia walk-forward (62,864 partidos)

| Métrica | Producción (bug) | Real | Fix propuesto |
|---|---|---|---|
| λ local | 2.266 | 1.459 | 1.455 ✅ |
| λ visitante | 0.836 | 1.116 | 1.100 ✅ |
| **λ total** | **3.102 (+20.5%)** | **2.575** | **2.555 (−0.8%)** ✅ |

- Sesgo estable en TODAS las temporadas 2005-2017 (−0.44 a −0.68 goles) y las 15 ligas (−0.34 a −1.02).
  → Es estructural, no varianza.
- P(over) medio del modelo: 58.6% vs over real 47.4%.
- Fix = intercambiar divisores (`D_j/lgH`, `D_i/lgA`) y quitar multiplicadores fijos.

### 2.3 Confirmación cruzada con producción (2026)

- λ predicho medio en apuestas reales: 3.35 | WR por tramos: λ∈[2.5,3) → 61%;
  λ∈[3,3.5) → 34%; λ∈[3.5,4) → 36%; λ≥4 → 40%. **A mayor λ predicho, peor WR** (señal invertida).
- Histórico goles: 386 asentadas, WR 44.6%, P&L −93,185 COP. Explicado por completo por el sesgo.

---

## 3) ¿Y si lo arreglamos? — El mercado sigue ganando

### 3.1 Poder predictivo (62,864 partidos, walk-forward puro)

| Modelo | Brier ↓ | AUC ↑ |
|---|---|---|
| Producción (corregido nivel) | 0.2528 | 0.5489 |
| + Isotonic forma | 0.2477 | 0.5481 |
| **Ridge ratings (mejor modelo probado)** | 0.2481 | 0.5448 |
| **Mercado (cuotas devigged)** | **0.2446** | **0.5773** |

- **Blend logístico:** coef modelo +0.066 vs mercado +1.001 → el modelo no aporta info
  más allá del mercado (blend AUC 0.5776 ≈ mercado 0.5779).
- Ridge blend (train): coef ridge **−0.21** vs mercado +1.14 → peso negativo, cero aporte.

### 3.2 ROI por estrategia (modelo arreglado, edge vs cuota justa)

| Estrategia | n | WR | ROI (cuota avg) | ROI (cuota max) |
|---|---|---|---|---|
| UNDER edge≥5% | 23,801 | 53.6% | −4.81% | — |
| OVER edge≥5% | 17,199 | 48.7% | −5.90% | — |
| Ambos edge≥5% (max) | 41,000 | 51.5% | — | **−0.44%** (z=−0.9) |
| Ambos EV≥15% (max) | 27,373 | 50.0% | — | −0.54% (z=−0.9) |

**Lectura directa:** cuota promedio = pagar vig 7% sin edge ⇒ −5%.
Cuota máxima = vig 1.88% ⇒ ≈ 0%. El modelo no genera ROI positivo en ningún corte.
Ningún nicho significativo (todos |z|<1.1 salvo los negativos).

---

## 4) ¿Qué haría falta para hacerlo rentable? (análisis, sin implementar)

### Opción A — Corregir el bug (prerequisito de cualquier escenario)
El fix de 173-174/177-178 deja el λ casi insesgado. **Necesario** para integridad de la web
(la "Predicción Oficial" de goles muestra +20% inflado) — **no suficiente** para apostar.
Riesgo: tocar la fórmula cambia TODOS los cálculos de goles (web, autobet, BTTS-adyacentes).

### Opción B — Para apostar goles "por volumen" (no recomendado para P&L)
Si se quisiera reactivar: solo con modelo corregido, solo cuota máxima conseguible,
shadow mode previo. Expectativa honesta: **≈ 0 ± ruido** (moneda al aire con trabajo).
No apto para generar dinero.

### Opción C — Para edge real (la única vía con futuro)
Se necesita información que el mercado NO tenga al precio que paga BetPlay:
1. **Datos nuevos:** alineaciones confirmadas, bajas, xG de las últimas rondas
   (hoy el modelo usa medias de hasta 2 años), descanso/calendario, clima.
2. **Ancla sharp:** contrastar contra cuota de cierre de un libro sharp (Pinnacle) y
   apostar solo divergencias justificadas — requiere alimentar esas cuotas.
3. **Mercados alternativos** donde el mercado es menos eficiente (el estudio validó el harness:
   reutilizable para córners/SOT/goles por equipo si algún día se quiere reabrir con criterio).

**Umbral duro a batir:** AUC 0.577 (el mercado). Modelo actual: 0.548. Brecha: 0.03.

---

## 5) Estado y siguientes pasos sugeridos

- ❌ NADA implementado (John: "No lo implementes aún"). Cero cambios en producción.
- ✅ Esperado si un día se decide: (1) fix del sesgo con tests de regresión sobre la web;
  (2) decisión separada sobre reapertura (con shadow mode + criterio go/no-go).
- ✅ El harness walk-forward queda listo para auditar cualquier otro mercado sellado.

---

## Artefactos

```
scripts/walkforward_goals/
├── load_full.py / load_dataset.py     # datasets (84,565 / 62,864 con cuotas)
├── engine.py                          # réplica walk-forward de producción (62,864 sims)
├── evaluate.py                        # sesgo + corrección + estrategias (evaluation_report.txt)
├── niche_search.py                    # nichos/colas/contrarian (niche_report.txt)
├── form_blend.py                      # isotonic + blend (form_report.txt)
├── ridge_ratings.py / ridge_eval.py   # modelo mejorado (ridge_report.txt)
├── fix_test.py / fix_eval.py          # test del bug + modelo arreglado (fixed_out.pkl)
└── *.pkl                              # datos y salidas para reproducir
```
