# -*- coding: utf-8 -*-
"""Recalcula la calibración del motor OU descanso (hoja Patron) desde BasketSample.

Guarda una fila por config en BasketOuCalib (versionada con cfg_version). La
última fila vigente es la que usa el bot (`run_paper_bets_ou`). Si la fila más
reciente está `congelada` (regla de oro del experimento: no tocar parámetros
mientras corre el paper), no se recalcula salvo --force.

Solo se usan partidos SANOS con los 4 cuartos y SIN prórroga (el total final
debe coincidir con la suma de la regulación).

Uso: manage.py calibrar_ou [--cfg EUROPA] [--force] [--dry-run]
"""
from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting import basket_ou as ou
from auto_betting.models import BasketOuCalib, BasketSample, LeagueRegistry


def juegos_limpios(ligas, fecha_lt=None):
    """Partidos de BasketSample con 4 cuartos, sin prórroga y sanos."""
    qs = BasketSample.objects.filter(liga__in=ligas, q3__isnull=False,
                                     q4__isnull=False)
    if fecha_lt is not None:
        qs = qs.filter(fecha__lt=fecha_lt)
    return ou.filtrar_juegos_limpios(
        qs.values_list('q1', 'q2', 'q3', 'q4', 'total').iterator())


class Command(BaseCommand):
    help = 'Calibración (Patron) del motor OU descanso desde BasketSample.'

    def add_arguments(self, parser):
        parser.add_argument('--cfg', action='append', choices=sorted(ou.CFG),
                            help='Config a recalcular (default: todas).')
        parser.add_argument('--liga', action='append', default=None,
                            help='league_id del registro (ligas con config '
                                 'propia). Default: todas las del registro.')
        parser.add_argument('--force', action='store_true',
                            help='Recalcular aunque la calibración esté congelada.')
        parser.add_argument('--dry-run', action='store_true')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        for cfg_key in (opts['cfg'] or sorted(ou.CFG)):
            ult = (BasketOuCalib.objects.filter(cfg=cfg_key)
                   .order_by('-calculada_en').first())
            if ult and ult.congelada and not opts['force']:
                self.stdout.write(
                    f'{cfg_key}: calibración CONGELADA '
                    f'({ult.calculada_en:%Y-%m-%d %H:%M}) — se mantiene')
                continue
            ligas = ou.CAL_LIGAS[cfg_key]
            juegos = juegos_limpios(ligas)
            cal = ou.calibrar(juegos, ou.CFG[cfg_key], cfg_key)
            self.stdout.write(
                f'{cfg_key}: n={cal.n} '
                f'pct=({", ".join(f"{v:.4f}" for v in cal.pct)}) '
                f'league_mean={cal.league_mean:.1f} sigma={cal.sigma:.2f} '
                f'({cal.sigma_fuente})'
                + (' [DRY]' if dry else ''))
            if dry:
                continue
            BasketOuCalib.objects.create(
                cfg=cfg_key, calculada_en=timezone.now(), n=cal.n,
                pct_1=cal.pct[0], pct_2=cal.pct[1],
                pct_3=cal.pct[2], pct_4=cal.pct[3],
                league_mean=cal.league_mean, sigma=cal.sigma,
                sigma_fuente=cal.sigma_fuente,
                detalles={'t_stats': list(cal.t_stats),
                          'significativas': list(cal.significativas),
                          'ligas': list(ligas)},
                cfg_version=ou.cfg_version(ou.CFG[cfg_key]))

        # Ligas del registro con config propia (provisional/medida). Cada liga
        # se calibra por separado (spec de ligas: no se mezclan).
        regs = LeagueRegistry.objects.exclude(cfg_json={}).order_by('league_id')
        if opts['liga']:
            regs = regs.filter(league_id__in=opts['liga'])
        for reg in regs:
            if reg.estructura == 'HALVES_2x20':
                self.stdout.write(
                    f'{reg.league_id}: HALVES_2x20 sin muestras de mitades en '
                    'BasketSample — calibración pendiente de cosecha.')
                continue
            ult = (BasketOuCalib.objects.filter(cfg=reg.league_id)
                   .order_by('-calculada_en').first())
            if ult and ult.congelada and not opts['force']:
                self.stdout.write(
                    f'{reg.league_id}: calibración CONGELADA '
                    f'({ult.calculada_en:%Y-%m-%d %H:%M}) — se mantiene')
                continue
            cfg = reg.config_efectiva()
            juegos = juegos_limpios([reg.league_id])
            if not juegos:
                self.stdout.write(f'{reg.league_id}: sin muestras limpias — se omite')
                continue
            cal = ou.calibrar(juegos, cfg, reg.league_id)
            pct = list(cal.pct) + [0.0] * (4 - len(cal.pct))
            self.stdout.write(
                f'{reg.league_id}: n={cal.n} '
                f'pct=({", ".join(f"{v:.4f}" for v in cal.pct)}) '
                f'league_mean={cal.league_mean:.1f} sigma={cal.sigma:.2f} '
                f'({cal.sigma_fuente}, {cfg.get("calibration_mode", "excel_hard")})'
                + (' [DRY]' if dry else ''))
            if dry:
                continue
            BasketOuCalib.objects.create(
                cfg=reg.league_id, calculada_en=timezone.now(), n=cal.n,
                pct_1=pct[0], pct_2=pct[1], pct_3=pct[2], pct_4=pct[3],
                league_mean=cal.league_mean, sigma=cal.sigma,
                sigma_fuente=cal.sigma_fuente,
                detalles={'t_stats': list(cal.t_stats),
                          'significativas': list(cal.significativas),
                          'ligas': [reg.league_id],
                          'estructura': reg.estructura,
                          'modo': cfg.get('calibration_mode', 'excel_hard')},
                cfg_version=ou.cfg_version(cfg))
        self.stdout.write(self.style.SUCCESS('calibrar_ou: listo'))
