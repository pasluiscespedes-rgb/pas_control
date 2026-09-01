from django.db import models
from django.db import models

from clientes.models import Cliente


class ConversacionWhatsApp(models.Model):
    telefono = models.CharField(
        max_length=30,
        unique=True,
        db_index=True,
    )

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="conversaciones_whatsapp",
    )

    nombre_whatsapp = models.CharField(
        max_length=200,
        blank=True,
    )

    ultimo_mensaje_en = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
    )

    ultimo_mensaje_entrante_en = models.DateTimeField(
        null=True,
        blank=True,
    )

    no_leidos = models.PositiveIntegerField(
        default=0,
    )

    activa = models.BooleanField(
        default=True,
    )

    creada_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizada_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-ultimo_mensaje_en", "-actualizada_en"]
        verbose_name = "Conversación de WhatsApp"
        verbose_name_plural = "Conversaciones de WhatsApp"

    def __str__(self):
        if self.cliente:
            return f"{self.cliente} - {self.telefono}"

        if self.nombre_whatsapp:
            return f"{self.nombre_whatsapp} - {self.telefono}"

        return self.telefono


class MensajeWhatsApp(models.Model):
    DIRECCION_ENTRANTE = "entrante"
    DIRECCION_SALIENTE = "saliente"

    DIRECCIONES = [
        (DIRECCION_ENTRANTE, "Entrante"),
        (DIRECCION_SALIENTE, "Saliente"),
    ]

    TIPO_TEXTO = "text"
    TIPO_IMAGEN = "image"
    TIPO_AUDIO = "audio"
    TIPO_VIDEO = "video"
    TIPO_DOCUMENTO = "document"
    TIPO_STICKER = "sticker"
    TIPO_UBICACION = "location"
    TIPO_CONTACTO = "contacts"
    TIPO_REACCION = "reaction"
    TIPO_DESCONOCIDO = "unknown"

    TIPOS = [
        (TIPO_TEXTO, "Texto"),
        (TIPO_IMAGEN, "Imagen"),
        (TIPO_AUDIO, "Audio"),
        (TIPO_VIDEO, "Video"),
        (TIPO_DOCUMENTO, "Documento"),
        (TIPO_STICKER, "Sticker"),
        (TIPO_UBICACION, "Ubicación"),
        (TIPO_CONTACTO, "Contacto"),
        (TIPO_REACCION, "Reacción"),
        (TIPO_DESCONOCIDO, "Desconocido"),
    ]

    ESTADO_RECIBIDO = "received"
    ESTADO_PENDIENTE = "pending"
    ESTADO_ENVIADO = "sent"
    ESTADO_ENTREGADO = "delivered"
    ESTADO_LEIDO = "read"
    ESTADO_FALLIDO = "failed"

    ESTADOS = [
        (ESTADO_RECIBIDO, "Recibido"),
        (ESTADO_PENDIENTE, "Pendiente"),
        (ESTADO_ENVIADO, "Enviado"),
        (ESTADO_ENTREGADO, "Entregado"),
        (ESTADO_LEIDO, "Leído"),
        (ESTADO_FALLIDO, "Fallido"),
    ]

    conversacion = models.ForeignKey(
        ConversacionWhatsApp,
        on_delete=models.CASCADE,
        related_name="mensajes",
    )

    meta_message_id = models.CharField(
        max_length=255,
        unique=True,
        null=True,
        blank=True,
    )

    direccion = models.CharField(
        max_length=10,
        choices=DIRECCIONES,
        db_index=True,
    )

    tipo = models.CharField(
        max_length=20,
        choices=TIPOS,
        default=TIPO_TEXTO,
    )

    texto = models.TextField(
        blank=True,
    )

    media_id = models.CharField(
        max_length=255,
        blank=True,
    )

    nombre_archivo = models.CharField(
        max_length=255,
        blank=True,
    )

    mime_type = models.CharField(
        max_length=120,
        blank=True,
    )

    fecha_mensaje = models.DateTimeField(
        db_index=True,
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default=ESTADO_RECIBIDO,
        db_index=True,
    )

    leido_en_fortex = models.BooleanField(
        default=False,
    )

    fecha_leido_en_fortex = models.DateTimeField(
        null=True,
        blank=True,
    )

    error_codigo = models.CharField(
        max_length=100,
        blank=True,
    )

    error_detalle = models.TextField(
        blank=True,
    )

    payload_original = models.JSONField(
        default=dict,
        blank=True,
    )

    creado_en = models.DateTimeField(
        auto_now_add=True,
    )

    actualizado_en = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["fecha_mensaje", "id"]
        verbose_name = "Mensaje de WhatsApp"
        verbose_name_plural = "Mensajes de WhatsApp"
        indexes = [
            models.Index(
                fields=["conversacion", "fecha_mensaje"],
                name="msg_wa_conv_fecha_idx",
            ),
            models.Index(
                fields=["estado", "fecha_mensaje"],
                name="msg_wa_estado_fecha_idx",
            ),
        ]

    def __str__(self):
        return (
            f"{self.get_direccion_display()} - "
            f"{self.conversacion.telefono} - "
            f"{self.fecha_mensaje:%d/%m/%Y %H:%M}"
        )
# Create your models here.
