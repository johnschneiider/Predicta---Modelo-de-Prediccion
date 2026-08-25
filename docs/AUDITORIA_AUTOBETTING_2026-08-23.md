# Auditoría Auto-Betting Predicta — 23-Ago-2026

> **Alcance:** SOLO apuestas del sistema (`is_system=1`). Se excluyen todas las manuales.
> **Fuente:** `auto_betting_historialapuesta` cruzado con `auto_betting_autobet` por `usuario_id + coupon_ref`.
> **Corte:** 2026-08-23 19:48 UTC.
> **Autor:** Owen (agente).

---

## 0. TL;DR

El sistema **sigue en verde** (+47.355 COP, ROI +10.7%), pero **la calidad predictiva se está deteriorando**, no mejorando. La rentabilidad viene casi toda de **seleccionar cuotas/mercados con colchón** (Goles Over, cuotas ≥2.5), NO de que el modelo prediga bien. De hecho el modelo tiene una **anti-señal** en su zona de máxima confianza: cuanto más alta dice que es la probabilidad, peor acierta.

El mayor problema operativo hoy es que **no se puede controlar el EV ni apagar submercados desde la vista de umbrales**. Todo el dinero que se está quemando cae en segmentos que ya sabemos que son malos (cuota 2.0-2.5, EV 10-20%, córners Under, BTTS No) y no hay palanca en la UI para cortarlos.

---

## 1. Resultados globales (solo sistema, asentadas)

| Métrica | Valor |
|---|---:|
| Registros asentados (WON/LOST) | 164 |
| W / L | 68 / 96 |
| **Win rate** | **41.5%** |
| Stake asentado | 441.000 COP |
| Payout | 488.355 COP |
| **P&L** | **+47.355 COP** |
| **ROI** | **+10.7%** |
| Abiertas | 29 por 164.500 COP |

> El WR bajó de **43.0% (auditoría anterior) → 41.5%**. No es mejora: es deterioro leve pero consistente.

### Por cuenta

| Cuenta | N | WR | Stake medio | P&L | ROI |
|---|---:|---:|---:|---:|---:|
| `admin` (id 48) | 122 | 39.3% | **500 COP** | +3.505 | +5.7% |
| `admin2` (id 49) | 42 | 47.6% | **9.048 COP** | +43.850 | +11.5% |

⚠️ **`admin2` corre con stake ~18x el de `admin`** sobre la misma señal. No es diversificación: es la misma apuesta con exposición multiplicada. El 92% del P&L del sistema depende de `admin2`, que es justo la cuenta con más riesgo por evento.

---

## 2. El problema central: el modelo está MAL calibrado (y empeorando)

Calibración global (164 asentadas):

| Métrica | Valor |
|---|---:|
| Probabilidad media predicha | **55.7%** |
| Win rate real | **41.5%** |
| Victorias esperadas | 91.3 |
| Victorias reales | **68** |
| Déficit | **−23.3 victorias** |
| Brier score | **0.2712** (peor que el 0.269 anterior) |

Sobreconfianza de **~14 puntos**. Antes eran 8. **Va a peor.**

### Lo más grave — la probabilidad alta es una anti-señal

| Prob. predicha | N | WR real | ROI |
|---|---:|---:|---:|
| <50% | 14 | 35.7% | **+153.0%** |
| 50–55% | 66 | 42.4% | +10.1% |
| 55–60% | 60 | 48.3% | +6.0% |
| **60–65%** | **8** | **12.5%** | **−73.0%** |
| **65%+** | **16** | **31.3%** | **−17.3%** |

Léelo con calma: **cuando el modelo dice "esto es 65%+ seguro", acierta 31%. Cuando dice "<50%", acierta con ROI +153%.** La confianza del modelo está **invertida** por encima de 60%. Esto explica el "cada vez predice peor": el pipeline está sobreajustando y produciendo probabilidades altas que son ruido.

El `calibrate_probability()` actual (cap 65%, shrinkage 0.50 arriba de 60%) **es insuficiente**. La evidencia dice que arriba de 60% habría que **cortar directamente**, no solo encoger.

---

## 3. Dónde se gana y dónde se quema plata

### Por submercado

