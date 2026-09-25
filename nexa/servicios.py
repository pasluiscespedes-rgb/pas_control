import calendar

from cobros.models import Cobro
from polizas.models import Poliza


def _sumar_meses(fecha, cantidad):
    mes_total = fecha.month - 1 + cantidad
    anio = fecha.year + mes_total // 12
    mes = mes_total % 12 + 1

    ultimo_dia = calendar.monthrange(anio, mes)[1]
    dia = min(fecha.day, ultimo_dia)

    return fecha.replace(
        year=anio,
        month=mes,
        day=dia,
    )


def obtener_contexto_cliente(cliente):
    """
    Devuelve a NEXA información REAL de FORTEX.
    No genera respuestas ni inventa datos.
    """

    polizas = (
        Poliza.objects
        .filter(cliente=cliente)
        .exclude(estado="Anulada")
        .select_related("vehiculo")
        .order_by("-fecha_alta")
    )

    resultado_polizas = []

    for poliza in polizas:

        cobros = (
            Cobro.objects
            .filter(
                poliza=poliza,
                anulado=False,
            )
            .order_by("cuota", "fecha_pago")
        )

        cuotas_pagadas_set = set()

        for cobro in cobros:
            inicio = cobro.cuota
            fin = inicio + cobro.cantidad_cuotas - 1

            cuotas_pagadas_set.update(
                range(inicio, fin + 1)
            )

        cuotas_pagadas = sorted(cuotas_pagadas_set)

        proxima_cuota = None
        proximo_vencimiento = None

        for numero in range(
            1,
            poliza.cantidad_cuotas + 1,
        ):
            if numero not in cuotas_pagadas:
                proxima_cuota = numero

                if poliza.fecha_alta:
                    proximo_vencimiento = _sumar_meses(
                        poliza.fecha_alta,
                        numero,
                    )

                break

        vehiculo = None

        if poliza.vehiculo:
            vehiculo = {
                "patente": poliza.vehiculo.patente,
                "marca": poliza.vehiculo.marca,
                "modelo": poliza.vehiculo.modelo,
                "anio": poliza.vehiculo.anio,
            }

        resultado_polizas.append({
            "id": poliza.id,
            "numero_poliza": poliza.numero_poliza,
            "compania": poliza.compania,
            "tipo_seguro": poliza.tipo_seguro,
            "cobertura": poliza.cobertura,
            "estado": poliza.estado,

            "fecha_alta": (
                poliza.fecha_alta.isoformat()
                if poliza.fecha_alta
                else None
            ),

            "fecha_fin_vigencia": (
                poliza.fecha_fin_vigencia.isoformat()
                if poliza.fecha_fin_vigencia
                else None
            ),

            "importe_cuota": (
                str(poliza.importe_cuota)
                if poliza.importe_cuota is not None
                else None
            ),

            "cantidad_cuotas": poliza.cantidad_cuotas,
            "cuotas_pagadas": cuotas_pagadas,
            "proxima_cuota": proxima_cuota,

            "proximo_vencimiento": (
                proximo_vencimiento.isoformat()
                if proximo_vencimiento
                else None
            ),

            "vehiculo": vehiculo,
        })

    return {
        "cliente": {
            "id": cliente.id,
            "nombre": cliente.nombre,
            "apellido": cliente.apellido,
            "dni": cliente.dni,
            "whatsapp": cliente.whatsapp,
        },
        "polizas": resultado_polizas,
    }