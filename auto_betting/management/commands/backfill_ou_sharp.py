# -*- coding: utf-8 -*-
"""Backfill de líneas del descanso para el motor OU (OddsPapi, solo datos).

Reconstruye, para cada partido ya finalizado de los torneos del motor OU
(Euroliga, EuroCup, Europe Cup, NBA y NBA-pretemporada), la línea y cuotas
principales ACTIVAS justo antes del 3Q — de BetPlay (casa objetivo del
paperbet) y de Pinnacle (referencia sharp) — y las guarda en BasketOuSharp.

Cuota del plan free de OddsPapi: 250 req/periodo. `historical-odds` es GRATIS;
`fixtures` (1 llamada para toda la ventana si ≤10 días) y `scores` (1 por
partido) consumen. Idempotente por api_fixture_id (--refrescar rehace;
--re-seleccionar solo re-elige líneas ya guardadas, sin gastar cuota por
partido).

Uso: manage.py backfill_ou_sharp [--dias 3] [--desde YYYY-MM-DD]
     [--hasta YYYY-MM-DD] [--refrescar] [--re-seleccionar] [--dry-run]
"""
import os
import time
from datetime import date, datetime, timedelta

import requests
from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting import basket_1q2q as bk
from auto_betting import basket_ou as ou
from auto_betting.models import BasketMarketSnapshot, BasketOuSharp

BASE = 'https://api.oddspapi.io/v4'
PAUSA_FIXTURES = 3.0      # cooldown del endpoint (2000 ms)
PAUSA_SCORES = 3.0
PAUSA_HIST = 40.0         # rate-limit real medido 2026-10-15: ~1 llamada/30-40s
                          # margen (visto rate-limit 2026-10-15 a ~5.5 s)
RUTA_ENV = '/var/www/predicta.com.co/.env'


class ErrorOdds(Exception):
    """OddsPapi no respondió o respondió con errores."""


def _api_key():
    key = os.environ.get('ODDS_API_IO_KEY')
    if key:
        return key
    with open(RUTA_ENV, encoding='utf-8') as fh:
        for linea in fh:
            if linea.strip().startswith('ODDS_API_IO_KEY='):
                return linea.split('=', 1)[1].strip().strip('"').strip("'")
    raise ErrorOdds('ODDS_API_IO_KEY no encontrada (.env)')


def api_get(ruta, **params):
    params['apiKey'] = _api_key()
    for intento in (1, 2, 3):
        r = requests.get(f'{BASE}/{ruta}', params=params, timeout=60)
        if r.status_code == 429:
            if 'REQUEST_LIMIT_EXCEEDED' in r.text:
                raise ErrorOdds('Cuota mensual agotada: ' + r.text[:120])
            if intento < 3:
                time.sleep(300)          # rate-limit temporal: esperar (bucket lento)
                continue
        break
    if r.status_code != 200:
        raise ErrorOdds(f'OddsPapi HTTP {r.status_code} en /{ruta}: '
                        f'{r.text[:150]}')
    return r.json()


def _ts(iso):
    return datetime.fromisoformat(str(iso).replace('Z', '+00:00'))


