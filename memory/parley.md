# Motor de Parleys reales — Predicta

**Fecha:** 2026-10-30 (actualizado 2026-10-31: multi-usuario)
**Estado:** ACTIVO en real para todos los usuarios elegibles.
**Regla de oro:** motor **adicional e independiente**. No modifica `run_auto_bets`,
`AutoBetConfig`, `DailyCounter`, `paperparleys` ni sus cron.

---

## 0. Actualización 2026-10-31 — motor multi-usuario (ACTIVO)

### Qué cambió
- **Sin hardcode de `admin`**: `run_real_parleys` y `sync_parleys` recorren todos
  los usuarios elegibles. `--usuario <pk>` limita a uno.
- **Elegibilidad** (LIVE): `AutoBetConfig.activo=True` con ticket/punter_id,
  `ParleyEngineConfig.activo=True`, `CapitalConfig` con balance/ancla declarados,
  `bankroll_cop >= stake`, login BetPlay OK, fit >= `min_fit` y al menos 2
  eventos futuros en la ventana de 24 h.
- **Usuario nuevo con AutoBetConfig activo y cuenta válida**: en la primera
  corrida LIVE se le crea automáticamente `ParleyEngineConfig` con los mismos
  parámetros del admin: `stake=500`, `capital_inicial=100000`, `ev_gate=0.80`,
  `max_legs=2`, `min_fit=50`, `max_placements_per_run=0` (sin tope),
  `place_interval_seconds=30`, `dry_run=False`, `activo=True`.
- **Un fallo no aborta a los demás**: login vencido, sync o error de un usuario
  se registra y se sigue con el siguiente. Lock global único.
- **Presupuesto por usuario**: `min(ledger_interno, bankroll_cop)` y se descuenta
  localmente en cada colocación. Evita apostar más que el balance paralelo.
- **Sync final por usuario** tras colocar: llena `placed_date` y liquida lo que
  BetPlay ya resolvió (antes quedaban cupones sin fecha hasta el día siguiente).
- **WhatsApp**: al terminar una corrida con cupones nuevos se envía un resumen
  por usuario (`notificar_parleys`, evento `parleys_colocados`, máx. 10 bloques).
  Si el microservicio WhatsApp está desconectado, falla solo el aviso (no la
  apuesta) y queda auditado en `NotificacionLog`.
- **Guard `coupon_ref`**: si un `coupon_ref` ya pertenece a otro usuario, se
  omite y se alerta en log; nunca se reasigna de cuenta.

### Estado verificado (2026-10-31)
- Configs: `admin` (100.000/500/0/30s, LIVE) y `carlos3`
  (100.000/500/0/30s, LIVE, creada automáticamente).
- `admin`: 21 cupones motor, 10.500 COP, ledger 89.500; 6 LOST / 15 OPEN;
  los 11 cupones que estaban sin `placed_date` quedaron sincronizados.
- `carlos3`: **14 cupones motor** (7.000 COP, ledger 93.000), todos OPEN.
  De 15 combinaciones posibles se colocaron 14; `1791-1799` no se pudo porque
  el partido de 1791 ya había empezado. `1793-1799` se colocó al tercer intento
  (las dos primeras BetPlay lo rechazó por `ODDS_CHANGED`).
- `parley_reconcile`: 0 ambiguos, 0 placeholders huérfanos, 0 ERROR.
- Panel `/parleys/`: 200 y visible para admin (21) y carlos3 (14).
- Tests: `manage.py test parley_engine notificaciones` → **46/46 OK**;
  `manage.py check` → sin issues.
- **WhatsApp pendiente operativo**: el microservicio `predicta-whatsapp` está
  `disconnected` (generando QR). Los 3 resúmenes de la corrida fallaron con
  `HTTP 500 WhatsApp client not ready`. Se debe reescanear el QR en
  `/notificaciones/whatsapp/` (solo superuser) y reenviar el resumen.
  No se reinició ni modificó el servicio.

### Exclusiones actuales (no elegibles)
- `admin2`: ticket vencido (253 h) y sin picks futuros; 277 AutoBet OPEN de
  agosto sin liquidar (pipeline AutoBet no sano).
