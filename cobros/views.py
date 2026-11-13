from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Exists, OuterRef, Q
from django.http import Http404
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods
from polizas.models import Poliza
from recibos.permisos import recibos_visibles

from .models import Cobro
from principal.views import calcular_proximo_vencimiento, actualizar_estado_poliza


def cobros_anulables(usuario):
    cobros = Cobro.objects.all()
    if not usuario.is_active or not usuario.has_perm('cobros.anular_cobro'):
        return cobros.none()
    if usuario.is_superuser:
        return cobros
    return cobros.filter(
        Q(autenticidadrecibo__recibo__in=recibos_visibles(usuario))
        | Q(autenticidadrecibo__isnull=True, registrado_por=usuario)
    )


@login_required
@permission_required('cobros.anular_cobro', raise_exception=True)
@require_http_methods(['GET', 'HEAD', 'POST'])
@csrf_protect
@transaction.atomic
def anular_cobro(request, cobro_id):
    autorizados = cobros_anulables(request.user)
    cobro = get_object_or_404(autorizados, id=cobro_id)

    if request.method == "POST":
        # Orden compartido con el alta: poliza, cobro, autenticidad.
        poliza_bloqueada = Poliza.objects.select_for_update().get(pk=cobro.poliza_id)
        cobro = get_object_or_404(Cobro.objects.select_for_update(), pk=cobro_id)
        if not autorizados.filter(pk=cobro.pk).exists():
            raise Http404
        motivo = request.POST.get("motivo", "").strip()

        if not motivo:
            messages.error(request, "Debés indicar el motivo de la anulación.")
            return render(request, "cobros/anular_cobro.html", {"cobro": cobro})

        if cobro.anulado:
            messages.warning(request, "Este cobro ya se encuentra anulado.")
            return redirect("inicio")

        cobro.anulado = True
        cobro.fecha_anulacion = timezone.now()
        cobro.motivo_anulacion = motivo
        cobro.anulado_por = request.user
        cobro.save()

        # Recalcular la póliza después de anular el cobro
        poliza = poliza_bloqueada

        cuotas_pagadas = set()

        cobros_activos = Cobro.objects.filter(
          poliza=poliza,
         anulado=False,
        )

        for cobro_activo in cobros_activos:
          inicio = cobro_activo.cuota
          fin = inicio + cobro_activo.cantidad_cuotas - 1

          cuotas_pagadas.update(
             range(inicio, fin + 1)
        )

        # Buscar hasta qué cuota están pagadas consecutivamente desde la cuota 1
        ultima_cuota_consecutiva = 0

        for numero in range(1, poliza.cantidad_cuotas + 1):
          if numero in cuotas_pagadas:
              ultima_cuota_consecutiva = numero
          else:
             break

        poliza.numero_cuota = ultima_cuota_consecutiva

        # El próximo vencimiento corresponde a la primera cuota pendiente
        poliza.fecha_vencimiento = calcular_proximo_vencimiento(
          poliza.fecha_alta,
          ultima_cuota_consecutiva + 1,
        )

        actualizar_estado_poliza(poliza)
        poliza.save()

        messages.success(
            request,
            f"El cobro #{cobro.id} fue anulado correctamente."
        )
        return redirect("inicio")

    return render(request, "cobros/anular_cobro.html", {"cobro": cobro})

@login_required
def historial_cobros(request):
    cobros = (
        Cobro.objects
        .select_related("cliente", "poliza", "anulado_por")
        .annotate(puede_anular=Exists(cobros_anulables(request.user).filter(pk=OuterRef('pk'))))
        .order_by("-fecha_pago", "-id")
    )

    return render(
        request,
        "cobros/historial_cobros.html",
        {"cobros": cobros}
    )
