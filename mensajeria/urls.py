from django.urls import path

from . import views


app_name = "mensajeria"

urlpatterns = [
    path(
        "webhook/",
        views.webhook_whatsapp,
        name="webhook_whatsapp",
    ),
]