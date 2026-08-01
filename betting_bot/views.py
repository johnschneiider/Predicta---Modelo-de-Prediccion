from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache

@never_cache
def landing_page(request):
    """Página de inicio premium Predicta - Edge Estadístico"""
    return render(request, 'index.html', {
        'user': request.user
    })
