# Auditoría Auto-Betting — 2026-08-22

> Alcance: estado actual del sistema tras las Fases 1-4 (aplicadas 20-Ago) + datos reales acumulados 16→22 Ago (221 apuestas en `HistorialApuesta`, 153 en `AutoBet`).
> Metodología: lectura de código (`strategy.py`, `run_auto_bets.py`, `services.py`), queries directas a `db.sqlite3`, logs de `logs/auto_betting.log`, crontab `www-data`.

---

## 1. Resumen ejecutivo

El sistema está **ligeramente rentable en conjunto pero con riesgo estructural sin controlar**:

- **P&L global asentado (todas las apuestas, sistema+manual): +249.324 COP** (85 WON / 92 LOST, WR 48.0%).
- **Solo sistema (`is_system=True`): +64.155 COP** en 115 apuestas asentadas, WR 43.5% — rentable por tamaño de cuota media ganada, no por win rate.
- **Riesgo #1 (grave):** NO existe stop-loss ni circuit breaker. Un día malo (como el 21-Ago, −5.800 COP en un solo día para 1 usuario con stake bajo) puede escalar sin límite, especialmente con el usuario `admin2` que tiene **stake 20x mayor** (10.000 COP vs 500 COP).
- **Riesgo #2 (grave):** duplicación estructural de apuestas — 2 usuarios (`admin`, `admin2`) corren el mismo escaneo y terminan apostando el **mismo partido+mercado+selección** de forma independiente (35+ casos detectados). No es un bug de "doble apuesta" del mismo usuario, sino concentración de riesgo no gestionada a nivel de exposición total del negocio (mismo evento, dos cuentas, mismo lado).
- **Riesgo #3 (medio):** el mercado "Total de tiros a puerta" activo hoy tiene WR real 40% en 15 apuestas — no ha demostrado edge, sigue dependiendo de datos `hst`/`ast` parciales.
- **Riesgo #4 (medio):** córners (mercado núcleo, el que dio origen a la app) tiene WR 28.6% con ROI −27.1% en 28 apuestas asentadas del sistema — es el peor mercado activo, a pesar del fix de `min_p=0.56` aplicado.
- No se detectó ningún **bug de ejecución activo** (los bugs de Problema 1-5 del 20-Ago ya están corregidos en el código actual). Sí hay **una brecha de diseño**: falta de stop-loss/circuit-breaker y de coordinación de exposición entre las dos cuentas.

---

## 2. Estado del código vs. auditoría anterior (20-Ago)

| Fix del 20-Ago | Estado verificado hoy (22-Ago) |
|---|---|
| Fase 1: 1X2 y tiros a puerta (SOT roto) desactivados | ✅ Confirmado: `_build_market_data()` no llama `predict_x12`; el bloque de tiros a puerta activo hoy es **"shots_on_target"**, que usa `xg_shots_model.predict_shots_on_target_total()` con **fallback a promedio de liga** (Fase 3), distinto del que causó el caso Toronto. No es el mismo bug. |
| Fase 2: Predicción Oficial (promedio de modelos) | ✅ Confirmado en logs de hoy: goles promedia 4 modelos, remates 2 modelos. |
| Fase 3: validación de cobertura de datos (≥10 partidos/equipo) | ✅ Confirmado: `validate_market_data()` presente y usada en `get_official_predictions()` y en el comando. |
| Fase 4: calibración de probabilidad (shrinkage, cap 60%) | ✅ Confirmado, con filtro adicional por mercado (`MARKET_FILTERS`, córners/SOT en 0.56) añadido después. |
| Fase 5 (monitoreo/CLV/stop-loss) | ⚠️ CLV: implementado y corriendo (cron `*/15 * * * *`). **Stop-loss: NO implementado.** No hay ningún campo ni lógica de límite de pérdida diaria/semanal en `AutoBetConfig` ni en el comando. |

