# -*- coding: utf-8 -*-
"""basket_ou.py — Motor Over/Under al descanso (baloncesto) para el PAPERBET.

Port del modelo de los libros `EUROPA.xlsx` / `NBA.xlsx` (spec:
`spec_modelo_ou_descanso_paperbet.md`) + extensión multi-liga (spec
complementaria 2026-10-16): estructuras de N periodos (`ESTRUCTURAS`),
config provisional (`config_provisional`), suavizado (`suavizar`) y
compuertas por liga (`evaluar_compuerta`). Mismas fórmulas para todas las
ligas; solo cambia la config (`CFG` o la del registro de ligas).

Flujo:
  * `calibrar(games, cfg)` — hoja Patron: patrón por cuartos, media de liga y
    sigma del error, a partir de partidos con los 4 cuartos (sin prórroga).
  * `decidir(cfg, cal, inp)` — hoja Calculadora: decisión al descanso con
    métodos A (patrón), C (posesiones, opcional), L (línea viva) y M (ancla).
  * `fila_historial(cfg, cal, g)` — versión Historial/Backtest (sin método C,
    elige lado por probabilidad) para reprocesar partidos pasados.
  * `metricas(rows, cfg)` — hoja Backtest: acierto, ROI (push en el
    denominador), breakeven, Wilson 95 %, acierto por lado y veredicto.

Módulo PURO (sin Django ni red). Los comandos de management hacen la
persistencia. Regla de oro del experimento: la config se congela y cada
apuesta/shadow registra su `cfg_version`.
"""
from __future__ import annotations

import hashlib
import json
import math
import re
import statistics
from dataclasses import dataclass
from typing import Iterable, Optional

MOTOR = 'basket_ou'
MERCADO = 'Total de puntos (OU descanso)'
SEL_OVER = 'Más de'
SEL_UNDER = 'Menos de'
STAKE_DEFECTO = 10000       # COP virtuales (1 u del paperbet, igual que el resto)

# --------------------------------------------------------------------------- #
#  Config por liga (valores del spec; congelar mientras corre el paper)        #
# --------------------------------------------------------------------------- #
CFG: dict[str, dict] = {
    'EUROPA': dict(
        min_sample=30, t_crit=2.0,
        league_avg=160.0, league_ppp=1.11, w_ppp_h1=0.5, pos_factor=1.0,
        wA=0.25, wC=0.20, wL=0.45, wM=0.10,
        sigma_default=9.0, min_prob=0.60, min_ev=0.03, min_diff=3.0,
        odds_min=1.70, odds_max=2.20, max_margin=18,
        bankroll=1000.0, kelly_fraction=0.25, stake_cap=0.03,
        default_odds=1.9, anchor_to_market=1,
    ),
    'NBA': dict(
        min_sample=30, t_crit=2.0,
        league_avg=228.0, league_ppp=1.14, w_ppp_h1=0.5, pos_factor=1.0,
        wA=0.25, wC=0.20, wL=0.45, wM=0.10,
        sigma_default=12.0, min_prob=0.60, min_ev=0.03, min_diff=4.0,
        odds_min=1.70, odds_max=2.20, max_margin=20,
        bankroll=1000.0, kelly_fraction=0.25, stake_cap=0.03,
        default_odds=1.9, anchor_to_market=1,
    ),
}

# Liga del feed Kambi (clave_liga) -> config. Fuera de ese mapa no se apuesta.
LIGAS_CFG: dict[str, str] = {
    'euroleague': 'EUROPA',
    'eurocup': 'EUROPA',
    'fiba_europe_cup': 'EUROPA',   # Europe Cup FIBA (no es la BCL)
    'nba': 'NBA',
    # 'nba_preseason' queda fuera del bot en vivo (régimen distinto); los
    # reportes históricos pueden evaluarlo aparte con cfg NBA.
}

# Config de TODA liga conocida (backfill/reportes). Incluye NBA pretemporada,
# que queda fuera del bot en vivo (régimen de puntuación distinto).
CFG_DE_LIGA: dict[str, str] = {
    **LIGAS_CFG,
    'nba_preseason': 'NBA',
}

# Ligas (BasketSample.liga) usadas para calibrar cada config.
CAL_LIGAS: dict[str, tuple[str, ...]] = {
    'EUROPA': ('euroleague', 'eurocup'),
    'NBA': ('nba',),
}

# Torneos en OddsPapi (para el backfill de líneas del descanso) -> liga local.
TORNEOS_ODDSPAPI: dict[int, str] = {
    138: 'euroleague',
    141: 'eurocup',
    2388: 'fiba_europe_cup',
    2382: 'nba_preseason',
    132: 'nba',
}

