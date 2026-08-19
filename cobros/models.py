from django.db import models
from clientes.models import Cliente
from polizas.models import Poliza
from django.conf import settings


class Cobro(models.Model):

    FORMAS_PAGO = [
        ("Efectivo", "Efectivo"),
        ("Transferencia", "Transferencia"),
        ("Débito", "Débito"),
        ("Tarjeta", "Tarjeta"),
    ]

    ESTADOS = [
        ("Pendiente", "Pendiente"),
        ("Pagado", "Pagado"),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE
    )

    poliza = models.ForeignKey(
        Poliza,
        on_delete=models.CASCADE
    )

    fecha_pago = models.DateField("Fecha de pago")

    importe = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    plus = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=0
    )

    comision = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=0
    )

    registrado_por = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.PROTECT,
    null=True,
    blank=True,
    related_name="cobros_registrados",
    )

    turno = models.ForeignKey(
      "principal.TurnoCaja",
       on_delete=models.PROTECT,
       null=True,
       blank=True,
       related_name="cobros",
    )

    fecha_registro = models.DateTimeField(
    auto_now_add=True,
    null=True,
    blank=True,
    )

    cuota = models.PositiveIntegerField(default=1)
    cantidad_cuotas = models.PositiveIntegerField(default=1)

    forma_pago = models.CharField(
        max_length=30,
        choices=FORMAS_PAGO,
        default="Efectivo"
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="Pagado"
    )

    observaciones = models.TextField(
        blank=True
    )

    anulado = models.BooleanField(default=False)

    fecha_anulacion = models.DateTimeField(
      null=True,
      blank=True
    )

    motivo_anulacion = models.TextField(
      blank=True
    )

    anulado_por = models.ForeignKey(
      settings.AUTH_USER_MODEL,
      on_delete=models.PROTECT,
      null=True,
      blank=True,
      related_name="cobros_anulados"
    )

    def __str__(self):
        return f"{self.cliente} - Cuota {self.cuota}"
