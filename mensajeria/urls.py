from django.urls import path

from . import views


app_name = "mensajeria"

urlpatterns = [
    path(
        "webhook/",
        views.webhook_whatsapp,
        name="webhook_whatsapp",
    ),
    path("estado-no-leidos/", views.estado_no_leidos_whatsapp, name="estado_no_leidos_whatsapp"),
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
    path(
        "conversacion/<int:conversacion_id>/enviar/",
        views.enviar_mensaje_whatsapp,
        name="enviar_mensaje_whatsapp",
    ),
    path(
        "media/<int:mensaje_id>/",
        views.ver_media_whatsapp,
        name="ver_media_whatsapp",
    ),
        path(
        "push/suscribir/",
        views.suscribir_push,
        name="suscribir_push",
    ),
        path(
        "buscar-clientes/",
        views.buscar_clientes_whatsapp,
        name="buscar_clientes_whatsapp",
    ),
        path(
        "cliente/<int:cliente_id>/abrir/",
        views.abrir_conversacion_cliente_whatsapp,
        name="abrir_conversacion_cliente_whatsapp",
    ),
        path(
        "conversacion/<int:conversacion_id>/plantilla/",
        views.enviar_plantilla_conversacion_whatsapp,
        name="enviar_plantilla_conversacion_whatsapp",
    ),
]