# --------------------------------------------------------------------------- #
#  Estructuras de periodos (spec complementaria de ligas, 2026-10-16)          #
# --------------------------------------------------------------------------- #
# El motor asume N periodos; la config declara su estructura con `estructura`
# (ausente = FIBA_4x10, el comportamiento histórico del libro). CFG['EUROPA'] y
# CFG['NBA'] se mantienen tal cual: sus cfg_version no cambian mientras corre
# el paper actual.
ESTRUCTURAS: dict[str, dict] = {
    'FIBA_4x10': dict(n_periodos=4, ot_minutos=5),
    'NBA_4x12': dict(n_periodos=4, ot_minutos=5),
    'HALVES_2x20': dict(n_periodos=2, ot_minutos=5),
}

# Parámetros no liga-específicos de cada estructura (base de config_provisional).
CFG_ESTRUCTURA: dict[str, dict] = {
    'FIBA_4x10': dict(
        min_sample=30, t_crit=2.0,
        league_ppp=1.11, w_ppp_h1=0.5, pos_factor=1.0,
        wA=0.25, wC=0.20, wL=0.45, wM=0.10,
        min_prob=0.60, min_ev=0.03,
        odds_min=1.70, odds_max=2.20,
        bankroll=1000.0, kelly_fraction=0.25, stake_cap=0.03,
        default_odds=1.9, anchor_to_market=1,
        calibration_mode='excel_hard', estructura='FIBA_4x10',
    ),
    'NBA_4x12': dict(
        min_sample=30, t_crit=2.0,
        league_ppp=1.14, w_ppp_h1=0.5, pos_factor=1.0,
        wA=0.25, wC=0.20, wL=0.45, wM=0.10,
        min_prob=0.60, min_ev=0.03,
        odds_min=1.70, odds_max=2.20,
        bankroll=1000.0, kelly_fraction=0.25, stake_cap=0.03,
        default_odds=1.9, anchor_to_market=1,
        calibration_mode='excel_hard', estructura='NBA_4x12',
    ),
    'HALVES_2x20': dict(
        min_sample=30, t_crit=2.0,
        league_ppp=1.11, w_ppp_h1=0.5, pos_factor=1.0,
        wA=0.25, wC=0.20, wL=0.45, wM=0.10,
        min_prob=0.60, min_ev=0.03,
        odds_min=1.70, odds_max=2.20,
        bankroll=1000.0, kelly_fraction=0.25, stake_cap=0.03,
        default_odds=1.9, anchor_to_market=1,
        calibration_mode='excel_hard', estructura='HALVES_2x20',
    ),
}


def estructura_de(cfg: dict) -> str:
    """Clave de estructura de la config ('FIBA_4x10' si no declara ninguna)."""
    est = (cfg or {}).get('estructura') or 'FIBA_4x10'
    return est if est in ESTRUCTURAS else 'FIBA_4x10'


def n_periodos_de(cfg: dict) -> int:
    return ESTRUCTURAS[estructura_de(cfg)]['n_periodos']


def periodos_primera_mitad(estructura: str) -> list:
    """Periodos (1-indexados) que componen la primera mitad en cada estructura."""
    if estructura == 'HALVES_2x20':
        return [1]
    return [1, 2]


def A_metodo(h1: float, pct, estructura: str) -> float:
    """Método A generalizado: extrapola la 1ª mitad con el patrón calibrado."""
    per = periodos_primera_mitad(estructura)
    return h1 / sum(pct[p - 1] for p in per)


# --------------------------------------------------------------------------- #
#  Ligas nuevas: config provisional, suavizado y compuertas (spec ligas)       #
# --------------------------------------------------------------------------- #
def suavizar(n: int, valor_liga: float, prior: float, k0: int = 20) -> float:
    """Shrinkage empírico-Bayes simple hacia un prior (k0 pseudo-partidos)."""
    return (n * valor_liga + k0 * prior) / (n + k0)


def sigma_suavizada(n: int, s: float, prior: float, k0: int = 20) -> float:
    """Sigma del error mezclada con el prior (spec de ligas §5)."""
    return math.sqrt((n * s * s + k0 * prior * prior) / (n + k0))


def config_provisional(liga: str, hist: Iterable[dict],
                       estructura: str = 'FIBA_4x10') -> Optional[dict]:
    """Config provisional para una liga nueva (heurísticas de la spec de ligas).

    `hist`: resultados históricos recientes de la liga — dicts con `total`
    (regulación). Devuelve la LeagueConfig marcada `proveniente='provisional'`
    (sigma/min_diff/max_margin derivados de la media; el resto, del default de
    la estructura), o None si no hay historia.
    """
    totales = [float(g['total']) for g in hist if g.get('total')]
    if not totales:
        return None
    n_hist = len(totales)
    league_avg = statistics.fmean(totales)
    sigma_default = round(0.06 * league_avg, 1)
    min_diff = round(sigma_default / 3)
    max_margin = math.floor(0.10 * league_avg + 0.5)
    cfg = dict(CFG_ESTRUCTURA.get(estructura, CFG_ESTRUCTURA['FIBA_4x10']))
    cfg.update(
        liga=liga, league_avg=league_avg, sigma_default=sigma_default,
        min_diff=float(min_diff), max_margin=max_margin, n_hist=n_hist,
        proveniente='provisional')
    return cfg


