from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import Cobro
from principal.views import calcular_proximo_vencimiento, actualizar_estado_poliza

@login_required
def anular_cobro(request, cobro_id):
    cobro = get_object_or_404(Cobro, id=cobro_id)

    if request.method == "POST":
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
        poliza = cobro.poliza

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
        .order_by("-fecha_pago", "-id")
    )

    return render(
        request,
        "cobros/historial_cobros.html",
        {"cobros": cobros}
    )
