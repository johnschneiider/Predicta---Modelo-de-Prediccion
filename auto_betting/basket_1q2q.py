# -*- coding: utf-8 -*-
"""
basket_1q2q.py — Motor de totales de baloncesto (1Q+2Q) para el PAPERBET.

Portado de la app de escritorio "App de Baloncesto"
(github.com/kellyr259103-cmyk/App-de-Baloncesto) a la infraestructura de
Predicta. Solo papel (sin dinero real).

Lógica portada:
  * Modelo MCO por liga:  TOTAL = b0 + b1·1Q + b2·2Q
    (entrenado con partidos reales acabados de API-Sports; RMSE con holdout
    del 20 % más reciente).
  * Probabilidad del lado elegido: Φ(Δ / (k · RMSE_test)), Δ = predicción − línea.
   * Apuesta SOLO en el descanso 2Q→3Q (1Q y 2Q finales, 3Q sin empezar), con
     cuota viva del feed Kambi/BetPlay, |Δ| dentro de
     [DELTA_MINIMO, DELTA_MAXIMO] (original del repo: [3, 5]; desde 2026-10-12
     en modo muestreo temporal: [0, 500]) y SIN filtro de EV (EV_MINIMA=0,
     2026-10-13: pasan todos los partidos en ventana; el EV se calcula y
     guarda solo para trazabilidad).
  * Liquidación con el total final (prórroga incluida): el lado elegido gana
    si el total queda de su lado de la línea; empate exacto = anulada (push).

Este módulo es puro (sin Django): los comandos de management hacen la
persistencia (BasketSample / BasketModel / PaperBet).
"""

from __future__ import annotations

import math
import os
import re
import time
import unicodedata
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Callable, Iterable, Optional

import requests

# --------------------------------------------------------------------------- #
#  Constantes de la estrategia (portadas del repo)                             #
# --------------------------------------------------------------------------- #
MOTOR = 'basket_1q2q'
MOTOR_GATED = 'basket_1q2q_gated'
MERCADO = 'Total de puntos (1Q+2Q)'
SEL_OVER = 'Más de'
SEL_UNDER = 'Menos de'

DELTA_MINIMO = 0.0          # Δ mínimo (pts) para apostar en el descanso (temporal: muestreo)
DELTA_MAXIMO = 500.0        # tope superior del rango (0 = sin tope) (temporal: muestreo)
EV_MINIMA = 0.0             # EV mínimo exigido; 0 = SIN filtro de EV (modo
                            # muestreo: se registra el EV, no se descarta nada)
GATE_DELTA_MIN = 3.0
GATE_DELTA_MAX = 5.0
GATE_EV_MIN = 0.02
FACTOR_RMSE = 1.1           # enfriamiento de Φ (calibracion.factor_rmse)
STAKE_DEFECTO = 10000       # COP virtuales (igual que el resto del paperbet)

MINIMO_MUESTRAS = 30        # mínimo para publicar modelo propio de una liga
MINIMO_POOL = 8             # con menos que esto ni mezcla con el global
FRACCION_TEST = 0.2         # 20 % más reciente = validación (holdout)
MINIMO_GLOBAL = 200         # muestras totales mínimas para el modelo global
CLAVE_GLOBAL = '__global__'  # clave reservada del modelo de respaldo (todas las
                             # ligas): garantiza apuesta en ventana aunque la
                             # liga no tenga modelo propio ni muestras aún.
STALE_VOID_HORAS = 40       # sin resultado tras N h → VOID (igual que fútbol)

VEREDICTOS = ('OVER', 'UNDER')

# Depuración 2026-10-24: OVER acumuló ROI -20,1% (n=625, z=-5,5).
# Se sigue registrando solo UNDER; OVER queda desactivado hasta nueva evidencia.
LADOS_PAPER_ACTIVOS = frozenset({'UNDER'})  # valores de `evaluar()['lado']`

# clave de BetPlay -> id(s) de liga en API-Sports (verificados 10-10-2026
# por el autor del repo; se portan tal cual).
LIGAS_API_SPORTS: dict[str, tuple[int, ...]] = {
    "euroleague": (120,),
    "nba": (12,),
    "nba_preseason": (12,),
    "nba_cup": (422,),
    "wnba": (13,),
    "aba_league": (198,),
    "bnxt_league": (368,),
    "club_friendly_matches": (205,),
    "latvian-estonian_league": (204,),
    "argentina/lnb": (18,),
    "austria/obl": (217,),
    "austria/obl__w_": (218,),
    "australia/nbl": (1,),
    "belgium/top_division_1": (374,),
    "belgium/top_division__w_": (25,),
    "bulgaria/nbl": (113,),
    "chile/liga_nacional": (114,),
    "china/cba_preseason": (31,),
    "cyprus/division_a": (115,),
    "czech_republic/nbl": (32,),
    "czech_republic/1__liga": (228,),
    "france/elite": (2,),
    "france/lfb__w_": (10,),
    "greece/a1__w_": (234,),
    "germany/bbl": (40,),
    "germany/dbbl__w_": (41,),
    "germany/pro_a": (42,),
    "greece/gbl": (45,),
    "hungary/nb_i_a": (46,),
    "hungary/nb_i__w_": (47,),
    "italy/a2__w_": (243, 244,),
    "italy/lega_a": (52,),
    "italy/a1__w_": (53,),
    "italy/serie_a2": (242,),
    "israel/super_league": (51,),
    "japan/b1__league": (56,),
    "japan/b2_league": (407,),
    "lithuania/lkl": (60,),
    "lithuania/lmkl__w_": (62,),
    "mexico/lnbp": (63,),
    "new_zealand/tauihi_basketball_aotearoa__w_": (375,),
    "norway/blno": (68,),
    "philippines/pba": (151, 152, 153,),
    "poland/1_liga": (71,),
    "poland/plk": (72,),
    "portugal/campeonato_nacional_2": (261,),
    "portugal/lpb": (74,),
    "portugal/lfb__w_": (260,),
    "portugal/taca_de_portugal": (75,),
    "portugal/taca_de_portugal__w_": (400,),
    "south_korea/kbl": (91,),
    "spain/leb_oro": (95,),
    "spain/leb_plata": (96,),
    "spain/liga_acb": (117,),
    "spain/liga_femenina__w_": (94,),
    "sweden/basketligan__w_": (97,),
    "sweden/superettan": (99,),
    "switzerland/sb_league__w_": (101,),
    "turkey/super_league": (104,),
    "turkey/tbl": (102,),
    "united_kingdom/super_league_basketball": (108,),
    "united_kingdom/women_super_league_basketball__w_": (109,),
}