**Conclusión:** los 5 problemas graves de la auditoría del 20-Ago están corregidos en el código vigente. El sistema actual (v7, revisado hoy) es sustancialmente más sano que el que causó la pérdida del 19-Ago. El riesgo hoy es de **otra naturaleza**: falta de gestión de exposición/stop-loss, no de modelos rotos.

---

## 3. Datos estadísticos — auditoría completa (221 apuestas asentadas + abiertas)

### 3.1 Resultado global (todas, sistema + manual)
| Métrica | Valor |
|---|---|
| Total registros | 221 (85 WON, 92 LOST, 38 OPEN, 6 VOID) |
| Win rate asentadas | 48.0% |
| Stake total asentado | 687.400 COP |
| Payout total asentado | 936.724 COP |
| **P&L neto** | **+249.324 COP** |

### 3.2 Solo sistema automático (`is_system=True`), por usuario
| Usuario | N asentadas | WR | Stake total | P&L | ROI |
|---|---|---|---|---|---|
| admin (stake 500 COP) | 81 | 40.7% | 40.500 COP | +6.605 COP | +16.3% |
| admin2 (stake 5-10k COP) | 34 | 50.0% | 300.000 COP | +57.550 COP | +19.2% |

**Observación clave:** `admin2` apuesta **20x más dinero por ticket** que `admin`. Ambos corren la misma lógica de selección sobre los mismos partidos → mismo perfil de riesgo, exposición 20x mayor. Si el sistema tiene una mala racha, `admin2` pierde 20x más en términos absolutos.

### 3.3 Por día (solo sistema, asentadas)
| Fecha | N | WR | P&L COP |
|---|---|---|---|
| 16-Ago | 8 | 37.5% | +1.040 |
| 17-Ago | 21 | 42.9% | +3.130 |
| 18-Ago | 3 | 66.7% | +755 |
| **19-Ago** | 18 | **22.2%** | **−2.335** |
| 20-Ago | 6 | 66.7% | +22.815 |
| **21-Ago** | 33 | 42.4% | **−5.800** |
| 22-Ago (parcial) | 26 | 53.8% | +44.550 |

**Varianza alta día a día**, típico de un sistema con volumen bajo-medio y edges marginales. El 22-Ago concentra la mayor parte de la ganancia total (una racha positiva, no necesariamente reproducible).

### 3.4 Por mercado (solo sistema)
| Mercado | N | WR | P&L COP | ROI% |
|---|---|---|---|---|
| **Total de goles** | 45 | 53.3% | **+87.775** | **+55.4%** ✅ mejor mercado, con margen |
| Total de Tiros de Esquina (córners) | 28 | **28.6%** | **−28.140** | **−27.1%** ⚠️ peor mercado |
| Total de tiros a puerta | 15 | 40.0% | +55 | +0.7% (break-even, no demuestra edge) |
| Resultado Final (1X2, ya desactivado) | 14 | 35.7% | −380 | −5.4% |
| Ambos Equipos Marcarán (BTTS) | 13 | 53.8% | +4.845 | +7.6% |

**Córners es el mercado que originó la app (sección 10 del SOUL.md la llama "núcleo") y hoy tiene el peor ROI de todos los mercados activos**, incluso después del ajuste de `min_p` a 0.56 el 22-Ago.

### 3.5 Por rango de cuota jugada (solo sistema)
| Rango | N | WR | P&L COP |
|---|---|---|---|
| <2.0 | 3 | 0.0% | −1.500 |
| 2.0–2.5 | 67 | 44.8% | **−50.085** |
| 2.5–3.0 | 19 | 36.8% | +48.815 |
| 3.0–4.0 | 11 | 45.5% | +10.800 |
| 4.0+ | 15 | 53.3% | +56.125 |

**Hallazgo importante:** el tramo de cuota 2.0–2.5 (el más usado, 67 de 115 apuestas = 58% del volumen) es el que **más dinero pierde** (−50.085 COP), mientras que cuotas más altas (2.5+) generan toda la ganancia. Esto sugiere que el filtro de cuota mínima (2.0) está dejando pasar demasiadas apuestas de bajo valor esperado real, y que el edge del sistema aparece más claro en cuotas medias/altas donde exige más EV/confidence por los tiers.

