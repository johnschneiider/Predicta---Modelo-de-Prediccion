# Agente Predicta — Instrucciones de proyecto

Aplican las reglas globales de OpenCode de la VPS (`/opt/opencode/data/config/opencode/AGENTS.md`):
producción, backups, validación, secretos y prohibición de tocar `/root/.openclaw/**`.

## Memoria obligatoria

Antes de trabajar en el motor de parleys, leer:

- **`memory/parley.md`** — arquitectura, configuración, comandos, estado actual,
  riesgos y siguiente paso del motor independiente de parleys.

Otras memorias del proyecto:

- `memory/2026-10-03.md`
- `memory/2026-10-01.md`
- `memory/2026-09-29.md`
- `memory/2026-09-09.md`

## Regla de oro: aislamiento del motor real

El motor de parleys es **adicional e independiente**. No se debe modificar:

- `auto_betting/management/commands/run_auto_bets.py`
- `auto_betting/models.py` (`AutoBet`, `AutoBetConfig`, `DailyCounter`)
- `auto_betting/paper_parleys.py` y `paperparleys`
- Los cron/horarios existentes del motor real

El motor de parleys solo **lee** `AutoBet` (picks OPEN del día). Sus tablas,
comando, ledger, cron y panel son propios (`parley_engine`).

## Estado actual del motor de parleys (2026-10-31)

- **Multiusuario y ACTIVO en real** (`dry_run=False`). Sin usuario hardcodeado.
- Panel: **`/parleys/`** (tab “Parleys” en `/auto-betting/historial/`).
- Elegibilidad LIVE: `AutoBetConfig.activo` + ticket/punter_id,
  `ParleyEngineConfig.activo`, `CapitalConfig` con balance/ancla,
  `bankroll_cop >= stake`, login OK, fit ≥ 50 y ≥ 2 eventos futuros.
- A un usuario nuevo con cuenta válida se le crea automáticamente
  `ParleyEngineConfig` con los parámetros del admin: stake 500, capital
  100.000, EV 0.80, 2 patas, **sin tope por corrida** y pausa de 30 s.
- Comandos:
  - `venv/bin/python manage.py run_real_parleys` (todos los elegibles; LIVE
    según su config)
  - `venv/bin/python manage.py run_real_parleys --usuario 9 --live`
  - `venv/bin/python manage.py run_real_parleys --dry-run --no-whatsapp`
  - `venv/bin/python manage.py run_real_parleys --sync-only`
  - `venv/bin/python manage.py sync_parleys` (todos los activos)
- Scheduler: tarea `real_parleys` **cada 1440 min (00:00 UTC)**, log en
  `logs/real_parleys.log`. `sync_parleys` no está agendado; se ejecuta al
  inicio/fin de cada corrida y a mano.
- WhatsApp: `notificar_parleys` envía un resumen por usuario/corrida. Si el
  microservicio `predicta-whatsapp` está `disconnected`, el aviso falla pero
  la apuesta no. Reconectar en `/notificaciones/whatsapp/` (superuser).
- Estrategia: 2 patas, stake 500 COP, EV ≥ 0.80 con cuota actual, capital
  interno 100.000 COP, filtros actuales + `ganador` + `esquina`.

## Antes de tocar el motor de parleys

1. Leer `memory/parley.md` (sección 0: multi-usuario).
2. Verificar que el cambio no toca el motor real.
3. Backup con timestamp si se edita un archivo compartido.
4. Probar con `manage.py test parley_engine notificaciones` y `manage.py check`.
5. No colocar dinero real sin autorización explícita del humano.
6. Revisar exclusiones vigentes: `admin2` (ticket vencido y datos de agosto),
   `carlosantoniom051` (inactivo), `flavio` (sin cuenta).