| Mercado — Lado | N | WR | P&L | ROI |
|---|---:|---:|---:|---:|
| Goles Over | 66 | 43.9% | +59.445 | **+32.4%** ← motor |
| Córners Over | 20 | 55.0% | +17.670 | +20.5% |
| Goles Under | 12 | 41.7% | +4.415 | +15.0% |
| BTTS Sí | 14 | 42.9% | +3.305 | +5.2% |
| Tiros Under | 9 | 44.4% | +625 | +13.9% |
| Tiros Over | 7 | 42.9% | +205 | +5.9% |
| Resultado Final (1X2) | 14 | 35.7% | −380 | −5.4% |
| **BTTS No** | **3** | 33.3% | **−9.960** | **−90.5%** |
| **Córners Under** | **19** | **21.1%** | **−27.970** | **−53.8%** |

**Córners Under solo ha destruido −27.970 COP.** BTTS No, −9.960. Juntos borran casi todo lo que aporta Córners Over.

### Por rango de cuota

| Rango | N | WR | P&L | ROI |
|---|---:|---:|---:|---:|
| <2.0 | 3 | 0% | −1.500 | −100% |
| **2.0–2.5** | **101** | 40.6% | **−64.175** | **−20.0%** |
| 2.5–3.0 | 33 | 42.4% | +46.605 | +56.5% |
| 3.0–4.0 | 12 | 41.7% | +10.300 | +68.7% |
| 4.0+ | 15 | 53.3% | +56.125 | **+261.0%** |

**El tramo 2.0–2.5 es un agujero negro: 101 apuestas, −64.175 COP.** Es donde el sistema MÁS apuesta y donde MÁS pierde. Todo lo demás (≥2.5) es muy rentable.

### Por EV calibrado

| EV | N | WR | ROI |
|---|---:|---:|---:|
| 5–10% | 21 | 42.9% | +15.4% |
| **10–20%** | **35** | **25.7%** | **−54.9%** ← desastre |
| 20–40% | 47 | 48.9% | +27.6% |
| 40%+ | 61 | 44.3% | +79.2% |

El bucket **EV 10–20% es letal (−54.9%)** porque es exactamente donde caen las cuotas 2.0–2.5 con probabilidad inflada. El EV≥5% actual en cuotas bajas es demasiado laxo.

### CLV

- CLV promedio: **+1.26%** (bajó desde +1.36%).
- Solo **33.8%** de apuestas con CLV positivo.
- Traducción: hay una pizca de edge, pero **no es robusto**. El sistema no le está ganando consistentemente a la línea de cierre.

---

## 4. Diagnóstico de "¿hay una falla prediciendo?"

**Sí. Hay una falla real de calibración, y se está agravando.** No es solo ruido:

1. **Sobreconfianza creciente** (8pp → 14pp) y **Brier empeorando** (0.269 → 0.271).
2. **Anti-señal en prob >60%**: el modelo acierta menos justo donde más confía. Esto es firma clásica de **overfitting** en el pipeline oficial (promedio ponderado de muchos modelos que amplifican outliers en muestras pequeñas de ligas de 2ª división).
3. **Hoy (23-Ago): WR 25% (3/12), −2.490 COP.** Con p≈55.8% predicha, sacar ≤3 aciertos en 12 tiene prob ~3%: es una racha rara, señal de que la capa probabilística está desalineada, no solo mala suerte.

El sistema gana **a pesar** del modelo, no **gracias** a él: gana por el filtro de cuota/mercado. Si no cortamos lo malo, el margen se erosiona a medida que el modelo mete más volumen en la zona 2.0–2.5 / prob-alta.

---

## 5. La falla operativa: la UI de umbrales no controla lo que importa

Estado actual de `/auto-betting/configuracion/umbrales/` (`MarketFilterConfig`):

- Solo permite editar **`min_p`** y **`min_confidence`** por submercado.
- **NO** permite controlar:
  - ❌ **EV mínimo por submercado** (hoy hardcoded en `strategy._get_tier_thresholds`: EV≥5% cuota baja).
  - ❌ **Cuota mínima global** (vive en `AutoBetConfig` por usuario, default 2.0 — el peor tramo).
  - ❌ **Activar/desactivar un submercado** (no se puede apagar Córners Under ni BTTS No sin tocar código).
  - ❌ **Cap/shrinkage de calibración** (hardcoded, cap 65%).
  - ❌ **Stop-loss diario/semanal**.
  - ❌ **Límite de exposición combinado admin/admin2 por evento**.

Es decir: **sabemos qué cortar desde hace días, pero no hay palanca en la UI para hacerlo.** Cada ajuste requiere editar `strategy.py` y desplegar.

---

## 6. Propuesta de solución

### 6.1. Ampliar `MarketFilterConfig` y la vista de umbrales (lo que pediste)

Agregar por cada submercado (goles/córners/tiros/BTTS × over/under/sí/no) **3 campos nuevos**:

