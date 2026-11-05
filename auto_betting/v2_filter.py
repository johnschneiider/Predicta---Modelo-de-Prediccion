# -*- coding: utf-8 -*-
"""
Filtro V2 — regla de apuestas real (2026-10-03, pedido de John).

Deja pasar SOLO combinaciones liga × mercado × día con ROI positivo observado
(backtest walk-forward motores de producción ene-2025→sep-2026 + sistema real
ago-sep-2026). Incluye celdas con ruido por decisión explícita del usuario;
la lista es editable desde /auto-betting/configuracion/v2/ (auditoría semanal).

Formato del texto de reglas (una por línea):
    liga | mercado | días
    liga:    nombre exacto (ej. "Serie A") o * (cualquiera)
    mercado: clave de submercado (goals_over, x12, btts_si, remates_over,
             corners_over, corners_under, shots_on_target_over,
             shots_on_target_under, ...) o *
    días:    lun,mar,mié,jue,vie,sáb,dom  o *
Las líneas vacías o con # se ignoran.
"""
import unicodedata

DAY_TOKENS = {
    'lun': 0, 'lunes': 0, '0': 0,
    'mar': 1, 'martes': 1, '1': 1,
    'mie': 2, 'mié': 2, 'miercoles': 2, 'miércoles': 2, '2': 2,
    'jue': 3, 'jueves': 3, '3': 3,
    'vie': 4, 'viernes': 4, '4': 4,
    'sab': 5, 'sáb': 5, 'sabado': 5, 'sábado': 5, '5': 5,
    'dom': 6, 'domingo': 6, '6': 6,
}

DEFAULT_RULES = """# ═══ FILTRO V2 — regla de apuestas real (2026-10-03) ═══
# Formato: liga | mercado | días   (una por línea; # comenta)
# Fuente: backtest motores producción ene-2025→sep-2026 + sistema real ago-sep-2026.
# Incluye celdas con ruido (decisión John). Auditar semanalmente.

# ── BLOQUEOS por lado (2026-10-31, '!' = precedencia sobre todo) ──
# BTTS 'No': WR 46% real (85W/100L), ROI -11,9% → lado perdedor.
# x12 '1' (local): WR 43% real (23W/30L) → lado perdedor.
! * | btts_no | *
! * | x12_1 | *

# ── x12 por liga×día (backtest escala, 5 ligas; solo lados 2 y X) ──
Premier League | x12_2 | sáb,mar,mié
Premier League | x12_x | sáb,mar,mié
Serie A | x12_2 | sáb,jue,vie
Serie A | x12_x | sáb,jue,vie
Ligue 1 | x12_2 | sáb,vie
Ligue 1 | x12_x | sáb,vie
Eredivisie | x12_2 | sáb,mié
Eredivisie | x12_x | sáb,mié
Super League | x12_2 | sáb,lun,mar,jue
Super League | x12_x | sáb,lun,mar,jue

# ── goles over por liga×día (backtest escala) ──
Premier League | goals_over | mar,sáb
Serie A | goals_over | lun
Eredivisie | goals_over | sáb,dom

# ── sistema real: mercado×día (todas las ligas) ──
* | btts_si | mar,mié,sáb
* | remates_over | lun,jue,vie,sáb,dom
* | goals_over | vie
* | x12_2 | lun,mar
* | x12_x | lun,mar
* | corners_over | mar,jue,sáb,dom
* | corners_under | mar,jue,sáb,dom
* | shots_on_target_over | mié,jue,vie
* | shots_on_target_under | mié,jue,vie

# ── sistema real: liga×mercado×día ──
Serie A | btts_si | sáb
Serie A | remates_over | lun,vie,sáb
Serie A | goals_over | sáb,dom
Eredivisie | remates_over | sáb,dom
Eredivisie | goals_over | sáb,dom
Eredivisie | shots_on_target_over | sáb,dom
Eredivisie | shots_on_target_under | sáb,dom
Ligue 1 | goals_over | vie,sáb
Premier League | remates_over | sáb,dom
Premier League | goals_over | mar
Premier League | shots_on_target_over | sáb,dom
Premier League | shots_on_target_under | sáb,dom
Super League | goals_over | mar

# ── ligas con ROI total positivo en el sistema real (todas sus apuestas) ──
Liga Dos | * | *
PFL 1 | * | *
Championship | * | *
Liga MX | * | *
Liga Profesional Argentina | * | *
La Liga | * | *
Brasileirao Serie B | * | *
MLS | * | *
Primeira Liga | * | *
Super League | * | *
"""