# Umbrales de compuertas (spec §4; propuestas congeladas al arrancar).
UMBRAL_G1 = dict(n_partidos_limpios=30, cobertura_linea_descanso=0.80,
                 cobertura_periodos=0.95, mismatch_reconciliacion=0.03)
UMBRAL_G2 = dict(n_shadow=100)
UMBRAL_G3 = dict(n_paper=300)


def evaluar_compuerta(s: dict) -> dict:
    """Compuertas DISCOVERY->SHADOW (G1), SHADOW->PAPER (G2), PAPER->LIVE (G3).

    `s` = stats por liga (stats_liga): n_partidos_limpios,
    cobertura_linea_descanso, cobertura_periodos, mismatch_reconciliacion,
    n_shadow, rmse_modelo, rmse_linea, slope_b, slope_b_lo, slope_b_hi,
    n_paper, margen_medio_vs_linea, roi_plano.
    """
    f1, f2, f3 = [], [], []

    n_limpios = s.get('n_partidos_limpios') or 0
    if n_limpios < UMBRAL_G1['n_partidos_limpios']:
        f1.append(
            f"faltan {UMBRAL_G1['n_partidos_limpios'] - n_limpios} partidos "
            f"limpios ({n_limpios}/{UMBRAL_G1['n_partidos_limpios']})")
    cob_l = s.get('cobertura_linea_descanso')
    if cob_l is None or cob_l < UMBRAL_G1['cobertura_linea_descanso']:
        f1.append('cobertura de línea al descanso <80%'
                  + ('' if cob_l is None else f' ({cob_l * 100:.0f}%)'))
    cob_p = s.get('cobertura_periodos')
    if cob_p is None or cob_p < UMBRAL_G1['cobertura_periodos']:
        f1.append('cobertura de periodos <95%'
                  + ('' if cob_p is None else f' ({cob_p * 100:.0f}%)'))
    mis = s.get('mismatch_reconciliacion')
    if mis is None or mis > UMBRAL_G1['mismatch_reconciliacion']:
        f1.append('mismatch reconciliación >3%'
                  + ('' if mis is None else f' ({mis * 100:.1f}%)'))

    n_sh = s.get('n_shadow') or 0
    if n_sh < UMBRAL_G2['n_shadow']:
        f2.append(f"faltan {UMBRAL_G2['n_shadow'] - n_sh} shadows "
                  f"({n_sh}/{UMBRAL_G2['n_shadow']})")
    rm, rl = s.get('rmse_modelo'), s.get('rmse_linea')
    if rm is None or rl is None:
        f2.append('RMSE modelo/línea sin datos')
    elif rm > rl:
        f2.append(f'RMSE modelo > RMSE línea ({rm:.2f} > {rl:.2f})')
    b, blo, bhi = s.get('slope_b'), s.get('slope_b_lo'), s.get('slope_b_hi')
    if b is None or blo is None or bhi is None:
        f2.append('regresión slope_b sin datos')
    elif blo <= 0 <= bhi:
        f2.append(f'slope_b IC95 incluye 0 [{blo:.3f}, {bhi:.3f}]')

    n_pa = s.get('n_paper') or 0
    if n_pa < UMBRAL_G3['n_paper']:
        f3.append(f"faltan {UMBRAL_G3['n_paper'] - n_pa} apuestas paper "
                  f"({n_pa}/{UMBRAL_G3['n_paper']})")
    mm = s.get('margen_medio_vs_linea')
    if mm is None or mm <= 0:
        f3.append('margen medio vs línea no es positivo'
                  + ('' if mm is None else f' ({mm:+.2f})'))
    roi = s.get('roi_plano')
    if roi is None or roi <= 0:
        f3.append('ROI plano no es positivo'
                  + ('' if roi is None else f' ({roi * 100:+.1f}%)'))

    return {'G1': not f1, 'G2': not f2, 'G3': not f3,
            'falta': {'G1': '; '.join(f1), 'G2': '; '.join(f2),
                      'G3': '; '.join(f3)}}


