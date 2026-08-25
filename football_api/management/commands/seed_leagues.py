from django.core.management.base import BaseCommand

from football_api import services


class Command(BaseCommand):
    help = "Crea/actualiza las ligas API-Football desde el diccionario estático (cobertura + temporadas)."

    def handle(self, *args, **options):
        created, updated = services.seed_leagues()
        self.stdout.write(self.style.SUCCESS(f"Ligas: {created} creadas, {updated} actualizadas."))
