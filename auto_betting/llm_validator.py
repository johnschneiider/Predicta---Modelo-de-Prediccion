# -*- coding: utf-8 -*-
"""Validador LLM para paperbet.

Cada pick candidato (ya filtrado por el gate duro: cuota >= 1.75, edge >= 6pp)
se envía a un LLM con acceso a búsqueda web. El LLM recibe TODOS los datos
(EV, edge, cuota, prob, mercado, selección, equipos, liga, fecha) y responde
SI/NO. Solo los picks aprobados se escriben en PaperBet.

Proveedores soportados (configurable vía settings):
  LLM_PROVIDER='openai' -> OpenAI Responses API + herramienta web_search
  LLM_PROVIDER='gemini' -> Google Gemini + grounding en Google Search
  LLM_API_KEY  -> clave de la API
  LLM_MODEL    -> 'gpt-4.1-mini' (openai) | 'gemini-3.5-flash' (gemini)
  LLM_TIMEOUT  -> segundos por petición

Fallos de red/API => FAIL-CLOSED (el pick se descarta), nunca se aprueba a ciegas.
"""
import json
import os
import re
import time
import logging
from pathlib import Path

import requests
from django.conf import settings
from django.utils import timezone

log = logging.getLogger('paperbet.llm')

GEMINI_ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'
OPENAI_ENDPOINT = 'https://api.openai.com/v1/responses'

# --------------------------------------------------------------------------- #
#  Configuración web de la IA de apuestas reales (LlmRealConfig + .env)        #
# --------------------------------------------------------------------------- #
ENV_PATH = Path(str(getattr(settings, 'BASE_DIR', '/var/www/predicta.com.co'))) / '.env'
DEFAULT_BASE_V1 = 'https://api.openai.com/v1'


def endpoint_efectivo(base_url: str = '') -> str:
    """Endpoint /responses a partir de la base configurada (o el default)."""
    base = (base_url or '').strip().rstrip('/')
    if not base:
        return OPENAI_ENDPOINT
    if base.endswith('/responses'):
        return base
    return base + '/responses'


def base_v1_efectiva(base_url: str = '') -> str:
    """Base /v1 para listar modelos a partir de la configuración."""
    base = (base_url or '').strip().rstrip('/')
    if not base:
        return DEFAULT_BASE_V1
    if base.endswith('/responses'):
        base = base[: -len('/responses')]
    return base


def api_key_real(path=None) -> str:
    """API key vigente: primero el .env (fresco), luego el entorno de settings."""
    try:
        p = Path(path) if path else ENV_PATH
        if p.exists():
            for linea in p.read_text(encoding='utf-8').splitlines():
                if linea.strip().startswith('LLM_API_KEY='):
                    valor = linea.split('=', 1)[1].strip().strip('"').strip("'")
                    if valor:
                        return valor
    except Exception:  # noqa: BLE001 — sin .env legible se usa settings
        pass
    return getattr(settings, 'LLM_API_KEY', '') or ''


def guardar_api_key(valor: str, path=None) -> None:
    """Actualiza LLM_API_KEY en el .env preservando el resto (atómico, 600)."""
    valor = (valor or '').strip()
    if not valor or '\n' in valor or '\r' in valor:
        raise ValueError('API key vacía o inválida')
    p = Path(path) if path else ENV_PATH
    lineas = p.read_text(encoding='utf-8').splitlines() if p.exists() else []
    nuevas, vista = [], False
    for l in lineas:
        if l.strip().startswith('LLM_API_KEY='):
            nuevas.append(f'LLM_API_KEY={valor}')
            vista = True
        else:
            nuevas.append(l)
    if not vista:
        nuevas.append(f'LLM_API_KEY={valor}')
    tmp = p.with_name(p.name + '.tmp')
    tmp.write_text('\n'.join(nuevas) + '\n', encoding='utf-8')
    os.chmod(tmp, 0o600)
    tmp.replace(p)


def listar_modelos(base_url: str = '', api_key=None, timeout: int = 10):
    """Lista de modelos del proveedor (GET {base}/models).

    Devuelve (modelos: list[str], error: str|None). El error se muestra tal
    cual en la página de umbrales.
    """
    key = api_key if api_key is not None else api_key_real()
    if not key:
        return [], 'API key no configurada'
    url = base_v1_efectiva(base_url) + '/models'
    try:
        r = requests.get(url, headers={'Authorization': f'Bearer {key}'},
                         timeout=timeout)
        if r.status_code >= 400:
            return [], f'HTTP {r.status_code}: {r.text[:200]}'
        data = r.json()
        modelos = sorted({str(m.get('id')) for m in (data.get('data') or [])
                          if m.get('id')})
        return modelos, None
    except Exception as e:  # noqa: BLE001 — el error se reporta a la página
        return [], f'error de conexión: {e}'


