# -*- coding: utf-8 -*-
"""Catálogo de opciones del menú de usuario (templates/partials/navbar.html).

Fuente de verdad única del control de acceso: si se agrega una opción al
navbar, se agrega aquí (mismo `codigo`) para que la reconozcan el middleware
de bloqueo, el contexto de plantillas y el panel de permisos del superadmin.

`url_names` = nombres de URL de Django que habilita la opción, incluidas sus
subpáginas dependientes (p. ej. paperbet de baloncesto/papertrading cuelgan
de "Paperbet (Motores)").

Modelo de permisos (decisión 2026-10-13): por defecto TODO denegado; el
superadmin asigna opción por opción en el panel de usuarios. Los superusuarios
conservan acceso total y no se ven afectados.
"""

MENU_OPCIONES = [
    {
        'grupo': 'Predicciones',
        'grupo_icono': '📊',
        'items': [
            {'codigo': 'pred_dashboard', 'etiqueta': '📊 Dashboard',
             'url_names': ('ai_predictions:dashboard',)},
            {'codigo': 'pred_nueva', 'etiqueta': '🔮 Predicciones',
             'url_names': ('ai_predictions:prediction_form',)},
            {'codigo': 'pred_historial', 'etiqueta': '🕘 Historial',
             'url_names': ('ai_predictions:prediction_history',)},
            {'codigo': 'pred_mis_apuestas', 'etiqueta': '🎟️ Mis apuestas',
             'url_names': ('ai_predictions:mis_apuestas',)},
        ],
    },
    {
        'grupo': 'NBA / MLB',
        'grupo_icono': '🏀⚾',
        'items': [
            {'codigo': 'nba_prediccion', 'etiqueta': '🏀 Predicción NBA',
             'url_names': ('basketball_data:prediction_form',)},
            {'codigo': 'nba_valor', 'etiqueta': '🏀 Valor NBA',
             'url_names': ('basketball_data:value_finder',)},
            {'codigo': 'nba_dashboard', 'etiqueta': '🏀 Dashboard NBA',
             'url_names': ('basketball_data:dashboard',)},
            {'codigo': 'mlb_prediccion', 'etiqueta': '⚾ Predicción MLB',
             'url_names': ('baseball_data:prediction_form',)},
            {'codigo': 'mlb_valor', 'etiqueta': '⚾ Valor MLB',
             'url_names': ('baseball_data:value_finder',)},
            {'codigo': 'mlb_dashboard', 'etiqueta': '⚾ Dashboard MLB',
             'url_names': ('baseball_data:dashboard',)},
        ],
    },
    {
        'grupo': 'Datos',
        'grupo_icono': '🗂',
        'items': [
            {'codigo': 'datos_dashboard', 'etiqueta': '📁 Datos',
             'url_names': ('football_data:dashboard',)},
            {'codigo': 'datos_partidos', 'etiqueta': '📋 Partidos',
             'url_names': ('football_data:matches_list',)},
            {'codigo': 'datos_importar', 'etiqueta': '⬆️ Importar',
             'url_names': ('football_data:import',)},
            {'codigo': 'datos_scraper', 'etiqueta': '🤖 Scraper',
             'url_names': ('ai_predictions:scraper_corners',)},
        ],
    },
    {
        'grupo': 'Apuestas & Paperbet',
        'grupo_icono': '🎰',
        'items': [
            {'codigo': 'ap_value', 'etiqueta': '💰 Value Bets',
             'url_names': ('value_betting:dashboard',)},
            {'codigo': 'ap_betplay', 'etiqueta': '🎰 Apuestas BetPlay',
             'url_names': ('auto_betting:historial',)},
            {'codigo': 'ap_paperbet', 'etiqueta': '📄 Paperbet (Motores)',
             'url_names': ('auto_betting:paperbet',
                           'auto_betting:paperbet_basket',
                           'auto_betting:papertrading')},
            {'codigo': 'ap_config', 'etiqueta': '⚙️ Config BetPlay',
             'url_names': ('auto_betting:configuracion',)},
        ],
    },
]

OPCIONES = [item for grupo in MENU_OPCIONES for item in grupo['items']]
OPCIONES_POR_CODIGO = {o['codigo']: o for o in OPCIONES}
CODIGO_POR_URL_NAME = {url_name: o['codigo']
                       for o in OPCIONES
                       for url_name in o['url_names']}


def permisos_efectivos(user) -> dict:
    """{codigo: bool} de todas las opciones del menú para un usuario.

    Superusuario -> todo permitido (no se consulta la BD).
    Resto -> fila explícita en PermisoMenu; sin fila = denegado.
    Se cachea en el objeto user para reutilizar entre middleware y plantillas.
    """
    cache = getattr(user, '_permisos_menu_cache', None)
    if cache is not None:
        return cache

    if not user.is_authenticated:
        cache = {}
    elif user.is_superuser:
        cache = {codigo: True for codigo in OPCIONES_POR_CODIGO}
    else:
        from .models import PermisoMenu
        filas = dict(PermisoMenu.objects.filter(usuario=user)
                     .values_list('codigo', 'permitido'))
        cache = {codigo: bool(filas.get(codigo, False))
                 for codigo in OPCIONES_POR_CODIGO}
    user._permisos_menu_cache = cache
    return cache


def grupos_con_estado(user) -> list[dict]:
    """Catálogo agrupado con el estado actual (para el panel de permisos)."""
    efectivos = permisos_efectivos(user)
    return [
        {
            'grupo': grupo['grupo'],
            'grupo_icono': grupo['grupo_icono'],
            'items': [
                {**item, 'permitido': efectivos.get(item['codigo'], False)}
                for item in grupo['items']
            ],
        }
        for grupo in MENU_OPCIONES
    ]