def _norm(s):
    s = unicodedata.normalize('NFKD', str(s or ''))
    s = ''.join(c for c in s if not unicodedata.combining(c)).lower().strip()
    return ' '.join(s.split())


# Mapeo lado interno → sufijo de submercado (idéntico a strategy._SIDE_KEY_SUFFIX)
# 2026-10-31: se añaden los lados x12 ('1','X','2') para poder filtrar por lado
# (ej. x12_1 = local). Los rules existentes 'x12' (sin lado) dejan de matchear
# con las claves nuevas: las reglas deben escribirse como x12_1/x12_x/x12_2.
_SIDE_SUFFIX = {'over': 'over', 'under': 'under', 'Sí': 'si', 'No': 'no', 'si': 'si', 'no': 'no',
                '1': '1', '2': '2', 'X': 'x', 'x': 'x'}


def submarket_key(mercado, side):
    """Clave de submercado usada por el filtro (ej. ('remates','over')→'remates_over').
    Para x12 (side None) la clave es el mercado tal cual."""
    suffix = _SIDE_SUFFIX.get(side)
    return f"{mercado}_{suffix}" if suffix else mercado


def _parse_days(token):
    token = token.strip().lower()
    if token in ('*', 'todos', 'all'):
        return '*'
    days = set()
    for part in token.replace(';', ',').split(','):
        part = part.strip()
        if not part:
            continue
        if part in DAY_TOKENS:
            days.add(DAY_TOKENS[part])
        else:
            # intentar sin acentos
            p2 = _norm(part)
            if p2 in DAY_TOKENS:
                days.add(DAY_TOKENS[p2])
            else:
                raise ValueError(f"día no reconocido: '{part}'")
    return days if days else '*'


def parse_rules(text):
    """Devuelve (reglas, errores). Cada regla = (liga_norm|None, mercado_norm|None, set|'*', bloquear).

    Prefijo '!' al inicio de la línea = regla de BLOQUEO (tiene precedencia
    sobre cualquier allow, incluidas las ligas con mercado/días '*')."""
    rules = []
    errors = []
    for i, line in enumerate((text or '').splitlines(), 1):
        raw = line.strip()
        if not raw or raw.startswith('#'):
            continue
        bloquear = False
        if raw.startswith('!'):
            bloquear = True
            raw = raw[1:].strip()
        parts = [p.strip() for p in raw.split('|')]
        if len(parts) != 3:
            errors.append(f"línea {i}: se esperan 3 campos separados por | → '{raw[:60]}'")
            continue
        liga, mercado, dias = parts
        try:
            d = _parse_days(dias)
        except ValueError as e:
            errors.append(f"línea {i}: {e}")
            continue
        rules.append((None if liga == '*' else _norm(liga),
                      None if mercado == '*' else _norm(mercado), d, bloquear))
    return rules, errors


def load_config():
    """Devuelve (activo, texto_reglas, objeto). Crea el singleton si no existe."""
    from auto_betting.models import BettingFilterV2
    obj, created = BettingFilterV2.objects.get_or_create(
        pk=1, defaults={'activo': True, 'reglas': DEFAULT_RULES})
    if created or not (obj.reglas or '').strip():
        obj.reglas = DEFAULT_RULES
        obj.save(update_fields=['reglas'])
    return obj.activo, obj.reglas, obj


def v2_activo():
    activo, text, _ = load_config()
    return bool(activo)


def is_allowed(liga, mercado, local_dt):
    """True si la combinación liga×mercado×día pasa el filtro v2.

    Las reglas de BLOQUEO ('!' al inicio) se evalúan primero y tienen
    precedencia sobre cualquier allow (incluidas ligas con '*' en todo)."""
    activo, text, _ = load_config()
    if not activo:
        return True
    rules, _ = parse_rules(text)
    if not rules:
        return True  # sin reglas válidas, no bloquear (fail-open)
    ln = _norm(liga)
    mn = _norm(mercado)
    wd = local_dt.weekday()
    for rl, rm, rd, bloquear in rules:
        if not bloquear:
            continue
        if rl is not None and rl != ln:
            continue
        if rm is not None and rm != mn:
            continue
        if rd == '*' or wd in rd:
            return False
    for rl, rm, rd, bloquear in rules:
        if bloquear:
            continue
        if rl is not None and rl != ln:
            continue
        if rm is not None and rm != mn:
            continue
        if rd == '*' or wd in rd:
            return True
    return False
