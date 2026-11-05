"""
Sincroniza datos MLB desde API-Sports baseball (plan Pro 7500 req/día).
Uso: manage.py sync_mlb_data [--season 2026] [--teams] [--games]
"""
from django.core.management.base import BaseCommand
from baseball_data.services import mlb_service


class Command(BaseCommand):
    help = "Sincroniza equipos y partidos MLB desde API-Sports baseball"

    def add_arguments(self, parser):
        parser.add_argument('--season', type=int, default=2026)
        parser.add_argument('--teams', action='store_true', help='Sincronizar equipos')
        parser.add_argument('--games', action='store_true', help='Sincronizar partidos de --season')
        parser.add_argument('--all', action='store_true', help='Equipos + partidos')

    def handle(self, *args, **options):
        season = options['season']
        do_teams = options['teams'] or options['all']
        do_games = options['games'] or options['all']
        if not (do_teams or do_games):
            self.stderr.write("Indica --teams, --games o --all")
            return

        if do_teams:
            r = mlb_service.sync_teams(season=season)
            self.stdout.write(self.style.SUCCESS(f"Equipos: {r}"))

        if do_games:
            r = mlb_service.sync_games(season)
            self.stdout.write(self.style.SUCCESS(f"Partidos {season}: {r}"))
