"""Acceso explícito por recibo; view_recibo por sí solo no concede acceso global."""
from .models import Recibo


def puede_ver_todos_recibos(usuario):
    return usuario.is_authenticated and usuario.is_active and (
        usuario.is_superuser or usuario.has_perm('recibos.ver_todos_recibos')
    )


def recibos_visibles(usuario, queryset=None):
    qs = Recibo.objects.all() if queryset is None else queryset
    if not usuario.is_authenticated or not usuario.is_active:
        return qs.none()
    if puede_ver_todos_recibos(usuario):
        return qs
    return qs.filter(autorizaciones__usuario=usuario).distinct()


def puede_ver_recibo(usuario, recibo_id):
    return recibos_visibles(usuario).filter(pk=recibo_id).exists()


def puede_emitir_recibo(usuario, registro):
    return puede_ver_recibo(usuario, registro.recibo_id) and (
        usuario.is_superuser or registro.cobro.registrado_por_id == usuario.pk
    )


def autorizar_emisor(recibo, cobro):
    """Sólo para el alta nueva: no infiere permisos sobre recibos históricos."""
    from .models import AccesoRecibo
    if cobro.registrado_por_id:
        AccesoRecibo.objects.get_or_create(recibo=recibo, usuario_id=cobro.registrado_por_id,
                                          defaults={'otorgado_por_id': cobro.registrado_por_id})
