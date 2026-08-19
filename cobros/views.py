from django.shortcuts import get_object_or_404, redirect, render
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from .models import Cobro

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
