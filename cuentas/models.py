from django.contrib.auth.models import AbstractUser
from django.db import models

class Usuario(AbstractUser):
    """
    Modelo de usuario personalizado que extiende AbstractUser
    """
    email = models.EmailField(unique=True, verbose_name="Correo electrónico")
    first_name = models.CharField(max_length=30, verbose_name="Nombre")
    last_name = models.CharField(max_length=30, verbose_name="Apellido")
    avatar = models.URLField(blank=True, null=True, verbose_name="Avatar")
    fecha_registro = models.DateTimeField(auto_now_add=True, verbose_name="Fecha de registro")
    is_verified = models.BooleanField(default=False, verbose_name="Verificado")
    
    # Usar email como campo de login
    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['username', 'first_name', 'last_name']
    
    class Meta:
        verbose_name = "Usuario"
        verbose_name_plural = "Usuarios"
        db_table = 'usuarios'
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.email})"


class LoginAttempt(models.Model):
    """
    Registro de intentos de inicio de sesión para protección contra fuerza bruta.
    """
    ip_address = models.GenericIPAddressField(verbose_name="Dirección IP")
    username = models.CharField(max_length=150, blank=True, default="", verbose_name="Identificador usado")
    success = models.BooleanField(default=False, verbose_name="Éxito")
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Fecha")

    class Meta:
        verbose_name = "Intento de login"
        verbose_name_plural = "Intentos de login"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['ip_address', '-timestamp']),
        ]

    def __str__(self):
        estado = "OK" if self.success else "FALLÓ"
        return f"{self.ip_address} - {estado} ({self.timestamp:%Y-%m-%d %H:%M})"
    
    def get_full_name(self):
        """Retorna el nombre completo del usuario"""
        return f"{self.first_name} {self.last_name}".strip()
    
    def get_short_name(self):
        """Retorna el nombre corto del usuario"""
        return self.first_name