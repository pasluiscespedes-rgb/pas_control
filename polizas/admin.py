from django.contrib import admin
from .models import Poliza

@admin.register(Poliza)
class PolizaAdmin(admin.ModelAdmin):
    list_display = (
        "cliente",
        "tipo_seguro",
        "vehiculo",
        "compania",
        "numero_poliza",
        "fecha_alta",
        "fecha_vencimiento",
        "numero_cuota",
        "estado",
    )

    search_fields = (
        "cliente__apellido",
        "cliente__nombre",
        "cliente__dni",
        "vehiculo__patente",
        "compania",
        "numero_poliza",
    )

    list_filter = (
        "tipo_seguro",
        "compania",
        "estado",
        "periodicidad",
    )
