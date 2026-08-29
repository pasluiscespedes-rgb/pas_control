from django.conf import settings
from django.db import models

from clientes.models import Cliente


class MovimientoCliente(models.Model):

    TIPOS_MOVIMIENTO = [
        ("cliente", "Datos del cliente"),
        ("riesgo", "Riesgo"),
        ("poliza", "Póliza"),
        ("cobro", "Cobro"),
        ("recibo", "Recibo"),
        ("whatsapp", "WhatsApp"),
        ("endoso", "Endoso"),
        ("aseguradora", "Cambio de aseguradora"),
        ("otro", "Otro"),
    ]

    cliente = models.ForeignKey(
        Cliente,
        on_delete=models.CASCADE,
        related_name="movimientos",
    )

    tipo = models.CharField(
        max_length=20,
        choices=TIPOS_MOVIMIENTO,
    )

    titulo = models.CharField(
        max_length=150,
    )

    descripcion = models.TextField(
        blank=True,
    )

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    fecha = models.DateTimeField(
        auto_now_add=True,
    )

    class Meta:
        ordering = ["-fecha"]
        verbose_name = "Movimiento del cliente"
        verbose_name_plural = "Movimientos de clientes"

    def __str__(self):
        return f"{self.cliente} - {self.titulo}"

class GastoCaja(models.Model):
    fecha = models.DateField(auto_now_add=True)
    concepto = models.CharField(max_length=200)
    importe = models.DecimalField(max_digits=10, decimal_places=2)
    observaciones = models.TextField(blank=True)
    usuario = models.ForeignKey(
    settings.AUTH_USER_MODEL,
    on_delete=models.SET_NULL,
    null=True,
    blank=True
)

    turno = models.ForeignKey(
      "TurnoCaja",
       on_delete=models.PROTECT,
       null=True,
       blank=True,
       related_name="gastos",
    )    

    fecha_hora = models.DateTimeField(auto_now_add=True) 

class Sucursal(models.Model):
    nombre = models.CharField(
        max_length=120
    )

    provincia = models.CharField(
        max_length=80
    )

    codigo = models.CharField(
        max_length=20,
        unique=True
    )

    activa = models.BooleanField(
        default=True
    )

    def __str__(self):
        return f"{self.provincia} - {self.nombre}"

class PerfilUsuario(models.Model):
    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil_fortex"
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        related_name="usuarios"
    )

    activo = models.BooleanField(default=True)

    def __str__(self):
        return f"{self.usuario} - {self.sucursal}"    

class TurnoCaja(models.Model):
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="turnos_caja"
    )

    sucursal = models.ForeignKey(
        Sucursal,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="turnos"
    )

    fecha_apertura = models.DateTimeField(auto_now_add=True)

    fecha_cierre = models.DateTimeField(
        null=True,
        blank=True
    )

    abierto = models.BooleanField(default=True)

    total_cobrado = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=0
    )

    total_gastos = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=0
    )

    saldo_neto = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=0
    )


    def __str__(self):
        estado = "Abierto" if self.abierto else "Cerrado"
        return f"{self.usuario} - {self.fecha_apertura} - {estado}"

class CierreCaja(models.Model):
    fecha = models.DateField()

    total_cobrado = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    total_gastos = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    saldo_neto = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    efectivo = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    tarjeta = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    transferencia = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    debito = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0
    )

    turno = models.ForeignKey(
    "TurnoCaja",
    on_delete=models.PROTECT,
    null=True,
    blank=True,
    related_name="cierres",
    )

    cbu = models.DecimalField(
    max_digits=12,
    decimal_places=2,
    default=0
    )

    fecha_hora_cierre = models.DateTimeField(auto_now_add=True)

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True
    )

    

    def __str__(self):
        return f"Cierre {self.fecha} - ${self.saldo_neto}"
  

    
class Aseguradora(models.Model):
    nombre = models.CharField(
        max_length=200,
        unique=True,
    )

    codigo_ssn = models.CharField(
        max_length=50,
        blank=True,
    )

    activa = models.BooleanField(
        default=True,
    )

    def __str__(self):
        return self.nombre

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Aseguradora"
        verbose_name_plural = "Aseguradoras"     