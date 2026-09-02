from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views import View
from django.views.decorators.http import require_POST
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from .forms import FormularioLogin, FormularioRegistro, FormularioCrearUsuario, FormularioEditarUsuario, FormularioCambiarContraseña
from .models import Usuario, LoginAttempt

# ── Rate limit de login (anti fuerza bruta) ──
MAX_LOGIN_ATTEMPTS = 5        # intentos fallidos permitidos
LOGIN_WINDOW_MINUTES = 15     # ventana de tiempo en minutos
LOGIN_BLOCK_MINUTES = 15      # tiempo de bloqueo en minutos


def get_client_ip(request):
    """Obtiene la IP real del cliente, considerando el proxy de nginx (X-Forwarded-For)."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        return xff.split(',')[0].strip()
    return request.META.get('HTTP_X_REAL_IP') or request.META.get('REMOTE_ADDR', '0.0.0.0')


def _ip_bloqueada(ip):
    """True si la IP superó el límite de intentos fallidos en la ventana."""
    cutoff = timezone.now() - timedelta(minutes=LOGIN_WINDOW_MINUTES)
    fallidos = LoginAttempt.objects.filter(
        ip_address=ip, success=False, timestamp__gte=cutoff
    ).count()
    return fallidos >= MAX_LOGIN_ATTEMPTS

class VistaLogin(View):
    """
    Vista para el login de usuarios
    """
    def get(self, request):
        if request.user.is_authenticated:
            return redirect('cuentas:dashboard')
        
        form = FormularioLogin()
        return render(request, 'cuentas/login.html', {'form': form})
    
    def post(self, request):
        ip = get_client_ip(request)

        # 1. Rate limit: bloquear IP con demasiados intentos fallidos
        if _ip_bloqueada(ip):
            messages.error(
                request,
                f'Demasiados intentos fallidos desde tu IP. Intenta de nuevo en {LOGIN_BLOCK_MINUTES} minutos.'
            )
            form = FormularioLogin()
            return render(request, 'cuentas/login.html', {'form': form}, status=429)

        form = FormularioLogin(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            # Registrar intento exitoso (y limpiar fallidos de esta IP)
            LoginAttempt.objects.create(ip_address=ip, username=request.POST.get('username', ''), success=True)
            LoginAttempt.objects.filter(ip_address=ip, success=False).delete()
            messages.success(request, f'¡Bienvenido, {user.get_full_name()}!')
            return redirect('cuentas:dashboard')
        else:
            # Registrar intento fallido
            LoginAttempt.objects.create(ip_address=ip, username=request.POST.get('username', ''), success=False)
            messages.error(request, 'Credenciales inválidas. Intenta de nuevo.')
        
        return render(request, 'cuentas/login.html', {'form': form})

class VistaRegistro(View):
    """
    REGISTRO DESHABILITADO - Plataforma cerrada
    """
    def get(self, request):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Registro deshabilitado. Solo acceso por invitación.")
    
    def post(self, request):
        from django.http import HttpResponseForbidden
        return HttpResponseForbidden("Registro deshabilitado. Solo acceso por invitación.")

@method_decorator(login_required, name='dispatch')
class VistaDashboard(View):
    """
    Vista del dashboard principal
    """
    def get(self, request):
        context = {
            'usuario': request.user,
        }
        return render(request, 'cuentas/dashboard.html', context)

def vista_logout(request):
    """
    Vista para cerrar sesión
    """
    logout(request)
    messages.info(request, 'Has cerrado sesión exitosamente.')
    return redirect('cuentas:login')

# Decorador para verificar que el usuario es superusuario
def es_superusuario(user):
    return user.is_authenticated and user.is_superuser

@method_decorator(user_passes_test(es_superusuario), name='dispatch')
class VistaPanelUsuarios(View):
    """
    Vista principal del panel de administración de usuarios
    """
    def get(self, request):
        # Obtener todos los usuarios excepto superusuarios
        usuarios = Usuario.objects.filter(is_superuser=False).order_by('-fecha_registro')
        
        # Búsqueda
        query = request.GET.get('q')
        if query:
            usuarios = usuarios.filter(
                Q(email__icontains=query) |
                Q(first_name__icontains=query) |
                Q(last_name__icontains=query)
            )
        
        # Paginación
        paginator = Paginator(usuarios, 10)
        page_number = request.GET.get('page')
        page_obj = paginator.get_page(page_number)
        
        context = {
            'page_obj': page_obj,   # el template itera page_obj.object_list
            'usuarios': page_obj,
            'query': query,
            'total_usuarios': usuarios.count(),
        }
        return render(request, 'cuentas/panel_usuarios.html', context)

@method_decorator(user_passes_test(es_superusuario), name='dispatch')
class VistaCrearUsuario(View):
    """
    Vista para crear nuevos usuarios
    """
    def get(self, request):
        form = FormularioCrearUsuario(initial={'is_active': True})
        return render(request, 'cuentas/crear_usuario.html', {'form': form})
    
    def post(self, request):
        form = FormularioCrearUsuario(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Usuario {user.get_full_name()} creado exitosamente.')
            return redirect('cuentas:panel_usuarios')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
        
        return render(request, 'cuentas/crear_usuario.html', {'form': form})

@method_decorator(user_passes_test(es_superusuario), name='dispatch')
class VistaEditarUsuario(View):
    """
    Vista para editar usuarios existentes
    """
    def get(self, request, user_id):
        usuario = get_object_or_404(Usuario, id=user_id)
        form = FormularioEditarUsuario(instance=usuario)
        return render(request, 'cuentas/editar_usuario.html', {'form': form, 'usuario': usuario})
    
    def post(self, request, user_id):
        usuario = get_object_or_404(Usuario, id=user_id)
        form = FormularioEditarUsuario(request.POST, instance=usuario)
        if form.is_valid():
            form.save()
            messages.success(request, f'Usuario {usuario.get_full_name()} actualizado exitosamente.')
            return redirect('cuentas:panel_usuarios')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
        
        return render(request, 'cuentas/editar_usuario.html', {'form': form, 'usuario': usuario})

@method_decorator(user_passes_test(es_superusuario), name='dispatch')
class VistaCambiarContraseña(View):
    """
    Vista para cambiar la contraseña de un usuario
    """
    def get(self, request, user_id):
        usuario = get_object_or_404(Usuario, id=user_id)
        form = FormularioCambiarContraseña()
        return render(request, 'cuentas/cambiar_contraseña.html', {'form': form, 'usuario': usuario})
    
    def post(self, request, user_id):
        usuario = get_object_or_404(Usuario, id=user_id)
        form = FormularioCambiarContraseña(request.POST)
        if form.is_valid():
            usuario.set_password(form.cleaned_data['password1'])
            usuario.save()
            messages.success(request, f'Contraseña de {usuario.get_full_name()} cambiada exitosamente.')
            return redirect('cuentas:panel_usuarios')
        else:
            messages.error(request, 'Por favor, corrige los errores en el formulario.')
        
        return render(request, 'cuentas/cambiar_contraseña.html', {'form': form, 'usuario': usuario})

@user_passes_test(es_superusuario)
def vista_eliminar_usuario(request, user_id):
    """
    Vista para eliminar un usuario
    """
    usuario = get_object_or_404(Usuario, id=user_id)
    
    if request.method == 'POST':
        nombre_usuario = usuario.get_full_name()
        usuario.delete()
        messages.success(request, f'Usuario {nombre_usuario} eliminado exitosamente.')
        return redirect('cuentas:panel_usuarios')
    
    return render(request, 'cuentas/eliminar_usuario.html', {'usuario': usuario})

@user_passes_test(es_superusuario)
@require_POST
def vista_suspender_usuario(request, user_id):
    """
    Suspende o reactiva una cuenta (toggle is_active).
    No permite suspender a otro superusuario ni a uno mismo.
    """
    usuario = get_object_or_404(Usuario, id=user_id)

    if usuario.is_superuser:
        messages.error(request, 'No puedes suspender a un superusuario.')
        return redirect('cuentas:panel_usuarios')
    if usuario == request.user:
        messages.error(request, 'No puedes suspender tu propia cuenta.')
        return redirect('cuentas:panel_usuarios')

    usuario.is_active = not usuario.is_active
    usuario.save(update_fields=['is_active'])

    estado = 'suspendida' if not usuario.is_active else 'reactivada'
    messages.success(request, f'Cuenta de {usuario.get_full_name()} {estado} exitosamente.')
    return redirect('cuentas:panel_usuarios')

@login_required
def configuracion_cuenta(request):
    """
    Configuración de la cuenta del usuario (número de WhatsApp para
    notificaciones). Cada usuario edita solo lo suyo.
    """
    from .forms import FormularioConfiguracionCuenta
    if request.method == 'POST':
        form = FormularioConfiguracionCuenta(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, '✅ Configuración de cuenta guardada.')
            return redirect('cuentas:configuracion_cuenta')
    else:
        form = FormularioConfiguracionCuenta(instance=request.user)
    return render(request, 'cuentas/configuracion.html', {
        'form': form,
        'usuario': request.user,
    })


@login_required
def enviar_bienvenida_whatsapp(request):
    """
    Botón de prueba de notificaciones (2026-09-02, pedido de John): envía el
    mensaje de bienvenida al WhatsApp del PROPIO usuario (nadie puede mandar
    mensajes a teléfonos ajenos). Auditado en NotificacionLog.
    """
    from notificaciones.models import NotificacionLog
    from notificaciones.services import enviar_bienvenida

    if request.method != 'POST':
        return redirect('cuentas:configuracion_cuenta')

    estado, detalle = enviar_bienvenida(request.user)
    if estado == NotificacionLog.ESTADO_ENVIADO:
        messages.success(
            request,
            '📱 ¡Mensaje de bienvenida enviado a tu WhatsApp! Revisa tu teléfono.',
        )
    elif estado == NotificacionLog.ESTADO_OMITIDO:
        messages.error(
            request,
            '⚠️ No tienes un número de WhatsApp registrado. Guárdalo en el '
            'formulario y vuelve a intentar.',
        )
    else:
        messages.error(
            request,
            f'❌ No se pudo enviar el mensaje ({detalle}). Intenta de nuevo en '
            'unos segundos.',
        )
    return redirect('cuentas:configuracion_cuenta')
