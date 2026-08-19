from django.contrib import admin
from .models import Recibo

@admin.register(Recibo)
class ReciboAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "poliza",
        "fecha",
        "numero_cuota",
        "importe",
        "forma_pago",
    )

    search_fields = (
        "poliza__cliente__apellido",
        "poliza__cliente__nombre",
        "poliza__cliente__dni",
        "poliza__vehiculo__patente",
    )

    list_filter = (
        "forma_pago",
        "fecha",
    )