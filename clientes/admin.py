from django.contrib import admin
from .models import Cliente

@admin.register(Cliente)
class ClienteAdmin(admin.ModelAdmin):
    list_display = (
        "apellido",
        "nombre",
        "dni",
        "whatsapp",
        "localidad",
    )

    search_fields = (
        "apellido",
        "nombre",
        "dni",
        "whatsapp",
    )