def siguiente_estado(estado: str, gates: dict) -> str:
    """Estado al que promueve cada compuerta. LIVE nunca es automático."""
    if estado == 'DISCOVERY':
        return 'SHADOW' if gates['G1'] else 'DISCOVERY'
    if estado == 'SHADOW':
        return 'PAPER' if gates['G2'] else 'SHADOW'
    return estado          # PAPER -> LIVE requiere aprobación humana


def regresion_simple(xs, ys) -> Optional[dict]:
    """Regresión y ~ a + b·x: slope, IC95 (normal) y R². None si no alcanza.

    Con varias ligas el azar produce 'positivas': por eso la compuerta G2
    exige el intervalo de confianza del slope, no solo un ROI.
    """
    pares = [(float(x), float(y)) for x, y in zip(xs, ys)
             if x is not None and y is not None]
    n = len(pares)
    if n < 3:
        return None
    mx = statistics.fmean(x for x, _ in pares)
    my = statistics.fmean(y for _, y in pares)
    sxx = sum((x - mx) ** 2 for x, _ in pares)
    if sxx <= 1e-12:
        return None
    sxy = sum((x - mx) * (y - my) for x, y in pares)
    b = sxy / sxx
    a = my - b * mx
    sse = sum((y - (a + b * x)) ** 2 for x, y in pares)
    syy = sum((y - my) ** 2 for _, y in pares)
    se = math.sqrt((sse / (n - 2)) / sxx)
    lo, hi = b - 1.96 * se, b + 1.96 * se
    r2 = 1.0 - sse / syy if syy > 1e-12 else None
    return {'b': b, 'a': a, 'se': se, 'lo': lo, 'hi': hi, 'r2': r2, 'n': n}


def Phi(x: float) -> float:
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


_RE_SPLIT = re.compile(r'Q([1-4])\s*:\s*(\d+)\s*-\s*(\d+)', re.IGNORECASE)


def parsear_cuartos_split(info: str) -> dict:
    """'Q1: 27-14 | Q2: 23-29' -> {'Q1': (27, 14), 'Q2': (23, 29)}.

    Igual que la suma que usa basket_1q2q, pero conservando local/visitante
    (el modelo OU necesita el margen al descanso).
    """
    salida: dict = {}
    for cuarto, local, visitante in _RE_SPLIT.findall(info or ''):
        salida[f'Q{cuarto}'] = (int(local), int(visitante))
    return salida


def cfg_version(cfg: dict) -> str:
    """Hash corto y estable de la config (regla de oro: queda fijada por apuesta)."""
    blob = json.dumps(cfg, sort_keys=True, separators=(',', ':')).encode()
    return hashlib.sha256(blob).hexdigest()[:12]


# --------------------------------------------------------------------------- #
#  Calibración (hoja Patron)                                                   #
# --------------------------------------------------------------------------- #
@dataclass
class Calibracion:
    pct: tuple = (0.25, 0.25, 0.25, 0.25)
    league_mean: float = 160.0
    sigma: float = 9.0
    n: int = 0
    t_stats: tuple = ()
    significativas: tuple = ()
    sigma_fuente: str = 'default'          # 'err' | 'err_shrink' | 'default'
    cfg: str = ''                          # clave de config (EUROPA/NBA/liga)

    @property
    def version(self) -> str:
        blob = json.dumps(
            [round(p, 6) for p in self.pct], sort_keys=False) + \
            f'|{self.league_mean:.4f}|{self.sigma:.4f}|{self.n}'
        return hashlib.sha256(blob.encode()).hexdigest()[:12]


def calibracion_inicial(cfg: dict, clave: str = '') -> Calibracion:
    """Defaults (n < min_sample): 1/N por periodo, league_avg, sigma_default."""
    nper = n_periodos_de(cfg)
    return Calibracion(
        pct=tuple(1.0 / nper for _ in range(nper)),
        league_mean=float(cfg['league_avg']),
        sigma=float(cfg['sigma_default']),
        n=0, t_stats=(None,) * nper, significativas=(False,) * nper, cfg=clave)


def _proyeccion_hist(cfg: dict, pct, league_mean: float,
                     h1: float, line: Optional[float]):
    """Proyección de la hoja Historial: A + L (si hay línea) + M (ancla)."""
    A = A_metodo(h1, pct, estructura_de(cfg))
    M = line if (cfg['anchor_to_market'] and line is not None) else league_mean
    num = cfg['wA'] * A + (cfg['wL'] * line if line is not None else 0.0) \
        + cfg['wM'] * M
    den = cfg['wA'] + (cfg['wL'] if line is not None else 0.0) + cfg['wM']
    return num / den