# Claves del feed que NO son ligas (mercados de series); se ignoran.
NO_SON_LIGAS = ("wnba_series_markets",)


class ErrorBasket(Exception):
    """No se pudo consultar/parsear una fuente de datos."""


# --------------------------------------------------------------------------- #
#  Kambi / BetPlay                                                             #
# --------------------------------------------------------------------------- #
KAMBI_BASE = "https://us.offering-api.kambicdn.com/offering/v2018/betplay"
KAMBI_PARAMS = ("channel_id=1&client_id=200&lang=es_CO&market=CO"
                "&useCombined=true&useCombinedLive=true")
KAMBI_HEADERS = {
    "Accept": "application/json",
    "Origin": "https://betplay.com.co",
    "Referer": "https://betplay.com.co/",
}
ID_TOTAL = 6                # betOfferType.id del mercado Más/Menos
ESTADOS_NO_FINAL = ("NOT_STARTED", "STARTED")

_RE_CUARTO = re.compile(r"Q([1-4]|OT)\s*:\s*(\d+)\s*-\s*(\d+)", re.IGNORECASE)


def parsear_cuartos(info: str) -> dict[str, int]:
    """'Q1: 20-29 | Q2: 19-24' -> {'Q1': 49, 'Q2': 43} (suma de ambos equipos)."""
    salida: dict[str, int] = {}
    if not info:
        return salida
    for clave, local, visitante in _RE_CUARTO.findall(info):
        clave = "QOT" if clave.upper() == "OT" else f"Q{clave}"
        salida[clave] = int(local) + int(visitante)
    return salida


def _num(valor, divisor=1000.0) -> Optional[float]:
    if valor is None:
        return None
    try:
        return float(valor) / divisor
    except (TypeError, ValueError):
        return None


def _liga_del_evento(ev: dict) -> tuple[str, str, str]:
    """event.path = [deporte, región?, liga] -> (nombre, region_tk, liga_tk)."""
    ruta = ev.get("path") or []
    nodos = [n for n in ruta if isinstance(n, dict)]
    region_tk = nodos[1].get("termKey", "") if len(nodos) > 2 else ""
    liga_tk = nodos[-1].get("termKey", "") if len(nodos) >= 2 else ""
    nombre = " / ".join(n.get("name", "") for n in nodos[1:] if n.get("name"))
    if not nombre:
        nombre = ev.get("group", "") or ""
    return nombre, region_tk, liga_tk


def _es_total_partido(criterio: str) -> bool:
    """¿Es el mercado de totales del PARTIDO COMPLETO (con prórroga)?"""
    c = (criterio or "").lower()
    if c.startswith("total de puntos de ") or c.startswith("total points of "):
        return False                                   # total de un solo equipo
    if not ("prórroga incluida" in c or "incluyendo prórroga" in c
            or "including overtime" in c):
        return False
    return not any(k in c for k in
                   ("parte", "cuarto", "periodo", "quarter", "half", "period"))