- `carlosantoniom051`: `AutoBetConfig.activo=False`, ticket vencido, bankroll 0.
- `flavio`: sin cuenta BetPlay vinculada ni historial.

### Archivos tocados
- `parley_engine/management/commands/run_real_parleys.py` (multi-usuario).
- `parley_engine/management/commands/sync_parleys.py` (multi-usuario).
- `parley_engine/services.py` (guard `coupon_ref` por usuario).
- `notificaciones/services.py` (`construir_mensaje_parleys`, `notificar_parleys`).
- `parley_engine/tests.py` (multi-usuario + WhatsApp).
- `memory/parley.md`, `agent.md`.
- Backups: `*.bak-multiuser-2026-10-31-141845`,
  `notificaciones/services.py.bak-parleys-2026-10-31-141845`; dump
  `/root/opencode/backups/parley_engine_pre_multiuser_2026-10-31-141845.json`.
- No hubo migraciones.

### Pendientes
1. Reconectar WhatsApp y reenviar el resumen de los 14 cupones de `carlos3`.
2. Revisar `admin2` antes de incluirlo (ticket + 277 OPEN de agosto).
3. Validar fuera de muestra el EV/ROI en cuentas distintas a `admin`; el
   backtest original es in-sample del admin (611 filas) y `carlos3` usa 109.
4. Decidir si se agenda `sync_parleys` (hoy solo corre al inicio/fin de
   `run_real_parleys` y manualmente); si se agenda, evitar choque con el run
   diario por el lock.
5. Los usuarios no reciben aviso de parleys si el microservicio WhatsApp está
   caído; monitorear `NotificacionLog` evento `parleys_colocados`.

---

## 0.1 Actualización 2026-11-01 — filtro de fechas y botón de liquidación

### Qué cambió
- **Filtro de fechas de `/parleys/` arreglado.** Antes filtraba por `dia` (día de
  los picks) y el panel capaba por defecto a "desde ayer", así que un rango
  anterior devolvía 0 aunque el cupón existiera. Ahora:
  - el rango se aplica a la **fecha del partido** (la columna Fecha,
    `fechas_encuentro`), igual que en `/auto-betting/historial/`;
  - con fechas explícitas se consulta todo el historial (sin el tope de ayer);
  - sin fechas se mantiene el comportamiento por defecto (motor desde ayer +
    excepción manual).
- **Botón "⟳ Actualizar / liquidar" en `/parleys/`**: POST a `/parleys/sync/`
  (CSRF protegido) que ejecuta `sync_user_history` para el usuario logueado y
  recarga la página. Liquida contra el historial real de BetPlay.
- **El botón de `/auto-betting/historial/` también liquida parleys**: tras
  `sync_historial` llama a `sync_user_history` (fallo de parleys no rompe el
  sync general; se reporta en `parleys_error`).
- `parley_engine/services.py`: nueva `sync_user_history(usuario)` con el mismo
  lock que las corridas; devuelve `{ok, updated, error}` sin lanzar.

### Archivos tocados
- `parley_engine/views.py`, `parley_engine/urls.py`, `parley_engine/services.py`,
  `parley_engine/templates/parley_engine/historial.html`, `auto_betting/views.py`.
- Backups: `*.bak-2026-11-01-200606`.
- Sin migraciones.

### Estado verificado (2026-11-01)
- 18 cupones OPEN liquidados manualmente con `sync_parleys` (4 WON:
  13298391744 +895.000, 13295956930 +1.025.000, 13301807866 y 13301822780
  +2.193.000 COP c/u; 14 LOST). **0 OPEN.**
- Filtro: sin fechas 7 cupones; 2026-11-01 → 6; 2026-10-31 → 21; rango
  2026-10-30→2026-11-01 → 27. Chips de deporte recalculados con el rango.
- Endpoint `/parleys/sync/`: GET 405, anónimo 302, autenticado 200
  (`updated: 40`); sin token CSRF 403, con token 200.