def filtrar_juegos_limpios(filas: Iterable[tuple], n_periodos: int = 4,
                           rango: tuple = (60.0, 350.0)) -> list:
    """(p1..pN, total) -> juegos válidos para el Patron (sin prórroga).

    Descarta: periodos incompletos, prórroga (total ≠ regulación) y totales
    fuera de rango (dato sucio). Devuelve dicts con 'periodos' y las claves
    q1..qN (compatibilidad con los consumidores históricos de 4 cuartos).
    """
    juegos = []
    for fila in filas:
        crudos = list(fila[:n_periodos])
        if len(crudos) < n_periodos or any(v is None for v in crudos):
            continue
        total = fila[n_periodos] if len(fila) > n_periodos else None
        reg = sum(float(v) for v in crudos)
        if total is not None and abs(float(total) - reg) > 0.01:
            continue
        if not (rango[0] <= reg <= rango[1]):
            continue
        juego = {'periodos': [float(v) for v in crudos]}
        for i, v in enumerate(juego['periodos'], 1):
            juego[f'q{i}'] = v
        juegos.append(juego)
    return juegos


def _periodos_de_juego(g: dict, nper: int):
    """Periodos del juego desde dict con 'periodos' o claves q1..qN. None si faltan."""
    if g.get('periodos') is not None:
        periodos = list(g['periodos'])[:nper]
    else:
        periodos = [g.get(f'q{i}') for i in range(1, nper + 1)]
    if len(periodos) < nper or any(p is None for p in periodos):
        return None
    return [float(p) for p in periodos]


def calibrar(games: Iterable[dict], cfg: dict, clave: str = '',
             modo: Optional[str] = None) -> Calibracion:
    """Hoja Patron generalizada a N periodos (sin prórroga).

    `games`: iterable de dicts con q1..qN (o 'periodos') y, opcionalmente,
    `line` (para el sigma del error de proyección). El total de referencia es
    la suma de la regulación.

    `modo`: 'excel_hard' (corte brusco n>=min_sample, como el Excel) o
    'shrinkage' (suavizado empírico-Bayes hacia el prior; spec de ligas §5).
    Por defecto, el declarado en la config (`calibration_mode`).
    """
    est = estructura_de(cfg)
    nper = n_periodos_de(cfg)
    per_half = periodos_primera_mitad(est)
    prior = 1.0 / nper
    modo = modo or cfg.get('calibration_mode', 'excel_hard')

    limpios: list[dict] = []
    for g in games:
        periodos = _periodos_de_juego(g, nper)
        if periodos is None:
            continue
        total = sum(periodos)
        if total <= 0:
            continue
        limpios.append({'q': periodos, 'total': total, 'line': g.get('line')})

    n = len(limpios)
    cal = calibracion_inicial(cfg, clave)
    cal.n = n
    if n == 0:
        return cal

    # patrón por periodo (media, t de significancia vs el prior 1/N)
    medias = [0.0] * nper
    for i in range(nper):
        pcts = [g['q'][i] / g['total'] for g in limpios]
        medias[i] = statistics.fmean(pcts)
        sd = statistics.stdev(pcts) if n >= 2 else 0.0
        t_i = ((medias[i] - prior) / (sd / math.sqrt(n))) if sd > 0 else None
        cal.t_stats = cal.t_stats[:i] + (t_i,) + cal.t_stats[i + 1:]

    raw = []
    signif = []
    for i in range(nper):
        t_i = cal.t_stats[i]
        if modo == 'shrinkage':
            s_i = True        # el suavizado no aplica el corte brusco del Excel
            v = suavizar(n, medias[i], prior)
        else:
            s_i = (n >= cfg['min_sample']) and (t_i is not None
                                                and abs(t_i) >= cfg['t_crit'])
            v = medias[i] if s_i else prior
        signif.append(s_i)
        raw.append(v)
    suma = sum(raw)
    cal.pct = tuple(r / suma for r in raw)
    cal.significativas = tuple(signif)

    # media de liga y sigma del error por partido
    media_liga = statistics.fmean(g['total'] for g in limpios)
    if modo == 'shrinkage':
        cal.league_mean = suavizar(n, media_liga, float(cfg['league_avg']))
    elif n >= cfg['min_sample']:
        cal.league_mean = media_liga

    errores = [g['total'] - _proyeccion_hist(
                   cfg, cal.pct, cal.league_mean,
                   sum(g['q'][p - 1] for p in per_half), g['line'])
               for g in limpios]
    sigma_err = statistics.stdev(errores) if n >= 2 else None
    if modo == 'shrinkage':
        if sigma_err is not None and sigma_err > 1e-12:
            cal.sigma = sigma_suavizada(n, sigma_err,
                                        float(cfg['sigma_default']))
            cal.sigma_fuente = 'err_shrink'
    elif n >= cfg['min_sample'] and sigma_err is not None and sigma_err > 1e-12:
        cal.sigma = sigma_err
        cal.sigma_fuente = 'err'
    return cal