class Command(BaseCommand):
    help = 'Reconstruye líneas del descanso (BetPlay/Pinnacle) desde OddsPapi.'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=3,
                            help='Tamaño de la ventana hacia atrás (default 3).')
        parser.add_argument('--desde', help='YYYY-MM-DD (reemplaza --dias).')
        parser.add_argument('--hasta', help='YYYY-MM-DD (default: hoy).')
        parser.add_argument('--refrescar', action='store_true',
                            help='Rehacer partidos que ya tienen fila.')
        parser.add_argument('--re-seleccionar', action='store_true',
                            help='Solo re-elegir la línea de filas existentes '
                                 '(historical-odds es gratis; usa t_q3 o '
                                 't_descanso+14min).')
        parser.add_argument('--todas', action='store_true',
                            help='Con --re-seleccionar: rehacer también las '
                                 'filas que ya tienen corte exacto (t_q3).')
        parser.add_argument('--torneo',
                            help='Limitar a un tournamentSlug (p. ej. '
                                 'nba-preseason, euroleague).')
        parser.add_argument('--limite', type=int, default=0,
                            help='Máximo de partidos NUEVOS a procesar en la '
                                 'corrida (protege la cuota free de 250/mes; '
                                 '0 = sin límite).')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        if opts['re_seleccionar']:
            self._re_seleccionar(dry, opts_todas=opts['todas'])
            return
        hasta = (date.fromisoformat(opts['hasta']) if opts['hasta']
                 else timezone.now().date())
        desde = (date.fromisoformat(opts['desde']) if opts['desde']
                 else hasta - timedelta(days=opts['dias']))
        self.stdout.write(f'Backfill OU sharp {desde} → {hasta}'
                          f'{" [DRY]" if dry else ""}')

        catalogo = self._catalogo_totales()
        fixtures = self._fixtures_ventana(desde, hasta)
        objetivos = [f for f in fixtures
                     if f.get('tournamentId') in ou.TORNEOS_ODDSPAPI]
        if opts['torneo']:
            objetivos = [f for f in objetivos
                         if f.get('tournamentSlug') == opts['torneo']]
        prioridad = {tid: i for i, tid in enumerate(ou.TORNEOS_ODDSPAPI)}
        objetivos.sort(key=lambda f: (prioridad.get(f.get('tournamentId'), 99),
                                      f.get('startTime') or ''))
        self.stdout.write(f'  fixtures en torneos del motor: {len(objetivos)}')

        n_new = n_skip = n_err = intentos = 0
        for f in objetivos:
            if f.get('statusId') != 2:        # solo terminados
                continue
            liga = ou.TORNEOS_ODDSPAPI[f['tournamentId']]
            if liga not in ou.CFG_DE_LIGA:
                continue
            fid = f['fixtureId']
            if not opts['refrescar'] and BasketOuSharp.objects.filter(
                    api_fixture_id=fid, linea__isnull=False).exists():
                n_skip += 1
                continue
            if opts['limite'] and intentos >= opts['limite']:
                self.stdout.write(f"  límite de {opts['limite']} partidos "
                                  'nuevos por corrida alcanzado; se corta')
                break
            intentos += 1
            try:
                fila = self._procesar(f, liga, catalogo, dry)
            except ErrorOdds as exc:
                self.stderr.write(f'{fid}: {exc}')
                n_err += 1
                continue
            if fila is None:
                n_skip += 1
                continue
            n_new += 1
            self.stdout.write(
                f"  · {liga}: {fila.get('home_team')} vs "
                f"{fila.get('away_team')} — BetPlay "
                f"{fila.get('linea')} O={fila.get('odds_over')} "
                f"U={fila.get('odds_under')} · Pinnacle "
                f"{fila.get('pin_linea')} ({fila.get('t_descanso'):%d-%m %H:%M})"
                + (' [DRY]' if dry else ''))

        self.stdout.write(
            f'Backfill: {n_new} partidos {"simulados" if dry else "guardados"} · '
            f'{n_skip} saltados · {n_err} errores')

    # ------------------------------------------------------------------ #
    def _catalogo_totales(self):
        """{marketId: mercado} de totales del partido completo (period result)."""
        mercados = api_get('markets', language='en')
        return {m['marketId']: m for m in mercados
                if m.get('sportId') == 11 and m.get('marketType') == 'totals'}

    @staticmethod
    def _fixtures_api(**params):
        """fixtures tolerando el 404 'No fixtures found' (torneo sin partidos)."""
        try:
            return list(api_get('fixtures', **params) or [])
        except ErrorOdds as exc:
            if '404' in str(exc) or 'FIXTURE_NOT_FOUND' in str(exc):
                return []
            raise

    def _fixtures_ventana(self, desde, hasta):
        """Fixtures de basketball de la ventana. 1 llamada si ≤10 días
        (sportId+from+to); si no, una por torneo."""
        rango = {'from': desde.isoformat(), 'to': hasta.isoformat()}
        if (hasta - desde).days <= 10:
            fx = self._fixtures_api(sportId=11, **rango)
            time.sleep(PAUSA_FIXTURES)
            return fx
        todos = []
        for tid in ou.TORNEOS_ODDSPAPI:
            fx = self._fixtures_api(tournamentId=tid, **rango)
            time.sleep(PAUSA_FIXTURES)
            todos.extend(fx)
        return todos

    def _procesar(self, f, liga, catalogo, dry):
        fid = f['fixtureId']
        sc = api_get('scores', fixtureId=fid)
        time.sleep(PAUSA_SCORES)
        per = (((sc or {}).get('scores') or {}).get('periods')) or {}
        if not all(k in per for k in ('p1', 'p2', 'p3')):
            return None
        q1h, q1a = per['p1']['participant1Score'], per['p1']['participant2Score']
        q2h, q2a = per['p2']['participant1Score'], per['p2']['participant2Score']
        q3 = per['p3']['participant1Score'] + per['p3']['participant2Score']
        q4 = ((per['p4']['participant1Score'] + per['p4']['participant2Score'])
              if 'p4' in per else None)
        total_reg = None
        if q4 is not None:
            total_reg = q1h + q1a + q2h + q2a + q3 + q4
        fin = per.get('result') or per.get('fulltime')
        total_ot = (fin['participant1Score'] + fin['participant2Score']
                    if fin else None)
        t_descanso = _ts(per['p2']['updatedAt'])
        # OJO: en este feed, periods[pN].startedAt = arranque del periodo
        # SIGUIENTE; el 3Q arranca en p2.startedAt (validado 2026-10-15 contra
        # los snapshots propios). Fallback: fin del 2Q + 14 min (medio descanso).
        t_q3 = (_ts(per['p2']['startedAt']) if per['p2'].get('startedAt')
                else t_descanso + timedelta(minutes=14))

        hist = api_get('historical-odds', fixtureId=fid,
                       bookmakers='betplay,pinnacle')
        time.sleep(PAUSA_HIST)
        bms = (hist or {}).get('bookmakers') or {}
        sel_bp = ou.linea_principal_descanso(
            ((bms.get('betplay') or {}).get('markets')) or {},
            catalogo, t_q3.timestamp())
        sel_pin = ou.linea_principal_descanso(
            ((bms.get('pinnacle') or {}).get('markets')) or {},
            catalogo, t_q3.timestamp())
        if sel_bp is None and sel_pin is None:
            return None

        inicio = _ts(f['startTime']) if f.get('startTime') else None
        evento_id = self._match_snapshot(f, liga, inicio)
        datos = dict(
            fuente='oddspapi', torneo=f.get('tournamentSlug', ''),
            clave_liga=liga, cfg=ou.CFG_DE_LIGA.get(liga, ''),
            home_team=f.get('participant1Name', ''),
            away_team=f.get('participant2Name', ''),
            start_time=inicio, t_descanso=t_descanso, t_q3=t_q3,
            q1h=q1h, q1a=q1a, q2h=q2h, q2a=q2a, q3=q3, q4=q4,
            total_reg=total_reg, total_ot=total_ot,
            linea=(sel_bp or {}).get('linea'),
            odds_over=(sel_bp or {}).get('over'),
            odds_under=(sel_bp or {}).get('under'),
            pin_linea=(sel_pin or {}).get('linea'),
            pin_over=(sel_pin or {}).get('over'),
            pin_under=(sel_pin or {}).get('under'),
            betplay_evento_id=evento_id or '',
        )
        if not dry:
            BasketOuSharp.objects.update_or_create(
                api_fixture_id=fid, defaults=datos)
        return datos

    def _re_seleccionar(self, dry, opts_todas=False):
        """Recalcula línea/cuotas de filas existentes con el mejor corte
        conocido (t_q3; si no, t_descanso+14min). historical-odds es gratis."""
        catalogo = self._catalogo_totales()
        time.sleep(PAUSA_FIXTURES)
        qs = BasketOuSharp.objects.order_by('start_time')
        if not opts_todas:
            qs = qs.filter(t_q3__isnull=True)   # solo filas sin corte exacto
        n = n_skip = n_err = 0
        for row in qs:
            if row.t_descanso is None:
                n_skip += 1
                continue
            t_corte = row.t_q3 or (row.t_descanso + timedelta(minutes=14))
            try:
                hist = api_get('historical-odds', fixtureId=row.api_fixture_id,
                               bookmakers='betplay,pinnacle')
            except ErrorOdds as exc:
                self.stderr.write(f'{row.api_fixture_id}: {exc}')
                n_err += 1
                continue
            time.sleep(PAUSA_HIST)
            bms = (hist or {}).get('bookmakers') or {}
            sel_bp = ou.linea_principal_descanso(
                ((bms.get('betplay') or {}).get('markets')) or {},
                catalogo, t_corte.timestamp())
            sel_pin = ou.linea_principal_descanso(
                ((bms.get('pinnacle') or {}).get('markets')) or {},
                catalogo, t_corte.timestamp())
            if sel_bp is None and sel_pin is None:
                n_skip += 1
                continue
            cambios = {}
            if sel_bp:
                cambios.update(linea=sel_bp['linea'], odds_over=sel_bp['over'],
                               odds_under=sel_bp['under'])
            if sel_pin:
                cambios.update(pin_linea=sel_pin['linea'],
                               pin_over=sel_pin['over'],
                               pin_under=sel_pin['under'])
            self.stdout.write(
                f'  · {row.clave_liga}: {row.home_team} vs {row.away_team} — '
                f"BetPlay {cambios.get('linea')} "
                f"O={cambios.get('odds_over')} U={cambios.get('odds_under')} · "
                f"Pinnacle {cambios.get('pin_linea')}"
                + (' [DRY]' if dry else ''))
            if not dry:
                BasketOuSharp.objects.filter(pk=row.pk).update(**cambios)
            n += 1
        self.stdout.write(f'Re-seleccionados: {n} · {n_skip} sin cambio · '
                          f'{n_err} errores{" (dry)" if dry else ""}')

    @staticmethod
    def _match_snapshot(f, liga, inicio):
        """evento_id Kambi (BasketMarketSnapshot) del mismo partido, si existe."""
        if inicio is None:
            return ''
        ventana = timedelta(hours=4)
        qs = (BasketMarketSnapshot.objects
              .filter(clave_liga=liga,
                      start_time__gte=inicio - ventana,
                      start_time__lte=inicio + ventana)
              .values('evento_id', 'home_team', 'away_team')
              .distinct())
        a_local = bk._norm(f.get('participant1Name', ''))
        a_vis = bk._norm(f.get('participant2Name', ''))
        for row in qs:
            s = min(bk._parecido(a_local, bk._norm(row['home_team'])),
                    bk._parecido(a_vis, bk._norm(row['away_team'])))
            if s >= 0.5:
                return row['evento_id']
        return ''
