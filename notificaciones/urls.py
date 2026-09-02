from django.urls import path

from . import views

app_name = 'notificaciones'

urlpatterns = [
    path('whatsapp/', views.landing_whatsapp, name='whatsapp_landing'),
    path('whatsapp/estado/', views.whatsapp_estado, name='whatsapp_estado'),
    path('whatsapp/logout/', views.whatsapp_logout, name='whatsapp_logout'),
]