# --------------------------------------------------------------------------- #
#  Decisión al descanso (hoja Calculadora)                                     #
# --------------------------------------------------------------------------- #
def probs(line: float, proj: float, sigma: float):
    """Probabilidades normal. Línea entera => media unidad de push."""
    if line == int(line):
        p_over = 1.0 - Phi((line + 0.5 - proj) / sigma)
        p_under = Phi((line - 0.5 - proj) / sigma)
    else:
        p_over = 1.0 - Phi((line - proj) / sigma)
        p_under = Phi((line - proj) / sigma)
    return p_over, p_under


def _kelly_stake(cfg: dict, p_side: float, odds_side: float) -> float:
    kelly_full = max(0.0, (p_side * odds_side - 1.0) / (odds_side - 1.0))
    return min(cfg['stake_cap'], cfg['kelly_fraction'] * kelly_full) * cfg['bankroll']


def decidir(cfg: dict, cal: Calibracion, inp: dict) -> dict:
    """Hoja Calculadora generalizada a N periodos. `inp` = q1h,q1a,q2h,q2a,
    line, odds_over, odds_under y, para estructuras de 2 periodos, `h1`
    directo; opcionales fga,orb,to,fta (Método C) y `margen` (override;
    replays sin desglose local/visita)."""
    est = estructura_de(cfg)
    con_cuartos = (inp.get('q1h') is not None) or (inp.get('h1') is None)
    requeridos = (('q1h', 'q1a', 'q2h', 'q2a') if con_cuartos else ('h1',)) + \
        ('line', 'odds_over', 'odds_under')
    faltan = any(inp.get(k) is None for k in requeridos)
    if faltan:
        return {
            'A': None, 'C': None, 'L': inp.get('line'), 'M': None,
            'proy': None, 'diff': None, 'sigma': cal.sigma, 'margin': None,
            'p_over': None, 'p_under': None, 'ev_over': None, 'ev_under': None,
            'side': None, 'p_side': None, 'ev_side': None, 'odds_side': None,
            'filtros': {'prob': False, 'ev': False, 'diff': False,
                        'cuota': False, 'margen': False, 'datos': False},
            'decision': 'FALTAN DATOS', 'stake': 0.0,
        }

    line = float(inp['line'])
    odds_o, odds_u = float(inp['odds_over']), float(inp['odds_under'])
    if con_cuartos:
        q1h, q1a, q2h, q2a = (float(inp['q1h']), float(inp['q1a']),
                              float(inp['q2h']), float(inp['q2a']))
        h1 = (q1h + q1a) + (q2h + q2a)
        margin = abs((q1h + q2h) - (q1a + q2a))
    else:
        h1 = float(inp['h1'])
        margin = None
    if inp.get('margen') is not None:
        margin = abs(float(inp['margen']))

    # Método A: extrapola la 1ª mitad con el patrón por periodos
    A = A_metodo(h1, cal.pct, est)

    # Método C: solo con posesiones (si no, se OMITE y los pesos renormalizan)
    C = None
    fga, orb, to, fta = (inp.get('fga'), inp.get('orb'), inp.get('to'),
                         inp.get('fta'))
    if None not in (fga, orb, to, fta):
        poss = float(fga) - float(orb) + 0.44 * float(fta) + float(to)
        if poss > 0:
            ppp = h1 / poss
            if cfg['anchor_to_market'] and line is not None:
                target_ppp = line / (poss * (1.0 + cfg['pos_factor']))
            else:
                target_ppp = cfg['league_ppp']
            C = h1 + poss * cfg['pos_factor'] * (
                cfg['w_ppp_h1'] * ppp + (1.0 - cfg['w_ppp_h1']) * target_ppp)

    L = line
    M = line if (cfg['anchor_to_market'] and line is not None) else cal.league_mean

    num = cfg['wA'] * A + (cfg['wC'] * C if C is not None else 0.0) \
        + cfg['wL'] * L + cfg['wM'] * M
    den = cfg['wA'] + (cfg['wC'] if C is not None else 0.0) + cfg['wL'] + cfg['wM']
    proy = num / den
    sigma = cal.sigma
    diff = proy - line

    p_over, p_under = probs(line, proy, sigma)
    ev_over = p_over * (odds_o - 1.0) - p_under
    ev_under = p_under * (odds_u - 1.0) - p_over

    side = 'OVER' if ev_over >= ev_under else 'UNDER'
    p_side = p_over if side == 'OVER' else p_under
    ev_side = ev_over if side == 'OVER' else ev_under
    odds_side = odds_o if side == 'OVER' else odds_u

    filtros = {
        'prob': p_side >= cfg['min_prob'],
        'ev': ev_side >= cfg['min_ev'],
        'diff': abs(diff) >= cfg['min_diff'],
        'cuota': cfg['odds_min'] <= odds_side <= cfg['odds_max'],
        'margen': margin is not None and margin <= cfg['max_margin'],
        'datos': True,
    }
    apostar = all(filtros.values())
    stake = _kelly_stake(cfg, p_side, odds_side) if apostar else 0.0
    return {
        'A': A, 'C': C, 'L': L, 'M': M, 'proy': proy, 'diff': diff,
        'sigma': sigma, 'margin': margin,
        'p_over': p_over, 'p_under': p_under,
        'ev_over': ev_over, 'ev_under': ev_under,
        'side': side, 'p_side': p_side, 'ev_side': ev_side,
        'odds_side': odds_side, 'filtros': filtros,
        'decision': ('APOSTAR ' + side) if apostar else 'NO APOSTAR',
        'stake': stake,
    }


