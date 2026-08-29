from django.contrib import admin
from .models import GastoCaja, Aseguradora, CierreCaja, Sucursal, PerfilUsuario
from django import forms

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

@admin.register(Sucursal)
class SucursalAdmin(admin.ModelAdmin):
    list_display = ("nombre", "provincia", "codigo", "activa")
    search_fields = ("nombre", "provincia", "codigo")
    list_filter = ("provincia", "activa")

class PerfilUsuarioForm(forms.ModelForm):
    class Meta:
        model = PerfilUsuario
        fields = ("usuario", "sucursal", "activo")
        labels = {
            "usuario": "Usuario",
            "sucursal": "Sucursal",
            "activo": "Activo",
        }
@admin.register(PerfilUsuario)
class PerfilUsuarioAdmin(admin.ModelAdmin):
    form = PerfilUsuarioForm
    list_display = ("usuario", "sucursal", "activo")
    list_filter = ("sucursal", "activo")
    search_fields = ("usuario__username",)   