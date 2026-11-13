from django.contrib import admin
from vehiculos.catalogo_maestro.modelos import (
    FuenteCatalogoVehiculo, RegistroFuenteModelo, AliasMarcaVehiculo, AliasModeloVehiculo
)

@admin.register(FuenteCatalogoVehiculo)
class FuenteCatalogoAdmin(admin.ModelAdmin):
    list_display = ('codigo','titulo','licencia','registrada_en')
    search_fields = ('codigo','titulo')

@admin.register(RegistroFuenteModelo)
class RegistroFuenteAdmin(admin.ModelAdmin):
    list_display = ('modelo','fuente','primera_carga','ultima_revision')
    list_filter = ('fuente',)
    search_fields = ('modelo__nombre','modelo__marca__nombre')

@admin.register(AliasMarcaVehiculo)
class AliasMarcaAdmin(admin.ModelAdmin):
    list_display = ('denominacion','marca','aprobada','origen')
    list_filter = ('aprobada',)
    search_fields = ('denominacion','marca__nombre')
    readonly_fields = ('normalizado',)

@admin.register(AliasModeloVehiculo)
class AliasModeloAdmin(admin.ModelAdmin):
    list_display = ('denominacion','modelo','aprobada','origen')
    list_filter = ('aprobada',)
    search_fields = ('denominacion','modelo__nombre','modelo__marca__nombre')
    readonly_fields = ('normalizado',)
