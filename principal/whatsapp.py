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