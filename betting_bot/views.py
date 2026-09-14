from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.views.decorators.cache import never_cache
from django.utils import timezone

from auto_betting.models import ShowcasePick


@never_cache
def landing_page(request):
    """Página de inicio premium Predicta - Edge Estadístico.

    El bloque de preview muestra el partido destacado más reciente generado
    por el motor (`manage.py build_showcase_pick`). Si no hay ninguno cuyo
    partido siga próximo, la portada muestra un estado neutro (sin datos
    fijos de ejemplo).
    """
    showcase = (
        ShowcasePick.objects
        .filter(start_time__gt=timezone.now())
        .order_by('-generado')
        .first()
    )
    return render(request, 'index.html', {
        'user': request.user,
        'showcase': showcase,
    })
