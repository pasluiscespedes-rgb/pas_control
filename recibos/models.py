from django.db import models
from django.conf import settings
from polizas.models import Poliza


class Recibo(models.Model):

    class Meta:
        permissions = [
            ('ver_todos_recibos', 'Puede consultar todos los recibos'),
            ('gestionar_accesos_recibo', 'Puede otorgar y revocar accesos a recibos'),
        ]

    FORMAS_PAGO = [
        ("Efectivo", "Efectivo"),
        ("Transferencia", "Transferencia"),
        ("Tarjeta", "Tarjeta"),
        ("CBU", "Débito CBU"),
    ]

    poliza = models.ForeignKey(
        Poliza,
        on_delete=models.CASCADE
    )

    fecha = models.DateField(
        auto_now_add=True
    )

    numero_cuota = models.PositiveIntegerField(
        default=1
    )

    cantidad_cuotas = models.PositiveIntegerField(default=1)

    importe = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    forma_pago = models.CharField(
        max_length=30,
        choices=FORMAS_PAGO,
        default="Efectivo"
    )

    numero_recibo = models.CharField(
        max_length=20,
        blank=True
    )

    emitido = models.BooleanField(
        default=False
    )

    observaciones = models.TextField(
        blank=True
    )

    def save(self, *args, **kwargs):

        super().save(*args, **kwargs)

        if not self.numero_recibo:
            self.numero_recibo = f"R-{self.id:06d}"
            super().save(update_fields=["numero_recibo"])

    def __str__(self):
        return self.numero_recibo


class SoloInsercion(models.Model):
    """Evita edición accidental por ORM; el servicio controla la emisión única."""
    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not self._state.adding:
            from django.core.exceptions import ValidationError
            raise ValidationError('Registro inmutable.')
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        from django.core.exceptions import ValidationError
        raise ValidationError('Registro inmutable.')


class AutenticidadRecibo(SoloInsercion):
    from .autenticidad import codigo_seguro
    recibo = models.OneToOneField(Recibo, on_delete=models.PROTECT, related_name='autenticidad')
    cobro = models.OneToOneField('cobros.Cobro', on_delete=models.PROTECT)
    codigo = models.CharField(max_length=32, unique=True, default=codigo_seguro, editable=False)
    original = models.JSONField(editable=False)
    key_id = models.CharField(max_length=40, editable=False)
    firma = models.CharField(max_length=64, editable=False)
    fecha_emision = models.DateTimeField(null=True, editable=False)
    pdf = models.BinaryField(null=True, editable=False)
    sha256_pdf = models.CharField(max_length=64, blank=True, editable=False)
    firma_pdf = models.CharField(max_length=64, blank=True, editable=False)


class AnulacionDocumento(SoloInsercion):
    registro = models.OneToOneField(AutenticidadRecibo, on_delete=models.PROTECT)
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    fecha = models.DateTimeField(auto_now_add=True)
    motivo = models.TextField()

    class Meta:
        permissions = [('anular_documento', 'Puede anular documentos autenticados')]


class AccesoRecibo(models.Model):
    recibo = models.ForeignKey(Recibo, on_delete=models.CASCADE, related_name='autorizaciones')
    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    otorgado_por = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT,
                                    related_name='accesos_recibo_otorgados')
    fecha = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=['recibo', 'usuario'], name='acceso_recibo_usuario_unico')]


class VentanaVerificacion(models.Model):
    # No almacena IP, codigo de recibo ni archivo recibido.
    clave = models.CharField(max_length=64, primary_key=True)
    ventana = models.BigIntegerField(db_index=True)
    intentos = models.PositiveIntegerField(default=0)
