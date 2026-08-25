from django.core.management.base import BaseCommand

from football_api import services


class Command(BaseCommand):
    help = "Backfill de 2 temporadas + actual (fixtures + estadísticas) desde API-Football."

    def add_arguments(self, parser):
        parser.add_argument("--no-stats", action="store_true", help="No traer estadísticas (solo fixtures)")
        parser.add_argument("--max-leagues", type=int, default=None, help="Límite de ligas a procesar (pruebas)")

    def handle(self, *args, **options):
        status = services.run_backfill(
            fetch_stats=not options["no_stats"],
            max_leagues=options["max_leagues"],
        )
        self.stdout.write(self.style.SUCCESS(f"Backfill finalizado con estado: {status}"))
