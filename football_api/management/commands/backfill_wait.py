import time

from django.core.management.base import BaseCommand

from football_api.client import ApiFootballClient, QuotaExceeded
from football_api import services


class Command(BaseCommand):
    help = (
        "Espera a que la cuota diaria resetee (polling a /status, que no consume quota) "
        "y luego lanza el backfill. Si la cuota aún no resetea, pausa y reintenta."
    )

    def add_arguments(self, parser):
        parser.add_argument("--max-wait", type=int, default=2400, help="Segundos máximos de espera")
        parser.add_argument("--poll", type=int, default=300, help="Intervalo de polling (seg)")
        parser.add_argument("--no-stats", action="store_true", help="No traer estadísticas")
        parser.add_argument("--max-leagues", type=int, default=None)

    def handle(self, *args, **options):
        client = ApiFootballClient()
        deadline = time.time() + options["max_wait"]
        waited = False
        while time.time() < deadline:
            client.daily_remaining = None  # fuerza consulta fresca de cuota
            try:
                client.status()
                rem = client.daily_remaining
                if rem and rem > 100:
                    self.stdout.write(f"✅ Cuota fresca (remaining={rem}). Arrancando backfill.")
                    break
                self.stdout.write(f"⏳ Cuota aún no resetea (remaining={rem}). Esperando {options['poll']}s…")
                waited = True
            except QuotaExceeded:
                self.stdout.write(f"⏳ QuotaExceeded. Esperando {options['poll']}s…")
                waited = True
            except Exception as e:
                self.stdout.write(f"⚠️ Error consultando status ({e}). Esperando {options['poll']}s…")
                waited = True
            time.sleep(options["poll"])

        if waited and time.time() >= deadline:
            self.stdout.write("⚠️ Cuota no reseteó dentro del tiempo límite; lanzo backfill igual (pausará si no hay cuota).")

        status = services.run_backfill(
            fetch_stats=not options["no_stats"],
            max_leagues=options["max_leagues"],
        )
        self.stdout.write(self.style.SUCCESS(f"Backfill finalizado con estado: {status}"))
