# SOUL.md — Predicta · Integración BetPlay (Kambi)

> Documentación de credenciales, APIs y flujos de la integración con BetPlay para predicta.com.co.
> **Última actualización:** 2026-09-01
> **Estado:** MOTOR ÚNICO DE PREDICCIÓN = WEB ✅ (§21) · PostgreSQL verificado en runtime ✅ (§21) · Apuestas + historial/tracking DESCIFRADO ✅ · Balance (backend JWT) PENDIENTE ⚠️ · Estrategia v3 FIX ✅ · Umbrales por submercado (Fase 6) ✅ · Filtro por línea tiros (Fase 7) ✅ (§12b) · Cron reordenado ✅ (§16) · Hardening operativo ✅ (§20)
> ⚠️ **SEGURIDAD:** credenciales en texto plano. NO subir a git público ni exponer en logs.

## 1. Credenciales BetPlay
| Campo | Valor |
|---|---|
| Usuario | `1143971600` |
| Contraseña | `Malware2025*` |
| Punter ID | `2585240` |
| Ticket de login | `DED15E71-97A3-325C-E6DB-260816162851` |
| Moneda | COP |

- El **ticket** es una credencial de sesión reutilizable; si el login falla, regenerarlo desde DevTools de `betplay.com.co` (§2).

## 2. Flujo de autenticación (login por TICKET)
El login NO es usuario/clave contra la API: el usuario se loguea en `betplay.com.co` (Cloudflare) → el sitio genera `ticket` + `punterId` → se redime contra la API de auth → devuelve `token` de sesión.

```http
POST https://cf-mt-auth-api.kambicdn.com/player/api/v2019/betplay/punter/login?lang=es_CO&market=CO
Content-Type: application/json
Origin: https://betplay.com.co
```
Body: `{"punterId":"2585240","ticket":"DED15E71-97A3-325C-E6DB-260816162851","customerSiteIdentifier":"","channel":"WEB","market":"CO","requestStreaming":true}`
Response 200: `{"currency":"COP","token":"***","routingKey":"v2019.<uuid>","hashedPunterId":"7liKnDmvy2C0yerEneAkV3kzeImTuAtyrwWlKLXq7F8="}`
- `token`: sesión TTL ~1h (`timeoutInSeconds:3600`). `routingKey`: enruta al backend de cuenta (cambia por login). Ticket válido por horas y reutilizable para generar tokens frescos.
- **Header de sesión: `Authorization: Bearer <token>`** (NO `X-Mt-Session-Token` — devuelve `validSession:false`).

## 3. APIs SIN auth (cuotas / ofrecimientos)
**Base:** `https://us.offering-api.kambicdn.com/offering/v2018/betplay`
**Headers:** `Origin: https://betplay.com.co` + `Referer: https://betplay.com.co/`
**Params:** `lang=es_CO&market=CO&client_id=200&channel_id=1&ncid=<timestamp_ms>`

| Endpoint | Método | Uso |
|---|---|---|
| `listView/football.json` | GET | Partidos pre-match |
| `event/live/open.json` | GET | Partidos en vivo (marcador, reloj, córners, tarjetas, cuota 1X2) |
| `betoffer/event/{eventId}.json` | GET | Cuotas de un evento |
| `betoffer/outcome.json?id={outcomeId}` | GET | Cuota exacta de un outcome por ID (sin matching de nombres) |

- `event/live/open.json` → `{liveEvents:[...]}`, cada uno: `event:{id,homeName,awayName,group,path[],state,start,tags[]}` · `liveData:{matchClock:{minute,period},score:{home,away},statistics:{football:{home:{corners,yellowCards,redCards},away:{...}}}}` · `mainBetOffer` (1X2 en vivo, odds÷1000).
- `betoffer/outcome.json?id=` → `{betOffers:[{id,criterion:{id,label,englishLabel,order,lifetime},betOfferType:{id,name:"Más/Menos de"},eventId,outcomes:[{id,label,englishLabel,odds,line,type:OT_OVER|OT_UNDER,betOfferId,status,cashOutStatus,displayOrder}],tags,cashOutStatus}],events:[{id,homeName,awayName,group,start,state}]}`
  Ejemplo outcomes: `{id:4283624859,label:"Más de",englishLabel:"Over",odds:1230,line:7500,type:OT_OVER}` y `{id:4283624858,label:"Menos de",englishLabel:"Under",odds:3600,line:7500,type:OT_UNDER}`.

**Mercados (categorías Kambi):** 12579 Resultado Final · 12580 Total de goles · 11942 Ambos Equipos Marcarán · 19260 Total de Tiros de Esquina · 12220 Doble Oportunidad · 11929 Apuesta sin empate

## 4. APIs CON auth (cuenta / apuestas)
**Base:** `https://cf-mt-auth-api.kambicdn.com/player/api/v2019/betplay` · **Auth:** `Authorization: Bearer <token>`

| Endpoint | Método | Auth | Uso | Estado |
|---|---|---|---|---|
| `punter/login` | POST | ticket | Login por ticket | ✅ |
| `punter/session.json` | POST | Bearer | Sesión (`{timeoutInSeconds:3600}`) | ✅ |
| `coupon/validate.json` | POST | Bearer | Validar cupón (no apuesta) | ✅ |
| `coupon.json` | POST | Bearer | Colocar apuesta (gasta plata) | ✅ |
| `coupon/history.json` | GET | Bearer | Historial de apuestas (resultados, payout) | ✅ |
| `reward/status/ACTIVE,IN_USE,USED,EXPIRED.json` | GET | Bearer | Recompensas | ✅ |
| `punter/balance.json` / `punter.json` / etc. | — | — | Balance/nombre | ❌ 404 (otro backend) |
| `coupon/place.json` | — | — | No existe | ❌ 404 |

## 5. Flujo de apuesta — DESCIFRADO y VERIFICADO (apuesta real 2026-08-16)
1. `coupon/validate.json` → valida el cupón (`{"status":"SUCCESS","validSession":true,...}`).
2. `coupon.json` → coloca la apuesta (mismo body).

