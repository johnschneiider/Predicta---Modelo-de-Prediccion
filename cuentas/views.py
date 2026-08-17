from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.views import View
from django.utils.decorators import method_decorator
from django.http import JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q

from .forms import FormularioLogin, FormularioRegistro, FormularioCrearUsuario, FormularioEditarUsuario, FormularioCambiarContraseña
from .models import Usuario

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
        form = FormularioLogin(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'¡Bienvenido, {user.get_full_name()}!')
            return redirect('cuentas:dashboard')
        else:
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
        form = FormularioCrearUsuario()
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