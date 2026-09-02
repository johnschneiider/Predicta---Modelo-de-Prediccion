"""
Vistas de notificaciones: landing de vinculación de WhatsApp (SOLO superuser).

El QR se obtiene del microservicio local vía proxy (sin CORS) y la plantilla
lo refresca hasta que la sesión queda conectada. Solo John (admin) puede
ver/vincular/desvincular la sesión.
"""

import requests
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from .services import API_KEY, INSTANCE_NAME, WHATSAPP_SERVICE_URL, TIMEOUT_S

SUPERUSER_REQUERIDO = user_passes_test(
    lambda u: u.is_superuser, login_url='/',
)


def _requiere_api_key():
    headers = {'X-Api-Key': API_KEY} if API_KEY else {}
    return headers


@login_required
@SUPERUSER_REQUERIDO
def landing_whatsapp(request):
    """Página exclusiva del admin para vincular/desvincular el WhatsApp."""
    return render(request, 'notificaciones/whatsapp.html', {})


@login_required
@SUPERUSER_REQUERIDO
def whatsapp_estado(request):
    """Proxy JSON: estado de conexión + QR (si hace falta vincular)."""
    try:
        state_resp = requests.get(
            f"{WHATSAPP_SERVICE_URL}/instance/connectionState/{INSTANCE_NAME}",
            timeout=5,
        )
        state_data = state_resp.json()
        state = state_data.get('instance', {}).get('state', 'disconnected')
        if state == 'open':
            return JsonResponse({'state': 'open'})

        qr_resp = requests.get(
            f"{WHATSAPP_SERVICE_URL}/instance/qrBase64/{INSTANCE_NAME}",
            timeout=10,
        )
        qr_data = qr_resp.json()
        raw = qr_data.get('qr') or qr_data.get('base64') or qr_data.get('qrCode', '')
        if raw:
            if not raw.startswith('data:'):
                raw = f'data:image/png;base64,{raw}'
            return JsonResponse({'state': 'qr', 'base64': raw})
        return JsonResponse({'state': 'esperando'})
    except requests.RequestException as e:
        return JsonResponse({'state': 'error', 'error': str(e)}, status=502)


@login_required
@SUPERUSER_REQUERIDO
@require_POST
def whatsapp_logout(request):
    """Desvincula la sesión de WhatsApp (borra la sesión local del servicio)."""
    try:
        resp = requests.delete(
            f"{WHATSAPP_SERVICE_URL}/instance/logout/{INSTANCE_NAME}",
            headers=_requiere_api_key(),
            timeout=10,
        )
        if resp.status_code in (200, 201):
            messages.success(request, '✅ Sesión de WhatsApp desvinculada. Escanea el nuevo QR para volver a vincular.')
        else:
            messages.error(request, f'❌ No se pudo desvincular: HTTP {resp.status_code}.')
    except requests.RequestException as e:
        messages.error(request, f'❌ Error de conexión con el servicio: {e}')
    return redirect('notificaciones:whatsapp_landing')