**Body del cupón (formato exacto, verificado):**
```json
{"couponRows":[{"index":0,"odds":1230,"outcomeId":4283624859,"type":"SIMPLE"}],"allowOddsChange":"NO","allowOddsChangeLive":"NO","allowOddsChangePreMatch":"NO","bets":[{"couponRowIndexes":[0],"eachWay":false,"stake":500000}],"channel":"WEB","requestId":"<uuid>","trackingData":{"hasTeaser":false,"isBetBuilderCombination":false,"isMultiBuilder":false,"isPrePackCombination":false,"partnerSpecials":[],"reward":{}},"selectedOutcomes":[{"id":4283624859,"outcomeId":4283624859,"betofferId":2676127866,"eventId":1025806482,"approvedOdds":1230,"betOfferTags":["OFFERED_PREMATCH","OFFERED_LIVE","BET_BUILDER"],"criterion":{"id":1001159897,"label":"Total de Tiros de Esquina","englishLabel":"Total Corners","order":[],"lifetime":"FULL_TIME"},"eachWayApproved":true,"fromBetBuilder":true,"fromPrePack":false,"isLiveBetoffer":true,"isPrematchBetoffer":true,"oddsApproved":true,"label":"Más de","englishLabel":"Over","line":7500,"type":"OT_OVER","status":"OPEN","odds":1230,"displayOrder":0,"cashOutStatus":"ENABLED","path":[{"id":1000093190,"name":"Fútbol","englishName":"Football","termKey":"football","sport":"FOOTBALL"},{"id":1000461816,"name":"Estados Unidos","englishName":"USA","termKey":"usa","sport":"FOOTBALL"},{"id":1000095063,"name":"MLS","englishName":"MLS","termKey":"mls","sport":"FOOTBALL"}]}]}
```
**Unidades:** `odds`÷1000 (1230=1.23) · `line`÷1000 (7500=7.5) · `stake`÷1000 (500000=500 COP).
- `couponRows[].type:"SIMPLE"` · `bets[].couponRowIndexes`: índice en `couponRows` · `allowOddsChange:"NO"` (rechazar si cambia la cuota).

**Respuesta de `coupon.json` (apuesta real):**
```json
{"status":"SUCCESS","couponRef":13008221103,"coupon":{"couponRef":13008221103,"couponExternalRef":"b206f91a-17a9-42c0-b3a3-080561c803c7","placedDate":"2026-08-16T22:26:43.074Z","currency":"COP","channel":"WEB","bets":[{"betRef":16158464863,"couponRowIndexes":[0],"betOdds":2950,"playedOdds":2950,"betStatus":"OPEN","stake":500000,"payout":0,"potentialPayout":1475000,"tags":["EDITABLE"]}],"outcomes":[{"outcomeId":4283662764,"eventId":1025806466,"betOfferId":2676133484,"label":"Austin FC","status":"OPEN"}],"couponRows":[{"index":0,"outcomeId":4283662764,"status":"OPEN","playedOdds":2950,"selectionType":"SIMPLE"}]}}
```
- `stake:500000`=500 COP · `potentialPayout:1475000`=1.475 COP (500×2.95) · `couponRef`/`betRef` sirven para consultar/cancelar (cashout).

## 6. Endpoints de cuenta (balance / nombre) — PENDIENTE (backend JWT)
`punter/balance.json`, `punter.json`, `profile.json` → 404 en `cf-mt-auth-api`. El balance está en otro backend enrutado por el `routingKey`.

**Endpoint descubierto (2026-08-17):** `GET https://betplay.com.co/reverse-proxy/accounts/me/balance` con `Authorization: Bearer <JWT>`.
- NO accesible desde el servidor: `betplay.com.co` está detrás de Cloudflare (bloquea curl y headless con 403). `*.kambicdn.com` sí.
- Usa un JWT (RS256) distinto al token del player API.

**Dos sistemas de auth:**
| Sistema | Token | TTL | Host | Uso |
|---|---|---|---|---|
| Player API | UUID (`punter/login`) | ~1h | `cf-mt-auth-api.kambicdn.com` | login, validate, place, history |
| Frontend accounts | JWT RS256 | 10 min | `betplay.com.co/reverse-proxy/*` (Cloudflare) | balance, perfil |

- JWT del balance decodifica: `{id, idPer:2585240, type:"Authentication", countryCode:"CO", iat, exp}`.
- **Pendiente:** (1) host real del backend de cuentas (response headers en DevTools o llamada directa a `*.kambicdn.com`), (2) endpoint que emite el JWT (renovación programática; expira en 10 min).
- **Cashout/cancelación:** la apuesta devuelve `betRef`/`couponRef` y tags `EDITABLE`; endpoint de cashout pendiente de identificar.

## 7. Notas / aprendizajes
- Frontend `betplay.com.co` detrás de Cloudflare (bloquea headless y `web_fetch` con 403 "Sorry, you have been blocked"). APIs Kambi (`*.kambicdn.com`) sí accesibles por curl.
- Header de sesión correcto: `Authorization: Bearer <token>` (no `X-Mt-Session-Token`).
- Login por ticket reutilizable mientras el ticket siga válido.
- `betStatus` usa `WON`/`LOST`/`OPEN`/`VOID` (no WIN/LOSE). Mapear `WON→WIN`, `LOST→LOSE` si el modelo usa esos choices.
- `coupon/history.json` resuelve el tracking de resultados (betStatus + payout por cupón). Ver §11.
- Plantillas en producción se cachean: con `DEBUG=False` Django usa `cached.Loader` → al editar `.html` hay que reiniciar gunicorn (`systemctl restart predicta`).
- **Apostar = dinero real.** Nunca colocar apuesta (`coupon.json`) sin aprobación explícita de John por apuesta concreta (partido + mercado + selección + monto). `coupon/validate.json` es seguro (no gasta plata).

## 8. Relación con el motor de value betting
`value_betting` ya usa `us.offering-api.kambicdn.com/offering/v2018/betplay` (constante `KAMBI_BASE` en `value_betting/services.py`): `listView/football.json` (fetch_kambi_football_matches) · `listView/{league_path}/all/matches.json` (fetch_kambi_bet_offers) · `betoffer/event/{id}.json`.
**Nuevas capacidades:** (1) value betting EN VIVO (`event/live/open.json`) · (2) cuota por outcome ID (`betoffer/outcome.json`) · (3) validación de apuestas (`coupon/validate.json`) · (4) apuestas programáticas (`coupon.json`, requiere aprobación).

## 9. Roadmap — pendientes para apostar automáticamente (24h)
**Ya existe (no re-hacer):** `value_betting/run_scan()` (escanea Kambi, mapea a Predicta, genera predicción, detecta value bets `ValueOpportunity` con edge/ev/is_value/bet_instruction) · motor `generate_full_prediction` (goles, 1X2, córners, BTS) · app `betting/` (`BettingStrategy` min_edge/min_confidence/min-max_stake/max_daily_bets, `BotSession`, `BotCycle`, backtesting).
**Gaps:** 1) `outcome_id` no se guarda en `KambiBetOffer` (falta campo + extraerlo en `fetch_kambi_bet_offers`) · 2) módulo cliente BetPlay (login ticket con refresh, validate, place — API descifrada §2/§5) · 3) capa de estrategia (edge mínimo, EV, stake, límite diario, dedup) · 4) orquestador/scheduler cron 24h · 5) tracking ✅ RESUELTO 2026-08-17 (`HistorialApuesta` + `coupon/history.json`, §11) · 6) seguridad (límites estrictos, stop-loss, confirmación, no apostar si cambió la cuota) · 7) endpoints balance/nombre (§6) y cashout.

## 10. App `auto_betting` — OPERATIVA ✅
App Django en `/var/www/predicta.com.co/auto_betting/`.

