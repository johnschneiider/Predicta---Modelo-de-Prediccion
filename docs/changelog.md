# Changelog — 2026-08-17

## Auto-betting: filtros de selección v4 + ventana temporal 730d

### Filtros de estrategia (`auto_betting/strategy.py`)
- `_add_candidate` y `select_bets` ahora aceptan `min_p=0.50` y `min_confidence=0.35`.
- Se añade filtro de **P ≥ 50%** (antes solo EV > 0, lo que dejaba pasar long shots
  tipo Casa Pia @13.0 con P=15.7%).
- Se añade filtro de **confidence ≥ 0.35** usando el valor que ya devolvían los
  motores pero se descartaba.
- `_build_market_data` (`run_auto_bets.py`) ahora propaga el campo `confidence` de
  cada predicción; 1X2 y BTTS usan 0.5 por defecto.

### Filtro de datos insuficientes (`run_auto_bets.py`)
- Antes de predecir, se verifica con `analyze_team_statistics` que ambos equipos
  tengan **≥ 10 partidos** (home+away) en la ventana temporal. Si no, se salta.

### Ventana temporal 365 → 730 días (`ai_predictions/`)
- `simple_models.py::analyze_team_statistics`: 365 → 730.
- `dixon_coles.py::calculate_lambda_parameters`: 365 → 730.
- `dixon_coles.py::predict_match`: 365 → 730.
- Motivación: ligas nuevas con 5-30 partidos en el último año producían
  predicciones sobreconfiadas por fallback a promedio de liga.

### Resultado
- Simulación con los 67 partidos próximos: los 3 filtros reducen de 21 a 16
  partidos con value bets (5 filtrados: 3 por datos, 2 por P/confidence).

### Seguridad
- `.gitignore`: se excluyen `SOUL.md` (credenciales), backups de DB y `data/`.
