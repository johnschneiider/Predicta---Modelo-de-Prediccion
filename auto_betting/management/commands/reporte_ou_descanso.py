# -*- coding: utf-8 -*-
"""Reporte ROI del motor OU descanso (SOLO LECTURA).

Replay sobre BasketOuSharp (líneas del descanso reconstruidas del histórico
real de BetPlay/Pinnacle vía OddsPapi) con calibración WALK-FORWARD: cada
partido se evalúa con la calibración calculada SOLO con partidos anteriores a
su fecha (BasketSample), como haría el job nocturno. Usa la versión
Historial/Backtest del spec (`fila_historial`) y las métricas de la hoja
Backtest (`metricas`).

- Tabla principal: líneas/cuotas de BetPlay (la casa del paperbet).
- Anexos: Pinnacle (sharp) y calibración en defaults (sin activar patrones).
- Cross-check contra los snapshots reales capturados por el bot
  (BasketMarketSnapshot, 12-oct+): comparación de la reconstrucción y
  sub-replay con la línea REAL capturada.
- Sombras del bot en vivo ya liquidadas (BasketOuShadow).

Escribe el informe en /root/opencode/reports/ou-descanso-roi-YYYY-MM-DD.md.

Uso: manage.py reporte_ou_descanso [--dias 15] [--desde YYYY-MM-DD]
     [--hasta YYYY-MM-DD] [--salida RUTA] [--sin-archivo]
"""
import pathlib
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting import basket_1q2q as bk
from auto_betting import basket_ou as ou
from auto_betting.models import (BasketMarketSnapshot, BasketOuShadow,
                                 BasketOuSharp)
from auto_betting.management.commands.calibrar_ou import juegos_limpios


def _pct(valor, dec=1):
    return 's/d' if valor is None else f'{valor * 100:.{dec}f}%'


def _linea_metricas(m, etiqueta):
    margen = 's/d' if m['margen_medio'] is None else f"{m['margen_medio']:+.2f}"
    return (
        f"| {etiqueta} | {m['n_shadow']} | {m['n_apuestas']} | "
        f"{m['w']}/{m['l']}/{m['push']} | {_pct(m['acierto'])} | "
        f"{_pct(m['roi'], 2)} | "
        f"{_pct(m['wilson_low'])}–{_pct(m['wilson_high'])} | "
        f"{margen} | {m['veredicto']} |")


