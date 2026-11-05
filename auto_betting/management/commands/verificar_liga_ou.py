# -*- coding: utf-8 -*-
"""Verificación de una liga candidata del motor OU descanso (spec de ligas §6).

Para la liga indicada del `LeagueRegistry`:

1. Mide los stats de las compuertas (cobertura de la línea del descanso,
   cobertura de periodos, mismatch de reconciliación, sombras, RMSE, regresión).
2. `--preparar`: calcula la config provisional desde el histórico de
   BasketSample (`config_provisional`) y la guarda en el registro (deja el
   estado como está).
3. `--aplicar`: promueve según compuertas — DISCOVERY→SHADOW (G1) y
   SHADOW→PAPER (G2). **LIVE nunca es automático**: requiere aprobación humana
   explícita (se cambia a mano en el registro).

Uso: manage.py verificar_liga_ou <league_id> [--preparar] [--aplicar]
"""
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from auto_betting import basket_ou as ou
from auto_betting.ligas_ou import stats_liga
from auto_betting.models import BasketSample, LeagueRegistry


def _pct(v, dec=1):
    return 's/d' if v is None else f'{v * 100:.{dec}f}%'


def _num(v, dec=2):
    return 's/d' if v is None else f'{v:+.{dec}f}'


class Command(BaseCommand):
    help = ('Verifica una liga candidata del motor OU (cobertura, '
            'reconciliación, compuertas).')

    def add_arguments(self, parser):
        parser.add_argument('liga', help='league_id del registro (clave del feed)')
        parser.add_argument('--preparar', action='store_true',
                            help='Calcular/guardar config provisional desde BasketSample.')
        parser.add_argument('--aplicar', action='store_true',
                            help='Promover DISCOVERY→SHADOW / SHADOW→PAPER si '
                                 'las compuertas pasan (nunca a LIVE).')

    def handle(self, *args, **opts):
        liga = opts['liga']
        reg = LeagueRegistry.objects.filter(league_id=liga).first()
        if reg is None:
            raise CommandError(f'La liga {liga!r} no está en LeagueRegistry.')

        self.stdout.write(f'═══ Verificación de liga: {liga} ═══')
        self.stdout.write(
            f'Registro: {reg.nombre or liga} · estructura={reg.estructura} · '
            f'estado={reg.estado} · cfg={"propia" if reg.cfg_json else reg.cfg_key or "—"}')

        # 1) Verificación del feed (§6): qué hay capturado y qué falta.
        s = stats_liga(reg)
        self.stdout.write(
            f'Captura en ventana: {s["n_eventos_ventana"]} eventos · '
            f'limpios={s["n_partidos_limpios"]} · '
            f'cobertura línea={_pct(s["cobertura_linea_descanso"])} · '
            f'periodos={_pct(s["cobertura_periodos"])}')
        self.stdout.write(
            f'Reconciliación: mismatch={_pct(s["mismatch_reconciliacion"])} '
            f'(comparables={s["n_reconciliados"]})')
        self.stdout.write(
            f'Motor: sombras={s["n_shadow"]} · apuestas={s["n_paper"]} · '
            f'RMSE modelo={_num(s["rmse_modelo"])} vs línea={_num(s["rmse_linea"])} · '
            f'slope_b={_num(s["slope_b"], 3)} '
            f'[{_num(s["slope_b_lo"], 3)}, {_num(s["slope_b_hi"], 3)}] · '
            f'ROI plano={_pct(s["roi_plano"])}')
        g = s['gates']
        self.stdout.write(f'Compuertas: G1={"OK" if g["G1"] else "NO"} · '
                          f'G2={"OK" if g["G2"] else "NO"} · '
                          f'G3={"OK" if g["G3"] else "NO"} (G3 manual)')
        for nombre, clave in (('G1', 'G1'), ('G2', 'G2')):
            if not g[clave] and g['falta'][clave]:
                self.stdout.write(f'  · falta {nombre}: {g["falta"][clave]}')

        # 2) Config provisional.
        if opts['preparar']:
            hist = [{'total': t} for t in
                    BasketSample.objects.filter(liga=liga, q3__isnull=False,
                                                q4__isnull=False)
                    .values_list('total', flat=True)]
            cfg = ou.config_provisional(liga, hist, reg.estructura)
            if cfg is None:
                self.stdout.write(self.style.WARNING(
                    f'{liga}: sin histórico en BasketSample — no se pudo '
                    'preparar la config provisional.'))
            else:
                reg.cfg_json = cfg
                reg.cfg_version = ou.cfg_version(cfg)
                reg.save(update_fields=['cfg_json', 'cfg_version', 'actualizado'])
                self.stdout.write(self.style.SUCCESS(
                    f'{liga}: config provisional guardada '
                    f'(n_hist={cfg["n_hist"]}, league_avg={cfg["league_avg"]:.1f}, '
                    f'sigma={cfg["sigma_default"]}, min_diff={cfg["min_diff"]}, '
                    f'max_margin={cfg["max_margin"]}, v={reg.cfg_version})'))

        # 3) Promoción por compuertas (nunca LIVE).
        if opts['aplicar']:
            siguiente = ou.siguiente_estado(reg.estado, g)
            if siguiente != reg.estado:
                anterior = reg.estado
                reg.estado = siguiente
                reg.notas = (reg.notas + '\n' if reg.notas else '') + (
                    f'{timezone.now():%Y-%m-%d %H:%M} UTC: promovida '
                    f'{anterior}→{siguiente} por verificar_liga_ou '
                    f'(G1={"OK" if g["G1"] else "NO"}, '
                    f'G2={"OK" if g["G2"] else "NO"}).')
                reg.save(update_fields=['estado', 'notas', 'actualizado'])
                self.stdout.write(self.style.SUCCESS(
                    f'{liga}: estado {anterior} → {siguiente}'))
            else:
                self.stdout.write(f'{liga}: sin cambio de estado '
                                  f'({reg.estado}; siguiente={siguiente}).')