def llm_ventana_alcanzada(start_time) -> bool:
    """¿La apuesta ya entró en la ventana T-X de la consulta IA?

    Los colocadores la usan al colocar: si aún no se alcanzó el T-X (según la
    configuración web), la opinión se difiere al job `ask_llm_real --ventana`.
    Si la config no se puede leer, cae al comportamiento histórico (preguntar
    al colocar) para no romper ninguna colocación.
    """
    try:
        from auto_betting.models import LlmRealConfig
        cfg = LlmRealConfig.get_solo()
        if not cfg.enabled:
            return False
        if start_time is None:
            return True
        return ((start_time - timezone.now()).total_seconds()
                <= cfg.anticipacion_min * 60)
    except Exception as e:  # noqa: BLE001 — fail-open al comportamiento previo
        log.warning('llm_ventana_alcanzada fallo (%s); se pregunta al colocar', e)
        return True

_SYSTEM = (
    "Eres un analista de apuestas deportivas de élite. Recibes una apuesta "
    "generada por un modelo estadístico y debes VALIDARLA usando búsqueda web. "
    "Busca información actual y relevante: alineaciones, lesiones, bajas, "
    "descanso entre partidos, motivación (torneo/tabla), contexto del partido, "
    "condiciones climáticas extremas. Luego decide si la apuesta mantiene valor. "
    "Responde ÚNICAMENTE con un objeto JSON válido, sin markdown ni texto extra, "
    'con esta forma exacta: {"approve": true|false, "reason": "..."}.\n'
    "REGLA DE VALOR (estricta, no la inviertas): hay valor POSITIVO cuando la "
    "probabilidad del modelo es MAYOR que la probabilidad implícita de la cuota "
    "(prob > 1/cuota), porque eso implica EV > 0. Hay valor NEGATIVO sólo cuando "
    "la probabilidad del modelo es MENOR que la implícita. Nunca escribas "
    "'valor negativo' si la prob del modelo supera a la implícita, ni 'valor "
    "positivo' si queda por debajo. "
    '"approve": true SOLO si tras buscar confirmas que el edge/EV sigue siendo '
    "positivo y no existe una razón contundente en contra. "
    '"reason": justificación breve en español (máx. 2 frases).'
)


def _build_prompt(bet):
    prob = float(bet.get('prob') or 0)
    cuota = float(bet.get('cuota') or 0)
    implied = (1.0 / cuota) if cuota > 0 else 0.0
    edge = prob - implied
    ev = bet.get('ev')
    if ev is None:
        ev = prob * cuota - 1.0
    linea = bet.get('linea')
    linea_txt = f"{linea}" if linea is not None else "n/a"
    sel = bet.get('seleccion') or "n/a"
    return (
        "Datos de la apuesta candidata:\n"
        f"- Evento: {bet.get('home')} vs {bet.get('away')} ({bet.get('liga')})\n"
        f"- Fecha inicio: {bet.get('start_time')}\n"
        f"- Mercado: {bet.get('mercado')}\n"
        f"- Selección: {sel}\n"
        f"- Línea: {linea_txt}\n"
        f"- Cuota (decimal): {cuota:.3f}\n"
        f"- Probabilidad del modelo: {prob*100:.1f}%\n"
        f"- Probabilidad implícita de la cuota: {implied*100:.1f}%\n"
        f"- Edge (prob - implícita): {edge*100:+.2f} pp\n"
        f"- EV (expected value): {ev:+.4f}\n"
        f"- Motor: {bet.get('motor')}\n\n"
        "Busca en internet sobre este partido/mercado y responde SOLO el JSON."
    )


def _extract_json(text):
    if not text:
        return None
    text = text.strip()
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        text = m.group(0)
    try:
        return json.loads(text)
    except Exception:
        return None


def _coerce_approve(raw):
    """Normaliza el campo `approve` del JSON del LLM a bool, de forma estricta.

    `bool("false")` es True en Python: si el modelo devuelve el approve como
    texto, un rechazo se convertiría en aprobación. Sólo se aceptan los
    booleanos reales y los equivalentes textuales inequívocos; cualquier otra
    cosa es FAIL-CLOSED (False = rechazo), igual que un error de red.
    """
    if isinstance(raw, bool):
        return raw
    if isinstance(raw, str):
        return raw.strip().lower() in ('true', '1', 'yes', 'si', 'sí', 'approve')
    if isinstance(raw, (int, float)):
        return bool(raw)
    return False


def _supports_temperature(model):
    """Los modelos de razonamiento (gpt-5*, gpt-6*, o1/o3/o4) rechazan
    `temperature` con HTTP 400. Para el resto (p. ej. gpt-4o-mini) se mantiene 0."""
    m = (model or '').lower()
    return not (m.startswith('gpt-5') or m.startswith('gpt-6')
                or m.startswith('o1') or m.startswith('o3') or m.startswith('o4'))


