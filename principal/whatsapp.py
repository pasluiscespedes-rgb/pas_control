import requests
from pathlib import Path
from django.conf import settings

RUTA_LOGO_FORTEX = (
    Path(settings.BASE_DIR)
    / "principal"
    / "static"
    / "principal"
    / "img"
    / "fortex_logo_redondo.png"
)

URL_LOGO_FORTEX = (
    "https://pascontrol-production.up.railway.app/"
    "static/principal/img/fortex_logo_redondo.png"
)

def subir_imagen_whatsapp(ruta_imagen):
    url = (
        f"https://graph.facebook.com/"
        f"{settings.WHATSAPP_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/media"
    )

    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
    }

    data = {
        "messaging_product": "whatsapp",
    }

    with open(ruta_imagen, "rb") as archivo:
        files = {
            "file": (
                "fortex_logo_redondo.png",
                archivo,
                "image/png",
            )
        }

        respuesta = requests.post(
            url,
            headers=headers,
            data=data,
            files=files,
            timeout=20,
        )

    if not respuesta.ok:
        print("META ERROR:", respuesta.text)

    respuesta.raise_for_status()

    return respuesta.json()["id"]


def enviar_plantilla_whatsapp(
    destinatario,
    nombre_plantilla,
    idioma="en_US",
    parametros=None,
    media_id_header=None,
    media_url_header=None,
):
    url = (
        f"https://graph.facebook.com/"
        f"{settings.WHATSAPP_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    datos = {
        "messaging_product": "whatsapp",
        "to": destinatario,
        "type": "template",
        "template": {
            "name": nombre_plantilla,
            "language": {
                "code": idioma
            }
        }
    }

    componentes = []

    # Encabezado con imagen/logo
   
    if media_url_header:
        componentes.append(
            {
                "type": "header",
                "parameters": [
                    {
                        "type": "image",
                        "image": {
                            "link": media_url_header
                        },
                    }
                ],
            }
        )
    elif media_id_header:
        componentes.append(
            {
                "type": "header",
                "parameters": [
                    {
                        "type": "image",
                        "image": {
                            "id": media_id_header
                        },
                    }
                ],
            }
        )

    # Variables del cuerpo de la plantilla
    if parametros:
        componentes.append(
            {
                "type": "body",
                "parameters": [
                    {
                        "type": "text",
                        "text": str(valor),
                    }
                    for valor in parametros
                ],
            }
        )

    if componentes:
        datos["template"]["components"] = componentes

    respuesta = requests.post(
        url,
        headers=headers,
        json=datos,
        timeout=20,
    )

    return respuesta

def enviar_mensaje_texto_whatsapp(destinatario, texto):
    texto = (texto or "").strip()

    if not texto:
        raise ValueError("El mensaje no puede estar vacío.")

    url = (
        f"https://graph.facebook.com/"
        f"{settings.WHATSAPP_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }

    datos = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": str(destinatario),
        "type": "text",
        "text": {
            "preview_url": False,
            "body": texto,
        },
    }

    respuesta = requests.post(
        url,
        headers=headers,
        json=datos,
        timeout=20,
    )

    if not respuesta.ok:
        print("META ERROR:", respuesta.text)

    respuesta.raise_for_status()

    return respuesta.json()

# ============================================================
# MULTIMEDIA WHATSAPP
# ============================================================

WHATSAPP_MEDIA_LIMITES = {
    "image": 5 * 1024 * 1024,
    "audio": 16 * 1024 * 1024,
    "video": 16 * 1024 * 1024,
    "document": 100 * 1024 * 1024,
}