**Modelos:**
- `AutoBetConfig` (por usuario): ticket, punter_id, cuota_minima (2.0), stake (500000=500 COP), max_apuestas_diarias (20), horas_adelante (24), activo. (`edge_minimo` eliminado por migración; `odds_minima` campo muerto.)
- `AutoBet`: evento_id, equipos, liga, mercado, selección, línea, cuota, corners_predichos, predicta_prob, edge, ev, coupon_ref, bet_ref, stake, potential_payout, estado (OPEN/WIN/LOSE/VOID/ERROR).
- `DailyCounter`: fecha + apuestas_colocadas. `HistorialApuesta`: historial completo de BetPlay (§11).

**Servicios:** `services.py` (`login`, `fetch_upcoming_matches`, `fetch_corners_odds`, `fetch_shots_on_target_odds`, `validate_coupon`, `place_bet`, `fetch_bet_history`, `sync_historial`) · `strategy.py` (`predict_corners`, `predict_shots_on_target`, `select_bets` v3: cuota ≥2.0 Y P≥50% Y EV>0 con tiers de confidence/EV por cuota).

**Filtros y mapeo (fixes 2026-08-17):**
- `fetch_upcoming_matches()` descarta eSports/virtual, ligas de reservas/juveniles, femenil y filiales (`_es_partido_no_valido()`).
- `find_predicta_league()` (run_auto_bets.py) usa solo mapeo exacto `LEAGUE_MAPPING`; fallback fuzzy (`SequenceMatcher`) eliminado (mapeaba `Superligaen`→`Süper Lig`, `Liga I`→`La Liga`).

**Comando / cron:**
```bash
cd /var/www/predicta.com.co && venv/bin/python manage.py run_auto_bets
```
- Flujo: login → escanear partidos → predecir córners → traer cuotas → detectar value → validar → colocar → guardar. Dedup: no apuesta 2 veces al mismo evento el mismo día.
- Cron: crontab www-data `10 5 * * *` (05:10 UTC = 00:10 Bogotá; Colombia UTC-5 fijo sin DST). `DJANGO_SETTINGS_MODULE=betting_bot.settings` forzado con `env` para no heredar `/etc/environment` global (`config.settings.production` de otro proyecto). `TIME_ZONE='America/Bogota'` + `timezone.localdate()` para DailyCounter en fecha Colombia. Cron OpenClaw de respaldo (`predicta-auto-bets`) deshabilitado (redundante). Log: `logs/auto_betting.log`.

**Estrategia v3 (fix 2026-08-20):** regla `cuota ≥ cuota_minima (2.0) Y P ≥ 50% Y EV > 0`. `min_p=0.50` es hard floor real en `select_bets()→_add_candidate()` (antes era código muerto y pasaban P hasta 25%). Tiers por cuota (solo agregan confidence/EV, nunca bajan P):

| Cuota | P mín | Conf mín | EV mín |
|---|---|---|---|
| ≤2.99 | 50% | 0.35 | 5% |
| 3.00-3.99 | 50% | 0.45 | 10% |
| 4.00-5.99 | 50% | 0.55 | 15% |
| ≥6.00 | 50% | 0.65 | 20% |

**Calibración (`calibrate_probability`):** shrinkage antes de evaluar filtros. P≤60%: ligero (factor 0.95 hacia 50%). P>60%: fuerte (factor 0.50) con cap 60%. Backtest (50 asentadas admin): P<30% → 11.1% WR 💀 · P 40-50% → 40.0% · P 50-60% → 64.3% ✅ · P≥60% → 27.3% 💀. Conclusión: el modelo solo es confiable en el rango 50-60%.

**Bugs corregidos (2026-08-20):** 5 apuestas del 16-Ago con `predicta_prob` en fracción (0.35) en vez de % → corregidas en DB (×100). 14 apuestas históricas con P<50% quedaron colocadas antes del fix (dinero real, no reversible). Ahora `min_p`/`min_confidence` se respetan vía `max(min_p, tier_min_p)` y `max(min_confidence, tier_min_conf)`.

**Pendientes:** 1) ✅ max_apuestas_diarias 20 · 2) ✅ mercado tiros a puerta (`fetch_shots_on_target_odds`) · 3) ✅ tracking (§11) · 4) cashout · 5) saldo/stop-loss (bloqueado, §6) · 6) robustez (`IndexError` en `place_bet`, token sin refresh/retry, DailyCounter en UTC) · 7) ✅ min_p hard floor (FIX 20-Ago) · 8) ✅ cap calibración 65%→60% (FIX 20-Ago; P≥60% = 27% WR real).

**Cambios 2026-08-29 (decisión de John):**
- **a) Tope por submercado ELIMINADO:** se quitó `MAX_BETS_PER_SUBMARKET_DAILY = 5` de run_auto_bets.py (y su helper `_side_prefix`). Motivo: con el tope, los usuarios de cuota mínima baja (admin2/carlos 1.6) NO eran superconjunto del admin (2.0) — sus 5 cupos se llenaban con apuestas 1.85-1.97 y quedaban por fuera partidos ≥2.0 que el admin sí apostaba. Ahora se apuestan TODOS los candidatos válidos, sujetos a `max_apuestas_diarias` por usuario + dedup por evento+mercado.
- **b) Botón manual (solo superuser):** en `/auto-betting/configuracion/umbrales/` → botón "▶️ Ejecutar auto-betting para todas las cuentas" hace POST a `/auto-betting/configuracion/umbrales/run/` (vista `auto_betting.views.run_manual`). Lanza en background `venv/bin/python manage.py run_auto_bets` (SIN --email → TODAS las AutoBetConfig activas, igual que el cron) con `DJANGO_SETTINGS_MODULE=betting_bot.settings`, salida a `logs/auto_betting.log`. Anti-concurrencia: `pgrep -f "manage.py run_auto_bets"` (si ya hay corrida, responde error). Semántica: NO repite apuestas ya colocadas (dedup usuario+evento+mercado, estado OPEN/WIN/LOSE/VOID); SÍ coloca nuevas que pasen filtros hasta el límite diario individual.

## 11. Historial de apuestas + tracking (HistorialApuesta) — 2026-08-17
**Modelo:** `coupon_ref` (unique), `placed_date`, `bet_ref`, `played_odds` (decimal), `bet_status` (WON/LOST/OPEN/VOID), `stake`, `payout`, `potential_payout` (÷1000=COP), equipos, liga, mercado, selección, línea, sport. Propiedades: `stake_cop`, `payout_cop`, `profit_cop`.

**Endpoint:**
```http
GET https://cf-mt-auth-api.kambicdn.com/player/api/v2019/betplay/coupon/history.json?lang=es_CO&market=CO&client_id=200&channel_id=1&range_size=200&range_start=0&toDate=<ISO>
Authorization: Bearer <uuid del login>
```
- Devuelve `{historyCoupons:[...]}`: `couponRef`, `placedDate`, `bets[{betRef,betOdds,playedOdds,betStatus,stake,payout,potentialPayout}]`, `outcomes`, `events[{homeName,awayName,eventGroups,eventStartDate}]`, `betOffers[{criterion,line}]`. Funciona con el token UUID del player API (NO necesita el JWT).

