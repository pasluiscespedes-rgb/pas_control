import hashlib
import hmac
import json
from datetime import datetime, timezone as dt_timezone

from django.conf import settings
from django.http import HttpResponse, HttpResponseForbidden, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.utils import timezone

from clientes.models import Cliente

from .models import ConversacionWhatsApp, MensajeWhatsApp
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, render


def _solo_digitos(valor):
    return "".join(
        caracter
        for caracter in str(valor or "")
        if caracter.isdigit()
    )


def _clave_telefono(valor):
    """
    Genera una clave comparable para teléfonos argentinos.

    Ejemplos:
    3814400515
    5493814400515
    +54 9 381 440-0515

    terminan comparándose como:
    3814400515
    """
    numero = _solo_digitos(valor)

    if numero.startswith("00"):
        numero = numero[2:]

    if numero.startswith("54"):
        numero = numero[2:]

        if numero.startswith("9"):
            numero = numero[1:]

    if numero.startswith("0"):
        numero = numero[1:]

    return numero


def _buscar_cliente_por_whatsapp(numero):
    clave_buscada = _clave_telefono(numero)

    if not clave_buscada:
        return None

    clientes = (
        Cliente.objects
        .exclude(whatsapp__isnull=True)
        .exclude(whatsapp="")
        .only("id", "whatsapp")
    )

    for cliente in clientes:
        if _clave_telefono(cliente.whatsapp) == clave_buscada:
            return cliente

    return None


def _fecha_desde_timestamp(valor):
    try:
        return datetime.fromtimestamp(
            int(valor),
            tz=dt_timezone.utc,
        )
    except (TypeError, ValueError, OverflowError):
        return timezone.now()


def _extraer_datos_mensaje(mensaje):
    tipo_original = mensaje.get("type", "unknown")

    tipos_permitidos = {
        "text",
        "image",
        "audio",
        "video",
        "document",
        "sticker",
        "location",
        "contacts",
        "reaction",
    }

    tipo = (
        tipo_original
        if tipo_original in tipos_permitidos
        else "unknown"
    )

    texto = ""
    media_id = ""
    nombre_archivo = ""
    mime_type = ""

    if tipo_original == "text":
        texto = mensaje.get("text", {}).get("body", "")

    elif tipo_original in {"image", "video"}:
        datos = mensaje.get(tipo_original, {})
        texto = datos.get("caption", "")
        media_id = datos.get("id", "")
        mime_type = datos.get("mime_type", "")

    elif tipo_original == "document":
        datos = mensaje.get("document", {})
        texto = datos.get("caption", "")
        media_id = datos.get("id", "")
        nombre_archivo = datos.get("filename", "")
        mime_type = datos.get("mime_type", "")

    elif tipo_original in {"audio", "sticker"}:
        datos = mensaje.get(tipo_original, {})
        media_id = datos.get("id", "")
        mime_type = datos.get("mime_type", "")

    elif tipo_original == "reaction":
        texto = mensaje.get("reaction", {}).get("emoji", "")

    elif tipo_original == "location":
        datos = mensaje.get("location", {})
        latitud = datos.get("latitude")
        longitud = datos.get("longitude")

        if latitud is not None and longitud is not None:
            texto = f"Ubicación: {latitud}, {longitud}"
        else:
            texto = "Ubicación compartida"

    elif tipo_original == "contacts":
        texto = "Contacto compartido"

    else:
        texto = f"Mensaje recibido de tipo: {tipo_original}"

    return {
        "tipo": tipo,
        "texto": texto,
        "media_id": media_id,
        "nombre_archivo": nombre_archivo,
        "mime_type": mime_type,
    }


