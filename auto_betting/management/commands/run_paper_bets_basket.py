# -*- coding: utf-8 -*-
"""PAPER: motor basket_1q2q — totales de baloncesto (1Q+2Q) en el descanso.

Revisa el feed Kambi/BetPlay y, para cada partido en el descanso 2Q→3Q con
modelo propio de su liga, aplica la compuerta en modo muestreo (2026-10-13):
Δ sin tope y SIN filtro de EV (pasan todos los partidos en ventana con
cuota viva; Δ y EV se guardan para trazabilidad). Si pasa, registra un
PaperBet (sin dinero real). Deduplicado por evento.

Uso: manage.py run_paper_bets_basket [--dry-run] [--stake 10000]
"""
import json
from collections import Counter
from datetime import timedelta
from zoneinfo import ZoneInfo

from django.core.management.base import BaseCommand
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from auto_betting import basket_1q2q as bk
from auto_betting import basket_pinnacle as bp
from auto_betting.models import (BasketMarketSnapshot, BasketModel,
                                 BasketSample, PaperBet)

# Filtro liga x dia (2026-10-31, pre-registrado): el motor opera SOLO en las
# celdas liga x dia de la semana (America/Bogota) con ROI>0 in-sample y >=5
# liquidadas. Whitelist estatica congelada; NO se recalcula dinamicamente.
FILTRO_LIGADIA_JSON = ('/var/www/predicta.com.co/scripts/paperbet/'
                       'basket_1q2q_filtro_ligadia.json')
ZONA_BOG = ZoneInfo('America/Bogota')
NOMBRE_DIA = ['Lun', 'Mar', 'Mie', 'Jue', 'Vie', 'Sab', 'Dom']


def cargar_filtro_ligadia():
    """Devuelve set[(liga, weekday)] o None si no hay filtro configurado."""
    try:
        with open(FILTRO_LIGADIA_JSON, encoding='utf-8') as f:
            data = json.load(f)
        celdas = {(c['liga'], int(c['dia']))
                  for c in data.get('celdas', [])}
        return celdas if celdas else None
    except Exception:  # noqa: BLE001
        return None


def modelo_de(m: BasketModel) -> bk.Modelo:
    return bk.Modelo(
        liga=m.liga, origen=m.origen, n=m.n,
        b0=m.b0, b1=m.b1, b2=m.b2, a0=m.a0, a1=m.a1,
        r2_dos=m.r2_dos, r2_uno=m.r2_uno,
        rmse_dos=m.rmse_dos, rmse_uno=m.rmse_uno, rmse_naive=m.rmse_naive,
        rmse_test_dos=m.rmse_test_dos, rmse_test_uno=m.rmse_test_uno,
        rmse_test_naive=m.rmse_test_naive,
        media_total=m.media_total, media_1q=m.media_1q, media_2q=m.media_2q,
    )


