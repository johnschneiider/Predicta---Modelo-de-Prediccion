# -*- coding: utf-8 -*-
"""PAPER: motor basket_ou — Over/Under del total (Prórroga incluida) al descanso.

Cada pasada (cron cada 2 min): lee el feed Kambi/BetPlay y, para cada partido en
la ventana del descanso 2Q→3Q, aplica la compuerta de `LeagueRegistry`:

- DISCOVERY: no se toca (la liga aún no cumple G1; se registra el motivo);
- SHADOW: guarda/actualiza la decisión SHADOW, sin registrar apuesta;
- PAPER / LIVE: decisión + apuesta paper si es APOSTAR y no hay previa
  (motor basket_ou, stake plano 1 u = 10000 COP; el stake Kelly va en
  stake_kelly). LIVE nunca se asigna automáticamente: lo aprueba un humano;
- liquida con el total final del feed (prórroga incluida) cuando el partido
  termina (sombras y apuestas, sin importar el estado de la liga).

La config de cada liga sale del registro (`config_efectiva()`): cfg_key a una
config congelada del libro (EUROPA/NBA) o cfg_json propio (provisional/medida).

Uso: manage.py run_paper_bets_ou [--dry-run] [--stake 10000]
"""
from collections import Counter
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from auto_betting import basket_1q2q as bk          # feed Kambi/BetPlay + helpers
from auto_betting import basket_ou as ou            # motor OU descanso
from auto_betting.models import (BasketOuCalib, BasketOuShadow,
                                 LeagueRegistry, PaperBet,
                                 PinnacleSnapshot)

# 2026-10-24: paper reanudado por pedido del humano para acumular muestra.
# Contexto: 22 paper / 26 sombras APOSTAR, ROI -16,8% / -15,6%; no promover
# a dinero real hasta tener muestra suficiente y ROI positivo. La sombra sigue.
PAPER_BETS_ENABLED = True


def calibracion_vigente(cfg_key, cfg):
    """(Calibracion, version) más reciente del DB, o defaults de la config.

    `cfg_key` = clave de calibración (EUROPA/NBA o la liga en el registro).
    BasketOuCalib guarda el patrón en 4 columnas; para estructuras de 2
    periodos solo usan pct_1/pct_2.
    """
    row = (BasketOuCalib.objects.filter(cfg=cfg_key)
           .order_by('-calculada_en').first())
    if row is None:
        return ou.calibracion_inicial(cfg, cfg_key), ''
    pct = (row.pct_1, row.pct_2, row.pct_3, row.pct_4)
    if ou.n_periodos_de(cfg) == 2:
        pct = (row.pct_1, row.pct_2)
    cal = ou.Calibracion(pct=pct, league_mean=row.league_mean,
                         sigma=row.sigma, n=row.n, cfg=cfg_key)
    return cal, cal.version


def _linea_pinnacle(en_ventana):
    """Fallback de fuente: línea al descanso de Pinnacle (The Odds API).

    Sólo interviene en partidos que el feed Kambi llegó SIN mercado de total
    (BetPlay no lo publicó, ej. Nets vs Hornets 2026-10-21): se toma la línea
    y cuotas de `PinnacleSnapshot tipo='break'` (mismo evento, ±6 h).
    Devuelve {evento_id: 'pinnacle'} — Kambi sigue siendo la fuente primaria;
    los partidos no tocados aquí no cambian en nada.
    """
    fuente: dict[str, str] = {}
    limite = timezone.now() - timedelta(hours=6)
    for p in en_ventana:
        if p.linea is not None:
            continue
        pin = (PinnacleSnapshot.objects
               .filter(tipo='break', kambi_event_id=str(p.evento_id),
                       capturado_en__gte=limite,
                       linea__isnull=False, cuota_over__isnull=False,
                       cuota_under__isnull=False)
               .order_by('-capturado_en').first())
        if pin is None:
            continue
        p.linea, p.cuota_over, p.cuota_under = (pin.linea, pin.cuota_over,
                                                pin.cuota_under)
        fuente[str(p.evento_id)] = 'pinnacle'
    return fuente


