# Guía de Scraping — Flashscore.com

> **Objetivo:** Extraer datos estadísticos de partidos de fútbol desde Flashscore para alimentar predicta.com.co.
> **Fecha:** 2026-08-07
> **Partido de prueba:** Once Caldas vs América de Cali (Primera A - Colombia, Clausura 2026, Fecha 3)

---

## 1. Arquitectura del sitio

Flashscore es un **SPA (Single Page Application)** con renderizado 100% cliente-side. Los datos NO están en el HTML inicial. Se cargan dinámicamente vía JavaScript/XHR.

### Capas detectadas:
- **Cookie consent** → Diálogo "We Care About Your Privacy" (botón "Reject All")
- **Age verification** → Diálogo "Help us verify your age" (botón "I'm 18 and older")
- **Iframes de anuncios** → Varios iframes de casas de apuestas
- **Datos reales** → Se renderizan en el DOM después de ejecutar JS

### Conclusión clave:
**`web_fetch` NO funciona** — solo devuelve HTML vacío con placeholders. Se requiere **browser headless** (Playwright/Puppeteer) para ejecutar el JavaScript y esperar a que los datos se rendericen.

---

## 2. URLs relevantes

### Página de resultados de liga:
```
https://www.flashscore.com/football/colombia/primera-a/results/
```

### Página de detalle del partido (stats):
```
https://www.flashscore.com/match/football/{team1-slug}/{team2-slug}/summary/stats/?mid={matchId}
```

### Ejemplo real:
```
https://www.flashscore.com/match/football/america-de-cali-Oh9HQv4e/once-caldas-bVsnDlMD/summary/stats/?mid=IupCRcZI
```

### Tabs de estadísticas:
- `/summary/stats/overall/` — Stats del partido completo
- `/summary/stats/1st-half/` — Stats del 1er tiempo
- `/summary/stats/2nd-half/` — Stats del 2do tiempo

---

## 3. Método exitoso (Browser Headless)

### Herramienta usada:
OpenClaw browser tool → Chromium headless (CDP en `127.0.0.1:18800`)

### Pasos exactos:

1. **Navegar a la página de resultados** de la liga:
   ```
   https://www.flashscore.com/football/colombia/primera-a/results/
   ```

2. **Dismiss popups:**
   - Click en "Reject All" (cookie consent)
   - Click en "I'm 18 and older" (age gate)

3. **Snapshot del DOM** → Identificar los partidos. Cada partido aparece como un bloque con:
   - Fecha (e.g., "06.08.")
   - Equipo local (nombre + img)
   - Equipo visitante (nombre + img)
   - Resultado (goles local, goles visitante)
   - Link al detalle: `/match/football/{team1-slug}/{team2-slug}/?mid={matchId}`

4. **Navegar al detalle del partido** usando el `matchId` extraído

5. **Hacer snapshot** de la pestaña "Stats" para obtener todas las estadísticas

---

## 4. Datos extraíbles por partido

### Top Stats (resumen):
| Métrica | Ejemplo (ONC vs AME) |
|---|---|
| Expected goals (xG) | 0.58 vs 1.30 |
| Ball possession | 47% vs 53% |
| Total shots | 13 vs 17 |
| Shots on target | 5 vs 5 |
| Big chances | 0 vs 0 |
| **Corner kicks** | **3 vs 5** |

### Stats detalladas disponibles:
- **Shots:** xG, xGOT, total shots, on target, off target, blocked, inside box, outside box, woodwork, headed goals
- **Attack:** Big chances, corner kicks, touches in opp box, through passes, offsides, free kicks
- **Passes:** total, long passes %, final third %, crosses %, xA
- **Defense:** Fouls, tackles %, duels won, clearances, interceptions, errors
- **Goalkeeping:** Saves, xGOT faced, goals prevented, goal kicks
- **Discipline:** Yellow cards, red cards

### Timeline del partido:
Cada evento contiene: minuto, tipo (gol, tarjeta, sustitución, gol anulado), jugador(es) involucrado(s), asistencia si aplica.

---