def _openai(bet, system=None, prompt=None, model=None, endpoint=None,
            api_key=None):
    model = model or getattr(settings, 'LLM_MODEL', 'gpt-4.1-mini')
    key = api_key or getattr(settings, 'LLM_API_KEY', '') or ''
    timeout = int(getattr(settings, 'LLM_TIMEOUT', 30) or 30)
    if not key:
        return False, "LLM_API_KEY no configurada", {'error': 'no_key'}
    payload = {
        "model": model,
        "input": (system or _SYSTEM) + "\n\n" + (prompt or _build_prompt(bet)),
        "tools": [{"type": "web_search"}],
    }
    if _supports_temperature(model):
        payload["temperature"] = 0
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    for attempt in (1, 2):
        try:
            r = requests.post(endpoint or OPENAI_ENDPOINT, json=payload,
                              headers=headers, timeout=timeout)
            if r.status_code == 429:
                log.warning("OpenAI 429, espera y reintento %d", attempt)
                time.sleep(5 * attempt)
                continue
            if r.status_code >= 400:
                log.warning("OpenAI HTTP %s: %s", r.status_code, r.text[:300])
            r.raise_for_status()
            data = r.json()
            text = ""
            searches = 0
            for item in (data.get('output') or []):
                t = item.get('type')
                if t == 'message':
                    for c in (item.get('content') or []):
                        if c.get('type') == 'output_text':
                            text += c.get('text', '')
                elif t in ('web_search_call', 'web_search_preview_call'):
                    searches += 1
            parsed = _extract_json(text)
            if parsed is None:
                return False, "respuesta LLM no parseable", {'raw': text[:200]}
            approve = _coerce_approve(parsed.get('approve'))
            reason = str(parsed.get('reason', ''))[:500]
            # Telemetría de uso (2026-10-13): permite medir consumo real de
            # tokens/search por llamada sin cambiar el comportamiento.
            usage = data.get('usage') or {}
            det = usage.get('output_tokens_details') or {}
            log.info(
                "LLM usage openai model=%s searches=%d in=%s out=%s reasoning=%s total=%s",
                model, searches, usage.get('input_tokens'), usage.get('output_tokens'),
                det.get('reasoning_tokens'), usage.get('total_tokens'),
            )
            meta = {'provider': 'openai', 'model': model, 'searches': searches,
                    'usage': usage, 'parsed': parsed}
            return approve, reason, meta
        except requests.RequestException as e:
            log.warning("OpenAI error (intento %d): %s", attempt, e)
            if attempt == 1:
                time.sleep(2)
    return False, "error de red/API", {'error': 'network'}


def _gemini(bet, system=None, prompt=None):
    model = getattr(settings, 'LLM_MODEL', 'gemini-3.5-flash')
    key = getattr(settings, 'LLM_API_KEY', '') or ''
    timeout = int(getattr(settings, 'LLM_TIMEOUT', 30) or 30)
    if not key:
        return False, "LLM_API_KEY no configurada", {'error': 'no_key'}
    url = GEMINI_ENDPOINT.format(model=model)
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": (system or _SYSTEM) + "\n\n" + (prompt or _build_prompt(bet))}]}
        ],
        "tools": [{"google_search": {}}],
        "generationConfig": {"temperature": 0.0, "responseMimeType": "application/json"},
    }
    headers = {"x-goog-api-key": key, "Content-Type": "application/json"}
    for attempt in (1, 2):
        try:
            r = requests.post(url, json=payload, headers=headers, timeout=timeout)
            if r.status_code == 429:
                log.warning("Gemini 429, espera y reintento %d", attempt)
                time.sleep(5 * attempt)
                continue
            r.raise_for_status()
            data = r.json()
            cand = (data.get('candidates') or [{}])[0]
            parts = (cand.get('content') or {}).get('parts') or []
            text = "".join(p.get('text', '') for p in parts)
            ground = cand.get('groundingMetadata') or {}
            parsed = _extract_json(text)
            if parsed is None:
                return False, "respuesta LLM no parseable", {'raw': text[:200]}
            approve = _coerce_approve(parsed.get('approve'))
            reason = str(parsed.get('reason', ''))[:500]
            # Telemetría de uso (2026-10-13), mismo criterio que _openai.
            usage = data.get('usageMetadata') or {}
            searches = len((ground.get('groundingChunks') or []))
            log.info(
                "LLM usage gemini model=%s searches=%d in=%s out=%s total=%s",
                model, searches, usage.get('promptTokenCount'),
                usage.get('candidatesTokenCount'), usage.get('totalTokenCount'),
            )
            meta = {'provider': 'gemini', 'model': model,
                    'searches': searches,
                    'web': bool(ground.get('webSearchQueries')),
                    'usage': usage, 'parsed': parsed}
            return approve, reason, meta
        except requests.RequestException as e:
            log.warning("Gemini error (intento %d): %s", attempt, e)
            if attempt == 1:
                time.sleep(2)
    return False, "error de red/API", {'error': 'network'}


def validate_bet(bet, model=None, endpoint=None, api_key=None):
    """Validador genérico (fallback sin prompt por mercado).

    Devuelve (approved: bool, reason: str, meta: dict). `model` permite forzar
    el modelo (p. ej. LLM_MODEL_PAPER desde el pipeline de paper);
    `endpoint`/`api_key` permiten la configuración web de la IA real.
    """
    if not getattr(settings, 'LLM_ENABLED', True):
        return True, "LLM deshabilitado (LLM_ENABLED=false)", {'skipped': True}
    provider = (getattr(settings, 'LLM_PROVIDER', 'openai') or 'openai').lower()
    if provider == 'openai':
        return _openai(bet, model=model, endpoint=endpoint, api_key=api_key)
    if provider == 'gemini':
        return _gemini(bet)
    return False, f"proveedor LLM no soportado: {provider}", {'error': 'provider'}


