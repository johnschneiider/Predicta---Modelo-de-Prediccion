from django.core.management.base import BaseCommand
from matchbook.orchestrator import PredictaMatchbookOrchestrator
import logging
import time

logger = logging.getLogger('matchbook_bot')


class Command(BaseCommand):
    help = 'Ejecuta bot de trading automatizado entre Predicta y Matchbook Exchange'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--username',
            type=str,
            help='Email de cuenta Matchbook'
        )
        parser.add_argument(
            '--password',
            type=str,
            help='Contraseña de cuenta Matchbook'
        )
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Intervalo entre ciclos en minutos (default: 30)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sin colocar apuestas reales'
        )
        parser.add_argument(
            '--single-cycle',
            action='store_true',
            help='Ejecutar solo un ciclo y salir'
        )
    
    def handle(self, *args, **options):
        username = options['username']
        password = options['password']
        interval = options['interval']
        dry_run = options['dry_run']
        single_cycle = options['single_cycle']
        
        # Validar credenciales
        if not username or not password:
            self.stderr.write(self.style.ERROR(
                'Se requieren --username y --password'
            ))
            self.stderr.write('Ejemplo: python manage.py run_matchbook_bot '
                            '--username tu@email.com --password tu_contraseña '
                            '--dry-run')
            return
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(self.stdout),
                logging.FileHandler('/var/log/predicta/matchbook_bot.log')
            ]
        )
        
        # Mostrar configuración
        self.stdout.write(self.style.SUCCESS(
            f'=== PREDICTA + MATCHBOOK BOT ==='
        ))
        self.stdout.write(f'Usuario: {username}')
        self.stdout.write(f'Intervalo: {interval} minutos')
        self.stdout.write(f'Dry Run: {'SÍ' if dry_run else 'NO (APUESTAS REALES)'}')
        if dry_run:
            self.stdout.write(self.style.WARNING(
                '⚠️  MODO DRY RUN ACTIVADO - No se colocarán apuestas reales'
            ))
        
        # Inicializar orquestador
        orchestrator = PredictaMatchbookOrchestrator(username, password)
        
        # Intentar conectar
        self.stdout.write('\nConectando a Matchbook Exchange...')
        if not orchestrator.connect():
            self.stderr.write(self.style.ERROR(
                'Error conectando a Matchbook. Verifica credenciales.'
            ))
            return
        
        self.stdout.write(self.style.SUCCESS('✅ Conectado a Matchbook Exchange'))
        
        try:
            if single_cycle:
                # Ejecutar solo un ciclo
                self.stdout.write('\n=== EJECUTANDO CICLO ÚNICO ===')
                orchestrator.execute_trading_cycle(dry_run=dry_run)
                
            else:
                # Ejecutar continuamente
                self.stdout.write(f'\n=== INICIANDO TRADING CONTINUO ===')
                self.stdout.write(f'Los ciclos se ejecutarán cada {interval} minutos')
                self.stdout.write('Presiona Ctrl+C para detener\n')
                
                orchestrator.run_continuous(
                    interval_minutes=interval,
                    dry_run=dry_run
                )
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS('\nBot detenido por usuario'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error fatal: {e}'))
            
            # Intentar desconectar limpiamente
            try:
                orchestrator.disconnect()
            except:
                pass
        finally:
            # Desconectar
            orchestrator.disconnect()
            self.stdout.write(self.style.SUCCESS('Sesión cerrada en Matchbook'))
        
        self.stdout.write(self.style.SUCCESS('Bot finalizado'))


def main():
    """Función principal para ejecución directa"""
    import sys
    import os
    
    # Configurar Django
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'betting_bot.settings')
    import django
    django.setup()
    
    # Ejecutar comando
    if len(sys.argv) > 1:
        from django.core.management import execute_from_command_line
        execute_from_command_line(sys.argv)
    else:
        print("Uso: python run_matchbook_bot.py --username EMAIL --password PASS [--dry-run]")
        print("O como comando Django: python manage.py run_matchbook_bot")


if __name__ == "__main__":
    main()