- `manage.py check` OK; `manage.py test parley_engine --keepdb` → **34/34 OK**.
- Servicio recargado con `systemctl reload predicta`; público:
  `https://www.predicta.com.co/parleys/` → 302 al login (anónimo), sitio 200.

### Pendientes (actualizado)
1. **`sync_parleys` sigue sin agendar**; con el botón manual ya se puede
   liquidar a demanda, pero la liquidación automática depende de la corrida de
   las 00:00 UTC. Decidir si se agenda 2-3 veces/día (respetar el lock).
2. **Rentabilidad real NEGATIVA** — ver sección 0.2. No ampliar capital ni
   aumentar stake hasta corregir el cálculo y validar fuera de muestra.

---

## 0.2 Rentabilidad real de los parleys (2026-11-01) — NO son rentables

### Resultado real (51 cupones LIVE del motor, todos liquidados)
| Usuario | Cupones | Stake | Payout | P&L | ROI | Winrate |
|---|---:|---:|---:|---:|---:|---:|
| admin | 27 | 13.500 | 3.218 | **-10.282** | -76,2% | 2/27 |
| carlos3 | 24 | 12.000 | 3.088 | **-8.912** | -74,3% | 2/24 |
| **Total** | **51** | **25.500** | **6.306** | **-19.194** | **-75,3%** | **7,8%** |

- Ledger: admin 100.000 → 89.718; carlos3 100.000 → 91.088.
- **Aclaración de unidades**: `payout` está en COP, no en miles. El cupón
  13295956930 pagó 1.025 COP (stake 500 × cuota 2,05 tras anularse la pata
  Cambuur); el log "payout 2193.0" = 2.193 COP. El ledger y el panel están
  bien: no hay bug de unidades (la nota anterior era un error de lectura).

### Por qué el cálculo está mal
1. **`ev_gate=0.80` no es "EV positivo"**: el motor compara
   `prod(p_rec × cuota) ≥ 0,80`, es decir acepta retornos esperados de hasta
   -20%. Para ser rentable el umbral debe ser **> 1,0**. De los 51 cupones,
   12 tenían EV < 1,0 por el propio modelo y perdieron todos.
2. **`p_rec` es plano (~0,50) para todas las patas** del bucket 50-60 de
   `predicta_prob`. Al ordenar por `prod(p_rec × cuota)` se ordena en la
   práctica por cuota: se eligen las patas donde el mercado más discrepa del
   modelo (selección adversa), no donde hay edge.
3. **Backtest in-sample**: el +49% de ROI se midió con el mismo histórico que
   alimentó el fit de deciles (sin fuera de muestra). El edge no se replicó.
4. **Concentración extrema**: 51 cupones construidos con solo **22 picks
   distintos** (5-7 eventos por corrida) y `max_placements_per_run=0` (sin
   tope). Una pata mala tumba decenas de cupones correlacionados.
5. **Drift del modelo fuente**: AutoBet plano histórico +2,1% global y +21,2%
   en Tiros Opta; pero los picks creados desde 2026-10-25 van +7,5% global y
   **-24,8% en Tiros Opta** (n=17). El fit no pondera recencia.

### Recomendación
- **Pausar LIVE** (`ParleyEngineConfig.dry_run=True` o `activo=False`) hasta
  corregir: gate EV > 1,0, calibración fuera de muestra, límite de exposición
  por evento y tope de cupones por corrida.
- No aumentar stake ni capital.

### Acción tomada (2026-11-01, orden del humano: "pausa los parleys")
- `ParleyEngineConfig.activo=False` y `dry_run=True` para `admin` y `carlos3`
  (nota de auditoría en `notas`).
- `CronSchedule(tarea='real_parleys').enabled=False` → el dispatcher ya no
  lanza la corrida diaria de 00:00 UTC.
- `admin2` no tenía config y una corrida manual sin flags se la habría creado
  LIVE: se creó **inactiva** (`activo=False`, `dry_run=True`) para cerrar ese
  hueco. `run_real_parleys --dry-run` ahora responde "motor inactivo" para los
  tres.
- El botón de `/parleys/` **sigue liquidando** con el motor pausado (solo lee
  historial y actualiza ledger); lo que está bloqueado es colocar.
