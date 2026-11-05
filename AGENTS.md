# Predicta — Puntero de instrucciones de proyecto

Aplican las reglas globales de OpenCode de la VPS.

- Instrucciones del agente de este proyecto: **`agent.md`**
- Memoria del motor independiente de parleys: **`memory/parley.md`**

Regla clave: el motor de parleys es **adicional e independiente**; no modificar
`run_auto_bets`, `AutoBetConfig`, `DailyCounter`, `paperparleys` ni sus cron.
