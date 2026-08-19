from django.db import models
from clientes.models import Cliente

class Vehiculo(models.Model):
    TIPO_CHOICES = [  
       ("Moto", "Moto"),  
       ("Auto", "Auto"),  
       ("Camioneta", "Camioneta"),  
       ("Furgón", "Furgón"),  
       ("Camión", "Camión"),  
       ("Acoplado", "Acoplado"),  
       ("Tráiler", "Tráiler"),  
]
    USO_CHOICES = [
        ("Particular", "Particular"),
        ("Comercial", "Comercial"),
        ("Taxi", "Taxi"),
        ("Remis", "Remis"),
        ("Moto", "Moto"),
        ("Camioneta", "Camioneta"),
        ("Camión", "Camión"),
        ("Furgón", "Furgón"),
        ("Acoplado", "Acoplado"),
        ("Tráiler", "Tráiler"),
    ]

    cliente = models.ForeignKey(Cliente, on_delete=models.CASCADE)

    tipo = models.CharField(
       max_length=30,
       choices=TIPO_CHOICES,
       default="Auto"
    )

    patente = models.CharField(max_length=20)
    marca = models.CharField(max_length=50)
    modelo = models.CharField(max_length=50)
    anio = models.PositiveIntegerField("Año", null=True, blank=True)

    motor = models.CharField(max_length=50)
    chasis = models.CharField(max_length=50)

    uso = models.CharField(
        max_length=30,
        choices=USO_CHOICES,
        default="Particular"
    )

    observaciones = models.TextField(blank=True)

    def __str__(self):
        return f"{self.patente} - {self.marca} {self.modelo}"

class MarcaVehiculo(models.Model):
    nombre = models.CharField(
        max_length=100,
        unique=True
    )

    activa = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["nombre"]
        verbose_name = "Marca de vehículo"
        verbose_name_plural = "Marcas de vehículos"

    def __str__(self):
        return self.nombre


class ModeloVehiculo(models.Model):
    marca = models.ForeignKey(
        MarcaVehiculo,
        on_delete=models.CASCADE,
        related_name="modelos"
    )

    nombre = models.CharField(
        max_length=100
    )

    anio_desde = models.PositiveIntegerField(
    null=True,
    blank=True
    )

    anio_hasta = models.PositiveIntegerField(
      null=True,
      blank=True
    )

    tipo = models.CharField(
        max_length=30,
        choices=Vehiculo.TIPO_CHOICES,
        default="Auto"
    )

    activa = models.BooleanField(
        default=True
    )

    class Meta:
        ordering = ["marca__nombre", "nombre"]
        constraints = [
            models.UniqueConstraint(
                fields=["marca", "nombre", "tipo"],
                name="modelo_vehiculo_unico"
            )
        ]
        verbose_name = "Modelo de vehículo"
        verbose_name_plural = "Modelos de vehículos"

    def __str__(self):
        return f"{self.marca.nombre} - {self.nombre}"  

class ModeloAnio(models.Model):
    modelo = models.ForeignKey(
        ModeloVehiculo,
        on_delete=models.CASCADE,
        related_name="anios",
    )

    anio = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["modelo", "anio"],
                name="unique_modelo_anio",
            )
        ]
        ordering = ["anio"]

    def __str__(self):
        return f"{self.modelo} - {self.anio}"      
