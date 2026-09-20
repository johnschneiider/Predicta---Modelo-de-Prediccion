# -*- coding: utf-8 -*-
"""Verificación estructural de cupones (simple vs combinada) vía BetPlay.

El sync (`auto_betting.services.sync_historial`) guarda SOLO la primera pata
de cada cupón (`bets[0]`/`outcomes[0]`/`events[0]`). Si un cupón es una
combinada de 2+ patas, su estado LOST/WON refleja TODAS las patas y no es
posible concluir sobre la pata almacenada sin más datos.

Para no generar falsos positivos, antes de avisar sobre un cupón el Inspector
consulta el historial real de la cuenta (login + fetch) y clasifica:

- 'single'  : 1 pata → analizable, se puede notificar.
- 'combo'   : 2+ patas → NO_VERIFICABLE (no se notifica; se descarta la duda).
- 'missing' : el cupón no aparece en el historial actual → no verificado.
- 'unknown' : login/descarga falló (ticket vencido, red) → se reintenta luego.

Cache por corrida: máximo 1 login + 1 fetch por usuario. Además, cada carga
aprovecha para rellenar `HistorialApuesta.coupon_legs` con el conteo real.
"""

import logging
import time

logger = logging.getLogger('inspector')


class CouponStructureChecker:
    """Clasifica cupones por estructura, con caché por usuario y corrida."""

    def __init__(self, sleep_between_users=3.0):
        self._by_user = {}   # uid -> {str(coupon_ref): n_legs} | None (fallo)
        self._tried = set()  # uids ya cargados (o intentados)
        self._sleep = sleep_between_users

    def _load_user(self, usuario):
        uid = usuario.id
        if uid in self._tried:
            return
        self._tried.add(uid)
        self._by_user[uid] = None

        from auto_betting.models import AutoBetConfig, HistorialApuesta
        from auto_betting.services import _count_coupon_legs, fetch_bet_history, login

        try:
            cfg = (AutoBetConfig.objects
                   .filter(usuario=usuario, activo=True)
                   .first())
            if cfg is None:
                return
            token, _ = login(cfg.ticket, cfg.punter_id)
            if not token:
                logger.info('structure check u=%s: login BetPlay falló (ticket vencido)', uid)
                return
            cups = fetch_bet_history(token, range_size=500)
            if not cups:
                return
            cups_map = {}
            for c in cups:
                ref = c.get('couponRef')
                if ref is None:
                    continue
                cups_map[str(ref)] = _count_coupon_legs(c)
            self._by_user[uid] = cups_map

            # Backfill oportunista de coupon_legs en las filas del usuario
            n_upd = 0
            for row in HistorialApuesta.objects.filter(usuario=usuario).only(
                    'id', 'coupon_ref', 'coupon_legs'):
                legs = cups_map.get(str(row.coupon_ref))
                if legs is not None and row.coupon_legs != legs:
                    row.coupon_legs = legs
                    row.save(update_fields=['coupon_legs'])
                    n_upd += 1
            if n_upd:
                logger.info('structure check u=%s: coupon_legs actualizado en %s filas', uid, n_upd)
        except Exception as e:  # noqa: BLE001 — red/parseo: no concluir nada
            logger.warning('structure check u=%s: %s', uid, e)
        finally:
            if self._sleep:
                time.sleep(self._sleep)

    def structure(self, usuario, coupon_ref):
        """Devuelve (status, legs): status ∈ single|combo|missing|unknown."""
        self._load_user(usuario)
        cups = self._by_user.get(usuario.id)
        if cups is None:
            return 'unknown', None
        legs = cups.get(str(coupon_ref))
        if legs is None:
            return 'missing', None
        return ('single' if legs <= 1 else 'combo'), legs
