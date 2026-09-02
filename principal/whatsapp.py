import requests
from pathlib import Path
from django.conf import settings
import os
import subprocess
import tempfile

import imageio_ffmpeg

from django.core.files.uploadedfile import SimpleUploadedFile

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

# ============================================================
# NOTAS DE VOZ WHATSAPP
# ============================================================

WHATSAPP_NOTA_VOZ_MAX_BYTES = 16 * 1024 * 1024


def convertir_nota_voz_a_ogg(archivo):
    """
    Convierte una grabación del navegador a OGG/Opus mono,
    formato requerido por WhatsApp para notas de voz.
    """

    if archivo is None:
        raise ValueError(
            "No se recibió ninguna grabación de voz."
        )

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
            "La grabación de voz está vacía."
        )

    if tamano > WHATSAPP_NOTA_VOZ_MAX_BYTES:
        raise ValueError(
            "La nota de voz supera el límite de 16 MB."
        )

    nombre_original = str(
        getattr(
            archivo,
            "name",
            "nota_voz.webm",
        )
        or "nota_voz.webm"
    )

    extension_original = (
        Path(nombre_original).suffix.lower()
        or ".webm"
    )

    ruta_entrada = None
    ruta_salida = None

    try:
        with tempfile.NamedTemporaryFile(
            suffix=extension_original,
            delete=False,
        ) as temporal_entrada:

            ruta_entrada = temporal_entrada.name

            if hasattr(archivo, "seek"):
                archivo.seek(0)

            for bloque in archivo.chunks():
                temporal_entrada.write(bloque)

        with tempfile.NamedTemporaryFile(
            suffix=".ogg",
            delete=False,
        ) as temporal_salida:

            ruta_salida = temporal_salida.name

        ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()

        comando = [
            ffmpeg,
            "-y",
            "-i",
            ruta_entrada,

            # Solo audio
            "-vn",

            # Una sola pista/canal, apropiado para voz
            "-ac",
            "1",

            # Frecuencia habitual para voz
            "-ar",
            "48000",

            # Codec requerido
            "-c:a",
            "libopus",

            # Perfil de voz
            "-application",
            "voip",

            # Bitrate suficiente para voz clara
            "-b:a",
            "32k",

            # Contenedor OGG
            "-f",
            "ogg",

            ruta_salida,
        ]

        resultado = subprocess.run(
            comando,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=120,
            check=False,
        )

        if resultado.returncode != 0:
            detalle = (
                resultado.stderr
                .decode(
                    "utf-8",
                    errors="replace",
                )
            )

            print(
                "FFMPEG NOTA VOZ ERROR:",
                detalle,
            )

            raise RuntimeError(
                "No se pudo convertir la nota de voz."
            )

        with open(
            ruta_salida,
            "rb",
        ) as archivo_convertido:

            contenido = archivo_convertido.read()

        if not contenido:
            raise RuntimeError(
                "La conversión de la nota de voz "
                "generó un archivo vacío."
            )

        if len(contenido) > WHATSAPP_NOTA_VOZ_MAX_BYTES:
            raise ValueError(
                "La nota de voz convertida supera "
                "el límite de 16 MB."
            )

        nombre_salida = (
            "nota_voz_whatsfortex.ogg"
        )

        return SimpleUploadedFile(
            nombre_salida,
            contenido,
            content_type="audio/ogg",
        )

    finally:
        for ruta in (
            ruta_entrada,
            ruta_salida,
        ):
            if (
                ruta
                and os.path.exists(ruta)
            ):
                try:
                    os.remove(ruta)
                except OSError:
                    pass


def enviar_nota_voz_whatsapp(
    destinatario,
    archivo_grabacion,
):
    """
    Convierte, sube y envía una grabación como
    nota de voz nativa de WhatsApp.
    """

    archivo_ogg = (
        convertir_nota_voz_a_ogg(
            archivo_grabacion
        )
    )

    datos_media = subir_media_whatsapp(
        archivo_ogg
    )

    media_id = datos_media.get(
        "media_id"
    )

    if not media_id:
        raise RuntimeError(
            "Meta no devolvió el media_id "
            "de la nota de voz."
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

    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": str(destinatario),
        "type": "audio",
        "audio": {
            "id": str(media_id),
            "voice": True,
        },
    }

    respuesta = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30,
    )

    if not respuesta.ok:
        print(
            "META NOTA VOZ ERROR:",
            respuesta.text,
        )

    respuesta.raise_for_status()

    return {
        "respuesta": respuesta.json(),
        "media_id": media_id,
        "mime_type": "audio/ogg",
        "nombre_archivo": (
            "nota_voz_whatsfortex.ogg"
        ),
    }

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