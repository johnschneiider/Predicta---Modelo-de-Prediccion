"""
Comando para sincronizar datos de NBA
"""

from django.core.management.base import BaseCommand, CommandError
from basketball_data.services import nba_service


class Command(BaseCommand):
    help = 'Sincroniza datos de NBA desde la API oficial'

    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            choices=['teams', 'players', 'games', 'all'],
            default='all',
            help='Tipo de datos a sincronizar'
        )
        parser.add_argument(
            '--season',
            type=str,
            default='2025-26',
            help='Temporada a sincronizar (ej: 2025-26)'
        )

    def handle(self, *args, **options):
        sync_type = options['type']
        season = options['season']

        self.stdout.write(
            self.style.SUCCESS(f'🏀 Iniciando sincronización de datos NBA...')
        )

        try:
            if sync_type in ['teams', 'all']:
                self.stdout.write('📋 Sincronizando equipos...')
                result = nba_service.sync_teams()
                if 'error' in result:
                    raise CommandError(f"Error sincronizando equipos: {result['error']}")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Equipos: {result['created']} creados, {result['updated']} actualizados"
                    )
                )

            if sync_type in ['players', 'all']:
                self.stdout.write('👥 Sincronizando jugadores...')
                result = nba_service.sync_players()
                if 'error' in result:
                    raise CommandError(f"Error sincronizando jugadores: {result['error']}")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Jugadores: {result['created']} creados, {result['updated']} actualizados"
                    )
                )

            if sync_type in ['games', 'all']:
                self.stdout.write(f'🏀 Sincronizando partidos de la temporada {season}...')
                result = nba_service.sync_current_season_games(season=season)
                if 'error' in result:
                    raise CommandError(f"Error sincronizando partidos: {result['error']}")
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✅ Partidos: {result['created']} creados, {result['updated']} actualizados, {result['errors']} errores"
                    )
                )

            self.stdout.write(
                self.style.SUCCESS('🎉 Sincronización completada exitosamente!')
            )

        except Exception as e:
            raise CommandError(f"Error durante la sincronización: {str(e)}")