**Sync:** `venv/bin/python manage.py sync_bet_history --since 2026-08-01` (`--since` default `2026-08-01`: importa desde esa fecha, borra previos y omite cupones viejos). Lógica en `services.sync_historial(since_str)`.

**UI:** URL `https://www.predicta.com.co/auto-betting/historial/` · sync POST `/auto-betting/historial/sync/` (vista `historial_sync`, `@csrf_exempt`) · plantilla `auto_betting/templates/auto_betting/historial.html` (tarjetas win rate/P&L/ROI + tabla scroll `max-height:68vh`, cabecera fija, zebra) · botón "⟳ Actualizar datos" (fetch POST → sync → reload) · link navbar: dropdown usuario → "🎰 Apuestas BetPlay" (`base.html`).

**Análisis inicial (61 apuestas, 17-Ago):** 27 WON/24 LOST/5 OPEN/5 VOID, WR 52.9%, P&L −15.095 COP. Auto-betting (500 COP) +1.305 COP (WR 54%); la cuenta cae por apuestas manuales grandes (una de 25.000 COP perdió). Córners (núcleo) 50% WR (sin edge demostrado). Cuota media ganada 2.03 < perdida 2.83 → sobreconfianza en cuotas altas.

**Post-fix v3 (20-Ago):** bug min_p corregido (hard floor real) · backtest admin: P<30% 11% WR 💀, P 50-60% 64% ✅, P≥60% 27% 💀 · cap calibración 65%→60% · 5 apuestas P-fracción corregidas · 14 históricas P<50% no reversibles · toda nueva apuesta cumple P≥50% garantizado.

## 12. CLV (Closing Line Value) — 2026-08-18
`CLV % = (played_odds / closing_odds − 1) × 100`. Positivo = mejor cuota que el cierre = value real (beat the closing line); negativo = peor que el cierre. Es la métrica más confiable de calidad de apuestas (independiente de la varianza a corto plazo).

**`HistorialApuesta` (migración 0004):** `closing_odds` Float null (último snapshot pre-partido) · `clv` Float null (`(played/closing−1)×100`) · `is_system` Bool (sistema vs manual).
**`OddsSnapshot` (0004):** `outcome_id` BigInteger indexed · `event_id` BigInteger indexed · `market` CharField · `seleccion` CharField · `linea` Float null · `side` CharField (over/under/1/x/2/si/no) · `odds_decimal` Float · `captured_at` DateTime auto. Índices `(outcome_id, -captured_at)` y `(event_id)`.

**Comando:** `venv/bin/python manage.py capture_closing_odds`. Dos fases: 1) Snapshot: apuestas `closing_odds IS NULL` y `event_start_date > now` → agrupa por event_id, `fetch_market_odds()`, guarda `OddsSnapshot` por outcome relevante. 2) Cálculo CLV: `closing_odds IS NULL` y `event_start_date <= now` → último snapshot del outcome → escribe closing_odds y calcula clv. Cron `*/15 * * * *` (www-data). Log `logs/closing_odds.log`.

**Fix sync_historial (18-Ago):** ahora llama `_capture_snapshot_for_apuesta()` tras importar cada apuesta con partido futuro (antes no se capturaban snapshots y el CLV era irrecuperable para partidos ya empezados).
```python
# En sync_historial(), después de update_or_create:
if ap.event_start_date and ap.event_start_date > now and ap.outcome_id:
    _capture_snapshot_for_apuesta(ap, now)
```
**Limitación:** las 74 apuestas históricas importadas antes del fix no tendrán CLV (cuotas de cierre ya no disponibles en Kambi para eventos finalizados).
**UI:** historial muestra CLV por apuesta (verde positivo/rojo negativo) · tarjetas CLV promedio y % positivo · gráfica CLV por mercado · ayuda si no hay CLV ("Ejecuta `manage.py capture_closing_odds` o espera al cron").

## 12b. Umbrales por SUBMERCADO (Fase 6) — 2026-08-23
**Motivo:** auditoría 22-Ago: el lado Over/Under rinde muy distinto dentro del mismo mercado (córners-over +20.5% ROI vs under −55.5%; tiros a puerta-under +13.9% vs over −19.0%). `MARKET_FILTERS` solo distinguía por mercado completo.
**Implementado:** 1) `MarketFilterConfig` (models.py, migración `0010_marketfilterconfig`): singleton global con min_p/min_confidence por submercado (`goals_over/under`, `corners_over/under`, `shots_on_target_over/under`, `btts_si/no`); defaults = `MARKET_FILTERS` legacy (sin cambio de comportamiento). 2) `strategy.get_market_filters()`: lee `get_solo()` → dict `{market_side:{min_p,min_confidence}}`; fallback legacy si falla (nunca rompe). 3) `select_bets()/_add_candidate()`: `_resolve_filters()` con prioridad market_side > market genérico > defaults. 4) run_auto_bets usa `get_market_filters()` (dinámico, lee DB por corrida). 5) UI `configuracion_umbrales` (`/auto-betting/configuracion/umbrales/`), form `MarketFilterConfigForm`, template `configuracion_umbrales.html`, link navbar "🎯 Umbrales (Global)" solo superuser. 6) `@user_passes_test(_es_admin_principal)` exige superuser: verificado admin@predicta.com.co accede y guarda (200 OK); admin2 redirigido (302) y su POST no modifica. Config única compartida (aplica igual admin + admin2 + futuros).
**Verificación:** `manage.py check` sin errores · test funcional django.test.Client (login real: 200/302 según superuser; POST de admin2 no persiste) · test unitario select_bets (invertir umbrales over↔under cambia qué lado pasa) · get_market_filters probado en proceso Python independiente (lee DB como el cron real) · tras pruebas, config restaurada a valores legacy exactos · backup `db.sqlite3.backup_pre_marketfilterconfig_20260823_022000` · `systemctl restart predicta.service` aplicado, 200 OK post-restart.
**Pendiente (John):** umbrales quedaron en legacy (sin cambio real). Propuesta de valores diferenciados para aplicar desde la UI cuando decida:

| Submercado | Propuesta |
|---|---|
| goals_over | 0.50 (sin cambio) |
| goals_under | 0.55 (leve, n pequeño) |
| corners_over | 0.52 (bajar, hoy penalizado sin necesidad) |
| corners_under | 0.65+ (subir fuerte, −55.5% ROI persistente) |
| shots_on_target_over | 0.62 (subir, ROI −19% n=6) |
| shots_on_target_under | 0.50 (bajar, mejor calibrado de los tres nuevos) |

