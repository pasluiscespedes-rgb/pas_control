from django.contrib import admin
from .models import Cobro

@admin.register(Cobro)
class CobroAdmin(admin.ModelAdmin):
    list_display = (
        "cliente",
        "poliza",
        "fecha_pago",
        "importe",
        "cuota",
        "forma_pago",
        "estado",
    )

    search_fields = (
        "cliente__apellido",
        "cliente__nombre",
        "cliente__dni",
        "poliza__compania",
        "poliza__numero_poliza",
    )

    list_filter = (
        "forma_pago",
        "estado",
        "fecha_pago",
    )