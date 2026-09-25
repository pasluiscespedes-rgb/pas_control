from django.conf import settings
from django.db import models


class InteraccionNexa(models.Model):

    CANALES = [
        ("interno", "FORTEX interno"),
        ("whatsapp", "WhatsFORTEX"),
    ]

    ESTADOS = [
        ("respondida", "Respondida por NEXA"),
        ("derivada", "Derivada a operador"),
        ("escalada", "Escalada a Victoria"),
        ("pendiente", "Pendiente"),
    ]

    TIPOS_INTERLOCUTOR = [
    ("cliente", "Cliente verificado"),
    (
        "cliente_no_verificado",
        "Cliente sin verificar",
    ),
    ("tercero", "Tercero"),
    ("desconocido", "Desconocido"),
    ]   

    canal = models.CharField(
        max_length=20,
        choices=CANALES,
        db_index=True,
    )

    operador = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interacciones_nexa",
    )

    conversacion_whatsapp = models.ForeignKey(
        "mensajeria.ConversacionWhatsApp",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="interacciones_nexa",
    )

    consulta = models.TextField()

    respuesta = models.TextField(
        blank=True,
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="pendiente",
        db_index=True,
    )

    tipo_interlocutor = models.CharField(
    max_length=30,
    choices=TIPOS_INTERLOCUTOR,
    default="desconocido",
    db_index=True,
    )

    identidad_verificada = models.BooleanField(
        default=False,
    )

    respuesta_bloqueada_privacidad = models.BooleanField(
        default=False,
    )

    motivo_bloqueo_privacidad = models.TextField(
        blank=True,
    )

    requiere_revision_humana = models.BooleanField(
        default=False,
    )

    motivo_escalamiento = models.TextField(
        blank=True,
    )

    datos_consultados = models.JSONField(
        default=dict,
        blank=True,
    )

    creada_en = models.DateTimeField(
        auto_now_add=True,
    )

    respondida_en = models.DateTimeField(
        null=True,
        blank=True,
    )

    class Meta:
        ordering = ["-creada_en"]
        verbose_name = "Interacción NEXA"
        verbose_name_plural = "Interacciones NEXA"

    def __str__(self):
        return f"NEXA - {self.get_canal_display()} - {self.creada_en:%d/%m/%Y %H:%M}"
