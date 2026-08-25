from django.core.management.base import BaseCommand

from football_api import services


class Command(BaseCommand):
    help = "Sync diario: fixtures próximos + estadísticas de finalizados recientes."

    def add_arguments(self, parser):
        parser.add_argument("--days-ahead", type=int, default=7)
        parser.add_argument("--days-back", type=int, default=3)

    def handle(self, *args, **options):
        status, fx, st = services.run_daily_sync(
            days_ahead=options["days_ahead"],
            days_back=options["days_back"],
        )
        self.stdout.write(self.style.SUCCESS(
            f"Daily sync: {status} | {fx} fixtures | {st} stats actualizadas"
        ))