# ─────────────────────────────────────────────────────────────────────────────
# SISTEMA DE PROMPTS POR MERCADO — PAPER TRADING (2026-10-07).
#
# Cada mercado del paper tiene su propio system prompt (checklist de búsqueda
# web + reglas de decisión + clave de estimación). El modelo es LLM_MODEL_PAPER
# (default "gpt-5.6-luna") para todos los mercados.
#
# Objetivo (John, 2026-10-07): registrar la OPINIÓN CRUDA de la IA (sí/no +
# confidence + razón) en PaperBet para medir si mejora los resultados. NO se
# aplican filtros/thresholds todavía: `corners_accept` queda disponible para
# cuando se decida pasar el gate a dinero real.
# Fail-closed: sin JSON válido no hay opinión (raw_approve=None).
# ─────────────────────────────────────────────────────────────────────────────

_SYS_COMMON = (
    "Eres un analista experto de apuestas deportivas. Recibes un pick de un modelo "
    "estadístico y debes emitir tu OPINIÓN (sí/no) con búsqueda web OBLIGATORIA. "
    "Tu trabajo NO es recalcular la probabilidad ni el edge: recíbelos como datos; "
    "tu tarea es confirmar o vetar la selección con evidencia externa que el modelo "
    "no ve.\n\n"
    "REGLAS:\n"
    "- Evalúa con TODA la información disponible aunque sea parcial: forma "
    "reciente, H2H, posición/motivación, calendario, noticias y alineaciones "
    "probables. NO exijas alineaciones confirmadas: si aún no se publican, "
    "decide con lo que haya y refleja la incertidumbre en \"confidence\".\n"
    "- Solo fuentes con fecha explícita; últimos 7 días para alineaciones/bajas. "
    "Si un dato no aparece, decláralo \"sin_dato\". PROHIBIDO inventar.\n"
    "- \"approve\": true si con lo disponible la selección mantiene sentido; "
    "false SOLO si encuentras evidencia concreta EN CONTRA (baja clave que rompe "
    "el mercado, contexto que invalida el pick). La ausencia de datos no es "
    "motivo de rechazo por sí sola: va en \"confidence\".\n"
    "- Responde ÚNICAMENTE un JSON válido, sin markdown ni texto extra, con este "
    "esquema exacto: {\"approve\": true|false, \"confidence\": 0-100, "
    "\"<ESTIM_KEY>\": <número>, \"lineups_confirmed\": true|false, "
    "\"key_absences\": [\"...\"], \"weather\": {\"temp_c\": 18, \"wind_kmh\": 12, "
    "\"rain\": \"no|light|heavy\"}, \"red_flags\": [{\"flag\": \"...\", "
    "\"severity\": \"high|medium|low\"}], \"reason\": \"máx 3 frases con evidencia "
    "y fechas\", \"sources\": [\"url\"]}."
)