@dataclass
class PartidoLive:
    """Un partido del feed Kambi con cuartos, reloj y mercado de total."""
    evento_id: int
    nombre: str
    local: str
    visitante: str
    state: str
    inicio: str
    liga_nombre: str = ""
    liga_tk: str = ""
    region_tk: str = ""
    period_id: str = ""
    corriendo: Optional[bool] = None
    reloj_min: int = 0
    izq_min: Optional[int] = None
    izq_seg: Optional[int] = None
    info_cuartos: str = ""
    marcador_local: Optional[int] = None
    marcador_visitante: Optional[int] = None
    q1: Optional[int] = None
    q2: Optional[int] = None
    q3: Optional[int] = None
    q4: Optional[int] = None
    linea: Optional[float] = None
    cuota_over: Optional[float] = None
    cuota_under: Optional[float] = None
    mercado_abierto: bool = False
    cuota_over_abierta: bool = False
    cuota_under_abierta: bool = False
    betoffer_id: Optional[int] = None
    criterion: dict = field(default_factory=dict)
    betoffer_tags: list = field(default_factory=list)
    event_path: list = field(default_factory=list)
    outcome_over_id: Optional[int] = None
    outcome_under_id: Optional[int] = None
    outcome_over_odds: Optional[int] = None
    outcome_under_odds: Optional[int] = None
    outcome_over_label: str = ""
    outcome_under_label: str = ""
    outcome_over_status: str = ""
    outcome_under_status: str = ""
    outcome_over_display_order: int = 0
    outcome_under_display_order: int = 0
    outcome_over_cashout: str = ""
    outcome_under_cashout: str = ""

    @property
    def clave_liga(self) -> str:
        """Clave con la que se guarda el modelo (p. ej. 'spain/liga_acb')."""
        return f"{self.region_tk}/{self.liga_tk}" if self.region_tk else (self.liga_tk or "")

    @property
    def q2_completo(self) -> bool:
        """¿El 2º cuarto ya terminó (q2 es final)?"""
        if self.q2 is None:
            return False
        if self.state == "NOT_STARTED":
            return False
        if self.period_id != "QUARTER2":
            return True
        return (self.corriendo is False
                and (self.izq_min or 0) == 0 and (self.izq_seg or 0) == 0)

    @property
    def finalizado(self) -> bool:
        """¿El partido ya terminó? (mismas reglas del feed que el repo)."""
        if self.state not in ESTADOS_NO_FINAL:
            return True
        if "Q4" not in self.info_cuartos:
            return False
        if (self.izq_min or 0) != 0 or (self.izq_seg or 0) != 0:
            return False
        if self.reloj_min < 40:
            return False
        empate = (self.marcador_local is not None
                  and self.marcador_local == self.marcador_visitante)
        return not empate

    @property
    def total_final(self) -> Optional[int]:
        if self.marcador_local is None or self.marcador_visitante is None:
            return None
        if self.finalizado:
            return self.marcador_local + self.marcador_visitante
        return None

    @property
    def hay_cuota_over(self) -> bool:
        return (self.mercado_abierto and self.cuota_over_abierta
                and self.cuota_over is not None)

    @property
    def hay_cuota_under(self) -> bool:
        return (self.mercado_abierto and self.cuota_under_abierta
                and self.cuota_under is not None)


_YA_EN_3P_O_DESPUES = ("QUARTER3", "QUARTER4", "PERIOD3", "PERIOD4",
                       "OVERTIME", "OT")


def en_ventana_descanso(p: Optional[PartidoLive]) -> bool:
    """¿El partido está en el hueco entre el fin del 2Q y el arranque del 3Q?

    Tolera la variante de feed que etiqueta el descanso como QUARTER3 con el
    marcador del 3Q publicado a 0-0 y el reloj del cuarto lleno y parado
    (visto 2026-10-12 en ligas sudamericanas/nórdicas).
    """
    if p is None or p.finalizado:
        return False
    if not p.q2_completo:
        return False
    periodo = (p.period_id or "").upper()
    if periodo in _YA_EN_3P_O_DESPUES:
        return (periodo == "QUARTER3" and p.q3 == 0
                and p.corriendo is False
                and (p.izq_min or 0) >= 10 and (p.izq_seg or 0) == 0)
    return p.q3 is None or p.q3 == 0