- Verificado: 0 configs activas, schedule deshabilitado, 0 cupones OPEN,
  `/parleys/` 200, sitio público 200. Para reanudar: reactivar
  `ParleyEngineConfig` y `CronSchedule` **solo** tras corregir el cálculo.

---

## Histórico (2026-10-30)

---

## 1. Estrategia aprobada

- **2 patas** (`max_legs=2`), stake fijo **500 COP**.
- **EV ≥ 0,80** calculado con la **cuota actual** al momento de colocar.
- Pool: picks **AutoBet OPEN cuyos partidos se juegan en las próximas 24 h**
  (`start_time`), solo lectura. La ventana es de partidos futuros, no de picks
  recientes: un pick creado hace días para un partido de mañana sí entra.
- Filtros `junk_mercados`: `descanso`, `primera parte`, `cuotas del partido`,
  `ganador`, `esquina`.
- Una pata por evento; cross-sport permitido.
- Se colocan **todas** las combinaciones que pasen el filtro; sin tope de cantidad.
- Capital dedicado **100.000 COP** en ledger interno; el motor se detiene si el
  disponible baja de 500 COP.

### Backtest de referencia (admin, octubre 2026, in-sample)

- Config recomendada: 406 operaciones, **30,30% winrate**, **49,17% ROI**,
  **+99.813 COP**, drawdown máximo **19.500 COP**.
- Con 100.000 COP de capital: 410/410 operaciones, +100.089 COP, ROI 48,82%,
  winrate 30,32%, drawdown máximo 62.000 COP.
- 3 o más patas bajan el winrate a ~22%; el objetivo de 30% exige `max_legs=2`.
- El ROI real puede ser menor que el backtest si las cuotas actuales empeoran;
  por eso el motor recalcula EV con cuota actual, no con la cuota vieja de AutoBet.

---

## 2. Arquitectura implementada

App nueva: `parley_engine`.

### Modelos
- `ParleyEngineConfig`: config singleton por usuario (admin), activo, dry_run,
  stake, capital inicial, ev_gate, max_legs, min_fit, filtros, rate limit,
  `max_placements_per_run` (5) y `place_interval_seconds` (30).
- `ParleyRun`: auditoría de cada corrida (DRY/LIVE, contadores, ledger, errores,
  rate limits).
- `ParleyCoupon`: cupón combinado (manual o del motor), `coupon_ref`, `key`
  idempotente, stake, payout, odds, estado, patas JSON, `is_motor`.
- `ParleyCouponLeg`: pata normalizada (evento, mercado, selección, línea, cuotas,
  `p_rec`, `q`, estado).
- `ParleyLedger`: movimientos del capital dedicado (PLACEMENT/SETTLEMENT).

### Comandos
- `manage.py run_real_parleys` — ventana de partidos próximos 24 h; hoy REAL
  (`dry_run=False` en la config del admin).
  - `--live`: fuerza colocación real (requiere config activa).
  - `--limit N`, `--max-placements N`, `--interval S`: canary/goteo.
  - `--fecha YYYY-MM-DD`: simula la ventana que termina ese día (Bogotá).
  - `--sync-only`: solo sincroniza historial/ledger.
- `manage.py sync_parleys` — sincroniza cupones combinados y liquida el ledger.

### Panel
- URL: **`/parleys/`**.
- Muestra **solo los cupones del sistema** (`is_motor=True`) colocados desde
  ayer en adelante; los manuales (historial de BetPlay, pruebas) quedan
  ocultos por diseño (2026-10-30). **Excepción puntual** (`EXCEPCION_MANUAL_
  VISIBLE` en views): el cupón manual 13291906849 (Memphis +1.5, WON ayer,
  2.991,5 COP) sigue visible; solo ese. Detalle de **todas las patas**
  expandible, estadísticas, ROI, winrate y DD solo sobre esos cupones.
- Se agregó el tab **“🎲 Parleys”** en `/auto-betting/historial/`.
- Los cupones del motor llevan badge **Motor**; los manuales, **Manual**.