class Command(BaseCommand):
    help = ('PAPER: apuestas de totales de baloncesto en el descanso 2Q→3Q '
            '(motor basket_1q2q). Sin dinero real.')

    def add_arguments(self, parser):
        parser.add_argument('--dry-run', action='store_true',
                            help='Simula y muestra; no escribe PaperBet.')
        parser.add_argument('--delta-min', type=float, default=bk.DELTA_MINIMO,
                            help=f'Δ mínimo en puntos (default {bk.DELTA_MINIMO}).')
        parser.add_argument('--delta-max', type=float, default=bk.DELTA_MAXIMO,
                            help=f'Tope del Δ (0 = sin tope; default {bk.DELTA_MAXIMO}).')
        parser.add_argument('--ev-min', type=float, default=bk.EV_MINIMA,
                            help='EV mínimo en fracción (default 0.02 = 2 %%).')
        parser.add_argument('--stake', type=int, default=bk.STAKE_DEFECTO,
                            help=f'Stake virtual COP (default {bk.STAKE_DEFECTO}).')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        self.stdout.write(f"{'🧪 DRY-RUN — ' if dry else ''}"
                          f"Paperbet baloncesto 1Q+2Q (motor {bk.MOTOR})")
        filtro_ligadia = cargar_filtro_ligadia()
        if filtro_ligadia:
            self.stdout.write(f'  [FILTRO LIGA-DIA] activo: {len(filtro_ligadia)} celdas whitelist')

        try:
            partidos = bk.fetch_live_partidos()
        except bk.ErrorBasket as exc:
            self.stderr.write(f'Kambi: {exc}')
            return

        # Cosecha: partidos finalizados del feed -> muestras de entrenamiento.
        n_cosecha = self._cosechar_muestras(partidos, dry)

        # Cascada de modelos (2026-10-13): propio -> pooled(liga, global)
        # -> global. "Falta de modelo" deja de ser motivo de no apuesta.
        modelos = {m.liga: modelo_de(m) for m in BasketModel.objects.all()}
        global_m = modelos.pop(bk.CLAVE_GLOBAL, None)
        cache_modelos: dict = {}
        origenes_uso: Counter = Counter()
        motivos: Counter = Counter()
        escritas: list[tuple] = []

        # Universo COMPLETO de la ventana (tenga o no modelo): los snapshots
        # de mercado son la base point-in-time para CLV/backtest (Fase 1).
        en_ventana_lista = [p for p in partidos if bk.en_ventana_descanso(p)]
        n_snap = self._capturar_snapshots(en_ventana_lista, dry)

        # Pinnacle (The Odds API): solo recolección de datos (pregame + 2Q→3Q).
        # No toma decisiones ni altera la apuesta; siempre atrapado en errores.
        n_pre = n_brk = 0
        try:
            n_pre, n_brk = bp.recolectar(partidos, en_ventana_lista,
                                         self.stdout, dry=dry)
        except Exception as exc:  # noqa: BLE001
            self.stderr.write(f'Pinnacle feed: {exc}')

        for p in en_ventana_lista:
            if p.clave_liga in bk.NO_SON_LIGAS:
                motivos['mercado de serie (no es liga)'] += 1
                continue

            modelo = self._modelo_para(p.clave_liga, modelos, global_m,
                                       cache_modelos)
            if modelo is None:
                etiqueta = 'sin modelo'
            elif modelo is global_m:
                etiqueta = f'{bk.CLAVE_GLOBAL} ({modelo.origen or "global"})'
            else:
                etiqueta = modelo.origen or 'sin origen'
            origenes_uso[etiqueta] += 1
            ev = bk.evaluar(p, modelo,
                            delta_min=opts['delta_min'],
                            delta_max=opts['delta_max'],
                            ev_min=opts['ev_min'])
            if not ev['ok']:
                motivos[ev['motivo']] += 1
                continue

            if ev['lado'] not in bk.LADOS_PAPER_ACTIVOS:
                motivos[f"lado {ev['lado']} depurado (solo paper UNDER)"] += 1
                continue

            if PaperBet.objects.filter(motor=bk.MOTOR,
                                        evento_id=str(p.evento_id)).exists():
                motivos['ya registrada'] += 1
                continue

            liga_almacenada = p.liga_nombre or p.clave_liga
            if filtro_ligadia is not None:
                dia = timezone.localtime(timezone.now(), ZONA_BOG).weekday()
                if (liga_almacenada, dia) not in filtro_ligadia:
                    motivos['filtro liga-dia (celda fuera de whitelist)'] += 1
                    self.stdout.write(
                        f'  [FILTRO LIGA-DIA] descartado {liga_almacenada} '
                        f'({NOMBRE_DIA[dia]})')
                    continue

            inicio = self._inicio(p)
            seleccion = bk.SEL_OVER if ev['lado'] == 'OVER' else bk.SEL_UNDER
            prob, cuota = ev['prob'], ev['cuota']

            if dry:
                escritas.append((None, p, seleccion, prob, cuota, ev))
                continue

            bet = PaperBet.objects.create(
                evento_id=str(p.evento_id),
                start_time=inicio,
                home_team=p.local,
                away_team=p.visitante,
                liga=liga_almacenada,
                mercado=bk.MERCADO,
                motor=bk.MOTOR,
                seleccion=seleccion,
                linea=p.linea,
                diferencia=round(ev['diferencia'], 2),
                cuota=cuota,
                prob=round(prob, 4),
                ev=round(prob * cuota - 1.0, 4),
                stake=opts['stake'],
            )
            try:
                bp.rellenar_pinnacle(bet)  # datos Pinnacle (solo lectura/registro)
            except Exception as exc:  # noqa: BLE001
                self.stderr.write(f'Pinnacle apuesta {bet.id}: {exc}')
            escritas.append((bet.id, p, seleccion, prob, cuota, ev))

        for bet_id, p, seleccion, prob, cuota, ev in escritas:
            pref = f'id={bet_id}' if bet_id else 'DRY'
            self.stdout.write(
                f'  ✔ [{pref}] {p.clave_liga}: {p.local} vs {p.visitante} — '
                f'{seleccion} {p.linea:g} @ {cuota:.2f} '
                f'(P={prob * 100:.1f}% EV={ev["ev"] * 100:+.1f}% '
                f'Δ={ev["diferencia"]:+.1f} 1Q={p.q1} 2Q={p.q2})')

        # Cierre (CLV): última línea/cuota vista en ventana para las apuestas OPEN.
        n_cierres = self._actualizar_cierres(en_ventana_lista, dry)

        # Liquidación oportunista con el total final del propio feed (por
        # evento_id exacto). Respaldo: score_paper_bets_basket con API-Sports.
        n_feed = self._liquidar_feed(partidos, dry)

        self.stdout.write(
            f'Partidos en ventana: {len(en_ventana_lista)} · snapshots: {n_snap} · '
            f'cierres actualizados: {n_cierres} · muestras cosechadas: {n_cosecha} · '
            f'liquidaciones feed: {n_feed} · '
            f'apuestas {"simuladas" if dry else "registradas"}: {len(escritas)}')
        self.stdout.write(f'Pinnacle (solo datos): llamadas pregame={n_pre} '
                          f'break={n_brk}')
        for motivo, n in motivos.most_common():
            self.stdout.write(f'  · {motivo}: {n}')
        if origenes_uso:
            self.stdout.write('Modelos usados en ventana: ' + ' · '.join(
                f'{origen}={n}' for origen, n in origenes_uso.most_common()))

    # ------------------------------------------------------------------ #
    #  Cascada de modelos (propio -> pooled -> global)                   #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _modelo_para(clave, modelos, global_m, cache):
        """Modelo para una liga: propio -> entrenado al vuelo (si ya hay
        muestras suficientes) -> pooled con el global -> global. Nunca None
        mientras exista el modelo global de respaldo."""
        if clave in cache:
            return cache[clave]
        modelo = modelos.get(clave)
        if modelo is None and global_m is not None:
            datos = list(BasketSample.objects.filter(liga=clave)
                         .order_by('fecha', 'id')
                         .values_list('q1', 'q2', 'total'))
            if len(datos) >= bk.MINIMO_MUESTRAS:
                modelo = bk.entrenar(datos, clave, bk.MINIMO_MUESTRAS)
            elif len(datos) >= bk.MINIMO_POOL:
                modelo = bk.entrenar_pooled(datos, clave, global_m,
                                            bk.MINIMO_MUESTRAS)
            if modelo is None:
                modelo = global_m
        cache[clave] = modelo
        return modelo

    # ------------------------------------------------------------------ #
    #  Cosecha de muestras desde el propio feed (Fase 2)                  #
    # ------------------------------------------------------------------ #
    def _cosechar_muestras(self, partidos, dry):
        """Partidos finalizados del feed (Q1..Q4 + total) -> BasketSample.

        Fuente de muestras independiente de API-Sports: toda liga que Kambi
        publique acumula datos y termina con modelo propio sin diccionario
        manual. Nunca en dry-run; deduplicado por evento_clave."""
        if dry:
            return 0
        filas = []
        for p in partidos:
            if not p.finalizado or p.total_final is None:
                continue
            if p.q1 is None or p.q2 is None:
                continue
            inicio = parse_datetime((p.inicio or '').replace('Z', '+00:00'))
            filas.append(BasketSample(
                liga=p.clave_liga, fecha=inicio.date() if inicio else None,
                q1=p.q1, q2=p.q2, q3=p.q3, q4=p.q4,
                total=float(p.total_final),
                partido=f'{p.local} - {p.visitante}',
                fuente='kambi', evento_clave=f'kambi|{p.evento_id}'))
        if not filas:
            return 0
        try:
            BasketSample.objects.bulk_create(filas, ignore_conflicts=True,
                                             batch_size=200)
        except Exception as exc:  # noqa: BLE001 (la cosecha no tumba al bot)
            self.stderr.write(f'Cosecha de muestras: no se pudo guardar ({exc})')
            return 0
        return len(filas)

    # ------------------------------------------------------------------ #
    #  Liquidación con el feed (Fase 5, fuente primaria)                  #
    # ------------------------------------------------------------------ #
    def _liquidar_feed(self, partidos, dry):
        """Liquida apuestas OPEN cuyo partido aparece finalizado en el feed
        (match exacto por evento_id, sin nombres). Si el feed ya no lo trae,
        score_paper_bets_basket lo resolverá con API-Sports."""
        if dry or not partidos:
            return 0
        por_id = {str(p.evento_id): p for p in partidos
                  if p.finalizado and p.total_final is not None}
        if not por_id:
            return 0
        abiertas = PaperBet.objects.filter(
            motor__in=(bk.MOTOR, bk.MOTOR_GATED), estado='OPEN',
            evento_id__in=list(por_id))
        n = 0
        for bet in abiertas:
            p = por_id[bet.evento_id]
            total = float(p.total_final)
            estado = bk.liquidar(bet.seleccion, bet.linea, total)
            if estado == 'VOID':
                resultado = f'{total:g} · push kambi'
                payout = float(bet.stake)
            else:
                resultado = f'{total:g} · kambi'
                payout = bet.stake * bet.cuota if estado == 'WON' else 0.0
            PaperBet.objects.filter(pk=bet.pk, estado='OPEN').update(
                estado=estado, resultado_real=resultado,
                payout=round(payout, 2), settled_at=timezone.now())
            n += 1
        return n

    # ------------------------------------------------------------------ #
    #  Captura point-in-time (Fase 1) y cierre (CLV)                     #
    # ------------------------------------------------------------------ #
    @staticmethod
    def _inicio(p):
        inicio = parse_datetime((p.inicio or '').replace('Z', '+00:00'))
        return inicio or timezone.now()

    def _capturar_snapshots(self, en_ventana, dry):
        """Un snapshot as-of por partido EN VENTANA (universo completo, no solo
        los que tienen modelo o apuesta). Nunca en dry-run."""
        if dry or not en_ventana:
            return 0
        ahora = timezone.now()
        filas = [BasketMarketSnapshot(
                    evento_id=str(p.evento_id),
                    capturado_en=ahora,
                    start_time=self._inicio(p),
                liga=p.liga_nombre or p.clave_liga,
                    clave_liga=p.clave_liga,
                    home_team=p.local,
                    away_team=p.visitante,
                    q1=p.q1,
                    q2=p.q2,
                    period_id=p.period_id,
                    linea=p.linea,
                    cuota_over=p.cuota_over,
                    cuota_under=p.cuota_under,
                    over_abierta=p.hay_cuota_over,
                    under_abierta=p.hay_cuota_under)
                for p in en_ventana]
        try:
            BasketMarketSnapshot.objects.bulk_create(filas, batch_size=100)
            return len(filas)
        except Exception as exc:  # noqa: BLE001 (la captura no tumba al bot)
            self.stderr.write(f'Snapshot: no se pudo guardar ({exc})')
            return 0

    def _actualizar_cierres(self, en_ventana, dry):
        """Cierre = última línea/cuota vistas en ventana para la apuesta OPEN.

        Se actualiza en cada pasada mientras el evento siga en el descanso y el
        lado cotice abierto; al arrancar el 3Q deja de encontrarse y el valor
        queda congelado. Si la casa suspende el lado, se conserva la última
        cuota abierta.
        """
        if dry or not en_ventana:
            return 0
        por_evento = {str(p.evento_id): p for p in en_ventana}
        abiertas = PaperBet.objects.filter(
            motor__in=(bk.MOTOR, bk.MOTOR_GATED), estado='OPEN',
            start_time__gte=timezone.now() - timedelta(hours=8))
        n = 0
        for bet in abiertas:
            p = por_evento.get(bet.evento_id)
            if p is None:
                continue
            if bet.seleccion == bk.SEL_OVER:
                cuota, abierta = p.cuota_over, p.hay_cuota_over
            else:
                cuota, abierta = p.cuota_under, p.hay_cuota_under
            if not abierta or not cuota:
                continue
            if bet.closing_odds == cuota and bet.closing_linea == p.linea:
                continue
            PaperBet.objects.filter(pk=bet.pk, estado='OPEN').update(
                closing_linea=p.linea, closing_odds=cuota)
            n += 1
        return n