# --------------------------------------------------------------------------- #
#  Versión Historial / Backtest (la que usa el Excel para evaluar pasado)      #
# --------------------------------------------------------------------------- #
def liquidar_apuesta(side: str, line: float, total: float,
                     odds: Optional[float]) -> tuple:
    """(resultado, ganancia_u): PUSH si total == línea; GANA si el lado coincide."""
    if abs(float(total) - float(line)) < 1e-9:
        return 'PUSH', (0.0 if odds is not None else None)
    gana = (total > line)
    if side == 'OVER':
        resultado = 'GANA' if gana else 'PIERDE'
    else:
        resultado = 'PIERDE' if gana else 'GANA'
    if odds is None:
        return resultado, None
    return resultado, (float(odds) - 1.0 if resultado == 'GANA' else -1.0)


def fila_historial(cfg: dict, cal: Calibracion, g: dict) -> dict:
    """Fila de la hoja Historial/Backtest generalizada a N periodos.
    `g` = q1..qN (o 'periodos'), line (opcional), odds (opcional), margin
    (opcional). Sin Método C (no hay posesiones)."""
    nper = n_periodos_de(cfg)
    periodos = _periodos_de_juego(g, nper)
    if periodos is None:
        raise ValueError('fila_historial: faltan periodos del partido')
    est = estructura_de(cfg)
    h1 = sum(periodos[p - 1] for p in periodos_primera_mitad(est))
    total = sum(periodos)
    line = g.get('line')
    A = A_metodo(h1, cal.pct, est)
    proy = _proyeccion_hist(cfg, cal.pct, cal.league_mean, h1, line)
    fila = {
        'proy': proy, 'total': total, 'error': total - proy, 'A': A,
        'side': None, 'apostar': False, 'resultado': None, 'ganancia_u': None,
        'p_side': None, 'odds': None,
    }
    if line is None:
        return fila

    p_over, p_under = probs(line, proy, cal.sigma)
    side = 'OVER' if p_over >= p_under else 'UNDER'
    o = cfg['default_odds'] if g.get('odds') is None else float(g['odds'])
    p, q = max(p_over, p_under), min(p_over, p_under)
    margin = g.get('margin')
    apostar = (p >= cfg['min_prob']
               and abs(proy - line) >= cfg['min_diff']
               and p * (o - 1.0) - q >= cfg['min_ev']
               and cfg['odds_min'] <= o <= cfg['odds_max']
               and (margin is None or margin <= cfg['max_margin']))
    fila.update({'side': side, 'p_side': p, 'odds': o, 'apostar': apostar,
                 'p_over': p_over, 'p_under': p_under})
    if apostar:
        resultado, ganancia = liquidar_apuesta(side, line, total, o)
        fila['resultado'] = resultado
        fila['ganancia_u'] = ganancia
    return fila


# --------------------------------------------------------------------------- #
#  Métricas (hoja Backtest)                                                    #
# --------------------------------------------------------------------------- #
def wilson_intervalo(aciertos: int, n: int, z: float = 1.96):
    """Intervalo de Wilson 95 % del acierto. None si n == 0."""
    if n <= 0:
        return None, None
    p = aciertos / n
    z2 = z * z
    centro = (p + z2 / (2 * n)) / (1 + z2 / n)
    media = z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n)) / (1 + z2 / n)
    return centro - media, centro + media