### Scheduler
- Tarea `real_parleys` en `CronSchedule`: **cada 1440 minutos** (24 h),
  habilitada. Con `hora_utc=0, minuto_utc=0` corre a las **00:00 UTC**
  (19:00 Bogotá). Actualizado 2026-10-30 (antes: 60 min).
- Comando: `venv/bin/python manage.py run_real_parleys` (sin `--live`; el
  `dry_run` de la config manda).
- Log: `logs/real_parleys.log`. Lock: `logs/real_parleys.lock`.
- No se modificó el horario ni la lógica de `run_auto_bets` ni de `paperparleys`.

### Rate limit / robustez
- Cliente HTTP propio secuencial: 30 requests/minuto (configurable).
- Backoff exponencial y respeto de `Retry-After` en 429/503.
- GET/validate reintentan; una colocación con 5xx/timeout se marca **ambigua** y
  no se reintenta a ciegas.
- Idempotencia por `key = ids` (sin día: la misma combinación de picks no se
  repite jamás); placeholder antes de colocar (constraint UNIQUE en `key`) y
  `IntegrityError` tratado como "ya cubierta".
- Guard anti-duplicados por **firmas de todos los cupones de la cuenta**
  (sin filtro de fecha: el pick pudo crearse hace días): set de `outcome_id`
  (y fallback evento+mercado+selección+línea). Si la combinación ya existe,
  no se vuelve a apostar.
- En LIVE, si el sync inicial del historial falla, la corrida **aborta**: sin
  historial fresco no se puede garantizar ausencia de duplicados.
- Goteo: `max_placements_per_run` (default 5) y `place_interval_seconds`
  (default 30) en `ParleyEngineConfig`; CLI `--max-placements` / `--interval`.
- Errores de colocación:
  - 429/503 en validate o 429 en place = no colocada → se borra el placeholder
    y la key queda libre para el siguiente run.
  - Timeout/5xx/SUCCESS sin `couponRef` = ambigua → **reconciliación
    automática**: busca en el historial (mismas patas + stake) con 2 intentos y
    5 s de margen y enlaza el cupón real (fusiona con la fila del sync si ya
    existe) registrando PLACEMENT/SETTLEMENT una sola vez. Si no aparece, la
    key se conserva (jamás se duplica) y queda en ERROR para revisión.
  - `manage.py parley_reconcile` lista ERROR y placeholders huérfanos (solo
    lectura) para conciliar a mano.
- Lock de proceso: nunca dos corridas de parleys simultáneas.

### Ledger
- Fórmula: `capital_inicial + suma(movimientos)`.
- Colocación: `-stake`. Liquidación: `+payout`.
- Si el disponible < stake, el motor no coloca más en esa corrida.
- Es un ledger **interno** sobre la misma cuenta BetPlay del admin: no es una
  segregación real de saldo. El motor real puede usar el mismo saldo.

---

## 3. Cambios compartidos (solo aditivos)

- `betting_bot/settings.py`: `'parley_engine'` en `INSTALLED_APPS`.
- `betting_bot/urls.py`: ruta `parleys/`.
- `auto_betting/templates/auto_betting/historial.html`: tab “Parleys”.
- `auto_betting/models.py`: choice `real_parleys` en `CronSchedule.TAREA_CHOICES`.
- `auto_betting/management/commands/run_scheduler.py`: comando, log y
  anti-concurrencia para `real_parleys`.
- Migraciones: `auto_betting/0042`, `auto_betting/0043`, `parley_engine/0001`,
  `parley_engine/0002` (pacing/cap, 2026-10-30).
- Backups de archivos compartidos: `*.bak-parley-2026-10-30-133538`.
- Backups de esta iteración: `*.bak-parley24-2026-10-30-150303` y dump
  `/root/opencode/backups/parley_engine_pre_24h_2026-10-30-150303.json`.

Nada de esto cambia el comportamiento del motor real. Las tablas nuevas son
independientes.

---

## 4. Estado actual verificado (2026-10-30, motor ACTIVO en real)

- Config admin: `activo=True`, **`dry_run=False`**, stake 500, capital 100.000,
  EV 0.80, max_legs 2, `max_placements_per_run=5`, `place_interval_seconds=30`.
