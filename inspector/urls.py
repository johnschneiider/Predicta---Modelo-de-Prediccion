from django.urls import path

from . import views

app_name = 'inspector'

urlpatterns = [
    path('', views.lista_inspecciones, name='lista'),
]