def _procesar_mensaje_entrante(mensaje, nombre_whatsapp=""):
    telefono = _solo_digitos(mensaje.get("from", ""))

    if not telefono:
        return

    cliente = _buscar_cliente_por_whatsapp(telefono)

    conversacion, creada = ConversacionWhatsApp.objects.get_or_create(
        telefono=telefono,
        defaults={
            "cliente": cliente,
            "nombre_whatsapp": nombre_whatsapp,
        },
    )

    cambios_conversacion = []

    if conversacion.cliente_id is None and cliente is not None:
        conversacion.cliente = cliente
        cambios_conversacion.append("cliente")

    if (
        nombre_whatsapp
        and conversacion.nombre_whatsapp != nombre_whatsapp
    ):
        conversacion.nombre_whatsapp = nombre_whatsapp
        cambios_conversacion.append("nombre_whatsapp")

    fecha_mensaje = _fecha_desde_timestamp(
        mensaje.get("timestamp")
    )

    datos = _extraer_datos_mensaje(mensaje)

    objeto_mensaje, mensaje_creado = MensajeWhatsApp.objects.get_or_create(
        meta_message_id=mensaje.get("id"),
        defaults={
            "conversacion": conversacion,
            "direccion": MensajeWhatsApp.DIRECCION_ENTRANTE,
            "tipo": datos["tipo"],
            "texto": datos["texto"],
            "media_id": datos["media_id"],
            "nombre_archivo": datos["nombre_archivo"],
            "mime_type": datos["mime_type"],
            "fecha_mensaje": fecha_mensaje,
            "estado": MensajeWhatsApp.ESTADO_RECIBIDO,
            "leido_en_fortex": False,
            "payload_original": mensaje,
        },
    )

    if not mensaje_creado:
        if cambios_conversacion:
            conversacion.save(
                update_fields=cambios_conversacion + ["actualizada_en"]
            )
        return

    conversacion.ultimo_mensaje_en = fecha_mensaje
    conversacion.ultimo_mensaje_entrante_en = fecha_mensaje
    conversacion.no_leidos += 1

    cambios_conversacion.extend(
        [
            "ultimo_mensaje_en",
            "ultimo_mensaje_entrante_en",
            "no_leidos",
            "actualizada_en",
        ]
    )

    conversacion.save(
        update_fields=list(dict.fromkeys(cambios_conversacion))
    )


def _procesar_estado(estado):
    mensaje_id = estado.get("id")
    nuevo_estado = estado.get("status")

    if not mensaje_id:
        return

    estados_permitidos = {
        MensajeWhatsApp.ESTADO_ENVIADO,
        MensajeWhatsApp.ESTADO_ENTREGADO,
        MensajeWhatsApp.ESTADO_LEIDO,
        MensajeWhatsApp.ESTADO_FALLIDO,
    }

    if nuevo_estado not in estados_permitidos:
        return

    mensaje = MensajeWhatsApp.objects.filter(
        meta_message_id=mensaje_id
    ).first()

    if mensaje is None:
        return

    mensaje.estado = nuevo_estado

    if nuevo_estado == MensajeWhatsApp.ESTADO_FALLIDO:
        errores = estado.get("errors") or []

        if errores:
            error = errores[0]
            mensaje.error_codigo = str(error.get("code", ""))
            mensaje.error_detalle = (
                error.get("message")
                or error.get("title")
                or str(error)
            )

    mensaje.save(
        update_fields=[
            "estado",
            "error_codigo",
            "error_detalle",
            "actualizado_en",
        ]
    )


def _procesar_payload(payload):
    for entrada in payload.get("entry", []):
        for cambio in entrada.get("changes", []):
            valor = cambio.get("value", {})

            contactos = valor.get("contacts") or []

            nombre_whatsapp = ""

            if contactos:
                nombre_whatsapp = (
                    contactos[0]
                    .get("profile", {})
                    .get("name", "")
                )

            for mensaje in valor.get("messages", []):
                _procesar_mensaje_entrante(
                    mensaje,
                    nombre_whatsapp=nombre_whatsapp,
                )

            for estado in valor.get("statuses", []):
                _procesar_estado(estado)


def _firma_valida(request):
    app_secret = getattr(
        settings,
        "META_APP_SECRET",
        "",
    )

    if not app_secret:
        return False

    firma_recibida = request.headers.get(
        "X-Hub-Signature-256",
        "",
    )

    firma_calculada = (
        "sha256="
        + hmac.new(
            app_secret.encode("utf-8"),
            request.body,
            hashlib.sha256,
        ).hexdigest()
    )

    return hmac.compare_digest(
        firma_recibida,
        firma_calculada,
    )


