"""
Cliente HTTP para API-Football v3 con control de rate-limit.

Dos límites:
- Por minuto: 300 req (header `x-ratelimit-remaining`).
- Por día: 75000 req (header `x-ratelimit-requests-remaining`).

Cuando el límite diario se agota -> `QuotaExceeded` (el cron pausa y reanuda en 24h).
"""

import logging
import os
import time
from urllib.parse import urlencode

import requests

logger = logging.getLogger("football_api")

BASE_URL = "https://v3.football.api-sports.io"


def _api_key():
    """Lee la key desde settings o env (nunca hardcodeada en git)."""
    try:
        from django.conf import settings
        key = getattr(settings, "APIFOOTBALL_KEY", "")
        if key:
            return key
    except Exception:
        pass
    return os.environ.get("APIFOOTBALL_KEY", "")


API_KEY = _api_key()

DAILY_LIMIT = 75000
MINUTE_LIMIT = 450
# Margen de seguridad: nunca gastar las últimas N requests del día
DAILY_BUFFER = 10
# Seguridad sobre el rate-limit por minuto (parar un poco antes de 450)
MINUTE_BUFFER = 20


class QuotaExceeded(Exception):
    """Límite diario alcanzado. Reanudar en 24h."""


class RateLimitError(Exception):
    """Rate-limit temporal (429). Reintentar tras Retry-After."""


class ApiFootballClient:
    def __init__(self, api_key=API_KEY, daily_buffer=DAILY_BUFFER):
        self.api_key = api_key
        self.daily_buffer = daily_buffer
        self.session = requests.Session()
        self.session.headers.update({"x-apisports-key": self.api_key})
        # Estado vivo (lo actualiza cada respuesta)
        self.daily_remaining = None
        self.daily_limit = DAILY_LIMIT
        self.minute_remaining = None
        self.requests_made = 0
        # Throttle por minuto: marca de tiempo de inicio de la ventana actual
        self._minute_start = None
        self._minute_count = 0

    def _throttle(self):
        """Evita superar el rate-limit por minuto durmiendo si hace falta."""
        import time as _t
        now = _t.monotonic()
        # resetear ventana cada 60s
        if self._minute_start is None or (now - self._minute_start) >= 60:
            self._minute_start = now
            self._minute_count = 0
        if self._minute_count > 0 and now - self._minute_start < 60:
            self._minute_count += 1
            if self._minute_count >= (MINUTE_LIMIT - MINUTE_BUFFER):
                wait = 60 - (now - self._minute_start) + 0.5
                if wait > 0:
                    time.sleep(wait)
                self._minute_start = _t.monotonic()
                self._minute_count = 0
        else:
            self._minute_count = 1

    def _get(self, endpoint, params=None, retries=3):
        url = f"{BASE_URL}/{endpoint}"
        if params:
            url = f"{url}?{urlencode(params, doseq=True)}"

        for attempt in range(retries):
            # Pre-check de cuota diaria antes de gastar un request
            self.check_quota()
            self._throttle()
            resp = self.session.get(url, timeout=30)
            self._update_limits(resp)

            if resp.status_code == 200:
                data = resp.json()
                errors = data.get("errors")
                if errors:
                    msg = str(errors).lower()
                    if any(k in msg for k in ("rate", "request", "limit", "quota", "many")):
                        if self.daily_remaining is not None and self.daily_remaining <= self.daily_buffer:
                            raise QuotaExceeded(f"Cuota diaria agotada: {errors}")
                        if attempt < retries - 1:
                            time.sleep(min(2 ** attempt, 60))
                            continue
                        raise RateLimitError(f"Rate-limit en {endpoint}: {errors}")
                    raise RuntimeError(f"API error en {endpoint}: {errors}")
                self.requests_made += 1
                return data

            if resp.status_code == 429:
                retry_after = int(resp.headers.get("Retry-After", "60"))
                logger.warning("429 rate-limit en %s (Retry-After=%ss)", endpoint, retry_after)
                if attempt < retries - 1:
                    time.sleep(min(retry_after, 120))
                    continue
                raise RateLimitError(f"429 persistente en {endpoint}")

            if resp.status_code in (401, 403):
                raise RuntimeError(f"Auth/permisos ({resp.status_code}) en {endpoint}: {resp.text[:200]}")

            # Otros errores: reintento con backoff
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
                continue
            raise RuntimeError(f"HTTP {resp.status_code} en {endpoint}: {resp.text[:300]}")

        raise RuntimeError(f"Sin respuesta en {endpoint}")

    def _update_limits(self, resp):
        h = resp.headers
        try:
            self.daily_remaining = int(h.get("x-ratelimit-requests-remaining", self.daily_remaining or DAILY_LIMIT))
            self.daily_limit = int(h.get("x-ratelimit-requests-limit", self.daily_limit))
        except (TypeError, ValueError):
            pass
        try:
            self.minute_remaining = int(h.get("x-ratelimit-remaining", self.minute_remaining or MINUTE_LIMIT))
        except (TypeError, ValueError):
            pass

    def check_quota(self):
        """Lanza QuotaExceeded si el presupuesto diario está agotado."""
        if self.daily_remaining is not None and self.daily_remaining <= self.daily_buffer:
            raise QuotaExceeded(
                f"Límite diario alcanzado (remaining={self.daily_remaining}, buffer={self.daily_buffer})"
            )

    # ── Endpoints ──
    def status(self):
        return self._get("status")

    def leagues(self, **params):
        return self._get("leagues", params)

    def teams(self, **params):
        return self._get("teams", params)

    def fixtures(self, **params):
        """params: league, season, from, to, page, next, status, etc."""
        return self._get("fixtures", params)

    def fixtures_statistics(self, fixture_id):
        return self._get("fixtures/statistics", {"fixture": fixture_id})

    def fixtures_rounds(self, **params):
        return self._get("fixtures/rounds", params)

    def predictions(self, fixture_id):
        return self._get("predictions", {"fixture": fixture_id})

    def standings(self, **params):
        return self._get("standings", params)

    def odds(self, **params):
        return self._get("odds", params)