def parsear_evento(bloque: dict) -> PartidoLive:
    """bloque = {'event': .., 'liveData': .., 'betOffers': ..} -> PartidoLive."""
    ev = bloque.get("event", {})
    ld = bloque.get("liveData") or {}
    ck = ld.get("matchClock") or {}
    sc = ld.get("score") or {}

    nombre_liga, region_tk, liga_tk = _liga_del_evento(ev)

    p = PartidoLive(
        evento_id=int(ev.get("id", 0)),
        nombre=ev.get("name", ""),
        local=ev.get("homeName", ""),
        visitante=ev.get("awayName", ""),
        state=ev.get("state", ""),
        inicio=ev.get("start", ""),
        liga_nombre=nombre_liga,
        liga_tk=liga_tk,
        region_tk=region_tk,
        period_id=ck.get("periodId", "") or "",
        corriendo=ck.get("running"),
        reloj_min=int(ck.get("minute", 0) or 0),
        izq_min=ck.get("minutesLeftInPeriod"),
        izq_seg=ck.get("secondsLeftInMinute"),
        info_cuartos=sc.get("info", "") or "",
        event_path=ev.get("path") or [],
    )

    if sc.get("home") not in (None, ""):
        try:
            p.marcador_local = int(sc["home"])
            p.marcador_visitante = int(sc["away"])
        except (TypeError, ValueError, KeyError):
            pass

    cuartos = parsear_cuartos(p.info_cuartos)
    p.q1 = cuartos.get("Q1")
    p.q2 = cuartos.get("Q2")
    p.q3 = cuartos.get("Q3")
    p.q4 = cuartos.get("Q4")

    candidatos_total: list[dict] = []
    for oferta in bloque.get("betOffers", []) or []:
        tipo = (oferta.get("betOfferType") or {}).get("id")
        if tipo != ID_TOTAL:
            continue
        criterio = (oferta.get("criterion") or {}).get("label", "")
        if not _es_total_partido(criterio):
            continue
        suspendida = bool(oferta.get("suspended"))
        linea = None
        over = under = None
        over_abierto = under_abierto = False
        datos = {
            'abierto': False,
            'linea': None,
            'cuota_over': None,
            'cuota_under': None,
            'over_abierto': False,
            'under_abierto': False,
            'betoffer_id': oferta.get("id"),
            'criterion': oferta.get("criterion") or {},
            'betoffer_tags': oferta.get("tags") or [],
            'outcome_over_id': None,
            'outcome_under_id': None,
            'outcome_over_odds': None,
            'outcome_under_odds': None,
            'outcome_over_label': "",
            'outcome_under_label': "",
            'outcome_over_status': "",
            'outcome_under_status': "",
            'outcome_over_display_order': 0,
            'outcome_under_display_order': 0,
            'outcome_over_cashout': "",
            'outcome_under_cashout': "",
        }
        for oc in oferta.get("outcomes", []) or []:
            abierto_oc = oc.get("status") == "OPEN" and not suspendida
            if oc.get("type") == "OT_OVER":
                linea = _num(oc.get("line")) or linea
                over = _num(oc.get("odds"))
                over_abierto = abierto_oc
                datos.update({
                    'outcome_over_id': oc.get("id"),
                    'outcome_over_odds': oc.get("odds"),
                    'outcome_over_label': oc.get("label", "") or "",
                    'outcome_over_status': oc.get("status", "") or "",
                    'outcome_over_display_order': oc.get("displayOrder", 0) or 0,
                    'outcome_over_cashout': oc.get("cashOutStatus", "") or "",
                })
            elif oc.get("type") == "OT_UNDER":
                linea = _num(oc.get("line")) or linea
                under = _num(oc.get("odds"))
                under_abierto = abierto_oc
                datos.update({
                    'outcome_under_id': oc.get("id"),
                    'outcome_under_odds': oc.get("odds"),
                    'outcome_under_label': oc.get("label", "") or "",
                    'outcome_under_status': oc.get("status", "") or "",
                    'outcome_under_display_order': oc.get("displayOrder", 0) or 0,
                    'outcome_under_cashout': oc.get("cashOutStatus", "") or "",
                })
        datos.update({
            'abierto': not suspendida and (over_abierto or under_abierto),
            'linea': linea,
            'cuota_over': over,
            'cuota_under': under,
            'over_abierto': over_abierto,
            'under_abierto': under_abierto,
        })
        if linea is not None:
            candidatos_total.append(datos)

    if candidatos_total:
        abiertos = [c for c in candidatos_total if c['abierto']]
        elegido = (abiertos or candidatos_total)[0]
        p.linea = elegido['linea']
        p.cuota_over = elegido['cuota_over']
        p.cuota_under = elegido['cuota_under']
        p.betoffer_id = elegido['betoffer_id']
        p.criterion = elegido['criterion']
        p.betoffer_tags = elegido['betoffer_tags']
        p.outcome_over_id = elegido['outcome_over_id']
        p.outcome_under_id = elegido['outcome_under_id']
        p.outcome_over_odds = elegido['outcome_over_odds']
        p.outcome_under_odds = elegido['outcome_under_odds']
        p.outcome_over_label = elegido['outcome_over_label']
        p.outcome_under_label = elegido['outcome_under_label']
        p.outcome_over_status = elegido['outcome_over_status']
        p.outcome_under_status = elegido['outcome_under_status']
        p.outcome_over_display_order = elegido['outcome_over_display_order']
        p.outcome_under_display_order = elegido['outcome_under_display_order']
        p.outcome_over_cashout = elegido['outcome_over_cashout']
        p.outcome_under_cashout = elegido['outcome_under_cashout']
        p.mercado_abierto = bool(abiertos)
        p.cuota_over_abierta = (p.mercado_abierto and elegido['over_abierto']
                                and p.cuota_over is not None)
        p.cuota_under_abierta = (p.mercado_abierto and elegido['under_abierto']
                                 and p.cuota_under is not None)
    return p


def fetch_live_partidos(timeout: float = 25.0, intentos: int = 2,
                        espera: float = 4.0) -> list[PartidoLive]:
    """Todos los partidos de baloncesto del feed Kambi (una sola petición).

    Reintenta con una espera corta: un timeout puntual del feed no debe hacer
    perder la ventana de descanso (el job corre cada 2 min y el guard
    anti-concurrencia del scheduler evita solapes).
    """
    url = f"{KAMBI_BASE}/listView/basketball.json"
    ultimo: Optional[Exception] = None
    for i in range(max(1, intentos)):
        try:
            r = requests.get(url, params=dict(
                channel_id=1, client_id=200, lang='es_CO', market='CO',
                useCombined='true', useCombinedLive='true'),
                headers=KAMBI_HEADERS, timeout=timeout)
            r.raise_for_status()
            datos = r.json()
            return [parsear_evento(b) for b in datos.get("events", []) or []]
        except Exception as exc:  # noqa: BLE001
            ultimo = exc
            if i + 1 < intentos:
                time.sleep(espera)
    raise ErrorBasket(f"Kambi no respondió: {ultimo}") from ultimo


# --------------------------------------------------------------------------- #
#  Modelo MCO (port fiel de motor.py del repo)                                 #
# --------------------------------------------------------------------------- #
def _resolver_3x3(a: list[list[float]], b: list[float]) -> tuple[float, float, float]:
    """Eliminación gaussiana con pivoteo parcial (ecuaciones normales 3x3)."""
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    n = 3
    for k in range(n):
        p = max(range(k, n), key=lambda i: abs(m[i][k]))
        m[k], m[p] = m[p], m[k]
        for i in range(k + 1, n):
            f = m[i][k] / m[k][k]
            for j in range(k, n + 1):
                m[i][j] -= f * m[k][j]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = m[i][n] - sum(m[i][j] * x[j] for j in range(i + 1, n))
        x[i] = s / m[i][i]
    return x[0], x[1], x[2]


