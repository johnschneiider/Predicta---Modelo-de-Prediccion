"""Vistas del Inspector: panel superuser con las inspecciones."""

from django.contrib.auth.decorators import login_required, user_passes_test
from django.db.models import Count
from django.shortcuts import render

from .models import InspeccionApuesta

SUPERUSER_REQUERIDO = user_passes_test(lambda u: u.is_superuser, login_url='/')


@login_required
@SUPERUSER_REQUERIDO
def lista_inspecciones(request):
    veredicto = request.GET.get('veredicto') or ''
    qs = (InspeccionApuesta.objects
          .select_related('apuesta', 'apuesta__usuario')
          .order_by('-creado'))
    if veredicto:
        qs = qs.filter(veredicto=veredicto)
    conteos = dict(InspeccionApuesta.objects
                   .values_list('veredicto')
                   .annotate(n=Count('id')))
    return render(request, 'inspector/lista.html', {
        'inspecciones': qs[:300],
        'conteos': conteos,
        'filtro': veredicto,
        'total': sum(conteos.values()),
    })
