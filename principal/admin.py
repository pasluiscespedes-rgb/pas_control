from django.contrib import admin
from .models import GastoCaja, Aseguradora
from .models import GastoCaja, Aseguradora, CierreCaja


@admin.register(GastoCaja)
class GastoCajaAdmin(admin.ModelAdmin):
    list_display = ("fecha_hora", "concepto", "importe")


@admin.register(Aseguradora)
class AseguradoraAdmin(admin.ModelAdmin):
    list_display = ("nombre", "codigo_ssn", "activa")
    search_fields = ("nombre", "codigo_ssn")
    list_filter = ("activa",)
    ordering = ("nombre",)

@admin.register(CierreCaja)
class CierreCajaAdmin(admin.ModelAdmin):
    list_display = (
        "fecha",
        "total_cobrado",
        "total_gastos",
        "saldo_neto",
        "efectivo",
        "tarjeta",
        "transferencia",
        "usuario",
        "fecha_hora_cierre",
    )

    ordering = ("-fecha",)   