_MARKET_SPECS = {
    'corners': {
        'nombre': 'CÓRNERS (tiros de esquina)',
        'estim_key': 'corners_estimados',
        'estim_desc': 'total de córners del partido (p. ej. 9.8)',
        'checklist': (
            "1) Alineaciones probables/confirmadas de AMBOS equipos (si el partido es "
            "en <3h, busca la confirmada; si no está publicada, dilo).\n"
            "2) Bajas de extremos, laterales ofensivos, lanzadores de córners y "
            "rematadores de cabeza.\n"
            "3) Clima en el estadio (viento km/h, lluvia, temperatura).\n"
            "4) Córners a favor/en contra de cada equipo (últimos 5-10 partidos) y "
            "estilo: centros, juego directo, balón parado, ritmo.\n"
            "5) Contexto: importancia, necesidad de ganar, derbi, fatiga, entrenador "
            "nuevo, estado del campo."
        ),
        'decision': (
            "- OVER: veta si ambos equipos son de bajo volumen/ritmo lento o falta el "
            "principal generador de córners; exige que volumen y tempo respalden la línea.\n"
            "- UNDER: veta si ambos generan alto volumen o hay contexto de partido "
            "abierto/necesidad mutua.\n"
            "- Viento >=30 km/h o lluvia fuerte: incertidumbre alta, sé más estricto."
        ),
    },
    'btts': {
        'nombre': 'AMBOS EQUIPOS MARCAN (BTTS)',
        'estim_key': 'prob_btts',
        'estim_desc': 'probabilidad 0-100 de que ambos equipos marquen',
        'checklist': (
            "1) Alineaciones confirmadas/probables, sobre todo delanteros titulares.\n"
            "2) Goles a favor/en contra de cada equipo (últimos 5-10) y racha de "
            "partidos con/sin gol de cada lado.\n"
            "3) Estilo ofensivo/defensivo, porteros, defensas frágiles o sólidas.\n"
            "4) Clima (lluvia fuerte/calor extremo) y estado del campo.\n"
            "5) Contexto y H2H reciente entre ambos."
        ),
        'decision': (
            "- BTTS SÍ: veta si un equipo es de bajo scoring o pierde a su goleador "
            "principal, o si su rival tiene defensa/portero en gran forma.\n"
            "- BTTS NO: veta si ambos anotan con regularidad o si ambos tienen defensas "
            "débiles y partido abierto esperado."
        ),
    },
    'goals': {
        'nombre': 'TOTAL DE GOLES',
        'estim_key': 'goles_estimados',
        'estim_desc': 'total de goles del partido (p. ej. 2.7)',
        'checklist': (
            "1) Goles a favor/en contra de cada equipo (últimos 5-10) y ritmo de juego.\n"
            "2) Alineaciones: presencia/ausencia de goleadores y creadores.\n"
            "3) Estilos (posesión vs contraataque), presión alta, defensas adelantadas.\n"
            "4) Clima y estado del campo (lluvia fuerte reduce ritmo; viento afecta).\n"
            "5) Contexto: necesidad de ganar, derbi, fatiga/descanso, H2H."
        ),
        'decision': (
            "- OVER: veta si ambos son de bajo scoring/ritmo lento o falta el generador "
            "principal de ocasiones.\n"
            "- UNDER: veta si hay contexto de partido abierto, necesidad mutua de ganar "
            "o ambos con defensas muy débiles."
        ),
    },
    'x12': {
        'nombre': 'RESULTADO FINAL (1X2)',
        'estim_key': 'prob_seleccion',
        'estim_desc': 'probabilidad 0-100 del resultado seleccionado (1, X o 2)',
        'checklist': (
            "1) Alineaciones confirmadas/probables y bajas importantes de ambos equipos.\n"
            "2) Forma reciente (últimos 5-10), rendimiento local/visitante y H2H.\n"
            "3) Motivación/contexto: necesidad de puntos, rotaciones, prioridad de "
            "competición, viaje/descanso.\n"
            "4) Estilos de juego y cómo se emparejan (presión vs bloque bajo).\n"
            "5) Clima y estado del campo si son extremos."
        ),
        'decision': (
            "- Veta si la evidencia contradice claramente el resultado seleccionado "
            "(p. ej. favorito con rotación masiva, visitante históricamente fuerte en "
            "esa cancha, contexto de empate que beneficia a ambos).\n"
            "- Confirma solo si alineación, forma y contexto respaldan la selección."
        ),
    },
    'sot': {
        'nombre': 'TIROS A PUERTA (SOT)',
        'estim_key': 'sot_estimados',
        'estim_desc': 'total de tiros a puerta del partido (p. ej. 8.6)',
        'checklist': (
            "1) Tiros a puerta a favor/en contra de cada equipo (últimos 5-10) y "
            "volumen de remate.\n"
            "2) Alineaciones: delanteros y mediapunas titulares; ausencias de "
            "rematadores.\n"
            "3) Estilo: remate exterior, centros, llegada de segunda línea.\n"
            "4) Porteros rivales (paradas) y defensas que conceden remates.\n"
            "5) Clima/contexto (partido abierto vs cerrado, necesidad de ganar)."
        ),
        'decision': (
            "- OVER: veta si ambos equipos son de bajo volumen de remate o falta su "
            "principal generador.\n"
            "- UNDER: veta si ambos rematan mucho a puerta o el partido se espera "
            "abierto con muchos ataques."
        ),
    },
    'doble_oportunidad': {
        'nombre': 'DOBLE OPORTUNIDAD (1X, X2 o 12)',
        'estim_key': 'prob_seleccion',
        'estim_desc': 'probabilidad 0-100 de la doble oportunidad seleccionada',
        'checklist': (
            "1) Alineaciones/bajas y forma reciente de ambos equipos.\n"
            "2) Fortaleza local/visitante y H2H.\n"
            "3) Contexto/motivación (un empate puede servir a uno o a ambos).\n"
            "4) Estilos: capacidad de un equipo de evitar la derrota (bloque bajo, "
            "portero en forma) o de no ganar (sequía goleadora).\n"
            "5) Riesgos: goleadas recientes en contra, cambios de entrenador."
        ),
        'decision': (
            "- Veta si la evidencia muestra que el/los resultados cubiertos son "
            "improbables (p. ej. visitante muy fuerte contra local en crisis para un 1X).\n"
            "- Confirma si la cobertura está respaldada por forma, contexto y H2H."
        ),
    },
    'remates': {
        'nombre': 'TOTAL DE TIROS (remates)',
        'estim_key': 'remates_estimados',
        'estim_desc': 'total de tiros (remates) del partido (p. ej. 27.5)',
        'checklist': (
            "1) Tiros totales a favor/en contra de cada equipo (últimos 5-10) y "
            "volumen de ataque.\n"
            "2) Alineaciones: delanteros/medios titulares y ausencias de "
            "rematadores habituales.\n"
            "3) Estilo: presión alta, remate exterior, centros, contraataque.\n"
            "4) Contexto: partido abierto/cerrado, necesidad de ganar, ritmo de liga.\n"
            "5) Clima/estado del campo (lluvia fuerte/calor extremo reducen ritmo)."
        ),
        'decision': (
            "- OVER: veta si ambos equipos son de bajo volumen de remate o falta su "
            "principal generador.\n"
            "- UNDER: veta si ambos rematan mucho o el partido se espera abierto con "
            "muchos ataques."
        ),
    },
    'nba_ml': {
        'nombre': 'GANADOR NBA (moneyline, prórroga incluida)',
        'estim_key': 'prob_seleccion',
        'estim_desc': 'probabilidad 0-100 de que el equipo seleccionado gane (incl. prórroga)',
        'checklist': (
            "1) Quintetos probables y bajas/lesiones de jugadores clave.\n"
            "2) Descanso: back-to-back, viaje, minutos de los titulares en el último "
            "partido.\n"
            "3) Ritmo (pace) y rating ofensivo/defensivo reciente de cada equipo.\n"
            "4) Localía y H2H de la temporada (si existe).\n"
            "5) Contexto: pretemporada vs temporada regular, rotaciones, motivación."
        ),
        'decision': (
            "- Veta si el equipo seleccionado llega con rotación masiva/back-to-back o "
            "el rival está claramente mejor perfilado para este emparejamiento.\n"
            "- Confirma solo si quinteto, descanso y ratings respaldan la selección."
        ),
    },
    'nba_spread': {
        'nombre': 'HÁNDICAP NBA (prórroga incluida)',
        'estim_key': 'prob_seleccion',
        'estim_desc': 'probabilidad 0-100 de que la selección cubra el hándicap',
        'checklist': (
            "1) Quintetos/bajas y descanso (back-to-back, viaje, minutos).\n"
            "2) Margen esperado: ratings ofensivo/defensivo y pace reciente.\n"
            "3) Localía y H2H; blowouts y garbage time reciente.\n"
            "4) Contexto: rotaciones, pretemporada vs temporada regular.\n"
            "5) Movimiento de línea si está disponible."
        ),
        'decision': (
            "- Veta si el margen es frágil (partido parejo, equipos de finales "
            "cerrados) o hay rotación que invalida el hándicap.\n"
            "- Confirma si el margen y el contexto respaldan la cobertura."
        ),
    },
    'nba_totals': {
        'nombre': 'TOTAL DE PUNTOS NBA (prórroga incluida)',
        'estim_key': 'puntos_estimados',
        'estim_desc': 'total de puntos del partido (p. ej. 224.5)',
        'checklist': (
            "1) Pace y eficiencia ofensiva/defensiva reciente de ambos equipos.\n"
            "2) Quintetos/bajas: ausencia de anotadores o de defensas clave.\n"
            "3) Descanso/back-to-back y viaje (afectan ritmo y puntería).\n"
            "4) H2H reciente (totales altos/bajos) y tendencia de la liga.\n"
            "5) Contexto: pretemporada (rotaciones largas), garbage time esperado."
        ),
        'decision': (
            "- OVER: veta si ambos son de bajo pace o faltan anotadores clave.\n"
            "- UNDER: veta si ambos juegan rápido y anotan eficientemente o hay "
            "contexto de partido suelto con ritmo alto."
        ),
    },
    'mlb': {
        'nombre': 'TOTAL DE CARRERAS MLB',
        'estim_key': 'carreras_estimadas',
        'estim_desc': 'total de carreras del partido (p. ej. 8.2)',
        'checklist': (
            "1) Abridores probables: ERA/FIP reciente, manos (zurdo/derecho), "
            "innings esperados.\n"
            "2) Bullpen: carga de los últimos 3 días y relevistas disponibles.\n"
            "3) Lineups probables: descansos, zurdos/derechos, forma reciente.\n"
            "4) Parque (park factor) y clima: viento (dirección/intensidad) y "
            "temperatura — crítico en carreras.\n"
            "5) Contexto: serie, viaje, umpire si hay reportes."
        ),
        'decision': (
            "- UNDER: veta si hay abridores débiles/bullpen agotado o clima de "
            "carreras (viento a favor, calor).\n"
            "- OVER: veta si hay abridores élite descansados y parque/clima de pocas "
            "carreras."
        ),
    },
}