### 3.6 CLV (Closing Line Value)
- 114 apuestas con CLV calculado, CLV promedio **+1.18%** (positivo, señal débil pero real de que se juega antes de que caiga la cuota).
- Solo **32.5%** de las apuestas tienen CLV positivo — mayoría negativo, promedio positivo por unos pocos casos con CLV alto. No es una señal fuerte de edge sostenido todavía (muestra chica).

### 3.7 Duplicación de apuestas entre cuentas
Se detectaron **35 pares** de eventos+mercado donde `admin` y `admin2` apostaron exactamente el mismo partido, mercado y selección (mismas cuotas, minutos de diferencia) — es esperado dado que ambos corren el mismo motor de predicción sobre el mismo universo de partidos, pero significa que **la exposición real del negocio a un mismo resultado está duplicada/multiplicada**, no diversificada. No es un bug de código (no es doble-apuesta del mismo usuario — hay `unique_together` correcto), es una **falta de gestión de portafolio a nivel de negocio**.

---

## 4. Riesgos identificados (priorizados)

### 🔴 Riesgo 1 — Sin stop-loss ni circuit breaker
No existe ningún límite de pérdida diaria o semanal. `AutoBetConfig` solo limita **cantidad de apuestas** (`max_apuestas_diarias`), no **pérdida acumulada**. Un día con mala racha estadística (ej. 21-Ago, −5.800 COP con stake bajo) puede repetirse con `admin2` (stake 20x mayor) y perder ~116.000 COP en un solo día sin que nada lo detenga.

### 🔴 Riesgo 2 — Exposición duplicada entre cuentas sin gestión de portafolio
Las dos cuentas activas corren el mismo motor sobre el mismo universo de partidos y terminan apostando el mismo lado del mismo evento en 35+ casos. Si se piensa en "banca total del negocio" (no por cuenta separada), el riesgo real por evento es la suma de ambos stakes, no gestionado como un límite de exposición único.

### 🟠 Riesgo 3 — Córners con ROI negativo persistente (−27.1%)
Es el mercado "núcleo" original de la app y hoy es el que más pierde. El fix de `min_p=0.56` (22-Ago) es muy reciente (mismo día) — no hay evidencia todavía de que haya arreglado el problema; los datos post-fix (19 apuestas registradas hoy, 8 OPEN) aún no se pueden evaluar.

### 🟠 Riesgo 4 — "Tiros a puerta" sin edge demostrado (ROI +0.7%, break-even)
A pesar de los fixes de cobertura de datos (Fase 3), el mercado sigue sin generar valor real. Su presencia diluye el rendimiento del portafolio sin aportar.

### 🟡 Riesgo 5 — Tramo de cuota 2.0-2.5 pierde dinero (−50.085 COP, 58% del volumen)
El filtro `cuota_minima=2.0` deja pasar demasiado volumen de bajo valor. La rentabilidad del sistema depende de un subconjunto (cuotas ≥2.5), y ese subconjunto es solo el 42% del volumen apostado.

### 🟡 Riesgo 6 — Credenciales en texto plano
Ya señalado en SOUL.md sección 13 (pendiente): tickets/punter_id de BetPlay sin cifrar en DB ni en documentación. Riesgo de seguridad, no de trading, pero relevante si se comparte el repo o hay una brecha.

### 🟢 Riesgo 7 — Muestra estadística todavía pequeña
115 apuestas del sistema (81+34) es insuficiente para conclusiones robustas por mercado/cuota. Los % de WR y ROI por segmento (tabla 3.4/3.5) tienen intervalos de confianza amplios; podrían revertirse con 50-100 apuestas más.

---

## 5. Cómo aumentar beneficio y reducir riesgo — Plan concreto