@dataclass
class Modelo:
    liga: str
    origen: str = ""
    n: int = 0
    media_total: float = 0.0
    media_1q: float = 0.0
    media_2q: float = 0.0
    b0: float = 0.0
    b1: float = 0.0
    b2: float = 0.0
    a0: float = 0.0
    a1: float = 0.0
    r2_dos: float = 0.0
    r2_uno: float = 0.0
    rmse_dos: float = 0.0
    rmse_uno: float = 0.0
    rmse_naive: float = 0.0
    rmse_test_dos: float = 0.0
    rmse_test_uno: float = 0.0
    rmse_test_naive: float = 0.0
    fecha_min: Optional[date] = None
    fecha_max: Optional[date] = None
    errores: list[str] = field(default_factory=list)

    def predecir_dos(self, q1: float, q2: float) -> float:
        return self.b0 + self.b1 * q1 + self.b2 * q2

    def predecir_uno(self, q1: float) -> float:
        return self.a0 + self.a1 * q1

    def naive(self, q1: float) -> float:
        return q1 * 4.0


def ajustar(datos: list[tuple[float, float, float]], liga: str,
            origen: str = "") -> Modelo:
    """MCO de la muestra completa (mismas fórmulas que LINEST/FORECAST)."""
    m = Modelo(liga=liga, origen=origen, n=len(datos))
    if not datos:
        m.errores.append("sin datos")
        return m

    n = float(len(datos))
    s1 = s2 = sy = 0.0
    s11 = s22 = s12 = s1y = s2y = syy = 0.0
    for x1, x2, y in datos:
        s1 += x1
        s2 += x2
        sy += y
        s11 += x1 * x1
        s22 += x2 * x2
        s12 += x1 * x2
        s1y += x1 * y
        s2y += x2 * y
        syy += y * y

    m.media_1q = s1 / n
    m.media_2q = s2 / n
    m.media_total = sy / n

    m.b1, m.b2, m.b0 = _resolver_3x3(
        [[s11, s12, s1], [s12, s22, s2], [s1, s2, n]],
        [s1y, s2y, sy],
    )

    mx, my = m.media_1q, m.media_total
    sxx = s11 - n * mx * mx
    sxy = s1y - n * mx * my
    m.a1 = sxy / sxx if sxx else 0.0
    m.a0 = my - m.a1 * mx

    sst = syy - n * my * my
    sse = sse1 = sse4 = 0.0
    for x1, x2, y in datos:
        sse += (y - (m.b0 + m.b1 * x1 + m.b2 * x2)) ** 2
        sse1 += (y - (m.a0 + m.a1 * x1)) ** 2
        sse4 += (y - x1 * 4.0) ** 2
    m.r2_dos = 1.0 - sse / sst if sst else 0.0
    m.r2_uno = 1.0 - sse1 / sst if sst else 0.0
    m.rmse_dos = (sse / n) ** 0.5
    m.rmse_uno = (sse1 / n) ** 0.5
    m.rmse_naive = (sse4 / n) ** 0.5
    m.rmse_test_dos = m.rmse_dos
    m.rmse_test_uno = m.rmse_uno
    m.rmse_test_naive = m.rmse_naive
    return m


def entrenar(datos: list[tuple[float, float, float]], liga: str,
             minimo: int = MINIMO_MUESTRAS) -> Optional[Modelo]:
    """
    Ajusta el modelo de una liga con holdout: el 20 % MÁS RECIENTE valida.

    `datos` debe venir ordenado por fecha ascendente. Con menos de `minimo`
    muestras no se publica modelo propio (devuelve None).
    """
    if len(datos) < minimo:
        return None
    datos = list(datos)
    corte = max(minimo, int(len(datos) * (1 - FRACCION_TEST)))
    ajuste, test = datos[:corte], datos[corte:]
    if not test:
        ajuste, test = datos, datos

    m = ajustar(ajuste, liga, "muestras propias")

    def _rmse(predecir) -> float:
        errores = [(y - predecir(x1, x2)) for x1, x2, y in test]
        return math.sqrt(sum(e * e for e in errores) / len(errores))

    m.rmse_test_dos = _rmse(lambda x1, x2: m.predecir_dos(x1, x2))
    m.rmse_test_uno = _rmse(lambda x1, _x2: m.predecir_uno(x1))
    m.rmse_test_naive = _rmse(lambda x1, _x2: x1 * 4.0)

    completo = ajustar(datos, liga, "muestras propias")
    m.n = completo.n
    m.media_total, m.media_1q, m.media_2q = (completo.media_total,
                                             completo.media_1q,
                                             completo.media_2q)
    m.r2_dos, m.r2_uno = completo.r2_dos, completo.r2_uno
    m.rmse_dos, m.rmse_uno, m.rmse_naive = (completo.rmse_dos, completo.rmse_uno,
                                            completo.rmse_naive)
    return m


