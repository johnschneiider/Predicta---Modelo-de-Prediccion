# Sistema de Auto-Betting (Apuestas Automáticas en BetPlay)

> Documentación técnica del sistema de apuestas automáticas de `predicta.com.co`.
> App Django: `auto_betting/` · Última actualización: 2026-08-17

---

## 1. Visión general

El auto-betting es el módulo que cierra el ciclo de **value betting** de Predicta:
escanea partidos de BetPlay (Kambi), los mapea a las ligas/equipos de Predicta,
genera predicciones con los motores propios y, si hay *edge* positivo, **coloca
apuestas reales** (stake chico, modo "dinero de prueba científica").

### Flujo completo (`run_auto_bets`)

```
login (ticket → token)
  → escanear partidos próximas 24h (filtrado: sin eSports/reservas/femenil)
  → mapear liga + equipos (fuzzy)
  → FILTRO datos insuficientes (<10 partidos/equipo)
  → predecir 6 mercados (motores de Predicta)
  → traer cuotas de BetPlay
  → seleccionar por EV + P + confidence + cuota
  → validar cupón (validate.json)
  → colocar apuesta (coupon.json)
  → guardar en AutoBet + DailyCounter
```

### Comando

```bash
cd /var/www/predicta.com.co && venv/bin/python manage.py run_auto_bets
```

- **Cron**: crontab www-data `0 19 * * *` (19:00 UTC = 14:00 Bogotá).
- **Log**: `logs/auto_betting.log`.

---

## 2. Modelos

| Modelo | Descripción |
|---|---|
| `AutoBetConfig` | Singleton. `ticket`, `punter_id`, `cuota_minima` (2.0), `stake` (500000=500 COP), `max_apuestas_diarias` (20), `horas_adelante` (24), `activo`. |
| `AutoBet` | Una apuesta colocada: evento, equipos, liga, mercado, selección, línea, cuota, predicción (λ, P, edge, EV), coupon/bet ref, estado (OPEN/WIN/LOSE/VOID/ERROR). |
| `DailyCounter` | Contador diario para el límite de apuestas. |
| `HistorialApuesta` | Historial completo sincronizado de `coupon/history.json`. |

---

## 3. Mercados y motores de predicción (Predicta)

El auto-betting **reutiliza los motores de predicción de Predicta**, no inventa
predicciones propias:

| Mercado | Motor (`ai_predictions/`) | Tipo |
|---|---|---|
| Córners (Over/Under) | `corners_model.predecir()` | Poisson |
| Tiros a puerta | `xg_shots_model.predict_shots_on_target_total()` | xG |
| Goles (Over/Under) | `dixon_coles.DixonColesModel.predict_match()` | Dixon-Coles |
| Remates totales | `xg_shots_model.predict_shots_total()` | xG |
| 1X2 (Resultado Final) | `DixonColesModel._calculate_match_outcome()` | Dixon-Coles |
| BTTS (Ambos marcan) | `enhanced_both_teams_score_model.predict()` | Modelo propio |

---

## 4. Filtros de selección (estrategia v4)

La selección (`strategy.py::select_bets`) ordena candidatos por EV descendente y
aplica **4 filtros acumulativos**:

1. **Cuota ≥ mínima** (`cuota_minima`, default 2.0).
2. **EV > 0** — `P_modelo × cuota > 1` (edge positivo).
3. **P ≥ 50%** (`min_p`) — descarta *long shots* de alta varianza.
4. **Confidence ≥ 0.35** (`min_confidence`) — usa la confianza que devuelve el
   modelo. Para 1X2 y BTTS (que no devuelven confidence) se usa 0.5 por defecto.

Además, en `run_auto_bets.py` hay un **filtro previo de datos insuficientes**:
si alguno de los dos equipos tiene **< 10 partidos** (home + away) en la ventana
temporal del modelo, el partido se descarta (evita predicciones espurias).

> ⚠️ `odds_minima` es un campo muerto del modelo (no se usa). No confundir con
> `cuota_minima`.

---

## 5. Ventana temporal del modelo (fix 2026-08-17)

**Problema:** Dixon-Coles usaba `cutoff = 365 días`. Las 14 ligas nuevas tenían
200-400 partidos históricos, pero **solo 5-30 en el último año** (ej. Azerbaiyán:
5, Bosnia: 8). Con 0-2 partidos por equipo, el modelo caía a "promedio de liga" y
producía probabilidades absurdas (P=83% para que Zalaegerszegi le ganara a
Ferencváros).

**Fix:** se amplió la ventana a **730 días (2 años)** en 4 puntos:

| Archivo | Línea | Cambio |
|---|---|---|
| `ai_predictions/simple_models.py` | `analyze_team_statistics` | 365 → 730 |
| `ai_predictions/dixon_coles.py` | `calculate_lambda_parameters` (league_matches) | 365 → 730 |
| `ai_predictions/dixon_coles.py` | `predict_match` (confidence/home_matches_count) | 365 → 730 |

**Impacto** (partidos en ventana):

| Liga | 365d | 730d | Mejora |
|---|---|---|---|
| Premier Liga (Azerbaiyán) | 5 | 109 | 21.8x |
| Premijer Liga (Bosnia) | 8 | 112 | 14.0x |
| Primera Div. (Costa Rica) | 17 | 115 | 6.8x |
| Superligaen (Dinamarca) | 21 | 129 | 6.1x |
| NB I (Hungría) | 22 | 128 | 5.8x |
| Super Liga (Serbia) | 30 | 134 | 4.5x |
| PFL 1 (Bulgaria) | 32 | 134 | 4.2x |

---

## 6. Auditoría de las primeras 20 apuestas (2026-08-17)

Con el cambio a 730 días, 18 de 20 apuestas siguen con EV positivo; 2 dejaron de
ser value bets:

| # | Partido | Mercado | P vieja | P nueva | Veredicto |
|---|---|---|---|---|---|
| 11 | FCSB vs Botosani | Goles Over 4.5 @4.6 | 46.1% | 15.4% | ❌ EV -29% |
| 18 | Gimnasia M. vs Talleres | 1X2 → 1 @3.1 | 52.7% | 30.0% | ❌ EV -7% |

Las correcciones más grandes (sobreconfianza corregida):
- Zalaegerszegi vs Ferencváros: P 83% → 48.6% (Δ -34.7pp).
- FCSB vs Botosani: P 46% → 15.4% (Δ -30.7pp).
- Gnistan vs Ilves: P 56% → 32.6% (Δ -23.7pp).

---

## 7. Seguridad

- **Apostar = dinero real.** El comando `run_auto_bets` coloca apuestas reales.
  Ejecutarlo manualmente implica riesgo económico (aunque el stake es 500 COP).
- `coupon/validate.json` es seguro (no gasta plata). `coupon.json` sí gasta.
- Las credenciales de BetPlay viven en `SOUL.md` (texto plano) y en
  `AutoBetConfig.ticket` de la DB. **Ambos están excluidos de git** (`.gitignore`).
- Límites: `max_apuestas_diarias=20` × 500 COP = 10.000 COP/día máximo.

---

## 8. Pendientes / roadmap

1. **Saldo / stop-loss** — bloqueado por el backend JWT del balance (Cloudflare).
2. **Cashout / cancelación** — endpoint aún no identificado.
3. **Refresh de token con retry** — hoy el login es de un solo intento.
4. **Backtest formal de los 3 filtros** — validar que P≥50% + conf≥0.35 mejoran
   el win-rate real (hoy es criterio heurístico).
5. **Confidence para 1X2 y BTTS** — hoy usan 0.5 fijo; los modelos podrían
   devolver una confianza real.
