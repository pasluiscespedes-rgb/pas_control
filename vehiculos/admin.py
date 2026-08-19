from django.contrib import admin
from .models import Vehiculo, MarcaVehiculo, ModeloVehiculo, ModeloAnio

@admin.register(Vehiculo)
class VehiculoAdmin(admin.ModelAdmin):
    list_display = (
        "patente",
        "cliente",
        "marca",
        "modelo",
        "anio",
        "uso",
    )

    search_fields = (
        "patente",
        "cliente__apellido",
        "cliente__nombre",
        "cliente__dni",
        "marca",
        "modelo",
    )

@admin.register(MarcaVehiculo)
class MarcaVehiculoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "activa",
    )

    search_fields = (
        "nombre",
    )

    list_filter = (
        "activa",
    )


@admin.register(ModeloVehiculo)
class ModeloVehiculoAdmin(admin.ModelAdmin):
    list_display = (
        "nombre",
        "marca",
        "tipo",
        "activa",
    )

    search_fields = (
        "nombre",
        "marca__nombre",
    )

    list_filter = (
        "tipo",
        "activa",
        "marca",
    )   

@admin.register(ModeloAnio)
class ModeloAnioAdmin(admin.ModelAdmin):
    list_display = (
        "modelo",
        "anio",
    )

    search_fields = (
        "modelo__nombre",
        "modelo__marca__nombre",
    )

    list_filter = (
        "anio",
    )   