def entrenar_pooled(datos: list[tuple[float, float, float]], liga: str,
                    global_m: Modelo,
                    minimo: int = MINIMO_MUESTRAS) -> Optional[Modelo]:
    """Liga con pocas muestras: mezcla del MCO propio con el GLOBAL (pooling)."""
    w = len(datos) / (len(datos) + float(minimo))
    local = ajustar(datos, liga, "mezcla global (pocas muestras)")
    if local.n == 0 or local.errores:
        return None

    m = Modelo(liga=liga, origen="mezcla global (pocas muestras)",
               n=len(datos),
               b0=w * local.b0 + (1 - w) * global_m.b0,
               b1=w * local.b1 + (1 - w) * global_m.b1,
               b2=w * local.b2 + (1 - w) * global_m.b2,
               a0=w * local.a0 + (1 - w) * global_m.a0,
               a1=w * local.a1 + (1 - w) * global_m.a1)
    err = [(y - m.predecir_dos(x1, x2)) for x1, x2, y in datos]
    err_uno = [(y - m.predecir_uno(x1)) for x1, _, y in datos]
    media = sum(y for _, _, y in datos) / len(datos)
    sst = sum((y - media) ** 2 for _, _, y in datos) or 1.0
    m.rmse_dos = math.sqrt(sum(e * e for e in err) / len(err))
    m.rmse_uno = math.sqrt(sum(e * e for e in err_uno) / len(err_uno))
    m.rmse_naive = math.sqrt(sum((y - x1 * 4.0) ** 2 for x1, _, y in datos)
                             / len(datos))
    m.r2_dos = 1 - sum(e * e for e in err) / sst
    m.r2_uno = 1 - sum(e * e for e in err_uno) / sst
    m.rmse_test_dos = m.rmse_dos
    m.rmse_test_uno = m.rmse_uno
    m.rmse_test_naive = m.rmse_naive
    m.media_total = media
    m.media_1q = sum(x1 for x1, _, _ in datos) / len(datos)
    m.media_2q = sum(x2 for _, x2, _ in datos) / len(datos)
    return m


# --------------------------------------------------------------------------- #
#  Predicción y compuerta                                                      #
# --------------------------------------------------------------------------- #
def _normal_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / 2.0 ** 0.5))


@dataclass
class Prediccion:
    prediccion: Optional[float] = None
    diferencia: Optional[float] = None
    veredicto: str = "faltan datos"
    prob_over: Optional[float] = None


def predecir(modelo: Modelo, q1, q2, linea) -> Prediccion:
    r = Prediccion()
    if modelo is None or not modelo.n or q1 is None:
        return r
    r.prediccion = (modelo.predecir_dos(q1, q2) if q2 is not None
                    else modelo.predecir_uno(q1))
    if linea is not None:
        r.diferencia = r.prediccion - linea
        r.veredicto = "OVER" if r.diferencia >= 0 else "UNDER"
        sigma = ((modelo.rmse_test_dos if q2 is not None
                  else modelo.rmse_test_uno) * FACTOR_RMSE)
        if sigma:
            r.prob_over = _normal_cdf(r.diferencia / sigma)
    return r


def evaluar(partido: PartidoLive, modelo: Optional[Modelo],
            delta_min: float = DELTA_MINIMO,
            delta_max: float = DELTA_MAXIMO,
            ev_min: float = EV_MINIMA) -> dict:
    """
    Compuerta completa del bot (mismas reglas del repo, en orden):

      ventana de descanso → modelo propio → línea → |Δ| en rango →
      cuota del lado abierta → EV ≥ mínimo (solo si ev_min > 0; con el
      valor por defecto 0 no hay filtro y solo se registra el EV).

    Devuelve {'ok': bool, 'motivo': str, ...datos si ok}.
    """
    def no(motivo: str) -> dict:
        return {'ok': False, 'motivo': motivo}

    if modelo is None or not modelo.n:
        return no('sin modelo propio de la liga')
    if not en_ventana_descanso(partido):
        return no('no está en el descanso 2Q→3Q')
    if partido.linea is None:
        return no('sin línea publicada')

    res = predecir(modelo, partido.q1,
                   partido.q2 if partido.q2_completo else None,
                   partido.linea)
    if res.veredicto not in VEREDICTOS:
        return no('veredicto sin decidir')
    if abs(res.diferencia) < delta_min:
        return no(f'|Δ| {abs(res.diferencia):.1f} < {delta_min:.1f}')
    if delta_max > 0 and abs(res.diferencia) > delta_max:
        return no(f'|Δ| {abs(res.diferencia):.1f} > {delta_max:.1f}')

    lado = res.veredicto
    cuota = partido.cuota_over if lado == 'OVER' else partido.cuota_under
    disponible = partido.hay_cuota_over if lado == 'OVER' else partido.hay_cuota_under
    if not cuota or cuota <= 1.0:
        return no(f'la casa no publica cuota del {lado}')
    if not disponible:
        return no(f'{lado} suspendido por la casa')

    if res.prob_over is None:
        prob_lado = 0.5
    else:
        prob_lado = res.prob_over if lado == 'OVER' else 1 - res.prob_over
    esperado = prob_lado * cuota - 1.0
    if ev_min > 0 and esperado < ev_min:
        return no(f'EV {esperado * 100:+.1f}% < {ev_min * 100:.1f}%')

    return {
        'ok': True, 'motivo': 'ventana abierta',
        'lado': lado, 'cuota': cuota, 'prob': prob_lado, 'ev': esperado,
        'prediccion': res.prediccion, 'diferencia': res.diferencia,
        'prob_over': res.prob_over,
    }