class Command(BaseCommand):
    help = 'Reporte ROI del motor OU descanso (replay líneas reales).'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=15)
        parser.add_argument('--desde')
        parser.add_argument('--hasta')
        parser.add_argument('--salida',
                            default='/root/opencode/reports')
        parser.add_argument('--sin-archivo', action='store_true')

    def handle(self, *args, **opts):
        hoy = timezone.now().date()
        hasta = date.fromisoformat(opts['hasta']) if opts['hasta'] else hoy
        desde = (date.fromisoformat(opts['desde']) if opts['desde']
                 else hasta - timedelta(days=opts['dias']))
        self._cache_cal = {}
        self._cache_juegos = {}
        self._cache_snap = {}
        self._cache_total = {}

        filas = [r for r in BasketOuSharp.objects
                 .filter(start_time__isnull=False,
                         start_time__date__gte=desde,
                         start_time__date__lte=hasta)
                 .order_by('start_time')
                 if r.clave_liga in ou.CFG_DE_LIGA]

        tabla = {
            'betplay': [self._evaluar(r, cal='wf', modo='betplay') for r in filas],
            'betplay_def': [self._evaluar(r, cal='def', modo='betplay') for r in filas],
            'pinnacle': [self._evaluar(r, cal='wf', modo='pinnacle') for r in filas],
            'real': [self._evaluar(r, cal='wf', modo='real') for r in filas],
        }
        capturas = self._capturas_propias(desde, hasta, filas)
        tabla_cap = [self._evaluar_captura(c) for c in capturas]

        texto = self._informe(desde, hasta, filas, tabla, opts['dias'],
                              capturas, tabla_cap)
        self.stdout.write(texto)
        if not opts['sin_archivo']:
            carpeta = pathlib.Path(opts['salida'])
            carpeta.mkdir(parents=True, exist_ok=True)
            destino = carpeta / f'ou-descanso-roi-{hoy.isoformat()}.md'
            destino.write_text(texto, encoding='utf-8')
            self.stdout.write(self.style.SUCCESS(f'Informe escrito: {destino}'))

    # ------------------------------------------------------------------ #
    def _cal_para(self, cfg_key, dia):
        key = (cfg_key, dia)
        if key not in self._cache_cal:
            key_j = (cfg_key, dia)
            if key_j not in self._cache_juegos:
                self._cache_juegos[key_j] = juegos_limpios(
                    ou.CAL_LIGAS[cfg_key], fecha_lt=dia)
            self._cache_cal[key] = ou.calibrar(
                self._cache_juegos[key_j], ou.CFG[cfg_key], cfg_key)
        return self._cache_cal[key]

    def _snapshot_real(self, fila):
        if not fila.betplay_evento_id:
            return None
        if fila.betplay_evento_id not in self._cache_snap:
            self._cache_snap[fila.betplay_evento_id] = (
                BasketMarketSnapshot.objects
                .filter(evento_id=fila.betplay_evento_id, linea__isnull=False,
                        cuota_over__isnull=False, cuota_under__isnull=False)
                .order_by('-capturado_en').first())
        return self._cache_snap[fila.betplay_evento_id]

    def _eval_comun(self, cfg_key, calib, g, line, oo, ou_, total_liq, liga):
        """Decisión (fila_historial, 2 pasadas para la cuota del lado) y
        liquidación con el total real del mercado (prórroga incluida)."""
        cfg = ou.CFG[cfg_key]
        fila = {'apostar': False, 'side': None, 'resultado': None,
                'ganancia_u': None, 'total': None, 'linea': line,
                'cfg': cfg_key, 'liga': liga}
        if None in (line, oo, ou_):
            return fila
        prelim = ou.fila_historial(cfg, calib, {**g, 'odds': oo})
        o = oo if prelim['side'] == 'OVER' else ou_
        base = ou.fila_historial(cfg, calib, {**g, 'odds': o})
        total = total_liq if total_liq is not None else base['total']
        fila.update({'side': base['side'], 'apostar': base['apostar'],
                     'p_side': base['p_side'], 'odds': o, 'total': total,
                     'proy': base['proy'], 'diff': base['proy'] - line})
        if base['apostar']:
            res, gan = ou.liquidar_apuesta(base['side'], line, total, o)
            fila['resultado'] = res
            fila['ganancia_u'] = gan
        return fila

    def _evaluar(self, r, cal, modo):
        """Fila para `metricas`. modo: betplay | pinnacle | real."""
        cfg_key = ou.CFG_DE_LIGA[r.clave_liga]
        if cal == 'wf':
            calib = self._cal_para(cfg_key, r.start_time.date())
        else:
            calib = ou.calibracion_inicial(ou.CFG[cfg_key], cfg_key)
        if modo == 'pinnacle':
            line, oo, ou_ = r.pin_linea, r.pin_over, r.pin_under
        elif modo == 'real':
            snap = self._snapshot_real(r)
            line, oo, ou_ = ((snap.linea, snap.cuota_over, snap.cuota_under)
                             if snap else (None, None, None))
        else:
            line, oo, ou_ = r.linea, r.odds_over, r.odds_under
        if None in (r.q1h, r.q1a, r.q2h, r.q2a, r.q3, r.q4):
            return {'apostar': False, 'side': None, 'resultado': None,
                    'ganancia_u': None, 'total': None, 'linea': line,
                    'cfg': cfg_key, 'liga': r.clave_liga}
        g = {'q1': r.q1h + r.q1a, 'q2': r.q2h + r.q2a, 'q3': r.q3, 'q4': r.q4,
             'line': line, 'margin': abs((r.q1h + r.q2h) - (r.q1a + r.q2a))}
        return self._eval_comun(cfg_key, calib, g, line, oo, ou_,
                                r.total_ot if r.total_ot is not None
                                else r.total_reg, r.clave_liga)

    def _total_api(self, home, away, fecha):
        key = (home, away, fecha)
        if key not in self._cache_total:
            try:
                self._cache_total[key] = bk.resultado_oficial(home, away, fecha)
            except Exception:  # noqa: BLE001 — sin API-Sports se omite la fila
                self._cache_total[key] = None
        return self._cache_total[key]

    def _capturas_propias(self, desde, hasta, filas_backfill):
        """Partidos con captura propia del bot (línea/cuotas REALES de BetPlay
        en el descanso) que no están cubiertos por el backfill. Cuartos: solo
        las sumas Q1/Q2 del feed (sin desglose local/visita → sin filtro de
        margen); total de liquidación: API-Sports (prórroga incluida)."""
        ya = {f.betplay_evento_id for f in filas_backfill
              if f.betplay_evento_id}
        qs = (BasketMarketSnapshot.objects
              .filter(capturado_en__date__gte=desde,
                      capturado_en__date__lte=hasta + timedelta(days=1),
                      linea__isnull=False, cuota_over__isnull=False,
                      cuota_under__isnull=False, q1__isnull=False,
                      q2__isnull=False)
              .order_by('capturado_en'))
        ultimas = {}
        for r in qs:
            if r.clave_liga not in ou.CFG_DE_LIGA or r.evento_id in ya:
                continue
            ultimas[r.evento_id] = r        # la última captura válida del descanso
        salen = []
        for r in ultimas.values():
            fecha = (r.start_time or r.capturado_en).date()
            total = self._total_api(r.home_team, r.away_team, fecha)
            if total is None:
                continue
            salen.append({'snap': r, 'total_ot': total})
        return salen

    def _evaluar_captura(self, c):
        r = c['snap']
        cfg_key = ou.CFG_DE_LIGA[r.clave_liga]
        fecha = (r.start_time or r.capturado_en).date()
        calib = self._cal_para(cfg_key, fecha)
        g = {'q1': r.q1, 'q2': r.q2, 'q3': 0.0, 'q4': 0.0,
             'line': r.linea, 'margin': None}
        return self._eval_comun(cfg_key, calib, g, r.linea, r.cuota_over,
                                r.cuota_under, c['total_ot'], r.clave_liga)

    def _bloque(self, titulo, filas_eval, filas_src):
        """Tabla de métricas + desglose por config del replay."""
        filas_eval = [f for f in filas_eval]
        lineas = ([f'### {titulo}', ''] if titulo else []) + [
            '| Corte | n_sh | n_ap | W/L/P | Acierto | ROI plano | Wilson95 | Margen/Línea | Veredicto |',
            '|---|---|---|---|---|---|---|---|---|',
        ]
        global_m = ou.metricas(filas_eval, ou.CFG['EUROPA'])
        lineas.append(_linea_metricas(global_m, 'GLOBAL'))
        for cfg_key in sorted(ou.CFG):
            sub = [f for f in filas_eval if f['cfg'] == cfg_key]
            m = ou.metricas(sub, ou.CFG[cfg_key])
            lineas.append(_linea_metricas(m, cfg_key))
        return '\n'.join(lineas)

    def _crosscheck(self, filas):
        pares = []
        for r in filas:
            snap = self._snapshot_real(r)
            if snap and r.linea is not None:
                pares.append((r, snap))
        if not pares:
            return ('### Cross-check reconstrucción vs captura real\n\n'
                    'Sin partidos con snapshot real capturado en la ventana.\n')
        d_line = [abs(r.linea - s.linea) for r, s in pares]
        sesgo = sum(r.linea - s.linea for r, s in pares) / len(pares)
        ratios_o = [r.odds_over / s.cuota_over for r, s in pares
                    if r.odds_over and s.cuota_over]
        n = len(pares)
        exactos = sum(1 for d in d_line if d < 1e-9)
        le05 = sum(1 for d in d_line if d <= 0.5 + 1e-9)
        le1 = sum(1 for d in d_line if d <= 1.0 + 1e-9)
        le2 = sum(1 for d in d_line if d <= 2.0 + 1e-9)
        ratio = (sum(ratios_o) / len(ratios_o)) if ratios_o else None
        lineas = [
            '### Cross-check reconstrucción vs captura real (Kambi/BetPlay)',
            '',
            f'- Partidos comparables: **{n}**',
            f'- Línea igual: {exactos}/{n} · |Δ|≤0.5: {le05}/{n} · '
            f'|Δ|≤1: {le1}/{n} · |Δ|≤2: {le2}/{n}',
            f'- Sesgo medio (reconstruida − capturada): {sesgo:+.2f} pts',
            f'- Ratio cuota Over reconstruida/capturada: '
            f'{"s/d" if ratio is None else f"{ratio:.4f}"}',
        ]
        return '\n'.join(lineas)

    def _shadows_vivo(self):
        qs = (BasketOuShadow.objects.filter(settled_at__isnull=False)
              .order_by('start_time'))
        if not qs.exists():
            return ('### Sombras del bot en vivo\n\n'
                    'Todavía no hay sombras liquidadas del bot.\n')
        filas = []
        for sh in qs:
            filas.append({
                'apostar': sh.decision.startswith('APOSTAR'), 'side': sh.lado,
                'resultado': sh.resultado or None,
                'ganancia_u': sh.ganancia_u, 'total': sh.total_ot,
                'linea': sh.linea, 'cfg': sh.cfg, 'liga': sh.clave_liga})
        return self._bloque('Sombras del bot en vivo (desde el despliegue)',
                            filas, None)

    def _desglose_ligas(self, filas_eval):
        lineas = [
            '### Por liga (exploratorio — no usar para conclusiones)',
            '',
            '| Liga | n_sh | n_ap | W/L/P | ROI plano | Acierto |',
            '|---|---|---|---|---|---|',
        ]
        ligas = sorted({f['liga'] for f in filas_eval})
        for liga in ligas:
            sub = [f for f in filas_eval if f['liga'] == liga]
            m = ou.metricas(sub, ou.CFG['EUROPA'])
            lineas.append(
                f"| {liga} | {m['n_shadow']} | {m['n_apuestas']} | "
                f"{m['w']}/{m['l']}/{m['push']} | {_pct(m['roi'], 2)} | "
                f"{_pct(m['acierto'])} |")
        return '\n'.join(lineas)

    def _informe(self, desde, hasta, filas, tabla, dias, capturas, tabla_cap):
        cab = f"""# Motor Over/Under al descanso — reporte ROI (paper)

**Ventana:** {desde} → {hasta} · **Partidos con línea reconstruida:** {len(filas)}
**Fuente:** histórico real de casas (OddsPapi) — línea/cuotas del descanso
2Q→3Q reconstruidas como "último estado ACTIVO justo antes del 3Q"; la
principal es la de precio two-way más cercano al 50 %. Calibración
**walk-forward** (solo partidos anteriores a cada fecha, vía BasketSample).
**Liquidación:** total final CON prórroga incluida (regla del mercado BetPlay);
pull el stake plano de 1 u; los push cuentan en el denominador del ROI.
**Limitación:** la reconstrucción puede diferir ±1 pt de la línea viva del
descanso (ver cross-check); muestra chica — ver veredicto.

Datos crudos en `BasketOuSharp`. Regenerable con
`manage.py reporte_ou_descanso --dias {dias}`.

"""
        partes = [cab]
        partes.append(self._bloque(
            'ROI principal — BetPlay (líneas/cuotas del libro objetivo)',
            tabla['betplay'], filas))
        partes.append(self._crosscheck(filas))
        partes.append(self._bloque(
            'Sub-replay con la línea REAL capturada por el bot (12-oct+)',
            tabla['real'], filas))
        partes.append(
            '### Capturas propias del bot — partidos fuera del backfill\n\n'
            f'Partidos con captura del descanso (línea/cuotas REALES de '
            f'BetPlay) sin fila en el backfill: **{len(capturas)}** '
            '(FIBA Europe Cup y NBA pretemporada del 13–14 oct). Cuartos: solo '
            'sumas Q1/Q2 del feed → sin filtro de margen; liquidación con el '
            'total de API-Sports (prórroga incluida).\n\n'
            + self._bloque('', tabla_cap, None))
        partes.append(self._bloque(
            'Anexo — Pinnacle (sharp), mismas decisiones',
            tabla['pinnacle'], filas))
        partes.append(self._bloque(
            'Anexo — BetPlay con calibración en DEFAULTS (sin patrones)',
            tabla['betplay_def'], filas))
        partes.append(self._desglose_ligas(tabla['betplay']))
        partes.append(self._shadows_vivo())
        return '\n\n'.join(partes) + '\n'
