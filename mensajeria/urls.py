from django.urls import path

from . import views


app_name = "mensajeria"

urlpatterns = [
    path(
        "webhook/",
        views.webhook_whatsapp,
        name="webhook_whatsapp",
    ),
    path(
        "",
        views.bandeja_whatsapp,
        name="bandeja_whatsapp",
    ),
    path(
        "conversacion/<int:conversacion_id>/",
        views.bandeja_whatsapp,
        name="conversacion_whatsapp",
    ),
]