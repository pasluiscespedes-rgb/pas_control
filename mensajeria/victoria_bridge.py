"""Consultas puntuales de WhatsFORTEX, sin alterar estado de lectura.

No es un conector externo: exige sesión Django, CSRF y solicitud POST
explícita del propietario. Nunca habilitar acceso mediante clave en URL.
"""
import logging
from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from .models import ConversacionWhatsApp, MensajeWhatsApp

audit = logging.getLogger("victoria_bridge.audit")


@login_required
@require_POST
def consultar_whatsfortex(request):
    """Una solicitud explícita por consulta, restringida al usuario propietario."""
    owner_id = getattr(settings, "VICTORIA_BRIDGE_OWNER_USER_ID", None)
    if not owner_id or not request.user.is_superuser or str(request.user.pk) != str(owner_id):
        return JsonResponse({"error": "Acceso no autorizado"}, status=403)

    try:
        limite = min(max(int(request.POST.get("limite", "30")), 1), 50)
    except (TypeError, ValueError):
        return JsonResponse({"error": "Límite inválido"}, status=400)

    termino = (request.POST.get("buscar") or "").strip()
    conversacion_id = (request.POST.get("conversacion_id") or "").strip()
    if not conversacion_id and len(termino) < 3:
        return JsonResponse({"error": "Indicar conversación o búsqueda de al menos 3 caracteres"}, status=400)

    conversaciones = ConversacionWhatsApp.objects.filter(activa=True)
    if conversacion_id:
        if not conversacion_id.isdecimal():
            return JsonResponse({"error": "ID inválido"}, status=400)
        conversaciones = conversaciones.filter(pk=int(conversacion_id))
    else:
        conversaciones = conversaciones.filter(
            Q(nombre_whatsapp__icontains=termino)
            | Q(cliente__nombre__icontains=termino)
            | Q(cliente__apellido__icontains=termino)
        ).distinct()

    conversaciones = list(conversaciones.order_by("-ultimo_mensaje_en", "-pk")[:10])
    resultado = []
    for conversacion in conversaciones:
        mensajes = list(
            MensajeWhatsApp.objects.filter(conversacion_id=conversacion.pk)
            .order_by("-fecha_mensaje", "-pk")
            .values("id", "direccion", "tipo", "texto", "fecha_mensaje", "estado")[:limite]
        )
        resultado.append({
            "conversacion_id": conversacion.pk,
            "nombre": conversacion.nombre_whatsapp,
            "mensajes": list(reversed(mensajes)),
        })

    # No incluir contenido, teléfonos ni nombres en registros de auditoría.
    audit.info("consulta_whatsfortex user_id=%s conversaciones=%s limite=%s", request.user.pk, len(resultado), limite)
    response = JsonResponse({"conversaciones": resultado})
    response["Cache-Control"] = "no-store"
    return response
