# -*- coding: utf-8 -*-
"""Validador LLM para paperbet.

Cada pick candidato (ya filtrado por el gate duro: cuota >= 1.75, edge >= 6pp)
se envía a un LLM con acceso a búsqueda web. El LLM recibe TODOS los datos
(EV, edge, cuota, prob, mercado, selección, equipos, liga, fecha) y responde
SI/NO. Solo los picks aprobados se escriben en PaperBet.

Proveedor por defecto: Google Gemini (tier gratuito) con grounding en Google
Search. Configurable vía settings:
  LLM_PROVIDER  -> 'gemini' (único con búsqueda web nativa)
  LLM_API_KEY   -> clave de la API
  LLM_MODEL     -> ej. 'gemini-2.5-flash'
  LLM_TIMEOUT   -> segundos por petición

Fallos de red/API => FAIL-CLOSED (el pick se descarta), nunca se aprueba a ciegas.
"""
import json
import re
import time
import logging

import requests
from django.conf import settings

log = logging.getLogger('paperbet.llm')

GEMINI_ENDPOINT = 'https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent'

_SYSTEM = (
    "Eres un analista de apuestas deportivas de élite. Recibes una apuesta "
    "generada por un modelo estadístico y debes VALIDARLA usando búsqueda web. "
    "Busca información actual y relevante: alineaciones, lesiones, bajas, "
    "descanso entre partidos, motivación (torneo/tabla), contexto del partido, "
    "condiciones climáticas extremas. Luego decide si la apuesta mantiene valor. "
    "Responde ÚNICAMENTE con un objeto JSON válido, sin markdown ni texto extra, "
    'con esta forma exacta: {"approve": true|false, "reason": "..."}. '
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
    # quitar fences markdown si los hubiera
    m = re.search(r'\{.*\}', text, re.DOTALL)
    if m:
        text = m.group(0)
    try:
        return json.loads(text)
    except Exception:
        return None


def _gemini(bet):
    model = getattr(settings, 'LLM_MODEL', 'gemini-3.5-flash')
    key = getattr(settings, 'LLM_API_KEY', '') or ''
    timeout = int(getattr(settings, 'LLM_TIMEOUT', 30) or 30)
    if not key:
        return False, "LLM_API_KEY no configurada", {'error': 'no_key'}
    url = GEMINI_ENDPOINT.format(model=model)
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": _SYSTEM + "\n\n" + _build_prompt(bet)}]}
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
            approve = bool(parsed.get('approve'))
            reason = str(parsed.get('reason', ''))[:500]
            meta = {'provider': 'gemini', 'model': model,
                    'searches': len((ground.get('groundingChunks') or [])),
                    'web': bool(ground.get('webSearchQueries'))}
            return approve, reason, meta
        except requests.RequestException as e:
            log.warning("Gemini error (intento %d): %s", attempt, e)
            if attempt == 1:
                time.sleep(2)
    return False, "error de red/API", {'error': 'network'}


def validate_bet(bet):
    """Devuelve (approved: bool, reason: str, meta: dict)."""
    if not getattr(settings, 'LLM_ENABLED', True):
        return True, "LLM deshabilitado (LLM_ENABLED=false)", {'skipped': True}
    provider = (getattr(settings, 'LLM_PROVIDER', 'gemini') or 'gemini').lower()
    if provider == 'gemini':
        return _gemini(bet)
    return False, f"proveedor LLM no soportado: {provider}", {'error': 'provider'}