def liquidar(seleccion: str, linea: float, total: float) -> str:
    """Estado final ('WON'/'LOST'/'VOID') del total vs la línea."""
    if abs(float(total) - float(linea)) < 1e-9:
        return 'VOID'                        # push: se devuelve el stake
    gana_over = float(total) > float(linea)
    if seleccion == SEL_OVER:
        return 'WON' if gana_over else 'LOST'
    if seleccion == SEL_UNDER:
        return 'WON' if not gana_over else 'LOST'
    raise ErrorBasket(f"selección desconocida: {seleccion!r}")


# --------------------------------------------------------------------------- #
#  API-Sports: histórico (entrenamiento) y resultados (liquidación)            #
# --------------------------------------------------------------------------- #
API_BASE = "https://v1.basketball.api-sports.io"
API_TIMEOUT = 30
ESTADOS_FINALIZADO = ("FT", "AET")
RUTA_ENV = "/var/www/predicta.com.co/.env"


class ErrorAPI(ErrorBasket):
    """API-Sports no respondió o respondió con errores."""


def _api_key() -> str:
    key = os.environ.get('APIFOOTBALL_KEY')
    if key:
        return key
    with open(RUTA_ENV, encoding='utf-8') as fh:
        for linea in fh:
            if linea.strip().startswith('APIFOOTBALL_KEY='):
                return linea.split('=', 1)[1].strip().strip('"').strip("'")
    raise ErrorAPI("APIFOOTBALL_KEY no encontrada en .env")


def api_get(ruta: str, **params) -> dict:
    try:
        r = requests.get(f"{API_BASE}/{ruta}",
                         params=params,
                         headers={'x-apisports-key': _api_key(),
                                  'Accept': 'application/json'},
                         timeout=API_TIMEOUT)
    except Exception as exc:  # noqa: BLE001
        raise ErrorAPI(f"sin conexión con API-Sports: {exc}") from exc
    if r.status_code != 200:
        raise ErrorAPI(f"API-Sports HTTP {r.status_code} en /{ruta}")
    d = r.json()
    if d.get("errors"):
        raise ErrorAPI("API-Sports: " + str(d["errors"])[:200])
    return d


def _anio_temporada(etiqueta) -> int:
    """2026 -> 2026 ; '2025-2026' -> 2026."""
    if isinstance(etiqueta, int):
        return etiqueta
    t = str(etiqueta)
    if "-" in t:
        try:
            return int(t.split("-")[1])
        except ValueError:
            pass
    try:
        return int(t)
    except ValueError:
        return 0


def inventario(cliente: Optional[Callable] = None) -> dict[int, list]:
    """{liga_id: [temporadas con datos (más nueva primero)]} en 1 petición."""
    d = (cliente or api_get)("leagues")
    inv: dict[int, list] = {}
    for l in d.get("response") or []:
        lid = l.get("id")
        con_datos = []
        for s in l.get("seasons") or []:
            cov = (((s.get("coverage") or {}).get("games") or {})
                   .get("statistics") or {})
            if cov.get("teams"):
                con_datos.append(s.get("season"))
        con_datos.sort(key=_anio_temporada, reverse=True)
        if con_datos:
            inv[lid] = con_datos
    return inv


def _fecha(texto) -> Optional[date]:
    if not texto:
        return None
    t = str(texto)
    try:
        return datetime.fromisoformat(t.replace("Z", "+00:00")).date()
    except ValueError:
        return None


def _parsear_partidos(d: dict, clave: str, etiqueta) -> list[dict]:
    """Respuesta de /games -> muestras (solo partidos acabados con cuartos)."""
    salen: list[dict] = []
    for g in d.get("response") or []:
        estado = (g.get("status") or {}).get("short")
        if estado not in ESTADOS_FINALIZADO:
            continue
        sc = g.get("scores") or {}
        h, a = sc.get("home") or {}, sc.get("away") or {}
        ch = [h.get(f"quarter_{i}") for i in (1, 2, 3, 4)]
        ca = [a.get(f"quarter_{i}") for i in (1, 2, 3, 4)]
        if any(v is None for v in ch + ca):
            continue
        cuartos = [float(x) + float(y) for x, y in zip(ch, ca)]
        th, ta = h.get("total"), a.get("total")
        if th is not None and ta is not None:
            total = float(th) + float(ta)
        else:
            total = (sum(cuartos) + float(h.get("over_time") or 0)
                     + float(a.get("over_time") or 0))
        if total <= 0:
            continue
        eq = g.get("teams") or {}

        def nombre(e) -> str:
            return (e or {}).get("name") or "?"

        fecha = _fecha(g.get("date"))
        partido = f"{nombre(eq.get('home'))} - {nombre(eq.get('away'))}"
        if g.get("id"):
            evento_clave = f"{clave}|{g.get('id')}"
        else:
            f = fecha.isoformat() if fecha else "s/f"
            evento_clave = f"{clave}|{f}|{partido}"
        salen.append({
            'liga': clave,
            'fecha': fecha,
            'q1': cuartos[0], 'q2': cuartos[1], 'q3': cuartos[2], 'q4': cuartos[3],
            'total': total,
            'partido': partido,
            'fuente': f"apisports:{etiqueta}",
            'evento_id': str(g.get("id")) if g.get("id") else None,
            'evento_clave': evento_clave,
        })
    return salen


