# -*- coding: utf-8 -*-
"""
Inspector de apuestas — management command.

Verifica las apuestas liquidadas (LOST/WON) de los últimos `--days` días que
aún no tienen inspección final, comparando el estado BetPlay/Kambi contra la
base de datos local (API-Football).

Uso:
  manage.py inspect_bets                 # corrida normal (cron)
  manage.py inspect_bets --days 21       # backfill de 3 semanas
  manage.py inspect_bets --dry-run       # sin escribir ni notificar
  manage.py inspect_bets --email x@y.z   # solo un usuario
  manage.py inspect_bets --force         # re-verificar también OK/REVISAR

Diseñado para correr DESPUÉS de sync_bet_history (estados BetPlay) y de
api_football_daily (stats), vía run_scheduler.
"""

from collections import Counter
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from auto_betting.models import HistorialApuesta
from inspector.models import InspeccionApuesta
from inspector.services import inspect_bet

MAX_REINTENTOS = 8

RETRYABLE_HINTS = (
    'aún no iniciado', 'en juego', 'sin stats', 'sin cobertura',
    'sin marcador', 'fixture no resuelto', 'sin candidatos',
)


class Command(BaseCommand):
    help = 'Inspector: verifica apuestas liquidadas contra la base de datos local (API-Football)'

    def add_arguments(self, parser):
        parser.add_argument('--days', type=int, default=14,
                            help='Ventana de días a inspeccionar (default 14)')
        parser.add_argument('--email', type=str, default=None,
                            help='Solo inspeccionar apuestas de este usuario')
        parser.add_argument('--dry-run', action='store_true',
                            help='No escribe inspecciones ni envía avisos')
        parser.add_argument('--force', action='store_true',
                            help='Re-verificar también apuestas ya OK/REVISAR')
        parser.add_argument('--no-notify', action='store_true',
                            help='Escribe inspecciones pero no envía WhatsApp')

    def handle(self, *args, **opts):
        days = opts['days']
        dry = opts['dry_run']
        force = opts['force']
        no_notify = opts['no_notify']
        email = opts['email']

        now = timezone.now()
        desde = now - timedelta(days=days)

        qs = (HistorialApuesta.objects
              .filter(bet_status__in=['LOST', 'WON'],
                      event_start_date__gte=desde,
                      event_start_date__lte=now - timedelta(minutes=90))
              .select_related('usuario')
              .order_by('event_start_date'))
        if email:
            qs = qs.filter(usuario__email=email)

        existing = {i.apuesta_id: i for i in
                    InspeccionApuesta.objects.filter(apuesta__in=qs.values('id'))}

        to_check = []
        for bet in qs:
            insp = existing.get(bet.id)
            if insp is None or force:
                to_check.append(bet)
                continue
            # Re-verificar siempre que BetPlay haya cambiado el estado
            # (p. ej. corrección manual de la liquidación tras un reclamo).
            if bet.bet_status != insp.estado_kambi:
                to_check.append(bet)
                continue
            if insp.veredicto == InspeccionApuesta.VEREDICTO_REVISAR:
                continue
            if insp.veredicto == InspeccionApuesta.VEREDICTO_OK:
                continue
            if insp.veredicto == InspeccionApuesta.VEREDICTO_NO_VERIFICABLE:
                if insp.reintentos >= MAX_REINTENTOS:
                    continue
                det = (insp.detalle or '').lower()
                if not any(h in det for h in RETRYABLE_HINTS):
                    continue
                if insp.actualizado and (now - insp.actualizado) < timedelta(hours=4):
                    continue
                to_check.append(bet)

        self.stdout.write(f'Inspector: {len(to_check)} apuestas a verificar '
                          f'(ventana {days}d, {"dry-run" if dry else "normal"}).')

        client = None
        tried_ids = set()
        verdicts = Counter()
        created = mismatches = 0

        for bet in to_check:
            need_client = any(k in (bet.mercado or '').lower()
                              for k in ('esquina', 'corner', 'tiros', 'disparos'))
            if need_client and client is None:
                from football_api.client import ApiFootballClient
                client = ApiFootballClient()

            result = inspect_bet(bet, client=client, tried_ids=tried_ids)
            verdicts[result['veredicto']] += 1

            if dry:
                if result['veredicto'] == 'REVISAR':
                    self.stdout.write(
                        f"  [DRY] REVISAR u={bet.usuario_id} "
                        f"{bet.event_start_date:%m-%d %H:%M} | "
                        f"{bet.home_team} vs {bet.away_team} | {bet.mercado} | "
                        f"{bet.seleccion} | {result['direccion']} {result['detalle']} | "
                        f"c={bet.coupon_ref}")
                continue

            insp = existing.get(bet.id)
            is_new = insp is None
            if is_new:
                insp = InspeccionApuesta(apuesta=bet)
                created += 1
            prev_veredicto = insp.veredicto if not is_new else ''
            insp.veredicto = result['veredicto']
            insp.direccion = result['direccion']
            insp.estado_kambi = bet.bet_status
            insp.estado_esperado = result['estado_esperado']
            insp.confianza = result['confianza']
            insp.detalle = result['detalle'][:400]
            insp.fixture_api_id = result['fixture_api_id']
            insp.margen = result.get('margen')
            if not is_new and insp.veredicto != InspeccionApuesta.VEREDICTO_OK:
                insp.reintentos += 1
            insp.save()
            if result['veredicto'] == 'REVISAR':
                mismatches += 1
                # Si la inspección cambió a REVISAR, resetear avisos para re-notificar
                if prev_veredicto and prev_veredicto != 'REVISAR' and not is_new:
                    insp.aviso_usuario = False
                    insp.aviso_admin = False
                    insp.save(update_fields=['aviso_usuario', 'aviso_admin'])

        self.stdout.write(f'Resultado: {dict(verdicts)} | nuevas: {created} | '
                          f'discrepancias: {mismatches}')

        if not dry and not no_notify:
            self._notify_pending()

    def _aviso_claro(self, insp):
        """True si la discrepancia es lo bastante clara para avisar al usuario.

        Mercados contados por proveedores distintos (córners/tiros/SOT) pueden
        diferir ±1: exigir margen >= 1.0 respecto a la línea. El resto de
        mercados (goles, BTTS, 1X2, HT, DO) no tiene ambigüedad de conteo.
        """
        if insp.confianza != 'alta':
            return False
        ml = (insp.apuesta.mercado or '').lower()
        counting = any(k in ml for k in ('esquina', 'corner', 'tiros', 'disparos'))
        if counting:
            return insp.margen is not None and float(insp.margen) >= 1.0
        return True

    def _notify_pending(self):
        """Envía avisos pendientes para inspecciones REVISAR.

        Antes de avisar, verifica la ESTRUCTURA de cada cupón: el sync solo
        guarda la primera pata, así que una combinada LOST/WON no permite
        concluir nada sobre la pata almacenada. Los cupones combinados se
        descartan (NO_VERIFICABLE); los no clasificables (ticket vencido)
        quedan pendientes para la próxima corrida.
        """
        from cuentas.models import Usuario
        from inspector.coupon_check import CouponStructureChecker
        from inspector.notifications import (enviar_aviso_admin_grupo,
                                             enviar_aviso_usuario)

        pending = list(InspeccionApuesta.objects
                       .filter(veredicto=InspeccionApuesta.VEREDICTO_REVISAR)
                       .select_related('apuesta__usuario')
                       .order_by('creado'))

        # ── Verificación estructural (simple vs combinada) ──
        checker = CouponStructureChecker()
        notifiable = []
        for insp in pending:
            bet = insp.apuesta
            legs = bet.coupon_legs
            if legs is None:
                status, n = checker.structure(bet.usuario, bet.coupon_ref)
                if status in ('unknown', 'missing'):
                    self.stdout.write(
                        f'  ⏳ cupón {bet.coupon_ref}: estructura {status} — '
                        f'sin avisos (se reintentará)')
                    continue
                legs = n or 1
            if legs > 1:
                insp.veredicto = InspeccionApuesta.VEREDICTO_NO_VERIFICABLE
                insp.detalle = (f'cupón combinada ({legs} patas): el estado '
                                f'global no es atribuible a la pata almacenada')
                insp.save(update_fields=['veredicto', 'detalle', 'actualizado'])
                self.stdout.write(f'  ↳ cupón {bet.coupon_ref} descartado '
                                  f'(combinada de {legs} patas)')
                continue
            notifiable.append(insp)
        pending = notifiable

        admin_user = (Usuario.objects.filter(is_superuser=True, is_active=True)
                      .order_by('id').first())

        # ── Avisos a usuarios (uno por apuesta, solo pérdidas claras) ──
        n_user = 0
        for insp in pending:
            if (insp.direccion == InspeccionApuesta.DIR_PERDIDA
                    and self._aviso_claro(insp)
                    and not insp.aviso_usuario and insp.intentos_aviso < 3):
                ok = enviar_aviso_usuario(insp)
                insp.intentos_aviso += 1
                if ok:
                    insp.aviso_usuario = True
                    n_user += 1
                insp.save(update_fields=['aviso_usuario', 'intentos_aviso', 'actualizado'])

        # ── Avisos al admin (agrupados por fixture + dirección) ──
        n_admin = n_grupos = 0
        if admin_user is not None:
            grupos = {}
            for insp in pending:
                if insp.aviso_admin or insp.intentos_aviso_admin >= 3:
                    continue
                key = (insp.fixture_api_id, insp.direccion)
                grupos.setdefault(key, []).append(insp)
            for key, rows in grupos.items():
                ok = enviar_aviso_admin_grupo(rows, admin_user)
                n_grupos += 1
                for insp in rows:
                    insp.intentos_aviso_admin += 1
                    if ok:
                        insp.aviso_admin = True
                        n_admin += 1
                    insp.save(update_fields=['aviso_admin', 'intentos_aviso_admin',
                                             'actualizado'])

        self.stdout.write(f'Avisos: {n_user} a usuarios | {n_admin} cupones al admin '
                          f'en {n_grupos} mensaje(s)')