**Fase 7 — Filtro por LÍNEA (2026-08-31, Fix aprobado por John):** la tabla de umbrales por submercado no distinguía por línea; el sangrador de tiros-under era por línea (7.5 → 27% WR, 8.5 → 40%, pero 9.5 → 80%). Subir `min_p` no servía (el `calib_cap=0.58` hacía que min_p≥0.59 matara el submercado entero, incluido el 9.5 rentable). Solución: campos nuevos en `MarketFilterConfig` (`shots_on_target_over/under_min_line/max_line`, migración `0013`), resolución en `_resolve_filters()` y filtro en `_add_candidate()` (line < min_line o > max_line ⇒ descartado). Default `shots_on_target_under_min_line=9.5` ⇒ solo se apuesta Under de tiros ≥9.5. UI: sección "🎯 Filtro por línea" en `/auto-betting/configuracion/umbrales/`. El over queda sin tope (0 = sin filtro) a la espera de más datos. **Impacto:** elimina −101.165 COP/mes (under 7.5+8.5 asentadas), conserva el +55.670 del 9.5 y deja de arriesgar el 6.5 (n=4, ruido). **Backup pre-cambio:** `db.sqlite3.pre_fix_20260831_144636` en workspace.

## 13. Multitenancy — aislamiento por usuario — 2026-08-19
Cada usuario (`cuentas.Usuario`) tiene su propio sistema aislado: credenciales, config de estrategia, apuestas, contador diario e historial.
**Modelos (migraciones 0005-0008):** `AutoBetConfig` dejó de ser singleton → `OneToOneField(Usuario)` · `AutoBet`/`DailyCounter`/`HistorialApuesta` → `ForeignKey(Usuario)` NOT NULL · `DailyCounter.unique_together=(usuario,fecha)` · `HistorialApuesta.unique_together=(usuario,coupon_ref)` · `punter_id` default `""` (antes hardcoded "2585240") · migración de datos `0006_backfill_usuario`: todo lo existente → admin@predicta.com.co.
**Flujo scoped por usuario:** `run_auto_bets` itera todas las configs activas (flag `--email <correo>` para un usuario) · `sync_bet_history` por usuario (`--email` opcional) · `services.sync_historial(since_str, usuario=None)` · `views.historial`/`historial_sync`: cada usuario ve/sincroniza solo lo suyo (se quitó candado superuser) · `scripts/dry_run_auto_bets.py` acepta email por argv.
**Self-service credenciales:** URL `/auto-betting/configuracion/` (navbar "⚙️ Config BetPlay"). Cada usuario logueado edita SU config (ticket, punter_id, cuota_minima, stake, max_apuestas_diarias, horas_adelante, activo) sin pasar por el agente ni admin. `get_or_create(usuario=request.user)` al primer acceso. admin2 sin staff (no ve otros vía admin). Form `auto_betting/forms.py` (`AutoBetConfigForm`), template `configuracion.html`.
**Activar usuario 2:** 1) entra con su cuenta → 2) "⚙️ Config BetPlay" → 3) pega ticket + punter_id + parámetros → 4) guarda; el cron (`10 5 * * *`) corre todas las configs activas.
**Pendiente (seguridad):** credenciales en texto plano (DB + este SOUL.md) → siguiente paso: encriptar `AutoBetConfig.ticket` con Fernet (key en settings + migrar valores). Backup pre-cambio `db.sqlite3.backup_pre_multitenant_20260819_101809`. Cambios aún sin commit en git.

## 14. API-Sports Football v3 — fuente de stats — 2026-08-25
Integración con API-Football para stats (xG, córners, remates, posesión, transfers, predicciones, cuotas). Complementa a Kambi (cuotas/apuestas) y sustituye al scraping de Flashscore como fuente única de stats.
**Credenciales:**
| Campo | Valor |
|---|---|
| Base URL | `https://v3.football.api-sports.io` |
| API Key | `a48e5245f8edcd8bfb0a91f8bfd3f0f9` |
| Header auth | `x-apisports-key: <token>` (NO `x-rapidapi-key`) |
| Cuenta | Vital Mix (`vital.mix324@gmail.com`) |
| Plan | Pro |
| Caducidad | 2026-09-25 |
| Cuota | 7.500 requests/día |

Ejemplo: `curl -s "https://v3.football.api-sports.io/status" -H "x-apisports-key: a48e5245f8edcd8bfb0a91f8bfd3f0f9"`

**Endpoints verificados (todos ✅):** `/status` (cuenta, plan, caducidad, cuota) · `/predictions?fixture=ID` (ganador %, goles over/under, advice, forma last_5) · `/standings?league=ID&season=YYYY` (rank, puntos, DG, PJ, form, goles local/visita) · `/players/topassists` (asistentes + stats) · `/fixtures/rounds` (jornadas) · `/transfers?player=ID` (historial traspasos) · `/odds/mapping` (IDs partidos con cuotas) · `/fixtures/statistics?fixture=ID` (stats por equipo: tiros, córners, xG, posesión, tarjetas, pases) · `/fixtures/players?fixture=ID` (stats por jugador: rating, tiros, goles, pases) · `/fixtures/events?fixture=ID` (Gol, Card, Var, subst) · `/players?league=ID&season=YYYY&page=N` (stats por temporada, sin xG).

`/fixtures/statistics` campos (por equipo): Shots on/off Goal · Total Shots · Blocked Shots · insidebox/outsidebox · Fouls · Corner Kicks · Offsides · Ball Possession · Yellow/Red Cards · Goalkeeper Saves · Total passes · Passes accurate · Passes % · expected_goals (xG por EQUIPO — solo aquí, NO por jugador) · goals_prevented (xG evitado por el portero). Córners = Corner Kicks (conteo agregado, no evento con minuto).

`/fixtures/players` estructura: `{player:{id,name,photo}, statistics:[{games:{minutes,position,rating,captain},shots:{total,on},goals:{total,conceded,assists,saves},passes:{total,key,accuracy},tackles:{},duels:{total,won},dribbles:{},fouls:{},cards:{yellow,red},penalty:{}}]}`

`/fixtures/events` tipos: `Goal` · `Card` · `Var` · `subst` (solo 4; córners/remates NO son eventos individuales).

**IDs útiles:** Ligas: 39 Premier League · 253 MLS. Equipos: 40 Liverpool · 42 Arsenal · 50 Man City · 49 Chelsea · 34 Newcastle · 66 Aston Villa · 1599 Philadelphia Union · 9568 Inter Miami. Jugadores: 306 Salah · 276 Neymar · 19163 J. Murphy. Para todos los IDs de ligas: `/leagues` (no testeado). `league=39` EPL verificado.

**Limitaciones:** 1) xG por jugador NO existe en API-Football (solo equipo en `/fixtures/statistics`) → Understat/fbref si se necesita · 2) `/transfers` devuelve vacío (`results:0`, sin error) si el jugador no tiene historial · 3) odds retroactivos limitados (pre-match recientes, no históricos de meses — afecta backtesting edge_detector; mitigación: conservar BD vieja) · 4) cobertura parcial ligas menores (Primera B Colombia, Expansión MX, Primera Nacional, Serie B Ecuador, Azerbaiyán, Bosnia) → probe por liga antes del refill · 5) córners sin minuto (solo conteo) → adamchoi `corners_scraped.db` sigue necesario para granularidad minuto a minuto.

**Costo (detalle en memory `2026-08-25-predicta-api-football-sizing.md`):** sync semanal ~42 ligas: ~950 req con odds / ~500 sin odds · flujo diario ~135 req/día (picos sáb/dom 180-200) · backfill histórico one-time (2 temporadas, 44 ligas): ~27.300 req → Free 273d ✗ · Pro ~37d · Ultra ~4d ✅ · Pro (7.500/día) da margen cómodo.

