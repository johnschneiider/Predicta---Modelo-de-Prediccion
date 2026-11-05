# -*- coding: utf-8 -*-
"""Bloqueo de acceso a las opciones del menú de usuario no asignadas.

Oculta el menú no basta: si un usuario escribe la URL directa de una sección
que no tiene asignada, se le redirige a su dashboard con un mensaje. Los
superusuarios y las rutas que no son opciones del menú no se tocan.
"""

from django.contrib import messages
from django.shortcuts import redirect

from .menu import CODIGO_POR_URL_NAME, permisos_efectivos


class PermisoMenuMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_view(self, request, view_func, view_args, view_kwargs):
        user = getattr(request, 'user', None)
        if user is None or not user.is_authenticated or user.is_superuser:
            return None

        match = getattr(request, 'resolver_match', None)
        if match is None:
            return None

        codigo = CODIGO_POR_URL_NAME.get(match.view_name)
        if codigo is None or permisos_efectivos(user).get(codigo):
            return None

        messages.error(
            request,
            'No tienes permiso para acceder a esa sección. '
            'Solicítalo al administrador.',
        )
        return redirect('cuentas:dashboard')