def _system_for(key):
    spec = _MARKET_SPECS[key]
    return (
        _SYS_COMMON.replace('<ESTIM_KEY>', spec['estim_key'])
        + f"\n\nMERCADO: {spec['nombre']}\n"
        + f"ESTIMACIÓN OBLIGATORIA: {spec['estim_desc']} en \"{spec['estim_key']}\".\n\n"
        + "CHECKLIST DE INVESTIGACIÓN (búscalo en internet):\n" + spec['checklist'] + "\n\n"
        + "REGLAS DE DECISIÓN:\n" + spec['decision']
    )


def market_key(mercado, motor=None):
    """Mapea el mercado de paper (etiqueta BetPlay o motor) a la clave del
    registro de prompts. None si no hay prompt específico (usar genérico)."""
    m = str(mercado or '').lower()
    if 'esquina' in m:
        return 'corners'
    if 'ambos equipos' in m:
        return 'btts'
    if 'total de goles' in m:
        return 'goals'
    if 'resultado final' in m:
        return 'x12'
    if 'tiros a puerta' in m:
        return 'sot'
    if 'doble oportunidad' in m:
        return 'doble_oportunidad'
    if 'total de tiros' in m:
        return 'remates'
    if 'total de carreras' in m:
        return 'mlb'
    if 'total de puntos' in m:
        return 'nba_totals'
    if 'hándicap' in m or 'handicap' in m:
        return 'nba_spread'
    if 'ganador' in m:
        return 'nba_ml'
    return {
        'corners_v2': 'corners', 'btts_v2': 'btts', 'goles_v2': 'goals',
        'x12_v2': 'x12', 'sot_v2': 'sot',
    }.get(str(motor or '').lower())


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _build_prompt_market(bet, key):
    spec = _MARKET_SPECS[key]
    cuota = float(bet.get('cuota') or 0)
    prob = float(bet.get('prob') or 0)
    implied = (1.0 / cuota) if cuota > 0 else 0.0
    ev = bet.get('ev')
    if ev is None:
        ev = prob * cuota - 1.0

    def f(v, fmt='{:.2f}'):
        n = _num(v)
        return fmt.format(n) if n is not None else 'n/d'

    extra_lam = f" | λ={f(bet.get('lambda'))}" if bet.get('lambda') is not None else ""
    return (
        f"Pick de {spec['nombre']} a evaluar:\n"
        f"- Evento: {bet.get('home')} vs {bet.get('away')} ({bet.get('liga')})\n"
        f"- Inicio: {bet.get('start_time')}\n"
        f"- Selección: {bet.get('seleccion')} | Línea: {bet.get('linea')}\n"
        f"- Cuota decimal: {cuota:.3f} | Implícita: {implied*100:.1f}%\n"
        f"- Modelo Predicta: P={prob*100:.1f}% | edge={f(bet.get('edge_pp'))}pp | "
        f"EV={f(ev, '{:+.4f}')}{extra_lam}\n"
        f"- Motor: {bet.get('motor')}\n\n"
        f"Busca en internet el checklist y responde SOLO el JSON "
        f"(incluye \"{spec['estim_key']}\")."
    )


