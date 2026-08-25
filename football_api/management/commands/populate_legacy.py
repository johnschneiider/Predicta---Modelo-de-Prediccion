from django.core.management.base import BaseCommand
from django.db import connection

from football_api.models import ApiLeague
from football_api import services


class Command(BaseCommand):
    help = "Poblar la tabla legacy football_data.Match desde API-Football (para que los motores lean la data nueva)."

    def add_arguments(self, parser):
        parser.add_argument("--league", type=int, default=None, help="API ID de una liga específica")
        parser.add_argument("--all", action="store_true", help="Procesar todas las ligas (no solo las 'done')")
        parser.add_argument("--clear", action="store_true", help="Borrar los Match legacy de la liga antes de insertar")
        parser.add_argument("--archive", action="store_true", help="Archivar Match actual en football_data_match_archive antes")

    def handle(self, *args, **options):
        if options["archive"]:
            with connection.cursor() as c:
                c.execute("DROP TABLE IF EXISTS football_data_match_archive")
                c.execute("CREATE TABLE football_data_match_archive AS SELECT * FROM football_data_match")
            self.stdout.write("✅ Match archivado en football_data_match_archive")

        if options["league"]:
            leagues = ApiLeague.objects.filter(api_id=options["league"])
        elif options["all"]:
            leagues = ApiLeague.objects.all()
        else:
            leagues = ApiLeague.objects.filter(backfill_status="done")

        created = updated = deleted = 0
        for al in leagues.order_by("id"):
            c, u, d = services.populate_legacy_matches(league_api_id=al.api_id, clear_first=options["clear"])
            created += c
            updated += u
            deleted += d
            self.stdout.write(f"  {al.name}: +{c} nuevos, ~{u} actualizados, -{d} borrados")

        self.stdout.write(self.style.SUCCESS(
            f"Match legacy: {created} creados, {updated} actualizados, {deleted} borrados"
        ))