**Relación con Predicta:** fuente única de stats para motores (`corners_model`, `xg_shots`, `DixonColes`), sustituye Flashscore · córners/xG unificados en `/fixtures/statistics` (hoy córners sudamericanos usan `corners_scraped.db` como secundaria) · team IDs canónicos → re-entrenar modelos, cero mapeos fuzzy · pendiente John: plan (Pro vs Ultra) y refill completo desde API como fuente única.

## 15. Migración SQLite → PostgreSQL — APLICADA 2026-08-31
**Estado: ✅ COMPLETADA.** Base central migrada de `db.sqlite3` (352 MB) a PostgreSQL 15 local.

**Qué se hizo:**
1. **Código adaptado ANTES de migrar** (probado en SQLite, sin romper nada):
   - Columna `as` (reservada en PG) → `db_column='as_field'` (migración `football_data/0006_alter_match_as_field`). El ORM ya usaba el nombre Python `as_field` en todos lados; solo cambió el nombre físico. Datos verificados intactos (40.016 filas).
   - Los 10 `.extra()` deprecados → `annotate`/`F()` (`football_data/views.py` ×8, `views_shots.py` ×2). Aritmética `fthg+ftag`, `hs+as_field`, `hst+ast`, `hc+ac` ahora con `F()`. Queries verificadas idénticas (over2.5=45018, buckets de tiros/córners iguales).
   - `populate_legacy.py` (`DROP TABLE`/`CREATE TABLE AS SELECT`) funciona en PG sin cambios.
2. **Migración pendiente preexistente aplicada:** `betfair/0003_betfairevent_competition_fields` (2 columnas) estaba sin aplicar y rompía `dumpdata`.
3. **Migración de datos:** `dumpdata` (SQLite, 514 MB) → `loaddata` (PG). **296.949 objetos**, conteos idénticos por tabla (Match 86.416, fixtures 104.523, stats 81.612, autobet 508, historial 612, usuarios 3). JSONField → `jsonb` correcto (seasons, raw_json verificados).
4. **Config:** `settings.py` y `settings_production.py` → `django.db.backends.postgresql`, `CONN_MAX_AGE=60`. Credenciales vía `os.getenv` con defaults (rol `predicta`, base `predicta`, host 127.0.0.1).
5. **Verificación:** `manage.py check` OK · `migrate` OK · sitio 200 OK post-restart · dry-run del embudo completo contra PG OK.

**Infra:** rol/base `predicta` en PostgreSQL 15 (password en `backups_predicta_fix/pg_password.txt`, mismo patrón de credenciales en texto plano que el resto).

**Beneficio:** adiós `database is locked` (MVCC) · se puede subir `gunicorn workers` de 1 a N (pendiente, no se tocó) · guards anti-colisión de `api_football_daily.sh` ya no son por lock (se dejan por seguridad).

**Pendientes/notas:** `db.sqlite3` viejo se conserva como rollback (backup pre-migración en `backups_predicta_fix/db.sqlite3.pre_fix_*`). Los scripts de análisis que conectan directo por `sqlite3` (`scripts/backtest_edge.py`, `backtest_goals.py`, `edge_detector.py`, `loocv_*.py`) siguen apuntando al SQLite viejo (datos congelados); adaptarlos a PG si se vuelven a usar. Rollback = revertir `DATABASES` a sqlite3.

## 16. Investigación patrón dominical + 3 propuestas — 2026-08-31
Investigación pedida por John (30/31-Ago): por qué los domingos pierden dinero en auto-betting.
**Veredicto: no existe "maldición dominical" estable.** Los domingos 09-Ago (+142.567, 58,3% WR) y 16-Ago (58,6%) fueron rentables. Los 2 últimos domingos malos tuvieron causas técnicas distintas e identificables:
- **23-Ago:** bug de λ de goles inflado (goles-over WR 21%) → YA CORREGIDO ese día (cap de sanidad 1.25x + calibración, §10). El cap sigue activo (descartó Benfica/Barcelona/etc. en la corrida del 31-Ago).
- **30-Ago:** `sync_daily` falló 27/28/29-Ago por "database is locked" → apuestas del domingo con BD sin sincronizar desde el jueves. Encima cayó sobre el sangrador de tiros a puerta UNDER (roto desde el sábado 29).
**Números clave (mes 01-30 Ago, asentadas):** Lun-Sáb +279.675 COP (+13,7% ROI) · Domingos +729 COP (break-even) · Mes ~+280K · Los 2 domingos malos: −154.490 COP ≈ 55% de la ganancia del mes.
P&L por submercado: Goles OVER 50% WR +54.385 · BTTS Sí 58% +84.710 · Córners ~50% ~+13,5K · Tiros UNDER 9.5 80% +55.670 · Tiros OVER 41% −2.660 · **Tiros UNDER 7.5: 29% −53.425** · **Tiros UNDER 8.5: 40% −38.380**.
Verificación partido a partido (BD sincronizada): el modelo sub-estima tiros a puerta ~2 de media en sus picks under (América-MG λ 7.25 → real 14; Grêmio λ 8.12 → real 14; Dundee λ 7.65 → real 10; Avaí λ 7.20 → real 9).
El "patrón dominical" real: el domingo es el día de máxima exposición (88-91 apuestas, ~35% en goles-over, mercado 50/50 con rachas 21%→71%→39%). El sábado los goles-over calientes taparon el sangrado de tiros; el domingo no. Córners se mantuvo verde el domingo (57%) porque usa `corners_scraped.db` (fuente separada).

**Propuesta 1 — Revisar Tiros a puerta UNDER 7.5/8.5 (el sangrador).** Estado: **APLICADO 2026-08-31** (Fase 7, §12b). Motivo: −101.165 COP en asentadas (WR 27%/40%), sin upside ningún día. Acción aplicada: filtro por línea — `shots_on_target_under_min_line=9.5` (solo se apuesta Under ≥9.5, que rinde 80% WR). El Under 9.5 (80%) y el 6.5 (n=4, ruido, se bloquea) no se tocan los goles ni BTTS.

**Propuesta 2 — Migración SQLite → PostgreSQL.** Estado: **APLICADO 2026-08-31**; detalle en §15. Motivo: sync_daily falló 27/28/29-Ago por "database is locked" → apuestas del domingo 30 con datos atrasados; el riesgo dejó de ser teórico (costó dinero real). Acción aplicada: base+usuario PG creados, DATABASES cambiados (2 settings), 352 MB migrados (dumpdata→loaddata, 296.949 objetos verificados), `as`→`as_field`, `.extra()`→`F()`.

**Propuesta 3 — Reordenar cron: sync ANTES que apuestas.** Estado: **APLICADO 2026-08-31**. Acción: `api_football_daily.sh` movido 06:00 → 05:00 UTC y `run_auto_bets` 05:10 → 06:10 UTC. Con sync_daily ~2 min y populate_legacy ~6 min (done ~05:08), las apuestas de las 06:10 siempre corren con la BD sincronizada. Bajo riesgo, no toca lógica. Nota: tras la migración a PostgreSQL (§15) ya no hay locks, pero el orden correcto elimina la clase de riesgo de apostar con datos atrasados.

