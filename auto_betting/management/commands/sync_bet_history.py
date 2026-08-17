"""
Comando que sincroniza el historial de apuestas de BetPlay (coupon/history.json)
hacia el modelo HistorialApuesta, con filtro de fecha `--since`.
"""

from django.core.management.base import BaseCommand

from auto_betting.services import sync_historial


class Command(BaseCommand):
    help = "Sincroniza el historial de apuestas de BetPlay a HistorialApuesta (con filtro de fecha)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--since',
            type=str,
            default='2026-08-01',
            help='Importar solo apuestas desde esta fecha (YYYY-MM-DD). Default: 2026-08-01',
        )

    def handle(self, *args, **options):
        since_str = options.get('since') or '2026-08-01'
        result = sync_historial(since_str)

        if result.get('error'):
            self.stderr.write(f"❌ {result['error']}")
            return

        if result.get('borrados'):
            self.stdout.write(f"🧹 Borrados {result['borrados']} registros anteriores a {since_str}.")

        self.stdout.write(
            self.style.SUCCESS(
                f"🏁 Historial sincronizado (desde {since_str}): "
                f"{result['creados']} nuevos, {result['actualizados']} actualizados, "
                f"{result['omitidos']} omitidos. Total en DB: {result['total']}."
            )
        )