### Inmediato (esta semana)
1. **Implementar stop-loss diario y semanal por usuario.**
   - Añadir campo `stop_loss_diario_cop` a `AutoBetConfig` (ej. 10 stakes = 10x el stake).
   - En `run_auto_bets.py`, antes de cada apuesta: calcular P&L neto del día (via `AutoBet`/`HistorialApuesta`) y si supera el límite negativo, saltar el resto del run y loguear alerta.
   - Sugerido: límite diario = 10× stake por usuario (5.000 COP para admin, 100.000 COP para admin2), límite semanal = 3× el límite diario.

2. **Desactivar o repensar córners** (ROI −27.1%, 28 muestras) hasta acumular ≥30 apuestas post-fix del 22-Ago con resultado positivo. Es el candidato más claro para pausar mientras se valida el fix reciente.

3. **Subir la cuota mínima a 2.5** (o filtrar el tramo 2.0-2.5 con EV mínimo más alto). Los datos muestran que ese tramo es el único negativo; todo lo demás es rentable.

4. **Gestionar exposición combinada entre cuentas.** Antes de que `admin2` apueste un evento+mercado que `admin` ya apostó (o viceversa), aplicar un límite de exposición total por evento (ej. no más de X COP combinados en el mismo partido/mercado entre todas las cuentas del sistema), o simplemente aceptarlo como riesgo conocido y dimensionarlo en el reporte de riesgo diario.

### Corto plazo (2-3 semanas)
5. **Retirar o reducir tiros a puerta** si no mejora tras 20-30 apuestas más — actualmente en break-even, no aporta EV real, solo diluye rendimiento del portafolio.

6. **Reporte automático diario** (ya insinuado en el plan del 20-Ago, sección 5.14, nunca implementado): WR, P&L, ROI, CLV por mercado y por usuario, enviado a John por Telegram. Permite detectar rachas negativas rápido sin depender de auditoría manual.

7. **Aprovechar el edge real detectado: goles (ROI +55.4%) y cuotas ≥2.5 (ROI positivo consistente).** Considerar aumentar ligeramente el stake o el `max_apuestas_diarias` **solo** para el mercado de goles con cuota ≥2.5, manteniendo el resto conservador. Esto concentra el capital donde ya hay evidencia de edge, en vez de repartirlo uniforme entre mercados con y sin edge.

### Medio plazo (1-2 meses)
8. **Calibración avanzada (Platt/isotonic) por mercado** cuando se acumulen ≥200 apuestas asentadas por mercado — la calibración actual (shrinkage lineal simple) es un parche razonable pero temporal.

9. **Kelly fraccional para el sizing del stake** en lugar de stake fijo — permitiría capitalizar más los mercados con edge demostrado (goles) y menos los marginales (córners, SOT), en vez del mismo stake fijo para todo.

10. **CLV como gate de entrada**, no solo métrica de reporte: si el CLV medio de un mercado cae por debajo de 0 sostenido durante N apuestas, pausar ese mercado automáticamente (ya se sugirió el 20-Ago, aún pendiente de automatizar — hoy solo se calcula, no se actúa sobre él).

---

## 6. Conclusión

El sistema **no tiene bugs de ejecución activos** — los 5 problemas graves de la auditoría anterior están corregidos y verificados en el código vigente. El riesgo hoy es de **gestión de capital, no de modelo roto**:
- Falta stop-loss/circuit-breaker (el hueco más urgente).
- Un mercado (córners) sigue perdiendo dinero de forma consistente.
- El tramo de cuota más usado (2.0-2.5) es el único que pierde dinero en conjunto.
- Dos cuentas duplican exposición sin coordinación.

**El camino de mayor apalancamiento para más beneficio con menos riesgo:** subir el filtro de cuota mínima a 2.5, pausar córners hasta validar el fix reciente, e implementar stop-loss diario — son 3 cambios de bajo esfuerzo con impacto directo en el ROI ya demostrado por los propios datos (tabla 3.4 y 3.5).
