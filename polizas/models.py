from django.db import models
from clientes.models import Cliente
from vehiculos.models import Vehiculo
from datetime import timedelta
import calendar
from django.conf import settings


class Poliza(models.Model):

    ESTADOS = [
    ("Al día", "Al día"),
    ("Pendiente", "Pendiente"),
    ("Morosa", "Morosa"),
    ("Vencida", "Vencida"),
    ("Anulada", "Anulada"),
    ]

    estado = models.CharField(
    max_length=20,
    choices=ESTADOS,
    default="Al día"
    )

    motivo_anulacion = models.TextField(
    blank=True,
    default="",
    )

    fecha_anulacion = models.DateTimeField(
     null=True,
     blank=True,
    )

    anulada_por = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    related_name="polizas_anuladas",
    )

    TIPOS_SEGURO = [
        ("Automotor", "Automotor"),
        ("Moto", "Moto"),
        ("Caución", "Caución"),
        ("Accidentes Personales", "Accidentes Personales"),
        ("Agro", "Agro"),
        ("Hogar", "Hogar"),
        ("Comercio", "Comercio"),
        ("Otro", "Otro"),
    ]

    PERIODICIDADES = [
        ("Mensual", "Mensual"),
        ("Bimestral", "Bimestral"),
        ("Trimestral", "Trimestral"),
        ("Cuatrimestral", "Cuatrimestral"),
        ("Semestral", "Semestral"),
        ("Anual", "Anual"),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE
    )

    tipo_seguro = models.CharField(
        max_length=50,
        choices=TIPOS_SEGURO,
        default="Automotor"
    )

    vehiculo = models.ForeignKey(
        Vehiculo,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    compania = models.CharField(
        "Compañía",
        max_length=100
    )

    numero_poliza = models.CharField(
        "Número de póliza",
        max_length=50,
        blank=True
    )

    fecha_alta = models.DateField(
        "Fecha de alta"
    )

    fecha_fin_vigencia = models.DateField(
    "Fin de vigencia",
    null=True,
    blank=True

    )

    periodicidad = models.CharField(
        max_length=20,
        choices=PERIODICIDADES,
        default="Mensual"
    )

    cantidad_cuotas = models.PositiveIntegerField(
        "Cantidad de cuotas",
        default=1
    )

    fecha_vencimiento = models.DateField(
        "Fecha de vencimiento",
        null=True,
        blank=True
    )

    numero_cuota = models.PositiveIntegerField(
        "Número de cuota",
        default=0
    )

    estado = models.CharField(
        max_length=20,
        choices=ESTADOS,
        default="Pendiente"
    )

    observaciones = models.TextField(
        blank=True
    )

    porcentaje_comision = models.DecimalField(
    "Porcentaje de comisión",
    max_digits=5,
    decimal_places=2,
    default=0,
    blank=True
    )

    def save(self, *args, **kwargs):
      import calendar

      def sumar_meses(fecha, cantidad):
        mes_total = fecha.month - 1 + cantidad
        anio = fecha.year + mes_total // 12
        mes = mes_total % 12 + 1

        ultimo_dia = calendar.monthrange(anio, mes)[1]
        dia = min(fecha.day, ultimo_dia)

        return fecha.replace(
            year=anio,
            month=mes,
            day=dia,
        )

      meses_vigencia = {
        "Mensual": 1,
        "Bimestral": 2,
        "Trimestral": 3,
        "Cuatrimestral": 4,
        "Semestral": 6,
        "Anual": 12,
    }

      if self.fecha_alta:
         duracion = meses_vigencia.get(self.periodicidad, 1)
         self.cantidad_cuotas = duracion

         # Final real de la cobertura.
         self.fecha_fin_vigencia = sumar_meses(
            self.fecha_alta,
            duracion
         )

         # Primer vencimiento de pago: un mes después del alta.
         if not self.fecha_vencimiento:
           self.fecha_vencimiento = sumar_meses(
              self.fecha_alta,
              1
            )
        

      super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.compania} - {self.cliente}"