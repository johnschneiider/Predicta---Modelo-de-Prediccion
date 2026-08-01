"""
Test para verificar el login con certificados SSL de Betfair
"""
import os
import django
import sys

sys.path.append('/var/www/predicta.com.co')
os.environ['DJANGO_SETTINGS_MODULE'] = 'betting_bot.settings'
django.setup()

from betfair.services import BetfairAPIService
from django.conf import settings

print("=== Configuración actual de Betfair ===")
print(f"BETFAIR_USERNAME: {getattr(settings, 'BETFAIR_USERNAME', 'NOT SET')}")
print(f"BETFAIR_APP_KEY: {getattr(settings, 'BETFAIR_APP_KEY', 'NOT SET')[:10]}...")
print(f"BETFAIR_SANDBOX: {getattr(settings, 'BETFAIR_SANDBOX', True)}")
print(f"BETFAIR_CERT_DIR: {getattr(settings, 'BETFAIR_CERT_DIR', 'NOT SET')}")

# Crear servicio
service = BetfairAPIService()
print("\n=== Método login actual ===")
print("service.client = APIClient(")
print(f"  username=service.username")
print(f"  password=service.password")
print(f"  app_key=service.app_key")
print(f"  certs='',  # ← PROBLEMA: vacío")
print("  locale='es',")
print("  light_weight=True")
print(")")

print("\n=== Requerimientos para robot login (producción) ===")
print("1. Crear cuenta Betfair Exchange Developer")
print("2. Generar Application Key en https://developer.betfair.com/")
print("3. Crear certificados SSL para autenticación robot:")
print("   - client-2048.crt (certificado público)")
print("   - client-2048.key (clave privada)")
print("4. Subir certificado público a Betfair Developer Dashboard")
print("5. Guardar ambos archivos en directorio seguro en VPS")

print("\n=== Directorio sugerido para certificados ===")
print("/etc/betfair/certs/")
print("   ├── client-2048.crt")
print("   └── client-2048.key")

print("\n=== Cambios necesarios en settings.py ===")
print("BETFAIR_CERT_DIR = '/etc/betfair/certs/'")
print("# O alternativamente: certificados individuales")
print("BETFAIR_CERT_PATH = '/etc/betfair/certs/client-2048.crt'")
print("BETFAIR_KEY_PATH = '/etc/betfair/certs/client-2048.key'")

print("\n=== Cambio en betfair/services.py ===")
print("En def login(self):")
print("    certs = settings.BETFAIR_CERT_DIR")
print("    self.client = APIClient(")
print("        username=self.username,")
print("        password=self.password,")
print("        app_key=self.app_key,")
print("        certs=certs,")
print("        locale='es',")
print("        light_weight=True")
print("    )")