@csrf_exempt
@require_http_methods(["GET", "POST"])
def webhook_whatsapp(request):
    if request.method == "GET":
        modo = request.GET.get("hub.mode")
        token = request.GET.get("hub.verify_token")
        challenge = request.GET.get("hub.challenge")

        verify_token = getattr(
            settings,
            "WHATSAPP_VERIFY_TOKEN",
            "",
        )

        if (
            modo == "subscribe"
            and verify_token
            and hmac.compare_digest(
                token or "",
                verify_token,
            )
        ):
            return HttpResponse(
                challenge or "",
                content_type="text/plain",
            )

        return HttpResponseForbidden(
            "Verificación de webhook rechazada."
        )

    if not _firma_valida(request):
        return HttpResponseForbidden(
            "Firma de Meta no válida."
        )

    try:
        payload = json.loads(
            request.body.decode("utf-8")
        )
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse(
            {"ok": False, "error": "JSON inválido"},
            status=400,
        )

    _procesar_payload(payload)

    return JsonResponse({"ok": True})

@login_required
def bandeja_whatsapp(request, conversacion_id=None):
    conversaciones = (
        ConversacionWhatsApp.objects
        .filter(activa=True)
        .select_related("cliente")
        .order_by("-ultimo_mensaje_en", "-actualizada_en")
    )

    conversacion_activa = None
    mensajes = MensajeWhatsApp.objects.none()

    if conversacion_id is not None:
        conversacion_activa = get_object_or_404(
            conversaciones,
            pk=conversacion_id,
        )

        mensajes = conversacion_activa.mensajes.all()

        ahora = timezone.now()

        mensajes.filter(
            direccion=MensajeWhatsApp.DIRECCION_ENTRANTE,
            leido_en_fortex=False,
        ).update(
            leido_en_fortex=True,
            fecha_leido_en_fortex=ahora,
        )

        if conversacion_activa.no_leidos:
            conversacion_activa.no_leidos = 0
            conversacion_activa.save(
                update_fields=[
                    "no_leidos",
                    "actualizada_en",
                ]
            )

    total_no_leidos = sum(
        conversacion.no_leidos
        for conversacion in conversaciones
    )

    return render(
        request,
        "mensajeria/bandeja_whatsapp.html",
        {
            "conversaciones": conversaciones,
            "conversacion_activa": conversacion_activa,
            "mensajes": mensajes,
            "total_no_leidos": total_no_leidos,
        },
    )

@login_required
def enviar_mensaje_whatsapp(request, conversacion_id):
    from datetime import timedelta
    from django.shortcuts import redirect

    from principal.whatsapp import enviar_mensaje_texto_whatsapp

    if request.method != "POST":
        return HttpResponse(status=405)

    conversacion = get_object_or_404(
        ConversacionWhatsApp.objects.filter(activa=True),
        pk=conversacion_id,
    )

    texto = (request.POST.get("texto") or "").strip()

    if not texto:
        return redirect(
            "mensajeria:conversacion_whatsapp",
            conversacion_id=conversacion.id,
        )

    ahora = timezone.now()

    limite_24_horas = ahora - timedelta(hours=24)

    if (
        not conversacion.ultimo_mensaje_entrante_en
        or conversacion.ultimo_mensaje_entrante_en < limite_24_horas
    ):
        return HttpResponse(
            "La ventana de 24 horas está cerrada. "
            "Para contactar a este cliente debe usarse una plantilla.",
            status=400,
        )

    try:
        respuesta = enviar_mensaje_texto_whatsapp(
            conversacion.telefono,
            texto,
        )
    except Exception:
        return HttpResponse(
            "No se pudo enviar el mensaje por WhatsApp.",
            status=502,
        )

    mensajes_meta = respuesta.get("messages") or []

    meta_message_id = None

    if mensajes_meta:
        meta_message_id = mensajes_meta[0].get("id")

    MensajeWhatsApp.objects.create(
        conversacion=conversacion,
        meta_message_id=meta_message_id,
        direccion=MensajeWhatsApp.DIRECCION_SALIENTE,
        tipo=MensajeWhatsApp.TIPO_TEXTO,
        texto=texto,
        fecha_mensaje=ahora,
        estado=MensajeWhatsApp.ESTADO_PENDIENTE,
        payload_original=respuesta,
    )

    conversacion.ultimo_mensaje_en = ahora
    conversacion.save(
        update_fields=[
            "ultimo_mensaje_en",
            "actualizada_en",
        ]
    )

    return redirect(
        "mensajeria:conversacion_whatsapp",
        conversacion_id=conversacion.id,
    )
