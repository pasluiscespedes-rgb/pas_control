from django.db import models
from polizas.models import Poliza


class Recibo(models.Model):

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