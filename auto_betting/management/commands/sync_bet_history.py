"""
Comando que sincroniza el historial de apuestas de BetPlay (coupon/history.json)
hacia el modelo HistorialApuesta, con filtro de fecha `--since` y opción `--email`.
"""

from django.core.management.base import BaseCommand

from auto_betting.models import AutoBetConfig
from auto_betting.services import sync_historial


class Command(BaseCommand):
    help = "Sincroniza el historial de apuestas de BetPlay a HistorialApuesta (con filtro de fecha y usuario)"

    def add_arguments(self, parser):
        parser.add_argument(
            '--since',
            type=str,
            default='2026-08-01',
            help='Importar solo apuestas desde esta fecha (YYYY-MM-DD). Default: 2026-08-01',
        )
        parser.add_argument(
            '--email',
            type=str,
            default=None,
            help='Correo del usuario. Si se omite, sincroniza para todos los usuarios con config.',
        )

    def handle(self, *args, **options):
        since_str = options.get('since') or '2026-08-01'
        email = options.get('email')

        configs = AutoBetConfig.objects.select_related('usuario').all()
        if email:
            configs = configs.filter(usuario__email=email)
        if not configs.exists():
            self.stderr.write("❌ No hay AutoBetConfig.")
            return

        for config in configs:
            result = sync_historial(since_str, usuario=config.usuario)
            self.stdout.write(f"\n👤 {config.usuario.email}:")
            if result.get('error'):
                self.stderr.write(f"   ❌ {result['error']}")
                continue
            if result.get('borrados'):
                self.stdout.write(f"   🧹 Borrados {result['borrados']} registros anteriores a {since_str}.")
            snaps = result.get('snapshots', 0)
            snaps_msg = f" 📸 {snaps} snapshots capturados." if snaps else ""
            self.stdout.write(
                self.style.SUCCESS(
                    f"   🏁 Historial sincronizado (desde {since_str}): "
                    f"{result['creados']} nuevos, {result['actualizados']} actualizados, "
                    f"{result['omitidos']} omitidos.{snaps_msg} Total en DB: {result['total']}."
                )
            )