def corners_accept(parsed, edge_pp, hours_to_kickoff, line, side):
    """Thresholds de aceptación de córners sobre el JSON del LLM.

    Devuelve (ok: bool, motivo: str). Fail-closed: dato faltante que impida
    verificar un umbral ⇒ rechazo. (Para dinero real; en paper se guarda la
    opinión cruda y estos thresholds se aplican al analizar/decidir.)
    """
    if not isinstance(parsed, dict):
        return False, 'respuesta LLM no parseable'
    if not _coerce_approve(parsed.get('approve')):
        return False, f"IA no aprueba: {str(parsed.get('reason') or '')[:160]}"
    conf = _num(parsed.get('confidence'))
    if conf is None:
        return False, 'sin confidence'
    edge_pp = _num(edge_pp) or 0.0
    if edge_pp >= 5:
        min_conf = 60
    elif edge_pp >= 3:
        min_conf = 70
    else:
        return False, f'edge {edge_pp:.1f}pp < 3pp'
    if conf < min_conf:
        return False, f'confidence {conf:.0f} < {min_conf} (edge {edge_pp:+.1f}pp)'
    est = _num(parsed.get('corners_estimados'))
    line = _num(line)
    if est is None:
        return False, 'sin corners_estimados'
    if line is None:
        return False, 'sin línea'
    if side == 'over' and est < line + 0.3:
        return False, f'IA estima {est:.1f} < línea+0.3 ({line + 0.3:.1f})'
    if side == 'under' and est > line - 0.3:
        return False, f'IA estima {est:.1f} > línea-0.3 ({line - 0.3:.1f})'
    flags = parsed.get('red_flags') or []
    if not isinstance(flags, list):
        flags = []
    highs = [x for x in flags if isinstance(x, dict) and str(x.get('severity', '')).lower() == 'high']
    meds = [x for x in flags if isinstance(x, dict) and str(x.get('severity', '')).lower() == 'medium']
    if highs:
        return False, f"red flag alto: {highs[0].get('flag', '?')}"
    if len(meds) > 1:
        return False, f'{len(meds)} red flags medios'
    w = parsed.get('weather') or {}
    wind = _num(w.get('wind_kmh')) or 0.0
    rain = str(w.get('rain') or '').lower()
    if wind >= 30 or rain == 'heavy':
        need = 85 if side == 'over' else 75
        if conf < need:
            return False, f'clima adverso (viento {wind:.0f} km/h, lluvia {rain}) exige confidence {need}'
    lc = parsed.get('lineups_confirmed')
    if hours_to_kickoff is not None:
        h = _num(hours_to_kickoff)
        if h is not None:
            if h <= 3 and lc is not True:
                return False, 'sin alineaciones confirmadas (kickoff <=3h)'
            if h > 3 and lc is not True and not (edge_pp >= 7 and conf >= 85):
                return False, f'aplazar: sin alineaciones a {h:.1f}h (exige edge>=7pp y conf>=85)'
    return True, f"IA OK (conf {conf:.0f}, est {est:.1f}, edge {edge_pp:+.1f}pp)"


