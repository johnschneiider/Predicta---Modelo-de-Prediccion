# -*- coding: utf-8 -*-
"""
Emparejamiento Kambi (apuesta) <-> API-Football (liquidación).

PROBLEMA QUE RESUELVE
---------------------
El sistema apuesta con partidos y cuotas de Kambi (BetPlay), pero liquida con
API-Football. Ambas fuentes ven el mismo fútbol con nombres y estructura distinta,
y este módulo es el único punto donde se decide "este partido de Kambi es este
partido de la API".

Dos fallos reales detectados (2026-09-25):

1. PARTIDOS FANTASMA. Se apostaba en eventos que no existen en API-Football:
   - Ligas de categorías bajas que Kambi ofrece y la API no cubre
     (Isthmian League Division One, Gaúcho 2...).
   - Eventos mal listados o con el rival equivocado (Danubio vs Liverpool
     Montevideo el 24-sep: ese día Danubio jugó contra Peñarol).
   Resultado: la apuesta entra, no se puede liquidar nunca y queda colgada.

2. FASES DE LIGA (Apertura/Clausura). Las ligas latinoamericanas cambian de fase
   dentro de la misma temporada. El mapeo guardaba una sola fase
   (Paraguay -> "Division Profesional - Apertura", id 250), pero los partidos se
   juegan en la otra (id 252, "Clausura"). Filtrar por id de liga descartaba
   partidos REALES, y la liquidación tampoco los habría encontrado jamás.

REGLA
-----
- Fase principal: mismo id de liga en la API (el caso normal, millones de partidos).
- Fase hermana: se acepta si AMBOS equipos coinciden con fuerza y la liga es la
  misma salvando el sufijo de fase ("X - Apertura" == "X - Clausura" == "X").
- Si no hay coincidencia, NO hay apuesta: mejor perder una apuesta que dejar una
  que jamás se podrá liquidar.
"""

import difflib
import unicodedata

# Mismo umbral que usa la liquidación: 0.7 por equipo.
UMBRAL_FASE_EXACTA = 1.4
# Fase hermana: ambos equipos deben coincidir con fuerza (0.75 cada uno).
UMBRAL_EQUIPO_FASE_HERMANA = 0.75


def norm(s):
    """Normaliza para comparar: sin acentos, sin puntuación, en minúsculas."""
    s = unicodedata.normalize('NFKD', s or '')
    return ''.join(x for x in s.lower() if x.isalnum())


def base_liga(name):
    """Quita el sufijo de fase: 'Division Profesional - Clausura' -> 'divisionprofesional'."""
    return norm((name or '').split(' - ')[0])


def _score(fixture, nh, na):
    s1 = difflib.SequenceMatcher(None, nh, norm(fixture['teams']['home']['name'])).ratio()
    s2 = difflib.SequenceMatcher(None, na, norm(fixture['teams']['away']['name'])).ratio()
    return s1, s2, s1 + s2


def match_fixture(fixtures, api_league_id, api_league_name, home, away):
    """
    Busca en `fixtures` el partido (home, away) de API-Football.

    Devuelve (fixture | None, motivo). Nunca lanza: ante datos raros, devuelve
    None con el motivo, que es el comportamiento seguro (no apostar).
    """
    if not fixtures:
        return None, 'la API no devolvió partidos para esa fecha'

    nh, na = norm(home), norm(away)

    # --- 1) Fase exacta: mismo id de liga -----------------------------------
    best = None
    best_s = 0.0
    for f in fixtures:
        if api_league_id and f['league']['id'] != api_league_id:
            continue
        _, _, sc = _score(f, nh, na)
        if sc > best_s:
            best_s, best = sc, f

    if best is not None and best_s >= UMBRAL_FASE_EXACTA:
        return best, 'ok (fase exacta)'

    # --- 2) Fase hermana: misma liga salvando el sufijo de fase -------------
    # Solo si la liga mapeada tiene un nombre base identificable.
    if api_league_name:
        base = base_liga(api_league_name)
        best2 = None
        best2_s = 0.0
        for f in fixtures:
            if base_liga(f['league']['name']) != base:
                continue
            s1, s2, sc = _score(f, nh, na)
            # Ambos equipos deben coincidir con fuerza: es lo que impide
            # confundir el partido correcto con un rival parecido.
            if s1 < UMBRAL_EQUIPO_FASE_HERMANA or s2 < UMBRAL_EQUIPO_FASE_HERMANA:
                continue
            if sc > best2_s:
                best2_s, best2 = sc, f
        if best2 is not None:
            return best2, f'ok (fase hermana: {best2["league"]["name"]})'

    if best is None:
        return None, 'no existe en API-Football (liga sin partidos ese día)'
    return None, f'no existe en API-Football (mejor coincidencia {best_s:.2f})'
