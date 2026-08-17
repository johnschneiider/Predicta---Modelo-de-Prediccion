from .settings import *
import os
from decouple import config

DEBUG = False
ALLOWED_HOSTS = ['*']
# Base de datos SQLite (más simple para el despliegue)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# Archivos estáticos - configuración limpia
STATIC_URL = '/static/'
STATIC_ROOT = '/var/www/predicta.com.co/staticfiles'

# Archivos de media
MEDIA_URL = '/media/'
MEDIA_ROOT = '/var/www/predicta.com.co/media/'

# Configuración de seguridad
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = 'DENY'
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_HTTPONLY = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True

# Eliminar configuraciones problemáticas
if 'STATICFILES_DIRS' in globals():
    del STATICFILES_DIRS
