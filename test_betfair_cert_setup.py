#!/usr/bin/env python3
"""
Script de configuración para certificados SSL de Betfair.

Pasos necesarios:
1. Crear cuenta Betfair Exchange Developer
2. Generar certificado SSL con OpenSSL
3. Subir certificado público a Betfair Developer Dashboard
4. Configurar archivos en VPS
"""

import os
import sys
import subprocess

def print_header(title):
    print("\n" + "="*60)
    print(f"  {title}")
    print("="*60)

def check_openssl():
    print_header("Verificando OpenSSL")
    try:
        result = subprocess.run(["openssl", "version"], capture_output=True, text=True)
        print(f"✓ OpenSSL instalado: {result.stdout.strip()}")
        return True
    except FileNotFoundError:
        print("✗ OpenSSL no encontrado. Instalar con: apt install openssl")
        return False

def generate_certificates():
    print_header("Generando certificados SSL para Betfair")
    
    cert_dir = "/etc/betfair/certs"
    os.makedirs(cert_dir, exist_ok=True)
    
    print(f"Directorio: {cert_dir}")
    
    # Generar clave privada RSA-2048
    key_path = os.path.join(cert_dir, "client-2048.key")
    print(f"\n1. Generando clave privada RSA-2048: {key_path}")
    
    key_cmd = [
        "openssl", "genrsa",
        "-out", key_path,
        "2048"
    ]
    
    try:
        subprocess.run(key_cmd, check=True)
        print(f"✓ Clave privada generada")
    except subprocess.CalledProcessError as e:
        print(f"✗ Error generando clave: {e}")
        return False
    
    # Generar CSR (Certificate Signing Request)
    csr_path = os.path.join(cert_dir, "client-2048.csr")
    print(f"\n2. Generando CSR: {csr_path}")
    
    csr_cmd = [
        "openssl", "req",
        "-new",
        "-key", key_path,
        "-out", csr_path,
        "-subj", "/C=CO/ST=Bogota/L=Bogota/O=Predicta Bot/CN=betfair.robot"
    ]
    
    try:
        subprocess.run(csr_cmd, check=True)
        print(f"✓ CSR generado")
    except subprocess.CalledProcessError as e:
        print(f"✗ Error generando CSR: {e}")
        return False
    
    # Auto-firmar certificado
    crt_path = os.path.join(cert_dir, "client-2048.crt")
    print(f"\n3. Auto-firmando certificado: {crt_path}")
    
    crt_cmd = [
        "openssl", "x509",
        "-req",
        "-days", "365",
        "-in", csr_path,
        "-signkey", key_path,
        "-out", crt_path
    ]
    
    try:
        subprocess.run(crt_cmd, check=True)
        print(f"✓ Certificado generado")
    except subprocess.CalledProcessError as e:
        print(f"✗ Error firmando certificado: {e}")
        return False
    
    # Crear archivo PEM combinado
    pem_path = os.path.join(cert_dir, "client-2048.pem")
    print(f"\n4. Creando archivo PEM combinado: {pem_path}")
    
    with open(crt_path, 'r') as crt_file:
        crt_content = crt_file.read()
    
    with open(key_path, 'r') as key_file:
        key_content = key_file.read()
    
    with open(pem_path, 'w') as pem_file:
        pem_file.write(crt_content + "\n" + key_content)
    
    print(f"✓ Archivo PEM creado")
    
    # Cambiar permisos (clave privada solo para root)
    os.chmod(key_path, 0o600)
    os.chmod(pem_path, 0o600)
    print(f"✓ Permisos ajustados para claves privadas")
    
    return True

def verify_certificates():
    print_header("Verificando certificados generados")
    
    cert_dir = "/etc/betfair/certs"
    
    files = [
        ("client-2048.key", "Clave privada RSA-2048"),
        ("client-2048.crt", "Certificado público"),
        ("client-2048.pem", "Certificado PEM combinado"),
        ("client-2048.csr", "CSR (puede borrarse)")
    ]
    
    for filename, description in files:
        path = os.path.join(cert_dir, filename)
        if os.path.exists(path):
            size = os.path.getsize(path)
            print(f"✓ {description:25} {path:30} {size:>8} bytes")
        else:
            print(f"✗ {description:25} {path:30} NO ENCONTRADO")
    
    # Verificar contenido
    print("\nInspección de certificado:")
    cert_path = os.path.join(cert_dir, "client-2048.crt")
    if os.path.exists(cert_path):
        try:
            result = subprocess.run(
                ["openssl", "x509", "-in", cert_path, "-text", "-noout"],
                capture_output=True, text=True
            )
            lines = result.stdout.split('\n')
            for line in lines[:5]:
                if line.strip():
                    print(f"  {line}")
        except:
            pass

def next_steps():
    print_header("PASOS SIGUIENTES")
    
    print("1. Crear cuenta Betfair Exchange Developer")
    print("   https://developer.betfair.com/")
    
    print("\n2. Generar Application Key")
    print("   - Ir a 'My Account' → 'Application Keys'")
    print("   - Crear nueva clave para 'API-NG'")
    
    print("\n3. Subir certificado a Betfair")
    print("   a. Ir a https://myaccount.betfair.com/accountdetails/mysecurity?showAPI=1")
    print("   b. Buscar sección 'Automated Betting Program Access'")
    print("   c. Click 'Edit' → 'Browse'")
    print("   d. Seleccionar /etc/betfair/certs/client-2048.crt")
    print("   e. Click 'Upload Certificate'")
    
    print("\n4. Configurar credenciales en settings.py")
    print("   BETFAIR_APP_KEY = 'tu_application_key'")
    print("   BETFAIR_USERNAME = 'tu_usuario_betfair'")
    print("   BETFAIR_PASSWORD = 'tu_contraseña'")
    print("   BETFAIR_SANDBOX = False  # Cambiar a False para producción")
    
    print("\n5. Configurar directorio de certificados")
    print("   BETFAIR_CERT_DIR = '/etc/betfair/certs/'")

def main():
    print_header("CONFIGURACIÓN CERTIFICADOS SSL BETFAIR")
    
    if not check_openssl():
        sys.exit(1)
    
    print("\n¿Deseas generar los certificados ahora? (s/n)")
    response = input().strip().lower()
    
    if response == 's':
        if generate_certificates():
            verify_certificates()
            next_steps()
    else:
        print("Saltando generación de certificados...")
        next_steps()

if __name__ == "__main__":
    main()