from django.contrib import admin
from .models import Recibo
from .permisos import recibos_visibles, puede_ver_recibo

@admin.register(Recibo)
class ReciboAdmin(admin.ModelAdmin):
    def get_queryset(self, request):
        return recibos_visibles(request.user, super().get_queryset(request))

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


from .models import AutenticidadRecibo, AnulacionDocumento


@admin.register(AutenticidadRecibo)
class AutenticidadReciboAdmin(admin.ModelAdmin):
    """Cotejo privado del original, con el permiso view_autenticidadrecibo."""
    list_display = ('codigo', 'recibo_id', 'fecha_emision')
    search_fields = ('codigo',)
    fields = ('codigo', 'integridad', 'recibo', 'cobro', 'original', 'fecha_emision', 'sha256_pdf', 'key_id')
    readonly_fields = fields

    def get_queryset(self, request):
        return super().get_queryset(request).filter(recibo__in=recibos_visibles(request.user))

    def has_view_permission(self, request, obj=None):
        return (super().has_view_permission(request, obj) and
                (obj is None or puede_ver_recibo(request.user, obj.recibo_id)))

    @admin.display(description='Integridad y estado al consultar')
    def integridad(self, obj):
        from .autenticidad import integro, pdf_integro, estado_anulacion
        if not integro(obj) or (obj.fecha_emision and not pdf_integro(obj)):
            return 'REGISTRO INCONSISTENTE: no usar para cotejo'
        if estado_anulacion(obj):
            return 'ANULADO'
        return 'Original íntegro; ' + ('PDF emitido' if obj.fecha_emision else 'PDF aún no emitido')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(AnulacionDocumento)
class AnulacionDocumentoAdmin(admin.ModelAdmin):
    list_display = ('registro', 'fecha', 'usuario')
    fields = ('registro', 'motivo', 'usuario', 'fecha')
    readonly_fields = ('usuario', 'fecha')

    def get_queryset(self, request):
        return super().get_queryset(request).filter(registro__recibo__in=recibos_visibles(request.user))

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'registro':
            kwargs['queryset'] = AutenticidadRecibo.objects.filter(recibo__in=recibos_visibles(request.user))
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def has_add_permission(self, request):
        return request.user.has_perm('recibos.anular_documento')

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def save_model(self, request, obj, form, change):
        from django.core.exceptions import PermissionDenied
        if change or not self.has_add_permission(request) or not puede_ver_recibo(request.user, obj.registro.recibo_id):
            raise PermissionDenied
        from .autenticidad import anular_documento
        nuevo = anular_documento(obj.registro, request.user, obj.motivo)
        obj.pk, obj.usuario, obj.fecha = nuevo.pk, nuevo.usuario, nuevo.fecha
        obj._state.adding = False


from .models import AccesoRecibo


@admin.register(AccesoRecibo)
class AccesoReciboAdmin(admin.ModelAdmin):
    list_display = ('recibo', 'usuario', 'otorgado_por', 'fecha')
    readonly_fields = ('otorgado_por', 'fecha')

    def has_module_permission(self, request):
        return request.user.has_perm('recibos.gestionar_accesos_recibo')

    def has_view_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def has_add_permission(self, request):
        return self.has_module_permission(request)

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return self.has_module_permission(request)

    def save_model(self, request, obj, form, change):
        from django.core.exceptions import PermissionDenied
        if change or not self.has_add_permission(request):
            raise PermissionDenied
        obj.otorgado_por = request.user
        super().save_model(request, obj, form, change)