## 17. Diagnóstico de calibración del modelo — 2026-08-31
Backtesting del domingo 30 (sin *lookahead*: predicciones registradas pre-partido vs resultados reales; NO re-ejecutado sobre BD actual porque los motores entrenan con los últimos 20 partidos y ya contienen el 30-Ago).

**Hallazgo:** el modelo sobrestima P ~17 pp en la zona de decisión. WR real ≪ P declarada:
| P declarada | n | WR real |
|---|---|---|
| 50-55% | 21 | 38% |
| 55-60% | 70 | 39% |
P&L domingo 30: −108.355 COP (91 apuestas, 38% WR). Tiros a puerta = 75% de la pérdida (under≤8.5 −57.220, over 8.5/9.5 −41.000, 0% WR). Goles +3.5 0/5 (−34.500).

**Causa raíz (rutas):**
- `auto_betting/strategy.py:390` `calibrate_probability(p, cap=0.58)` — shrinkage asimétrico: P≤60% factor 0.95 (casi no mueve), P>60% factor 0.50 + cap duro 0.58. Resultado: casi todo el volumen se apila en P 50-58% (el cap trunca la cola alta) donde el modelo está más descalibrado.
- `auto_betting/strategy.py:473` `_get_tier_thresholds(cuota)` — `min_p` es hard floor 0.50 en TODOS los tiers; los tiers solo suben confidence/EV, nunca P. Deja pasar P 50-58% descalibrada.
- `auto_betting/strategy.py:492-528` `_add_candidate()` — aplica `calibrate_probability` ANTES del filtro `p < min_p`; con `calib_cap=0.58`, `min_p` efectivo útil ≤0.58 (min_p≥0.59 mata el submercado entero, no solo la cola).
- `auto_betting/models.py` `MarketFilterConfig` — `calib_cap=0.58`, `*_min_p`, `*_min_ev` por submercado (singleton, editable en `/auto-betting/configuracion/umbrales/`).
- P cruda generada por motores: `ai_predictions/dixon_coles.py` (goles), `ai_predictions/xg_shots_model.py:160` `predict_shots_on_target_total` + `_get_team_xg_data` (tiros, `order_by('-date')[:20]` — subestima λ ~2, ver §16), `ai_predictions/corners_model.py`, `ai_predictions/advanced_features.py` (BTTS).
- Flujo: `auto_betting/management/commands/run_auto_bets.py:304` `get_market_filters()` → `select_bets(market_filters=…)`. Monitor: `auto_betting/management/commands/calibration_report.py` (cron 05:25, alerta WR≪P en `logs/auto_betting.log`).

**Puntos de intervención (pendientes de decisión):** (1) subir `min_p` por submercado solo donde la cola 50-58% pierde (tiros-over, goles-over cuota alta) sin tocar el núcleo calibrado; (2) bajar `calib_cap` o endurecer shrinkage para reflejar el 39% real; (3) corregir la subestimación de λ en tiros (factor defensivo/liga en `xg_shots_model.py`).

## 18. Solución definitiva: motor de ratings Poisson regularizados — 2026-08-31
**Diagnóstico de causa raíz (backtest walk-forward, `scripts/poisson_bench.py`, 26 ligas / 1224 partidos test, sin lookahead):**
- La P cruda NO discrimina dentro de cada submercado (curvas de fiabilidad planas/invertidas) porque los motores usan **promedios muestrales sin shrinkage**:
  - Goles: ratios ataque/defensa crudos (equipo fuerte → λ inflado → anti-señal en la cola alta; el "piso de liga" solo agravaba). El pipeline OLD es **peor que la media de liga**: RMSE 1.73 vs 1.68, ρ 0.185 vs 0.198, sesgo +0.36.
  - Tiros a puerta: medias por venue de últimos 20 partidos (ruidosas; ~115+ equipos test sin historial).
- El `xg_shots_model` ni siquiera usa el xG real disponible en `Match.xg_home/xg_away` (20.612 partidos con xG).

**Solución (APLICADA, validada walk-forward):**
- Nuevo `ai_predictions/poisson_ratings.py`: log λ_home = α + att[home] + def[away] + home_adv (ídem away), con **ridge** sobre ratings (encoge hacia media de liga → sin inflación ni sobreajuste) y **decaimiento temporal τ=90d** (adapta a forma reciente). Ventaja local aprendida por liga.
- Resultados vs pipeline viejo:
  | Mercado | métrica | OLD | NEW |
  |---|---|---|---|
  | GOLES | sesgo λ | +0.36 | **−0.10** |
  | GOLES | RMSE | 1.73 | **1.69** |
  | GOLES | ρ spearman | 0.185 | **0.223** |
  | SOT | RMSE | 3.25 | **3.19** |
  | SOT | ρ spearman | 0.205 | **0.248** |
- Curvas de fiabilidad monótonas en ambos mercados (34%→38%→46%→57% en SOT).
- ρ absoluto ~0.22-0.25 está cerca del techo teórico (ruido Poisson por partido): un solo partido no se puede discriminar mucho más. El edge real está en λ SIN SESGO contra la línea de mercado, que es lo que el ridge garantiza.
- **Cableado:** `strategy.get_official_predictions()` usa el motor para `goals_total` y `shots_on_target` (kill-switch `POISSON_RATINGS_ENABLED=True`). Fallback automático al pipeline legacy si no hay modelo. Cap sanidad goles 1.25x→**1.6x** (el 1.25x era remiendo del modelo sin shrinkage; ahora es solo red de seguridad extrema y también cubre al motor).
- **P raw persistida:** `AutoBet.predicta_prob_raw` (migración 0014) — la P cruda del modelo queda en BD para re-calibración futura sin depender de logs.
- Córners NO se tocó (usa `corners_scraped.db` y rinde bien); BTTS tampoco (58% WR, mejor submercado). El motor soporta 'corners' si se decide migrar luego.
- Dry-run post-cambio OK (10 candidatos, Benfica vs Estoril ya no lo descarta el cap).
- Restart `predicta.service` aplicado (200 OK). Commit git: `feat(calibracion): motor Poisson ridge...`.

## 19. Reapertura de submercados — 2026-08-31
**Pregunta de John:** ¿podemos habilitar los submercados porque el fondo está resuelto? **Respuesta: SÍ para goles/tiros/córners (todo pasa por el motor ridge), NO para BTTS-No y 1X2 (modelos intactos, sin validación).**