def metricas(rows: Iterable[dict], cfg: dict) -> dict:
    """Métricas de la hoja Backtest sobre filas con `apostar`, `side`,
    `resultado` (GANA/PIERDE/PUSH) y `ganancia_u`. Los push cuentan en el
    denominador del ROI."""
    filas = list(rows)
    apostadas = [r for r in filas if r.get('apostar')]
    n_apuestas = len(apostadas)
    w = sum(1 for r in apostadas if r.get('resultado') == 'GANA')
    l = sum(1 for r in apostadas if r.get('resultado') == 'PIERDE')
    p_push = sum(1 for r in apostadas if r.get('resultado') == 'PUSH')
    ganancia = sum(r.get('ganancia_u') or 0.0 for r in apostadas)
    decididas = w + l
    acierto = (w / decididas) if decididas else None
    roi = (ganancia / n_apuestas) if n_apuestas else None
    low, high = wilson_intervalo(w, decididas)

    def _acierto_lado(lado: str):
        sub = [r for r in apostadas
               if r.get('side') == lado and r.get('resultado') in ('GANA', 'PIERDE')]
        if not sub:
            return None
        return sum(1 for r in sub if r['resultado'] == 'GANA') / len(sub)

    margenes = [((1 if r.get('side') == 'OVER' else -1)
                 * (r['total'] - r['linea']))
                for r in apostadas
                if r.get('total') is not None and r.get('linea') is not None]
    margen_medio = statistics.fmean(margenes) if margenes else None

    breakeven = 1.0 / cfg['default_odds']
    if decididas < cfg['min_sample']:
        veredicto = 'MUESTRA INSUFICIENTE'
    elif low is not None and low >= cfg['min_prob']:
        veredicto = 'META CUMPLIDA'
    elif acierto is not None and acierto >= cfg['min_prob']:
        veredicto = 'ACIERTO >=60% SIN CONFIANZA ESTADÍSTICA'
    else:
        veredicto = 'POR DEBAJO DE 60%'

    return {
        'n_shadow': len(filas),
        'n_apuestas': n_apuestas, 'w': w, 'l': l, 'push': p_push,
        'ganancia_u': ganancia, 'acierto': acierto, 'roi': roi,
        'breakeven': breakeven, 'wilson_low': low, 'wilson_high': high,
        'acierto_over': _acierto_lado('OVER'),
        'acierto_under': _acierto_lado('UNDER'),
        'margen_medio': margen_medio,
        'veredicto': veredicto,
    }


# --------------------------------------------------------------------------- #
#  Reconstrucción desde histórico de casas (OddsPapi) — solo datos             #
# --------------------------------------------------------------------------- #
def _ts(iso) -> float:
    """Epoch de un timestamp ISO de OddsPapi (tolera 'Z' y microsegundos)."""
    from datetime import datetime
    return datetime.fromisoformat(str(iso).replace('Z', '+00:00')).timestamp()


def linea_principal_descanso(mercado_hist: dict, catalogo_totales: dict,
                             t_corte: float) -> Optional[dict]:
    """Línea principal ACTIVA justo antes del 3Q en el histórico de una casa.

    `mercado_hist`: markets del histórico (ventana completa del evento).
    `catalogo_totales`: {marketId: {handicap, outcomes:[{outcomeId,outcomeName}]}}
    de totales del partido completo ('result'). `t_corte`: epoch del corte.

    Devuelve {'linea', 'over', 'under', 'ts', 'market_id', 'limite'} de la
    línea con el precio two-way más cercano al 50 % (la principal del libro),
    o None si ninguna está activa al corte.
    """
    candidatos = []
    for mid_str, md in (mercado_hist or {}).items():
        mcat = catalogo_totales.get(int(mid_str))
        if not mcat or mcat.get('period') != 'result':
            continue
        ultimos = {}
        for oc in mcat.get('outcomes', []):
            ent = (md.get('outcomes') or {}).get(str(oc['outcomeId']))
            if not ent:
                continue
            entradas = (ent.get('players') or {}).get('0') or []
            ult = None
            for e in entradas:                      # orden no garantizado
                if _ts(e['createdAt']) <= t_corte:
                    if ult is None or _ts(e['createdAt']) > _ts(ult['createdAt']):
                        ult = e
            if ult is None or not ult.get('active'):
                continue
            nombre = (oc.get('outcomeName') or '').lower()
            if nombre == 'over':
                ultimos['over'] = ult
            elif nombre == 'under':
                ultimos['under'] = ult
        if 'over' in ultimos and 'under' in ultimos:
            o, u = ultimos['over']['price'], ultimos['under']['price']
            if not o or not u or o <= 1.0 or u <= 1.0:
                continue
            im_over = (1.0 / o) / ((1.0 / o) + (1.0 / u))
            candidatos.append({
                'linea': float(mcat.get('handicap')), 'over': o, 'under': u,
                'ts': max(ultimos['over']['createdAt'],
                          ultimos['under']['createdAt']),
                'market_id': int(mid_str),
                'limite': max(ultimos['over'].get('limit') or 0,
                              ultimos['under'].get('limit') or 0),
                'im_over': im_over,
            })
    if not candidatos:
        return None
    return min(candidatos, key=lambda c: (round(abs(c['im_over'] - 0.5), 6),
                                          c['linea']))
