# Gunicorn configuration file
import multiprocessing

# Server socket
bind = "127.0.0.1:8015"
backlog = 2048

# Worker processes
workers = 1
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
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "betting_bot.settings")