**Evidencia (`scripts/reopen_analysis.py`, walk-forward 5.850 partidos test, sin lookahead):** con el motor, TODOS los over/under quedan calibrados (±5pp):
| Submercado | P pred | WR real |
|---|---|---|
| Córners under 8.5 / 9.5 / 10.5 | 39/51/62% | 39.1/51.4/61.7% |
| Goles under 2.5 / 3.5 | 51.4/71.7% | 47.9/68.8% |
| Tiros under 7.5/8.5/9.5/10.5 | 39.5/52.1/63.9/74.2% | 36.2/48/59/69.7% |
- El gate de EV con P honesta filtra solo (cuota justa por línea: under 7.5 requiere 2.53+, el mercado casi nunca la paga).
- BTTS derivado del motor λ también calibra (70.2% vs 72.6% real), PERO no se toca: el modelo BTTS actual rinde 58% WR en apuestas reales y cambiarlo es decisión aparte.

**Cambios aplicados:** 1) `corners_total` al motor ridge (antes solo goals+sot). 2) Mercados del motor con P honesta (sin heurística shrinkage+cap; la heurística queda solo para BTTS/1X2 legacy). 3) Config: `corners_under` reabierto (min_p 0.40, min_ev 0.05) · `goals_under` des-atrapado (min_p 0.50) · filtro duro por línea tiros-under eliminado (`min_line=0`; el EV gate hace su trabajo). 4) Backup PG pre-cambio: `backups_predicta_fix/pg_predicta_pre_reopen_20260831_173538.sql`. Dry-run: 17 candidatos (antes 10), incluye córners-under y goles-under. Restart OK (200).

**Residual conocido (no bloquea):** el Poisson subestima la cola over ~3-5pp y sobrestima under ~3-5pp (over-dispersión). Próximo refinamiento natural: binomial negativa en `poisson_over` (parámetro φ por mercado). Los márgenes EV (10-20%) lo absorben hoy.

## 20. Hardening operativo — 2026-08-31
**Circuit breakers ACTIVADOS:** `stop_loss_diario_cop=-30000` y `max_exposicion_evento_cop=20000` en MarketFilterConfig (estaban en 0=desactivados; el código ya los aplicaba en run_auto_bets). Con los submercados reabiertos (§19), el freno diario y el tope por evento vuelven a operar.
**Monitor de calibración mejorado:** los submercados 🟡 (−10 a −20pp) ahora emiten WARNING visible en `logs/auto_betting.log` (antes solo los 🔴 ≤−20pp alertaban → los tiros sangraron −15-18pp días sin aviso). El cron sigue en 05:25 UTC.
**Gunicorn 1→3 workers** (`gunicorn_config.py`): seguro ahora con PostgreSQL (el lock de SQLite era la razón del worker único). Verificado 200 OK post-restart.
**Pendientes conocidos (priorizados):** (1) encriptar `AutoBetConfig.ticket` con Fernet (credenciales en texto plano DB+SOUL.md) · (2) binomial negativa en `poisson_over` (over-dispersión ±3-5pp) · (3) migrar 1X2 al motor (λ_home/λ_away → Skellam) con validación walk-forward · (4) BTTS desde el motor (medido calibrado 70.2 vs 72.6, requiere validación dedicada antes de tocar el modelo actual que rinde 58%) · (5) sincronizar `AutoBet.estado` con resultados en `sync_bet_history` (hoy queda OPEN) · (6) balance/cashout JWT (bloqueado por Cloudflare, requiere DevTools manual).

## 21. Motor único de predicción = WEB (/ai/predict/) — 2026-09-01
**Decisión de John (01-Sep):** la fuente oficial de verdad de predicciones es la web `https://predicta.com.co/ai/predict/`. Auto_betting y value_betting deben usar EL MISMO dato que la web. Solo se cambió el motor de predicción; todo lo demás (filtros, cobertura, calibración, cron, apuestas) quedó igual.

**Contexto (auditoría 01-Sep):** el fix del 31-Ago (§18) metió el motor `poisson_ratings` (ridge) SOLO en auto_betting (`POISSON_RATINGS_ENABLED=True` en strategy.py), dejando a la web con el pipeline legacy → datos distintos. Ej. Ghazl vs Enppi (01-Sep): auto_betting λ=2.83 → Over 2.5 (perdió, 0-0); web λ=2.11 → Under 2.5. Además auto_betting usaba solo xg_shots para tiros a puerta (web usa 2 modelos) y solo Enhanced para BTTS (web promedia 5).

**Cambios aplicados (commit en git):**
1. **Nuevo `ai_predictions/web_pipeline.py`** — `build_web_predictions()` replica EXACTO el pipeline de la web (views.py) por mercado + `get_official_prediction()`. Mercados: goals (Dixon+Avg+Ens+Híbrido), córners (corners_model 40/30/15/15), tiros a puerta (shots_prediction + xg_shots), BTTS (simples+Enhanced+Híbrido) → "Predicción Oficial" (promedio ponderado por confianza).
2. **`auto_betting/strategy.py::get_official_predictions`** — ahora llama `build_web_predictions` para los 4 mercados (mismo dato que la web). **Eliminado el override del ridge** (`POISSON_RATINGS_ENABLED` removido del flujo). Se mantienen: `validate_market_data` (gate de cobertura ≥10 partidos) y el cap de sanidad 1.6x de λ goles (red de seguridad).
3. **`value_betting/services.py::generate_full_prediction`** — λ_total = Predicción Oficial de goals_total de la web (antes: suma de ensambles home/away); BTTS = oficial web. Contrato de salida intacto.

**PostgreSQL verificado en runtime (no SQLite):** `settings.py` usa `django.db.backends.postgresql` (env DB_NAME/USER/HOST, password en `.env`); runtime confirma `vendor=postgresql` (PostgreSQL 15.19). El `db.sqlite3` de 352 MB en el directorio es un vestigio muerto (no se usa; candidato a archivar).

**Pruebas (01-Sep):**
- **Ghazl vs Enppi:** web = auto_betting = value_betting → goles λ=2.11, córners λ=8.54, tiros a puerta λ=5.3, BTTS p=0.42. ✔
- **`scripts/verify_motor_unico.py`:** 39 partidos (24 de las apuestas de hoy + 15 fixtures de mañana) → **0 desajustes reales** entre los 3 motores en todo mercado que ambos generan. Las omisiones del auto_betting son solo el gate de cobertura (esperado).
- **`scripts/dry_run_auto_bets.py` (flujo real mañana, sin apostar):** login OK, 126 partidos, embudo completo, 5 candidatos. Atlético-MG pasó de Under 7.5 tiros (ridge) a Over 9.5 @2.45 (web λ=10.70) ✔ consistente con la web.
- `manage.py check` sin errores · `predicta.service` reiniciado, 200 OK.

**Notas:**
- El motor `poisson_ratings` queda en el repo solo para análisis/backtests (scripts/poisson_bench.py, reopen_analysis.py, backtest_3_sistemas.py). No participa en producción.
- El cron de apuestas corre 06:10 UTC (01:10 Bogotá) por la reordenación del §16 (sync 05:00 → apuestas 06:10); no es 00:10 Bogotá por diseño.
- Pendiente heredado: la plantilla `prediction_result.html` etiqueta columnas "Over 1.5/2.5/3.5" pero renderiza `over_1/over_2/over_3` (etiquetado confuso, no afecta el dato del auto_betting).
