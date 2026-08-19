from django.db import models


class Cliente(models.Model):
    nombre = models.CharField("Nombre", max_length=100)
    apellido = models.CharField("Apellido", max_length=100)
    dni = models.CharField("DNI", max_length=20, unique=True)

    fecha_nacimiento = models.DateField(
        "Fecha de nacimiento",
        null=True,
        blank=True
    )

    whatsapp = models.CharField("WhatsApp", max_length=20, blank=True, default="")

    calle = models.CharField("Calle", max_length=150, blank=True)
    numero = models.CharField("Número", max_length=20, blank=True)
    piso = models.CharField("Piso", max_length=20, blank=True)
    departamento = models.CharField("Departamento", max_length=20, blank=True)
    barrio = models.CharField("Barrio", max_length=100, blank=True)
    codigo_postal = models.CharField("Código postal", max_length=20, blank=True)   
        
    

    email = models.EmailField("Email", blank=True)

    telefono_alternativo = models.CharField(
    "Teléfono alternativo",
    max_length=30,
    blank=True
    )

    estado = models.CharField(
    "Estado",
    max_length=20,
    choices=[
        ("Activo", "Activo"),
        ("Inactivo", "Inactivo"),
        ("Prospecto", "Prospecto"),
    ],
    default="Activo"
    )

    localidad = models.CharField(
        "Localidad",
        max_length=100,
        blank=True
    )

    provincia = models.CharField(
        "Provincia",
        max_length=100,
        blank=True
    )

    observaciones = models.TextField(
        "Observaciones",
        blank=True
    )

    def __str__(self):
        return f"{self.apellido}, {self.nombre}"