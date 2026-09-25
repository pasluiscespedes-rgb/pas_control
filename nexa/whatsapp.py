from django.conf import settings
from django.utils import timezone

from mensajeria.models import MensajeWhatsApp
from principal.whatsapp import enviar_mensaje_texto_whatsapp

from .motor import (
    responder_consulta_cliente,
    responder_consulta_no_vinculada,
)


def procesar_mensaje_whatsapp_nexa(
    conversacion,
    mensaje_entrante,
):
    """
    Puente seguro entre WhatsFORTEX y NEXA.

    Por ahora:
    - solo responde si NEXA_AUTO_REPLY está activo;
    - solo procesa mensajes de texto;
    - solo responde a conversaciones vinculadas
      con un cliente real de FORTEX;
    - guarda también la respuesta enviada.
    """

    if not getattr(
        settings,
        "NEXA_AUTO_REPLY",
        False,
    ):
        return False

    telefono_prueba = "".join(
    caracter
    for caracter in getattr(
        settings,
        "NEXA_TEST_PHONE",
        "",
    )
    if caracter.isdigit()
    )

    telefono_conversacion = "".join(
        caracter
        for caracter in str(
            getattr(
                conversacion,
                "telefono",
                "",
            )
        )
        if caracter.isdigit()
    )

    if (
        not telefono_prueba
        or telefono_conversacion != telefono_prueba
    ):
        return False
    
    if (
        mensaje_entrante.tipo
        != MensajeWhatsApp.TIPO_TEXTO
    ):
        return False

    consulta = (
    mensaje_entrante.texto
    or ""
    ).strip()

    if not consulta:
        return False

    if conversacion.cliente:
        respuesta_nexa = responder_consulta_cliente(
            cliente=conversacion.cliente,
            consulta=consulta,
            conversacion=conversacion,
        )
    else:
        respuesta_nexa = responder_consulta_no_vinculada(
            consulta=consulta,
            conversacion=conversacion,
        )

    if not respuesta_nexa:
        return False

    try:
        respuesta_meta = (
            enviar_mensaje_texto_whatsapp(
                conversacion.telefono,
                respuesta_nexa,
            )
        )

        mensajes_meta = (
            respuesta_meta.get("messages")
            or []
        )

        meta_message_id = None

        if mensajes_meta:
            meta_message_id = (
                mensajes_meta[0].get("id")
            )

        ahora = timezone.now()

        MensajeWhatsApp.objects.create(
            conversacion=conversacion,
            meta_message_id=meta_message_id,
            direccion=(
                MensajeWhatsApp
                .DIRECCION_SALIENTE
            ),
            tipo=(
                MensajeWhatsApp
                .TIPO_TEXTO
            ),
            texto=respuesta_nexa,
            fecha_mensaje=ahora,
            estado=(
                MensajeWhatsApp
                .ESTADO_PENDIENTE
            ),
            payload_original=respuesta_meta,
        )

        conversacion.ultimo_mensaje_en = ahora

        conversacion.save(
            update_fields=[
                "ultimo_mensaje_en",
                "actualizada_en",
            ]
        )

        return True

    except Exception as error:
        print(
            "NEXA WHATSAPP ERROR:",
            repr(error),
        )

        return False