- Scheduler `real_parleys`: habilitado **cada 1440 min (24 h, 00:00 UTC)**.
- Ventana: partidos que empiezan entre ahora y dentro de 24 h (`start_time`),
  no picks creados en las últimas 24 h. Eventos ya iniciados se descartan.
- Panel `/parleys/`: renderiza 200 para el admin; 302 sin sesión.
- **Canary real 2026-10-30 15:21 UTC**: cupón **13293782669**, 2 patas
  (1794 Ambos Marcan No + 1797 Tiros Over 27.5), stake 500, cuota 4.444,
  payout potencial 2.222 COP. Confirmado por `sync_parleys` en el historial de
  BetPlay (placedDate 15:21:20 UTC, OPEN). Ledger: 100.000 → 99.500.
- Sin duplicados: 1 cupón del motor, 0 ERROR, 0 placeholders huérfanos
  (`parley_reconcile` limpio). DRY run 8 (2026-10-30 16:11 UTC): 4 picks /
  4 eventos de partidos próximos; el combinado 1794-1797 ya colocado quedó
  excluido por firma.
- Tests: **31/31 OK** con `settings.py` y `settings_production`. Cubren
  ambiguo con y sin match, merge con fila de sync, 429, envelope sin
  `couponRef`, cap, pausa, duplicado manual, ventana 24 h y patas huérfanas.
- `manage.py check`: OK en ambos settings.
- Gunicorn recargado con `systemctl reload predicta`; app activa (200 en `/`,
  302 en `/parleys/` sin sesión).
- Cupón de prueba manual **13291906849**: WON, payout 2.991,5 COP (liquidado
  por `sync_bet_history` manual 2026-10-30), fuera del ledger del motor; es la
  única excepción manual visible en `/parleys/`.
- Sync manual `sync_bet_history` 2026-10-30: liquidó el cupón de sistema
  13290613595 (Memphis, WON → AutoBet WIN) y el manual 13291906849. Quedan 12
  cupones OPEN viejos (7 y 23-24 oct) que **BetPlay sigue reportando OPEN** en
  su historial (así los devuelve la API tras varios syncs).

---

## 5. Siguiente paso operativo

1. La corrida diaria de 00:00 UTC ya opera real (máx. 5 colocaciones, pausa
   30 s) sobre los partidos de las siguientes 24 h. Revisar cada día
   `ParleyRun`, `logs/real_parleys.log` y `/parleys/`.
2. Liquidación: `sync_parleys` actualiza el historial y el ledger; verificar
   que cada cupón del motor pase de OPEN a WON/LOST con su payout.
3. Si `parley_reconcile` muestra ERROR, conciliar a mano (nunca se reintenta
   solo, por diseño anti-duplicado).
4. Vigilar el comportamiento del EV/winrate real frente al backtest.

---

## 6. Riesgos / pendientes

- Rate limit real de BetPlay con volumen aún no medido; el cliente ya lo maneja
  y ahora hay tope de 5 colocaciones + 30 s entre ellas por defecto.
- La rama live ya colocó un cupón real (13293782669) y quedó confirmada en el
  historial; el resto de casos está cubierto con mocks.
- Si la reconciliación automática de un ambiguo no encuentra el cupón, queda en
  ERROR y requiere revisión manual (`parley_reconcile`); nunca se reintenta solo.
- El canary usó 1 de 4 picks; las combinaciones restantes podrán colocarse en
  la siguiente corrida diaria (hasta el tope de 5).
- Con la cadencia diaria, un fallo de API puede dejar el día sin parleys; es el
  precio de reducir riesgo (decisión del humano, 2026-10-30).
- El cupón de prueba es **manual**, no del motor; por eso no afecta el ledger.
- Backtest in-sample: los filtros se eligieron con octubre; validar fuera de
  muestra antes de escalar.
- El motor real y el de parleys comparten la misma cuenta BetPlay; el ledger de
  100k es un límite interno, no una cuenta separada.
- Los cupones manuales se sincronizan desde el historial de BetPlay; el panel
  muestra todos los combinados, no solo los del motor.