def descargar_liga(clave: str, ids: Iterable[int],
                   inv: Optional[dict[int, list]] = None,
                   n_temporadas: int = 2,
                   minimo_muestras: int = MINIMO_MUESTRAS,
                   progreso: Optional[Callable] = None) -> list[dict]:
    """
    Descarga las muestras de una liga desde API-Sports.

    Usa las `n_temporadas` más recientes con datos y, si aún no llega a
    `minimo_muestras`, sigue con temporadas anteriores (misma estrategia que
    el repo). Sin inventario previo lo pide (1 petición compartida).
    """
    inv = inv if inv is not None else inventario()
    pares: list[tuple] = []
    for lid in ids:
        for etiqueta in inv.get(lid, []):
            pares.append((etiqueta, lid))
    pares.sort(key=lambda t: _anio_temporada(t[0]), reverse=True)
    if not pares:
        if progreso:
            progreso(clave, 0, "sin temporadas con datos en API-Sports")
        return []

    limite = max(1, n_temporadas)
    vistos: dict[int, int] = {}
    primeras: list[tuple] = []
    resto: list[tuple] = []
    for etiqueta, lid in pares:
        vistos[lid] = vistos.get(lid, 0) + 1
        (primeras if vistos[lid] <= limite else resto).append((etiqueta, lid))

    plan = primeras + (resto if minimo_muestras > 0 else [])
    salen: list[dict] = []
    for etiqueta, lid in plan:
        d = api_get("games", league=lid, season=etiqueta)
        lote = _parsear_partidos(d, clave, etiqueta)
        salen.extend(lote)
        if progreso:
            progreso(clave, len(lote), f"temporada {etiqueta} (id {lid})")
        if minimo_muestras and len(salen) >= minimo_muestras:
            break
    return salen


# --- resultados oficiales (liquidación) ------------------------------------ #
_RELLENO = {
    "basket", "basketball", "baloncesto", "bc", "bk", "kk", "sc", "ac", "as",
    "cb", "club", "team", "b.c", "b", "c", "the", "de", "del",
    "women", "woman", "w", "f", "fem", "femenino", "femenina",
}

# Alias de abreviaturas Kambi -> API-Sports (se expanden en _norm para que el
# emparejamiento por tokens reconozca variantes: "Talk 'N Text" = "TNT").
_TOKENS_ALIAS = {
    "tnt": ("tnt", "talk", "text"),
    "talk": ("tnt", "talk", "text"),
    "text": ("tnt", "talk", "text"),
}

_cache_juegos: dict[str, list[dict]] = {}


def _norm(texto: str) -> set[str]:
    t = unicodedata.normalize("NFKD", texto or "")
    t = t.encode("ascii", "ignore").decode("ascii")
    t = t.lower()
    for ch in "().,-'’/*_":
        t = t.replace(ch, " ")
    partes = {p for p in t.split() if p and p not in _RELLENO}
    salida = set(partes)
    for p in partes:
        salida.update(_TOKENS_ALIAS.get(p, ()))
    return salida


def _parecido(a: set[str], b: set[str]) -> float:
    """Jaccard o contención, el mayor: tolera nombres cortos de API-Sports
    ("Abejas" vs "Abejas de León") sin exigir simetría exacta."""
    if not a or not b:
        return 0.0
    inter = len(a & b)
    if not inter:
        return 0.0
    return max(inter / len(a | b), inter / min(len(a), len(b)))


def juegos_del_dia(fecha: date) -> list[dict]:
    """Partidos TERMINADOS de esa fecha (caché por proceso)."""
    clave = fecha.isoformat()
    if clave in _cache_juegos:
        return _cache_juegos[clave]
    juegos: list[dict] = []
    try:
        d = api_get("games", date=clave)
    except ErrorAPI:
        _cache_juegos[clave] = juegos
        return juegos
    for g in d.get("response") or []:
        st = (((g.get("status") or {}).get("long") or "") + " " +
              ((g.get("status") or {}).get("short") or "")).lower()
        if "finish" not in st and "after" not in st:
            continue
        sc = g.get("scores") or {}
        h = (sc.get("home") or {}).get("total")
        a = (sc.get("away") or {}).get("total")
        if h is None or a is None:
            continue
        eq = g.get("teams") or {}
        juegos.append({
            "local": ((eq.get("home") or {}).get("name") or ""),
            "visitante": ((eq.get("away") or {}).get("name") or ""),
            "total": float(h) + float(a),
        })
    _cache_juegos[clave] = juegos
    return juegos


def resultado_oficial(local: str, visitante: str, fecha: date,
                      minimo: float = 0.5) -> Optional[float]:
    """Total final oficial (prórroga incluida) o None si no se encuentra."""
    a_local, a_vis = _norm(local), _norm(visitante)
    if not a_local or not a_vis:
        return None
    mejor_total: Optional[float] = None
    mejor_score = 0.0
    for dia in (fecha, fecha - timedelta(days=1), fecha + timedelta(days=1)):
        for j in juegos_del_dia(dia):
            s1 = _parecido(a_local, _norm(j["local"]))
            s2 = _parecido(a_vis, _norm(j["visitante"]))
            score = min(s1, s2)
            if score >= minimo and score > mejor_score:
                mejor_score = score
                mejor_total = j["total"]
    return mejor_total