| Campo nuevo | Tipo | Default | Función |
|---|---|---|---|
| `{sub}_enabled` | bool | True | Interruptor ON/OFF del submercado |
| `{sub}_min_ev` | float 0–2 | ver tabla | EV calibrado mínimo exigido |
| `{sub}_min_cuota` | float | 0 (=usa global) | Cuota mínima específica del submercado |

Y **3 campos globales** nuevos (sección aparte en la misma vista):

| Campo global | Default propuesto | Función |
|---|---|---|
| `cuota_minima_global` | **2.5** | Piso de cuota para TODO el sistema (reemplaza el 2.0 per-user) |
| `stop_loss_diario_cop` | −30.000 | Si el P&L del día baja de esto, se detiene el auto-betting |
| `max_exposicion_evento_cop` | 20.000 | Tope de stake combinado (admin+admin2) por evento/mercado |
| `calib_cap` | 0.58 | Cap duro de probabilidad calibrada (baja de 0.65) |

### 6.2. Cambios de configuración recomendados HOY (con datos)

| Parámetro | Actual | Propuesto | Motivo |
|---|---|---|---|
| Cuota mínima global | 2.0 | **2.5** | Tramo 2.0–2.5 = −64.175 COP |
| Córners Under | ON, p 0.56 | **OFF** | ROI −53.8% |
| BTTS No | ON, p 0.50 | **OFF** | ROI −90.5% |
| BTTS Sí | p 0.50 | p **0.52** | Margen flojo |
| Goles Under | p 0.50 | p **0.54** | Endurecer un poco |
| Córners Over | min_ev — | **EV ≥ 20%** | Rentable pero volátil |
| Goles Over | min_ev — | **EV ≥ 15%** | Proteger el motor |
| Cap calibración | 0.65 | **0.58** | Prob >60% es anti-señal |
| min_ev cuota 2.0–2.5 | 5% | **≥20%** | Bucket EV 10–20% = −54.9% |

### 6.3. Prioridad real (orden de impacto)

1. **Cortar el sangrado** (máximo impacto, cero riesgo de modelo):
   - Cuota mínima global → 2.5
   - Córners Under → OFF
   - BTTS No → OFF
   - EV mínimo ≥20% en cuotas <2.5
2. **Controles de riesgo** (protege el capital de `admin2`):
   - Stop-loss diario
   - Tope de exposición combinada por evento
3. **Arreglar la calibración** (el problema de fondo):
   - Bajar cap a 0.58 ya (parche)
   - A mediano plazo: recalibración isotónica/Platt sobre el histórico real, y **capar el peso de ligas con <30 partidos** en el promedio oficial (probable origen del overfitting).

### 6.4. Trabajo de implementación

- **Migración Django:** +~40 campos en `MarketFilterConfig` (3 por submercado × 8 + globales). Sin downtime, valores default = comportamiento actual.
- **`MarketFilterConfigForm`:** añadir campos + widgets (checkbox para enabled, number para ev/cuota).
- **Template `configuracion_umbrales.html`:** por submercado añadir columna "Activo", "EV mín", "Cuota mín"; nueva sección "Controles globales" (cuota mínima, stop-loss, exposición, cap calibración).
- **`strategy.py`:** `_resolve_filters` debe devolver también `enabled`, `min_ev`, `min_cuota`; `_add_candidate` los aplica; `_get_tier_thresholds` pasa a ser fallback. `calibrate_probability` lee `calib_cap`.
- **`run_auto_bets.py`:** chequear `stop_loss_diario` (sumando P&L del día) y `max_exposicion_evento` antes de colocar.
- **Backup previo** de `db.sqlite3` (ya hay backups automáticos pre-cambio).

---

## 7. Conclusión

- **No estás haciendo todo mal:** el sistema es rentable (+47.355 COP, ROI +10.7%).
- **Pero el modelo NO está calibrado y va a peor:** sobreconfianza subió de 8 a 14 puntos; arriba de 60% la confianza está invertida.
- **La rentabilidad es frágil:** depende de Goles Over, cuotas ≥2.5 y del stake grande de `admin2`. CLV apenas positivo (+1.26%, 33.8%).
- **La mayor mejora disponible NO es otro modelo:** es **poder cortar lo malo desde la UI** (EV, cuota, ON/OFF por submercado) + stop-loss. Eso lo pediste y es lo correcto.

Con esos ajustes el sistema debería quedar mucho más limpio antes de meternos en recalibración estadística seria.

---

**Ruta de este archivo:** `/var/www/predicta.com.co/docs/AUDITORIA_AUTOBETTING_2026-08-23.md`
