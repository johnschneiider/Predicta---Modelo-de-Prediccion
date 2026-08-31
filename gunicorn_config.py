# Gunicorn configuration file
import multiprocessing

# Server socket
bind = "127.0.0.1:8015"
backlog = 2048

# Worker processes
# FIX 2026-08-31: con PostgreSQL (sin 'database is locked') ya es seguro
# subir de 1 a 3 workers (mejora capacidad de respuesta de la web).
workers = 3
worker_class = "sync"
worker_connections = 1000
timeout = 300  # 5 minutos - tiempo suficiente para procesar predicciones
keepalive = 2

# Logging
accesslog = "-"  # stdout
errorlog = "-"   # stderr
loglevel = "info"

# Process naming
proc_name = "gunicorn_predicta"

# Server mechanics
daemon = False
pidfile = None
umask = 0
user = None
group = None
tmp_upload_dir = None

# SSL (si es necesario)
keyfile = None
certfile = None

# Configuración de Django
import os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "betting_bot.settings_production")