class Command(BaseCommand):
    help = ('PAPER: Over/Under del total al descanso (motor basket_ou). '
            'Sin dinero real.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Simula y muestra; no escribe nada.')
        parser.add_argument('--stake', type=int, default=ou.STAKE_DEFECTO,
                            help=f'Stake plano virtual COP (default {ou.STAKE_DEFECTO}).')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        self.stdout.write(f"{'🧪 DRY-RUN — ' if dry else ''}"
                          f'Paperbet OU descanso (motor {ou.MOTOR})')
        try:
            partidos = bk.fetch_live_partidos()
        except bk.ErrorBasket as exc:
            self.stderr.write(f'Kambi: {exc}')
            return

        registro = {r.league_id: r for r in LeagueRegistry.objects.all()}
        calibs: dict = {}          # clave de calibración -> (Calibr., version)
        en_ventana = [p for p in partidos if bk.en_ventana_descanso(p)]
        motivos = Counter()
        n_shadow = n_bets = 0
        fuente_linea = _linea_pinnacle(en_ventana)

        for p in en_ventana:
            reg = registro.get(p.clave_liga)
            if reg is None:
                motivos['liga sin registro'] += 1
                continue
            estado = (reg.estado or 'DISCOVERY').upper()
            if estado == 'DISCOVERY':
                motivos['liga en DISCOVERY (sin captura)'] += 1
                continue
            cfg = reg.config_efectiva()
            if not cfg:
                motivos['liga sin config'] += 1
                continue
            # Clave de calibración y de la sombra: cfg_key (EUROPA/NBA) o la liga.
            cfg_key = reg.clave_calibracion()
            if cfg_key not in calibs:
                calibs[cfg_key] = calibracion_vigente(cfg_key, cfg)
            cal, cal_ver = calibs[cfg_key]
            splits = ou.parsear_cuartos_split(p.info_cuartos)
            q1 = splits.get('Q1', (None, None))
            q2 = splits.get('Q2', (None, None))
            inp = dict(q1h=q1[0], q1a=q1[1], q2h=q2[0], q2a=q2[1],
                       line=p.linea, odds_over=p.cuota_over,
                       odds_under=p.cuota_under)
            d = ou.decidir(cfg, cal, inp)
            if fuente_linea.get(str(p.evento_id)):
                d['filtros'] = dict(d['filtros'],
                                    fuente=fuente_linea[str(p.evento_id)])

            if dry:
                extra = (f' proy={d["proy"]:.1f} diff={d["diff"]:+.1f}'
                         if d['proy'] is not None else '')
                origen = (f' [fuente={d["filtros"]["fuente"]}]'
                          if 'fuente' in d['filtros'] else '')
                self.stdout.write(
                    f'  · [DRY] {p.clave_liga}: {p.local} vs {p.visitante} '
                    f'q1={q1} q2={q2} linea={p.linea} O={p.cuota_over} '
                    f'U={p.cuota_under} → {d["decision"]}{extra}{origen}')
                if d['decision'].startswith('APOSTAR'):
                    n_bets += 1
                continue

            n_shadow += self._guardar_shadow(p, cfg_key, cfg, cal_ver, d, splits)
            if d['decision'].startswith('APOSTAR'):
                if estado == 'SHADOW':
                    # Compuerta: la liga aún no tiene aprobada la apuesta paper.
                    motivos['shadow: decisión sin apuesta'] += 1
                elif not PAPER_BETS_ENABLED:
                    motivos['paper detenido (solo sombra)'] += 1
                elif PaperBet.objects.filter(motor=ou.MOTOR,
                                             evento_id=str(p.evento_id)).exists():
                    motivos['apuesta ya registrada'] += 1
                else:
                    self._crear_apuesta(p, d, opts['stake'])
                    n_bets += 1
            else:
                motivos[d['decision']] += 1

        n_feed = 0 if dry else self._liquidar_feed(partidos)
        self.stdout.write(
            f'Partidos en ventana: {len(en_ventana)} · '
            f'sombras actualizadas: {n_shadow} · '
            f'apuestas {"simuladas" if dry else "registradas"}: {n_bets} · '
            f'liquidaciones feed: {n_feed}')
        for motivo, n in motivos.most_common():
            self.stdout.write(f'  · {motivo}: {n}')

    # ------------------------------------------------------------------ #
    @staticmethod
    def _inicio(p):
        return (parse_datetime((p.inicio or '').replace('Z', '+00:00'))
                or timezone.now())

    def _guardar_shadow(self, p, cfg_key, cfg, cal_ver, d, splits):
        """Upsert por evento: queda la decisión del ÚLTIMO snapshot válido."""
        evento = str(p.evento_id)
        if p.linea is None:
            return 0                       # sin línea no hay snapshot válido
        sh = BasketOuShadow.objects.filter(evento_id=evento).first()
        if sh is None:
            sh = BasketOuShadow(evento_id=evento)
        sh.n_snapshots = (sh.n_snapshots or 0) + 1
        sh.start_time = self._inicio(p)
        sh.liga = p.liga_nombre or p.clave_liga
        sh.clave_liga = p.clave_liga
        sh.cfg = cfg_key
        sh.home_team, sh.away_team = p.local, p.visitante

        q1 = splits.get('Q1', (None, None))
        q2 = splits.get('Q2', (None, None))
        completo = (None not in q1 and None not in q2
                    and p.cuota_over is not None and p.cuota_under is not None)
        if completo:
            sh.q1h, sh.q1a, sh.q2h, sh.q2a = q1[0], q1[1], q2[0], q2[1]
            sh.linea, sh.odds_over, sh.odds_under = (p.linea, p.cuota_over,
                                                     p.cuota_under)
            sh.margen = d['margin']
            sh.proy, sh.diff, sh.sigma = d['proy'], d['diff'], d['sigma']
            sh.p_over, sh.p_under = d['p_over'], d['p_under']
            sh.ev_over, sh.ev_under = d['ev_over'], d['ev_under']
            sh.lado = d['side'] or ''
            sh.p_side, sh.ev_side = d['p_side'], d['ev_side']
            sh.odds_side = d['odds_side']
            sh.stake_kelly = round(d['stake'], 4)
            sh.filtros = d['filtros']
            sh.decision = d['decision']
            sh.cfg_version = ou.cfg_version(cfg)
            sh.cal_version = cal_ver
        sh.save()
        return 1

    def _crear_apuesta(self, p, d, stake):
        PaperBet.objects.create(
            evento_id=str(p.evento_id),
            start_time=self._inicio(p),
            home_team=p.local,
            away_team=p.visitante,
            liga=p.liga_nombre or p.clave_liga,
            mercado=ou.MERCADO,
            motor=ou.MOTOR,
            seleccion=(ou.SEL_OVER if d['side'] == 'OVER' else ou.SEL_UNDER),
            linea=p.linea,
            diferencia=round(d['diff'], 2),
            cuota=d['odds_side'],
            prob=round(d['p_side'], 4),
            ev=round(d['ev_side'], 4),
            stake=stake,
            stake_kelly=round(d['stake'], 4),
        )

    def _liquidar_feed(self, partidos):
        """Liquida apuestas OPEN y sombras con el total final del feed
        (prórroga incluida, regla del mercado en BetPlay)."""
        por_id = {str(p.evento_id): p for p in partidos
                  if p.finalizado and p.total_final is not None}
        if not por_id:
            return 0
        n = 0
        for bet in PaperBet.objects.filter(motor=ou.MOTOR, estado='OPEN',
                                           evento_id__in=list(por_id)):
            p = por_id[bet.evento_id]
            total = float(p.total_final)
            estado = bk.liquidar(bet.seleccion, bet.linea, total)
            if estado == 'VOID':
                payout, resultado = float(bet.stake), f'{total:g} · push kambi'
            else:
                payout = bet.stake * bet.cuota if estado == 'WON' else 0.0
                resultado = f'{total:g} · kambi'
            PaperBet.objects.filter(pk=bet.pk, estado='OPEN').update(
                estado=estado, resultado_real=resultado,
                payout=round(payout, 2), settled_at=timezone.now())
            n += 1

        sombras = (BasketOuShadow.objects
                   .filter(evento_id__in=list(por_id), settled_at__isnull=True)
                   .exclude(lado=''))
        for sh in sombras:
            p = por_id[sh.evento_id]
            total = float(p.total_final)
            reg = None
            if None not in (p.q1, p.q2, p.q3, p.q4):
                reg = float(p.q1) + float(p.q2) + float(p.q3) + float(p.q4)
            res, gan = ou.liquidar_apuesta(sh.lado, sh.linea, total,
                                           sh.odds_side)
            BasketOuShadow.objects.filter(pk=sh.pk,
                                          settled_at__isnull=True).update(
                total_reg=reg, total_ot=total, resultado=res,
                ganancia_u=(None if gan is None else round(gan, 4)),
                settled_at=timezone.now())
            n += 1
        return n
