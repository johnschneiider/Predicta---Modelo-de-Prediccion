"""Sincroniza calendario/resultados NBA desde API-Sports (plan Pro basketball).
Uso: manage.py sync_nba_apisports --season 2026-2027
"""
from django.core.management.base import BaseCommand

from basketball_data.api_sports import basketball_api_service


class Command(BaseCommand):
    help = "Sincroniza partidos NBA desde API-Sports basketball (calendario/resultados)"

    def add_arguments(self, parser):
        parser.add_argument('--season', type=str, default='2026-2027',
                            help="Temporada API (ej. 2026-2027)")

    def handle(self, *args, **options):
        season = options['season']
        self.stdout.write(f"Sincronizando NBA {season} desde API-Sports...")
        r = basketball_api_service.sync_games(season)
        self.stdout.write(self.style.SUCCESS(f"Resultado: {r}"))
