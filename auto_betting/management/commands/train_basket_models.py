# -*- coding: utf-8 -*-
"""Entrena los modelos MCO de baloncesto (motor basket_1q2q) con API-Sports.

Uso:
    manage.py train_basket_models                 # todas las ligas mapeadas
    manage.py train_basket_models --ligas nba,euroleague
    manage.py train_basket_models --dry-run       # descarga y calcula, sin escribir

Liga con ≥ `--minimo` muestras → modelo propio (holdout 20 % más reciente).
Entre 8 y 29 → mezcla con el modelo global (pooling), igual que el repo.
"""
from datetime import date

from django.core.management.base import BaseCommand
from django.db.models import Max, Min

from auto_betting import basket_1q2q as bk
from auto_betting.models import BasketModel, BasketSample


class Command(BaseCommand):
    help = ('Descarga histórico de API-Sports y entrena/actualiza los modelos '
            'MCO por liga del paperbet de baloncesto (basket_1q2q).')

    def add_arguments(self, parser):
        parser.add_argument('--ligas', type=str, default=None,
                            help='Claves separadas por coma (default: todas las mapeadas).')
        parser.add_argument('--temporadas', type=int, default=2,
                            help='Temporadas más recientes con datos a descargar (default 2).')
        parser.add_argument('--minimo', type=int, default=bk.MINIMO_MUESTRAS,
                            help='Muestras mínimas para publicar modelo propio (default 30).')
        parser.add_argument('--dry-run', action='store_true',
                            help='No escribe en la BD (sí descarga y calcula).')
        parser.add_argument('--solo-global', action='store_true', dest='solo_global',
                            help='Solo (re)entrena el modelo global de respaldo desde '
                                 'las muestras de la BD, sin llamar a API-Sports.')

    def handle(self, *args, **opts):
        dry = opts['dry_run']
        if opts['solo_global']:
            self.stdout.write(
                f"{'🧪 DRY-RUN — ' if dry else ''}Modelo global de baloncesto "
                f"(solo BD, sin API-Sports)")
            self._entrenar_global(dry)
            return
        if opts['ligas']:
            claves = [c.strip() for c in opts['ligas'].split(',') if c.strip()]
        else:
            claves = sorted(bk.LIGAS_API_SPORTS)
        self.stdout.write(f"{'🧪 DRY-RUN — ' if dry else ''}Modelos baloncesto: "
                          f"{len(claves)} ligas")

        try:
            inv = bk.inventario()
        except bk.ErrorAPI as exc:
            self.stderr.write(f'API-Sports: {exc}')
            return

        self._cache_global = None
        recogidas: dict[str, list] = {}
        entrenados: list[tuple] = []
        sin_modelo: list[tuple] = []
        sin_datos_api: list[str] = []

        for clave in claves:
            ids = bk.LIGAS_API_SPORTS.get(clave)
            if not ids:
                continue
            if not any(lid in inv for lid in ids):
                sin_datos_api.append(clave)
                continue

            def progreso(clave_, n, detalle):
                self.stdout.write(f'  {clave_}: +{n} muestras ({detalle})')

            try:
                # minimo_muestras=0: se bajan SIEMPRE las `--temporadas` pedidas
                # (el mínimo solo decide si se publica modelo, como el repo).
                muestras = bk.descargar_liga(
                    clave, ids, inv=inv, n_temporadas=opts['temporadas'],
                    minimo_muestras=0, progreso=progreso)
            except bk.ErrorAPI as exc:
                self.stderr.write(f'  {clave}: error API ({exc}); se omite')
                continue

            if not dry and muestras:
                antes = BasketSample.objects.filter(liga=clave).count()
                BasketSample.objects.bulk_create(
                    [BasketSample(liga=m['liga'], fecha=m['fecha'], q1=m['q1'],
                                  q2=m['q2'], q3=m['q3'], q4=m['q4'],
                                  total=m['total'], partido=m['partido'],
                                  fuente=m['fuente'],
                                  evento_clave=m['evento_clave'])
                     for m in muestras],
                    ignore_conflicts=True, batch_size=500)
                nuevas = BasketSample.objects.filter(liga=clave).count() - antes
            else:
                nuevas = len(muestras)

            if dry:
                # Mismo orden que el modo real (fecha asc): el holdout debe ser
                # el 20 % MÁS RECIENTE también en el dry-run.
                ordenadas = sorted(muestras, key=lambda m: (m['fecha'] or date.min))
                datos = [(m['q1'], m['q2'], m['total']) for m in ordenadas]
                fechas = [m['fecha'] for m in muestras if m['fecha']]
            else:
                datos = list(BasketSample.objects.filter(liga=clave)
                             .order_by('fecha', 'id')
                             .values_list('q1', 'q2', 'total'))
                fq = BasketSample.objects.filter(liga=clave).aggregate(
                    a=Min('fecha'), b=Max('fecha'))
                fechas = [f for f in (fq['a'], fq['b']) if f]
            recogidas[clave] = datos

            modelo = bk.entrenar(datos, clave, opts['minimo'])
            if modelo is None and len(datos) >= bk.MINIMO_POOL:
                global_m = self._global(recogidas)
                if global_m is not None:
                    modelo = bk.entrenar_pooled(datos, clave, global_m, opts['minimo'])

            if modelo is None:
                sin_modelo.append((clave, len(datos)))
                continue

            if fechas:
                modelo.fecha_min = min(fechas)
                modelo.fecha_max = max(fechas)

            if not dry:
                self._guardar_modelo(modelo)
            entrenados.append((clave, modelo, nuevas))
            self.stdout.write(
                f'  ✔ {clave}: n={modelo.n} (+{nuevas} nuevas) '
                f'b=[{modelo.b0:.2f}, {modelo.b1:.3f}, {modelo.b2:.3f}] '
                f'R²={modelo.r2_dos:.3f} RMSE_test={modelo.rmse_test_dos:.2f} '
                f'({modelo.origen})')

        # Modelo global de respaldo (todas las muestras de la BD, sin API):
        # garantiza apuesta en ventana para ligas sin modelo propio ni muestras.
        self._entrenar_global(dry)

        self.stdout.write('')
        self.stdout.write(f'Modelos {"calculados" if dry else "guardados"}: '
                          f'{len(entrenados)}')
        if sin_modelo:
            self.stdout.write('Sin modelo (muestras insuficientes): ' +
                              ', '.join(f'{c} ({n})' for c, n in sin_modelo))
        if sin_datos_api:
            self.stdout.write('Sin datos en API-Sports: ' + ', '.join(sin_datos_api))

    def _guardar_modelo(self, modelo):
        BasketModel.objects.update_or_create(
            liga=modelo.liga,
            defaults=dict(
                origen=modelo.origen, n=modelo.n,
                b0=modelo.b0, b1=modelo.b1, b2=modelo.b2,
                a0=modelo.a0, a1=modelo.a1,
                r2_dos=modelo.r2_dos, r2_uno=modelo.r2_uno,
                rmse_dos=modelo.rmse_dos, rmse_uno=modelo.rmse_uno,
                rmse_naive=modelo.rmse_naive,
                rmse_test_dos=modelo.rmse_test_dos,
                rmse_test_uno=modelo.rmse_test_uno,
                rmse_test_naive=modelo.rmse_test_naive,
                media_total=modelo.media_total, media_1q=modelo.media_1q,
                media_2q=modelo.media_2q,
                fecha_min=modelo.fecha_min, fecha_max=modelo.fecha_max,
            ))

    def _entrenar_global(self, dry):
        """(Re)entrena el modelo global de respaldo con TODAS las muestras de
        la BD (cualquier fuente) y lo persiste con la clave reservada."""
        datos = list(BasketSample.objects.order_by('fecha', 'id')
                     .values_list('q1', 'q2', 'total'))
        if len(datos) < bk.MINIMO_GLOBAL:
            self.stdout.write(f'  · {bk.CLAVE_GLOBAL}: muestras insuficientes '
                              f'({len(datos)} < {bk.MINIMO_GLOBAL}); se omite')
            return None
        modelo = bk.entrenar(datos, bk.CLAVE_GLOBAL, minimo=bk.MINIMO_GLOBAL)
        if modelo is None:
            self.stdout.write(f'  · {bk.CLAVE_GLOBAL}: sin modelo (datos degenerados)')
            return None
        modelo.origen = 'global (respaldo, todas las ligas)'
        fq = BasketSample.objects.aggregate(a=Min('fecha'), b=Max('fecha'))
        modelo.fecha_min, modelo.fecha_max = fq['a'], fq['b']
        if not dry:
            self._guardar_modelo(modelo)
        self.stdout.write(
            f'  ✔ {bk.CLAVE_GLOBAL}: n={modelo.n} '
            f'b=[{modelo.b0:.2f}, {modelo.b1:.3f}, {modelo.b2:.3f}] '
            f'R²={modelo.r2_dos:.3f} RMSE_test={modelo.rmse_test_dos:.2f} '
            f'({modelo.origen})')
        return modelo

    def _global(self, recogidas: dict) -> dict:
        """Modelo global (todas las muestras) para el pooling de ligas chicas."""
        if self._cache_global is None:
            todas: list[tuple] = []
            for datos in recogidas.values():
                todas.extend(datos)
            if len(todas) >= bk.MINIMO_GLOBAL:
                self._cache_global = bk.ajustar(todas, 'global', 'pooled')
            else:
                self._cache_global = False
        return self._cache_global or None
