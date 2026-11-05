# -*- coding: utf-8 -*-
"""Context processors de la app cuentas."""

from .menu import permisos_efectivos


def menu_permisos(request):
    """Expone {codigo: bool} al navbar para decidir qué opciones mostrar.

    Anónimos no tienen permisos (el navbar solo muestra el botón de login);
    el usuario autenticado consulta una sola vez por request (cache en el
    objeto user, compartida con el middleware de bloqueo)."""
    user = getattr(request, 'user', None)
    if user is None or not user.is_authenticated:
        return {'menu_permisos': {}}
    return {'menu_permisos': permisos_efectivos(user)}