WHATSAPP_MEDIA_POR_MIME = {
    # Imágenes
    "image/jpeg": ("image", "image/jpeg"),
    "image/png": ("image", "image/png"),

    # Audio
    "audio/aac": ("audio", "audio/aac"),
    "audio/mp4": ("audio", "audio/mp4"),
    "audio/mpeg": ("audio", "audio/mpeg"),
    "audio/amr": ("audio", "audio/amr"),
    "audio/ogg": ("audio", "audio/ogg"),

    # Video
    "video/mp4": ("video", "video/mp4"),
    "video/3gpp": ("video", "video/3gpp"),

    # Documentos
    "text/plain": ("document", "text/plain"),
    "application/pdf": (
        "document",
        "application/pdf",
    ),
    "application/msword": (
        "document",
        "application/msword",
    ),
    "application/vnd.ms-powerpoint": (
        "document",
        "application/vnd.ms-powerpoint",
    ),
    "application/vnd.ms-excel": (
        "document",
        "application/vnd.ms-excel",
    ),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (
        "document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    "application/vnd.openxmlformats-officedocument.presentationml.presentation": (
        "document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (
        "document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
}


WHATSAPP_MEDIA_POR_EXTENSION = {
    ".jpg": ("image", "image/jpeg"),
    ".jpeg": ("image", "image/jpeg"),
    ".png": ("image", "image/png"),

    ".aac": ("audio", "audio/aac"),
    ".m4a": ("audio", "audio/mp4"),
    ".mp3": ("audio", "audio/mpeg"),
    ".amr": ("audio", "audio/amr"),
    ".ogg": ("audio", "audio/ogg"),
    ".opus": ("audio", "audio/ogg"),

    ".mp4": ("video", "video/mp4"),
    ".3gp": ("video", "video/3gpp"),

    ".txt": ("document", "text/plain"),
    ".pdf": ("document", "application/pdf"),
    ".doc": ("document", "application/msword"),
    ".docx": (
        "document",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    ".ppt": (
        "document",
        "application/vnd.ms-powerpoint",
    ),
    ".pptx": (
        "document",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    ".xls": (
        "document",
        "application/vnd.ms-excel",
    ),
    ".xlsx": (
        "document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
}


def _nombre_archivo_whatsapp(nombre):
    nombre = str(nombre or "archivo")

    nombre = (
        nombre
        .replace("\\", "/")
        .split("/")[-1]
        .replace('"', "")
        .replace("\r", "")
        .replace("\n", "")
        .strip()
    )

    return nombre or "archivo"


def clasificar_archivo_whatsapp(archivo):
    if archivo is None:
        raise ValueError(
            "No se recibió ningún archivo."
        )

    nombre_archivo = _nombre_archivo_whatsapp(
        getattr(
            archivo,
            "name",
            "archivo",
        )
    )

    extension = Path(
        nombre_archivo
    ).suffix.lower()

    mime_recibido = (
        getattr(
            archivo,
            "content_type",
            "",
        )
        or ""
    )

    mime_recibido = (
        mime_recibido
        .split(";")[0]
        .strip()
        .lower()
    )

    datos_media = None

    if mime_recibido in WHATSAPP_MEDIA_POR_MIME:
        datos_media = (
            WHATSAPP_MEDIA_POR_MIME[
                mime_recibido
            ]
        )

    elif extension in WHATSAPP_MEDIA_POR_EXTENSION:
        datos_media = (
            WHATSAPP_MEDIA_POR_EXTENSION[
                extension
            ]
        )

    if datos_media is None:
        raise ValueError(
            "Este tipo de archivo no está "
            "permitido para WhatsApp."
        )

    tipo_media, mime_type = datos_media

    tamano = int(
        getattr(
            archivo,
            "size",
            0,
        )
        or 0
    )

    if tamano <= 0:
        raise ValueError(
            "El archivo está vacío."
        )

    limite = WHATSAPP_MEDIA_LIMITES[
        tipo_media
    ]

    if tamano > limite:
        limite_mb = limite // (
            1024 * 1024
        )

        raise ValueError(
            f"El archivo supera el límite "
            f"de {limite_mb} MB permitido "
            f"para {tipo_media}."
        )

    return {
        "tipo": tipo_media,
        "mime_type": mime_type,
        "nombre_archivo": nombre_archivo,
        "tamano": tamano,
    }


def subir_media_whatsapp(archivo):
    datos_archivo = (
        clasificar_archivo_whatsapp(
            archivo
        )
    )

    url = (
        f"https://graph.facebook.com/"
        f"{settings.WHATSAPP_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/media"
    )

    headers = {
        "Authorization": (
            f"Bearer "
            f"{settings.WHATSAPP_ACCESS_TOKEN}"
        ),
    }

    data = {
        "messaging_product": "whatsapp",
        "type": datos_archivo[
            "mime_type"
        ],
    }

    if hasattr(archivo, "seek"):
        archivo.seek(0)

    files = {
        "file": (
            datos_archivo[
                "nombre_archivo"
            ],
            archivo,
            datos_archivo[
                "mime_type"
            ],
        )
    }

    respuesta = requests.post(
        url,
        headers=headers,
        data=data,
        files=files,
        timeout=120,
    )

    if not respuesta.ok:
        print(
            "META MEDIA ERROR:",
            respuesta.text,
        )

    respuesta.raise_for_status()

    payload = respuesta.json()

    media_id = payload.get("id")

    if not media_id:
        raise RuntimeError(
            "Meta no devolvió un media_id."
        )

    return {
        **datos_archivo,
        "media_id": media_id,
    }


def enviar_media_whatsapp(
    destinatario,
    media_id,
    tipo,
    caption="",
    nombre_archivo="",
):
    tipos_permitidos = {
        "image",
        "audio",
        "video",
        "document",
    }

    if tipo not in tipos_permitidos:
        raise ValueError(
            "Tipo multimedia no permitido."
        )

    if not media_id:
        raise ValueError(
            "Falta el media_id."
        )

    url = (
        f"https://graph.facebook.com/"
        f"{settings.WHATSAPP_API_VERSION}/"
        f"{settings.WHATSAPP_PHONE_NUMBER_ID}/messages"
    )

    headers = {
        "Authorization": (
            f"Bearer "
            f"{settings.WHATSAPP_ACCESS_TOKEN}"
        ),
        "Content-Type": "application/json",
    }

    objeto_media = {
        "id": str(media_id),
    }

    caption = (
        caption
        or ""
    ).strip()

    # Meta permite caption en:
    # imagen, video y documento.
    # Audio no lleva caption.
    if (
        caption
        and tipo in {
            "image",
            "video",
            "document",
        }
    ):
        objeto_media[
            "caption"
        ] = caption

    if (
        tipo == "document"
        and nombre_archivo
    ):
        objeto_media[
            "filename"
        ] = (
            _nombre_archivo_whatsapp(
                nombre_archivo
            )
        )

    datos = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": str(destinatario),
        "type": tipo,
        tipo: objeto_media,
    }

    respuesta = requests.post(
        url,
        headers=headers,
        json=datos,
        timeout=30,
    )

    if not respuesta.ok:
        print(
            "META ENVIO MEDIA ERROR:",
            respuesta.text,
        )

    respuesta.raise_for_status()

    return respuesta.json()

def enviar_recordatorio_vencimiento(
    destinatario,
    nombre,
    patente,
    fecha_vencimiento,
    importe,
):
    return enviar_plantilla_whatsapp(
        destinatario=destinatario,
        nombre_plantilla="recordatorio_vencimiento",
        idioma="es_AR",
        parametros=[
            nombre,
            patente,
            str(fecha_vencimiento),
            str(importe),
        ],
        media_url_header=URL_LOGO_FORTEX,
    )

def enviar_cuota_vencida(
    destinatario,
    nombre,
    patente,
    fecha_vencimiento,
    importe,
):
    return enviar_plantilla_whatsapp(
        destinatario=destinatario,
        nombre_plantilla="cuota_vencida",
        idioma="es_AR",
        parametros=[
            nombre,
            patente,
            str(fecha_vencimiento),
            str(importe),
        ],
        media_url_header=URL_LOGO_FORTEX,
    )

def obtener_importe_referencia(poliza):
    from cobros.models import Cobro

    # Si la póliza es anual, el importe puede variar mes a mes.
    if poliza.periodicidad == "Anual":
        return None

    # Si ya se pagaron todas las cuotas, estamos ante una renovación.
    if poliza.numero_cuota >= poliza.cantidad_cuotas:
        return None

    ultimo_cobro = (
        Cobro.objects
        .filter(
            poliza=poliza,
            anulado=False,
        )
        .order_by("-fecha_pago", "-id")
        .first()
    )

    if not ultimo_cobro:
        return None

    return ultimo_cobro.importe

def obtener_texto_importe(poliza):
    importe = obtener_importe_referencia(poliza)

    if poliza.periodicidad == "Anual":
        return "Consultá con tu asesor el importe actualizado."

    if poliza.numero_cuota >= poliza.cantidad_cuotas:
        return "Consultá con tu asesor el importe correspondiente a la renovación."

    if importe is None:
        return "Consultá con tu asesor el importe correspondiente."

    return f"Importe: ${importe:,.0f}".replace(",", ".")