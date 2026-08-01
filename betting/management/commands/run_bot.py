from django.core.management.base import BaseCommand
from betting_bot.main import BetfairOrchestrator
import logging

logger = logging.getLogger('betting')


class Command(BaseCommand):
    help = 'Ejecuta el bot de apuestas Predicta (automatización completa)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--interval',
            type=int,
            default=30,
            help='Intervalo entre ciclos en minutos (default: 30)'
        )
        parser.add_argument(
            '--cycles',
            type=int,
            default=None,
            help='Número de ciclos a ejecutar (default: infinito)'
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Simular sin colocar apuestas reales'
        )
    
    def handle(self, *args, **options):
        interval_minutes = options['interval']
        max_cycles = options['cycles'] or float('inf')
        dry_run = options['dry_run']
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Iniciando bot Predicta - Intervalo: {interval_minutes} min'
            )
        )
        
        if dry_run:
            self.stdout.write(
                self.style.WARNING('MODO DRY-RUN activado - No se colocarán apuestas reales')
            )
        
        # Configurar logging
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(self.stdout),
                logging.FileHandler('/var/log/predicta/betting_bot_django.log')
            ]
        )
        
        # Inicializar orquestador
        try:
            orchestrator = BetfairOrchestrator()
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error inicializando orquestador: {e}'))
            return
        
        # Ciclo principal
        cycle_count = 0
        
        import time
        from datetime import datetime
        
        try:
            while cycle_count < max_cycles:
                cycle_start = datetime.now()
                cycle_count += 1
                
                self.stdout.write(
                    self.style.SUCCESS(f'\n=== CICLO {cycle_count} - {cycle_start} ===')
                )
                
                if dry_run:
                    # Forzar sandbox en dry-run
                    from django.conf import settings
                    if hasattr(settings, 'BETFAIR_SANDBOX'):
                        original_sandbox = settings.BETFAIR_SANDBOX
                        settings.BETFAIR_SANDBOX = True
                
                # Ejecutar ciclo
                try:
                    orchestrator.run_cycle()
                except Exception as e:
                    self.stderr.write(self.style.ERROR(f'Error en ciclo {cycle_count}: {e}'))
                    logging.error(f'Error en ciclo {cycle_count}: {e}')
                
                if dry_run:
                    # Restaurar configuración original
                    from django.conf import settings
                    if hasattr(settings, 'BETFAIR_SANDBOX'):
                        settings.BETFAIR_SANDBOX = original_sandbox
                
                # Esperar para siguiente ciclo
                cycle_end = datetime.now()
                cycle_duration = (cycle_end - cycle_start).total_seconds() / 60.0
                
                self.stdout.write(
                    self.style.WARNING(
                        f'Ciclo {cycle_count} completado en {cycle_duration:.1f} min'
                    )
                )
                
                if cycle_count < max_cycles:
                    wait_minutes = max(1, interval_minutes - cycle_duration)
                    self.stdout.write(
                        f'Esperando {wait_minutes:.1f} minutos para próximo ciclo...'
                    )
                    
                    for minute in range(1, int(wait_minutes) + 1):
                        time.sleep(60)
                        if minute % 5 == 0:
                            self.stdout.write(f'  {minute} min...')
                    
                    # Esperar segundos restantes
                    remaining_seconds = (wait_minutes - int(wait_minutes)) * 60
                    if remaining_seconds > 0:
                        time.sleep(remaining_seconds)
                
        except KeyboardInterrupt:
            self.stdout.write(self.style.SUCCESS('\nBot detenido por usuario'))
        except Exception as e:
            self.stderr.write(self.style.ERROR(f'Error fatal: {e}'))
        
        self.stdout.write(self.style.SUCCESS('Bot finalizado'))