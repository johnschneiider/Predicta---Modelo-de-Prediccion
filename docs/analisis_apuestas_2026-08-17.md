# Análisis de Desempeño de Apuestas — Predicta BetPlay
> Fecha: 2026-08-17 | 75 apuestas en historial (61 asentadas + 9 open + 5 void)

## Resumen general (todas las apuestas)

| Métrica | Valor |
|---|---|
| Total apuestas | 75 |
| WON | 34 (45.3%) |
| LOST | 27 (36.0%) |
| VOID | 5 (6.7%) |
| OPEN | 9 (12.0%) |
| Total apostado | 62.000 COP |
| Total payout | 73.645 COP |
| P&L asentado | +11.645 COP |
| Win rate (WON/LOST) | 55.7% |

## Auto-betting (solo 500 COP) — por mercado

| Mercado | Bets | WR | Avg odds | Stake COP | Payout COP | Profit COP |
|---|---|---|---|---|---|---|
| Tiros de Esquina | 46 | 50.0% | 2.04 | 23.000 | 19.945 | **-3.055** |
| Total de goles | 10 | 66.7% | 4.05 | 5.000 | 8.970 | **+3.970** |
| Resultado Final | 10 | 44.4% | 4.48 | 5.000 | 5.450 | **+450** |
| Tiros a puerta | 7 | 100% | 2.57 | 3.500 | 4.780 | **+1.280** |
| BTTS | 1 | — | 2.08 | 500 | 0 | -500 (open) |
| **Total** | 74 | 51.4% | 2.69 | 37.000 | 39.145 | **+2.145** |

## Auto-betting — profit por día

| Día | Bets | WON | LOST | OPEN | Profit COP |
|---|---|---|---|---|---|
| 2026-08-09 | 21 | 11 | 8 | 0 | -310 |
| 2026-08-11 | 1 | 0 | 0 | 0 | 0 (void) |
| 2026-08-13 | 3 | 0 | 1 | 0 | -500 |
| 2026-08-15 | 3 | 1 | 2 | 0 | -200 |
| 2026-08-16 | 25 | 15 | 8 | 2 | **+3.690** |
| 2026-08-17 | 21 | 6 | 8 | 7 | -535 (7 open) |

## Problemas detectados

### 1. Córners = sin edge (50% WR, -3.055 COP)
- 46 apuestas asentadas, WR 50% exacto, avg odds 2.04.
- Break-even a 2.04 = 49.0%. Estamos en 50.0%, marginalmente positivo pero dentro de ruido.
- **El modelo no está generando edge en córners.** El problema principal.

### 2. Cuotas ≥5.0 = cementerio (1-6, -2.000 COP)
- 6 apuestas asentadas en cuotas ≥5.0: 1 WON (5.3), 5 LOST (avg 7.45).
- **16.7% WR vs break-even 13.4%** — parece marginal pero la muestra es chica y las pérdidas son grandes.
- Causa: el v3 seleccionaba por EV>0 sin filtro de probabilidad mínima. Apuestas como Casa Pia vs Benfica @13.0 (P=15.7%) o Almeria Over 4.5 @4.5 (P=50.5%).
- **El v4 ya filtra P≥50%**, lo que debería eliminar este problema.

### 3. WON avg odds (2.28) << LOST avg odds (3.17)
- Las apuestas ganadas tienen cuotas bajas, las perdidas altas.
- Sesgo clásico: sobreconfianza en cuotas altas. El v4 con P≥50% mitiga esto.

### 4. Tiros a puerta = 100% WR (4-0, +1.280 COP)
- Muestra chica (4 asentadas) pero prometedor. Modelo podría tener edge aquí.

### 5. Goles = mejor mercado por profit (+3.970 COP, 66.7% WR)
- 6W/3L a avg 4.05. Excelente. El modelo de Dixon-Coles parece calibrar bien en goles.

## Recomendaciones

### Esperar más datos SÍ, pero con ajustes:
1. **El v4 (P≥50%, cuota≥2.0, conf≥0.35) aún no tiene apuestas asentadas** (29 OPEN). Hay que esperar a que se asienten para evaluar la nueva estrategia.
2. **Córners necesita más datos o un mejor modelo.** 46 bets con 50% WR no es suficiente para concluir que no hay edge, pero la tendencia es preocupante.
3. **El v3 tenía un bug de selección (EV>0 sin P mínima) que generó la mayoría de las pérdidas.** El v4 corrige esto.
4. **No hacer cambios mayores hasta tener ≥100 apuestas asentadas del v4.** La varianza es alta con muestras chicas.

### Ajustes recomendados (cuando se confirmen más datos):
- **Córners:** Considerar subir confidence mínimo a 0.50 o agregar edge mínimo específico para córners.
- **Cuotas altas:** El filtro P≥50% del v4 debería bastar. Si no, considerar tope máximo de cuota (ej. ≤5.0).
- **Tiros a puerta:** Ampliar muestra — tiene pinta de ser el mejor mercado.

## Fixes aplicados hoy (2026-08-17)

### Fix 2: Cron roto ✅
- **Problema:** `/etc/environment` exporta `DJANGO_SETTINGS_MODULE=config.settings.production`. Runs sin override fallaban con `ModuleNotFoundError: No module named 'config'`.
- **Solución:** Wrapper script `scripts/run_auto_bets_cron.sh` que exporta `DJANGO_SETTINGS_MODULE=betting_bot.settings` explícitamente. Crontab actualizada para usar el wrapper.
- **Cron anterior:** `50 4 * * * cd /var/www/predicta.com.co && env DJANGO_SETTINGS_MODULE=betting_bot.settings /var/www/predicta.com.co/venv/bin/python manage.py run_auto_bets >> .../auto_betting.log 2>&1`
- **Cron nuevo:** `50 4 * * * /var/www/predicta.com.co/scripts/run_auto_bets_cron.sh`

### Fix 3: DailyCounter reconciliation ✅
- **Problema:** Runs manuales (v3) no persistían el `DailyCounter`. El contador decía 1 cuando había 21 apuestas reales en el día.
- **Solución:** Al inicio de `handle()`, reconciliar el contador desde `AutoBet.objects.filter(creado__date=hoy).count()`. Si difiere, se actualiza y se loguea.
- **Verificación:** El dry run detectó `DB=1 vs real=21` y reconcilió correctamente.

### Fix 1 (dedup cross-day): NO aplicado (pendiente OK de John)
- El bug de apostar 2x al mismo partido sigue activo. Fix propuesto: cambiar `creado__date=hoy` → sin filtro de fecha (dedup global por evento_id).
