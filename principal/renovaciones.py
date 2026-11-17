"""Continuación no destructiva de pólizas existentes."""
from datetime import date
from decimal import Decimal, InvalidOperation

from dateutil.relativedelta import relativedelta
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_protect

from polizas.models import Poliza
from principal.models import MovimientoCliente


def _importe(texto):
    texto = str(texto).strip().replace(" ", "")
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    return Decimal(texto)


@login_required
@csrf_protect
def continuar_poliza(request, poliza_id, operacion):
    if operacion not in {"renovar", "cambiar"}:
        from django.http import Http404
        raise Http404
    anterior = get_object_or_404(
        Poliza.objects.select_related("cliente", "vehiculo"), pk=poliza_id
    )
    es_cambio = operacion == "cambiar"
    errores = []
    # Opciones existentes sin reescribir denominaciones históricas.
    aseguradoras = sorted(set(
        Poliza.objects.exclude(compania__isnull=True)
        .exclude(compania="")
        .values_list("compania", flat=True).distinct()
    ) | {anterior.compania, "NRE COMPAÑÍA DE SEGUROS PATRIMONIALES Y DE PERSONAS S.A."})
    compania_manual = ""
    if request.method == "POST":
        compania = request.POST.get("compania", "").strip().upper()
        if es_cambio and compania == "__OTRA__":
            compania_manual = request.POST.get("compania_manual", "").strip().upper()
            compania = compania_manual
        if len(compania) > 100:
            errores.append("La razón social no puede superar 100 caracteres.")
        if es_cambio and compania and not compania_manual:
            catalogo_por_nombre = {nombre.strip().casefold(): nombre for nombre in aseguradoras if nombre}
            if compania.casefold() not in catalogo_por_nombre:
                errores.append("Seleccioná una aseguradora del listado o utilizá Otra aseguradora.")
            else:
                compania = catalogo_por_nombre[compania.casefold()]
        numero = request.POST.get("numero_poliza", "").strip().upper()
        cobertura = request.POST.get("cobertura", "").strip().upper()
        periodicidad = request.POST.get("periodicidad", "")
        fecha_texto = request.POST.get("fecha_alta", "")
        observaciones = request.POST.get("observaciones", "").strip()
        try:
            inicio = date.fromisoformat(fecha_texto)
        except ValueError:
            inicio = None
            errores.append("Ingresá una fecha de inicio válida.")
        try:
            importe = _importe(request.POST.get("importe_cuota", ""))
            if not importe.is_finite() or importe < 0 or importe > Decimal("9999999999.99"):
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            importe = None
            errores.append("Ingresá un importe de cuota válido.")
        try:
            comision = _importe(request.POST.get("porcentaje_comision", "0") or "0")
            if not comision.is_finite() or not 0 <= comision <= 100:
                raise InvalidOperation
        except (InvalidOperation, ValueError):
            comision = None
            errores.append("La comisión debe estar entre 0 y 100.")
        if not compania:
            errores.append("Indicá la aseguradora.")
        if es_cambio and compania.casefold() == anterior.compania.strip().casefold():
            errores.append("Para cambiar de aseguradora elegí una compañía distinta.")
        if not es_cambio and compania.casefold() != anterior.compania.strip().casefold():
            errores.append("Para cambiar de compañía utilizá Cambiar aseguradora.")
        if not numero:
            errores.append("La nueva póliza debe tener su número definitivo.")
        if numero and Poliza.objects.filter(numero_poliza__iexact=numero).exists():
            errores.append("Ya existe una póliza con ese número.")
        if periodicidad not in dict(Poliza.PERIODICIDADES):
            errores.append("Elegí una periodicidad válida.")
        if anterior.estado == "Anulada":
            errores.append("No se puede continuar una póliza anulada.")
        if not errores:
            with transaction.atomic():
                # Evitar dos continuaciones simultáneas de la misma póliza.
                origen = Poliza.objects.select_for_update().get(pk=anterior.pk)
                if origen.continuaciones.exists():
                    errores.append("Esta póliza ya tiene una continuación registrada.")
                elif Poliza.objects.filter(numero_poliza__iexact=numero).exists():
                    errores.append("El número de póliza ya fue utilizado.")
                else:
                    nueva = Poliza.objects.create(
                        cliente=origen.cliente, vehiculo=origen.vehiculo,
                        tipo_seguro=origen.tipo_seguro, compania=compania,
                        numero_poliza=numero, cobertura=cobertura,
                        fecha_alta=inicio,
                        fecha_vencimiento=inicio + relativedelta(months=1),
                        periodicidad=periodicidad, numero_cuota=0,
                        estado="Pendiente", importe_cuota=importe,
                        porcentaje_comision=comision, observaciones=observaciones,
                        poliza_anterior=origen,
                        tipo_continuacion="cambio" if es_cambio else "renovacion",
                    )
                    MovimientoCliente.objects.create(
                        cliente=origen.cliente, tipo="poliza",
                        titulo="Cambio de aseguradora" if es_cambio else "Póliza renovada",
                        descripcion=f"Anterior: {origen.numero_poliza or origen.pk} ({origen.compania}). Nueva: {nueva.numero_poliza} ({nueva.compania}).",
                        usuario=request.user,
                    )
                    messages.success(request, "Nueva póliza creada; historial anterior preservado.")
                    return redirect("detalle_cliente", cliente_id=origen.cliente_id)
    return render(request, "principal/continuar_poliza.html", {
        "anterior": anterior, "es_cambio": es_cambio, "errores": errores,
        "datos": request.POST if request.method == "POST" else None,
        "periodicidades": Poliza.PERIODICIDADES,
        "aseguradoras": aseguradoras,
        "compania_manual": compania_manual,
    })