def validate_market(bet, model=None, endpoint=None, api_key=None):
    """Emite la OPINIÓN CRUDA de la IA para un pick de paper (sin filtros).

    Elige el system prompt del mercado (`market_key`) y llama al proveedor con
    LLM_MODEL_PAPER (default "gpt-5.6-luna"). Si el mercado no tiene prompt
    específico, cae al validador genérico `validate_bet`.

    Devuelve (raw_approve: bool|None, raw_reason: str, meta: dict).
    meta: raw_approve, raw_reason, llm_confidence, llm_model, parsed, market.
    NO aplica thresholds: la opinión se guarda tal cual en PaperBet.
    """
    meta0 = {'raw_approve': None, 'raw_reason': '', 'llm_confidence': None,
             'llm_model': '', 'parsed': None, 'market': None}
    if not getattr(settings, 'LLM_ENABLED', True):
        return None, "LLM deshabilitado (LLM_ENABLED=false)", {**meta0, 'skipped': True}
    key = market_key(bet.get('mercado'), bet.get('motor'))
    if key is None:
        a, r, m = validate_bet(bet, model=model or getattr(settings, 'LLM_MODEL_PAPER', None),
                               endpoint=endpoint, api_key=api_key)
        return a, r, {**meta0, **(m or {}), 'llm_model': (m or {}).get('model', ''),
                      'raw_approve': a, 'raw_reason': r}
    provider = (getattr(settings, 'LLM_PROVIDER', 'openai') or 'openai').lower()
    system = _system_for(key)
    prompt = _build_prompt_market(bet, key)
    model = model or getattr(settings, 'LLM_MODEL_PAPER', 'gpt-5.6-luna')
    if provider == 'openai':
        _a, _r, meta = _openai(bet, system=system, prompt=prompt, model=model,
                               endpoint=endpoint, api_key=api_key)
    elif provider == 'gemini':
        _a, _r, meta = _gemini(bet, system=system, prompt=prompt)
    else:
        return None, f"proveedor LLM no soportado: {provider}", {**meta0, 'error': 'provider'}
    parsed = (meta or {}).get('parsed')
    raw_approve = _coerce_approve(parsed.get('approve')) if isinstance(parsed, dict) else None
    raw_reason = (str(parsed.get('reason') or '') if isinstance(parsed, dict)
                  else (_r or 'respuesta LLM no parseable'))
    conf = _num(parsed.get('confidence')) if isinstance(parsed, dict) else None
    return raw_approve, raw_reason, {
        **(meta or {}), **meta0,
        'raw_approve': raw_approve,
        'raw_reason': raw_reason[:500],
        'llm_confidence': int(conf) if conf is not None else None,
        'llm_model': (meta or {}).get('model', model),
        'market': key,
    }


def opinar_apuesta(autobet, bet):
    """Opinión IA para una apuesta REAL ya colocada (informativa, no operativa).

    La config web (`LlmRealConfig`, página de umbrales) manda: switch ON/OFF,
    modelo y endpoint; la API key sale del `.env` (fresca) con fallback al
    entorno. Best-effort: NUNCA lanza ni bloquea la corrida. Si el LLM falla,
    deja la fila con llm_verdict=None y el motivo del fallo en llm_reason.
    Guarda: llm_verdict, llm_confidence, llm_reason, llm_model, llm_asked_at.

    Devuelve (approved: bool|None, reason: str).
    """
    try:
        if not getattr(settings, 'LLM_REAL_ENABLED', True):
            return None, 'LLM real deshabilitado'
        from auto_betting.models import LlmRealConfig
        cfg = LlmRealConfig.get_solo()
        if not cfg.enabled:
            return None, 'IA real desactivada (página de umbrales)'
        model = cfg.modelo or getattr(settings, 'LLM_MODEL_REAL', 'gpt-5.6-luna')
        approved, reason, meta = validate_market(
            bet, model=model, endpoint=endpoint_efectivo(cfg.base_url),
            api_key=api_key_real())
        autobet.llm_verdict = approved
        autobet.llm_confidence = (meta or {}).get('llm_confidence')
        autobet.llm_reason = (reason or '')[:500]
        autobet.llm_model = (meta or {}).get('llm_model', model) or model
        autobet.llm_asked_at = timezone.now()
        autobet.save(update_fields=['llm_verdict', 'llm_confidence', 'llm_reason',
                                    'llm_model', 'llm_asked_at'])
        return approved, reason
    except Exception as e:
        log.warning("opinar_apuesta fallo (coupon=%s): %s",
                    getattr(autobet, 'coupon_ref', None), e)
        return None, f'error IA: {e}'
