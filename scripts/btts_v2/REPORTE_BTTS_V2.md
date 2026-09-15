# MOTOR BTTS v2 — Auditoría + motor independiente + test de hoy (14-sep-2026)

## 1. Qué pasa con el mercado BTTS (auditoría, HistorialApuesta)
- Total settled: n=286 · WR 54.9% · ROI +2.5% · net +64.2M COP.
- 7 días: n=116 · WR 47.4% · ROI −4.4% (degradándose).
- **24h (hoy): n=34 · WR 41.2% · ROI −17.0% · net −95.3M COP.**
- Pata Sí: n=259 WR 55.6% ROI +2.0% · Pata No: n=25 WR 48.0% ROI +2.7% (pata No estuvo APAGADA casi todo el histórico; históricamente −90.5% ROI).
- Hoy 03:00 UTC: corrida apostó 10 eventos × 4 cuentas. Las pérdidas grandes vienen de la cuenta de stake alto (40M/por apuesta): fallaron Torino-Sí, Ceramica-Sí, Braga-Sí, Rio Ave-No, Sligo-No, Leeds-No.
- Expuestos aún: 296 OPEN (260 Sí / 36 No) = 2.73B COP en juego.
- Causa raíz de la percepción de descalibración: día alto en BTTS (56.9% hoy vs ~53% histórico) + pata "No" reactivada (historial malo) + selección per-evento débil del modelo heurístico.

## 2. ¿Motor independiente? NO existía
Producción usa `ai_predictions/enhanced_both_teams_score.py` (heurística: Poisson últimos 20 + H2H 10 + forma 8 + baseline liga, pesos fijos + calibración por goles de liga). No hay motor ML independiente para BTTS.

## 3. Motor nuevo (scripts/btts_v2/)
- Features leak-free (solo info anterior al partido): goles for/against por venue (exp-weight half-life 120d), tasa BTTS propia, % anota, % clean-sheet, forma últimos 6 (puntos/goles), descanso, baseline liga (total + 90d), H2H (10 últimos, 3 años). Target: both_teams_score. 88.017 partidos (2005→13-sep).
- Modelo: HistGradientBoostingClassifier (400 iter) + calibración isotónica.
- Split: train <01-ago · calib agosto · test OOS 1-13 sep.

## 4. Resultados
- **OOS 1-13 sep (n=1452): AUC 0.553 · Brier 0.2475 · WR 55.0%** (base 53.0%). Calibración por buckets OK.
- **HOY 14-sep (58 partidos FT en ligas activas del bot; NO están en BD → sin sesgo):**
  - Base real BTTS hoy: 56.9% (día alto).
  - Motor nuevo: WR 48.3% · Brier 0.2530 · media P 0.554.
  - Motor producción: WR 48.3% · Brier 0.2639 · media P 0.585.
  - Empate técnico en el día; el nuevo está mejor calibrado (Brier y media más cercanas a la realidad).
  - Conviction picks del nuevo (Sí con P≥0.55): 18 picks, WR 61.1%.
- En los 9 eventos que el bot apostó hoy: nuevo 2/9 correctos, producción 3/9 (ambos mal; el día le pegó a los dos).

## 5. Veredicto
- Un día no decide (n=58, ±6.5pp de ruido). El motor nuevo iguala a producción hoy y gana en calibración; en OOS 13 días hace 55.0% WR.
- La "descalibración" percibida = día alto en BTTS + pata No reactivada (histórico malo) + stakes grandes concentrados.
- Recomendación: shadow-mode del motor nuevo (ledger diario, como remates_v2) ≥50-100 picks antes de decidir; revisar pata No tras liquidar las 36 OPEN (decisión John).

## Archivos
- scripts/btts_v2/build_features.py · train_eval.py · eval_today.py
- features_btts.csv · btts_state.pkl · gbm_btts.pkl · today_eval_20260914.json