## 5. Estructura del DOM (hallazgos del snapshot)

Los datos de stats se renderizan como **texto plano** dentro de elementos genéricos, intercalados con labels:

```
"0.58 Expected goals (xG) 1.30"
"47% Ball possession 53%"
"13 Total shots 17"
"3 Corner kicks 5"
```

### Patrón de parseo:
Cada línea de stats sigue el patrón:
```
{valor_local} {nombre_metrica} {valor_visitante}
```

Para métricas con porcentaje: `{valor}% {metrica} {valor}%`
Para métricas con fracción: `{porcentaje}% ({numerador}/{denominador}) {metrica} ...`

---

## 6. Obstáculos encontrados

| Problema | Solución |
|---|---|
| `web_fetch` devuelve HTML vacío (SPA) | Usar browser headless con JS |
| Cookie consent bloquea la página | Click en "Reject All" |
| Age gate bloquea la página | Click en "I'm 18 and older" |
| Popups condicionales (a veces no aparecen) | Verificar si existen antes de clickear |
| Anuncios de apuestas intercalados con stats | Filtrar al parsear |
| DOM genérico sin IDs ni data-attributes | Parsear patrones de texto "{valor} {label} {valor}" |
| Rate limiting | Usar delays entre requests |

---

## 7. Plan de scraping futuro

### Enfoque recomendado:

**Fase 1 — Browser headless (Playwright)**
- Usar el browser de OpenClaw o Playwright standalone
- Navegar a `/results/` de cada liga → extraer lista de `matchId`
- Por cada partido → navegar a `/summary/stats/?mid={matchId}` → extraer stats
- Guardar en DB (SQLite/Postgres)

**Fase 2 — Interceptar API calls (más eficiente)**
- Flashscore carga datos vía XHR/fetch internos
- Interceptar Network Requests con Playwright (`page.route()`)
- Capturar respuestas JSON directamente → parseo estructurado
- **Siguiente paso:** investigar cuál es el endpoint interno (probablemente algo como `https://www.flashscore.com/x/feed/...`)

**Fase 3 — Automatización periódica**
- Cron job que corra el scraper después de cada fecha de liga
- Detectar nuevos partidos vs. partidos ya scrapeados
- Solo scrapear stats de partidos finalizados (status = "Finished")

### Ligas objetivo iniciales:
- Primera A (Colombia) — Clausura y Apertura
- Premier League (Inglaterra)
- LaLiga (España)
- Serie A (Italia)
- Bundesliga (Alemania)
- Ligue 1 (Francia)
- Copa Libertadores
- Champions League

---

## 8. Código de referencia (Playwright)

```python
# Ejemplo conceptual para Playwright + Python
from playwright.sync_api import sync_playwright

def scrape_match_stats(match_id: str) -> dict:
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        
        # Stats URL
        url = f"https://www.flashscore.com/match/football/x/x/summary/stats/?mid={match_id}"
        page.goto(url)
        
        # Dismiss popups si aparecen
        try:
            page.click("button:has-text('Reject All')", timeout=3000)
        except:
            pass
        try:
            page.click("button:has-text('18 and older')", timeout=3000)
        except:
            pass
        
        # Esperar a que las stats se rendericen
        page.wait_for_selector("text=Corner kicks", timeout=10000)
        
        # Snapshot del DOM para parsear
        content = page.content()
        # ... parsear patrones
        
        browser.close()
        return stats
```

---

## 9. Notas adicionales

- Flashscore tiene **versión móvil** (`flashscore.mobi`) que podría ser más ligera para scrapear (menos JS, menos anuncios). Vale la pena probarla.
- Existen **APIs no oficiales** en GitHub (`flashscore-api`, `flashscore-scraper`) que pueden servir de referencia.
- La estructura de URLs usa **slugs** para equipos (ej: `once-caldas-bVsnDlMD`) donde la parte final es un ID único. El `matchId` (`IupCRcZI`) es lo único necesario para la URL de stats.
- **Rate limiting:** Flashscore puede bloquear IPs con muchas requests. Usar delays de 2-5 segundos entre partidos.
