from datetime import date, timedelta

from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.csrf import csrf_exempt

from clientes.models import Cliente
from vehiculos.models import Vehiculo, MarcaVehiculo, ModeloVehiculo
from polizas.models import Poliza
from cobros.models import Cobro
from recibos.models import Recibo
from datetime import datetime
from django.http import HttpResponse
from django.db.models import Q, Sum,Count
from cobros.models import Cobro
from django.http import HttpResponse
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import cm
from principal.fortex_pdf import dibujar_recibo_fortex
from django.conf import settings
from reportlab.lib.utils import ImageReader
import os
import calendar
from datetime import date, timedelta
from django.contrib.auth.decorators import login_required
from principal.models import MovimientoCliente
from dateutil.relativedelta import relativedelta
from django.shortcuts import render, redirect
from .models import GastoCaja, Aseguradora, CierreCaja, TurnoCaja, PerfilUsuario, Sucursal
from decimal import Decimal
from django.contrib import messages
from backup_db import crear_backup
import subprocess
from pathlib import Path
from django.utils import timezone
from principal.whatsapp import (enviar_recordatorio_vencimiento,enviar_cuota_vencida,obtener_importe_referencia,)



@login_required
def inicio(request):
    busqueda = request.GET.get("buscar", "").strip()

    clientes = Cliente.objects.all()

    if busqueda:
        clientes_por_patente = Vehiculo.objects.filter(
            patente__icontains=busqueda
        ).values_list("cliente_id", flat=True)

        clientes = clientes.filter(
            Q(apellido__icontains=busqueda) |
            Q(nombre__icontains=busqueda) |
            Q(dni__icontains=busqueda) |
            Q(id__in=clientes_por_patente)
        )

    hoy = date.today()
    en_7_dias = hoy + timedelta(days=7)
    manana = hoy + timedelta(days=1)
    fin_mes = hoy + timedelta(days=30)

    cantidad_clientes = clientes.count()

    total_polizas = Poliza.objects.count()

    polizas_vigentes = Poliza.objects.filter(
        fecha_vencimiento__gte=hoy
    ).count()

    polizas_por_vencer = Poliza.objects.filter(
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=fin_mes
    ).count()

    polizas_vencidas = Poliza.objects.filter(
        fecha_vencimiento__lt=hoy
    ).count()

    vencen_hoy = Poliza.objects.filter(
        fecha_vencimiento=hoy    
    )

    vencen_manana = Poliza.objects.filter(
    fecha_vencimiento=manana
)

    vencen_30_dias = Poliza.objects.filter(
    fecha_vencimiento__gt=en_7_dias,
    fecha_vencimiento__lte=fin_mes
)

    vencen_7_dias = Poliza.objects.filter(
        fecha_vencimiento__gt=hoy,
        fecha_vencimiento__lte=en_7_dias
    )

    cobros_hoy = Cobro.objects.filter(
        fecha_pago=hoy
    )

    total_cobrado_hoy = cobros_hoy.aggregate(
        total=Sum("importe")
    )["total"] or 0

    total_clientes = Cliente.objects.count()
    total_vehiculos = Vehiculo.objects.count()
    total_polizas = Poliza.objects.count()

      
    turno_abierto = TurnoCaja.objects.filter(
      usuario=request.user,
      abierto=True,
    ).first()

    if request.user.is_superuser or request.user.groups.filter(
       name="Administrador"
    ).exists():
       cobrado_hoy = Cobro.objects.filter(
         fecha_pago=hoy,
         anulado=False,
       ).aggregate(
          Sum("importe")
       )["importe__sum"] or 0
    else:
       
       if turno_abierto:
           cobrado_hoy = Cobro.objects.filter(
             turno=turno_abierto,
             anulado=False,
           ).aggregate(
              Sum("importe")
           )["importe__sum"] or 0
       else:
            cobrado_hoy = 0

    return render(request, "principal/inicio.html", {
        "clientes": clientes,
        "cantidad_clientes": cantidad_clientes,
        "total_polizas": total_polizas,
        "polizas_vigentes": polizas_vigentes,
        "polizas_por_vencer": polizas_por_vencer,
        "polizas_vencidas": polizas_vencidas,
        "vencen_hoy": vencen_hoy,
        "vencen_7_dias": vencen_7_dias,
        "cobros_hoy": cobros_hoy,
        "total_cobrado_hoy": total_cobrado_hoy,
        "vencen_manana": vencen_manana,
        "vencen_30_dias": vencen_30_dias,
        "total_clientes": total_clientes,
        "total_vehiculos": total_vehiculos,
        "total_polizas": total_polizas,
        "cobrado_hoy": cobrado_hoy,
    })

@login_required
def detalle_cliente(request, cliente_id):
    cliente = Cliente.objects.get(id=cliente_id)

    riesgos = Vehiculo.objects.filter(cliente=cliente)
    polizas = Poliza.objects.filter(cliente=cliente)
    recibos = Recibo.objects.filter(poliza__cliente=cliente).order_by("-fecha")
    cobros = Cobro.objects.filter(poliza__cliente=cliente).order_by("-fecha_pago")
    movimientos = MovimientoCliente.objects.filter(cliente=cliente).select_related("usuario")

    for poliza in polizas:
       poliza.ultimo_recibo = (
        Recibo.objects
        .filter(poliza=poliza)
        .order_by("-fecha", "-id")
        .first()
    )

    return render(request, "principal/detalle_cliente.html", {
    "cliente": cliente,
    "riesgos": riesgos,
    "polizas": polizas,
    "recibos": recibos,
    "cobros": cobros,
    "movimientos": movimientos,
    
})


@csrf_exempt
def crear_cliente(request):
    if request.method == "POST":
        apellido = request.POST.get("apellido", "").strip().upper()
        nombre = request.POST.get("nombre", "").strip().upper()
        dni = request.POST.get("dni", "").strip()
        fecha_nacimiento = request.POST.get("fecha_nacimiento", "").strip()
        whatsapp = request.POST.get("whatsapp", "").strip()

        errores = []

        if not apellido:
         errores.append("Debe ingresar el apellido.")

        if not nombre:
         errores.append("Debe ingresar el nombre.")

        if not dni:
         errores.append("Debe ingresar el DNI.")

        if not fecha_nacimiento:
         errores.append("Debe ingresar la fecha de nacimiento.")

        if not whatsapp:
         errores.append("Debe ingresar el WhatsApp.")

        if Cliente.objects.filter(dni=dni).exists():
         errores.append("Ya existe un cliente con ese DNI.")

        if Cliente.objects.filter(whatsapp=whatsapp).exists():
         errores.append("Ya existe un cliente con ese WhatsApp.") 

        if errores:
            return render(
              request,
             "principal/crear_cliente.html",
           {
             "errores": errores,
             "datos": request.POST,
            },
        )
         
        cliente = Cliente.objects.create(
          apellido=apellido,
          nombre=nombre,
          dni=dni,
          fecha_nacimiento=fecha_nacimiento,
          whatsapp=whatsapp,
          calle=request.POST.get("calle", "").strip().upper(),
          numero=request.POST.get("numero"),
          piso=request.POST.get("piso"),
          departamento=request.POST.get("departamento"),
          barrio=request.POST.get("barrio", "").strip().upper(),
          localidad=request.POST.get("localidad", "").strip().upper(),
          provincia=request.POST.get("provincia", "").strip().upper(),
          codigo_postal=request.POST.get("codigo_postal"),
          email=request.POST.get("email"),
          telefono_alternativo=request.POST.get("telefono_alternativo"),
          observaciones=request.POST.get("observaciones", "").strip().upper(),
        )

        MovimientoCliente.objects.create(
            cliente=cliente,
            tipo="cliente",
            titulo="Cliente registrado",
            descripcion="Se dio de alta el cliente en FORTEX.",
            usuario=request.user,
        )

        messages.success(
           request,
           f"Cliente {cliente.apellido}, {cliente.nombre} guardado correctamente."
)

        return redirect("detalle_cliente", cliente_id=cliente.id)

    return render(request, "principal/crear_cliente.html")


def editar_cliente(request, cliente_id):
    cliente = get_object_or_404(
        Cliente,
        id=cliente_id,
    )

    if request.method == "POST":
        apellido = request.POST.get(
            "apellido",
            "",
        ).strip()

        nombre = request.POST.get(
            "nombre",
            "",
        ).strip()

        dni = request.POST.get(
            "dni",
            "",
        ).strip()

        fecha_nacimiento = request.POST.get(
            "fecha_nacimiento",
            "",
        ).strip()

        whatsapp = request.POST.get(
            "whatsapp",
            "",
        ).strip()

        errores = []

        if not apellido:
            errores.append(
                "Debe ingresar el apellido."
            )

        if not nombre:
            errores.append(
                "Debe ingresar el nombre."
            )

        if not dni:
            errores.append(
                "Debe ingresar el DNI."
            )

        if not fecha_nacimiento:
            errores.append(
                "Debe ingresar la fecha de nacimiento."
            )

        if not whatsapp:
            errores.append(
                "Debe ingresar el WhatsApp."
            )

        if Cliente.objects.filter(
            dni=dni,
        ).exclude(
            id=cliente.id,
        ).exists():
            errores.append(
                "Ya existe otro cliente con ese DNI."
            )

        if Cliente.objects.filter(
            whatsapp=whatsapp,
        ).exclude(
            id=cliente.id,
        ).exists():
            errores.append(
                "Ya existe otro cliente con ese WhatsApp."
            )

        if errores:
            return render(
                request,
                "principal/editar_cliente.html",
                {
                    "cliente": cliente,
                    "errores": errores,
                    "datos": request.POST,
                },
            )

        cambios = []

        campos_controlados = [
            ("Apellido", cliente.apellido, apellido),
            ("Nombre", cliente.nombre, nombre),
            ("DNI", cliente.dni, dni),
            (
                "Fecha de nacimiento",
                str(cliente.fecha_nacimiento),
                fecha_nacimiento,
            ),
            (
                "WhatsApp",
                cliente.whatsapp,
                whatsapp,
            ),
            (
                "Calle",
                cliente.calle,
                request.POST.get("calle", "").strip(),
            ),
            (
                "Número",
                cliente.numero,
                request.POST.get("numero", "").strip(),
            ),
            (
                "Piso",
                cliente.piso,
                request.POST.get("piso", "").strip(),
            ),
            (
                "Departamento",
                cliente.departamento,
                request.POST.get(
                    "departamento",
                    "",
                ).strip(),
            ),
            (
                "Barrio",
                cliente.barrio,
                request.POST.get("barrio", "").strip(),
            ),
            (
                "Localidad",
                cliente.localidad,
                request.POST.get(
                    "localidad",
                    "",
                ).strip(),
            ),
            (
                "Provincia",
                cliente.provincia,
                request.POST.get(
                    "provincia",
                    "",
                ).strip(),
            ),
        ]

        for campo, valor_anterior, valor_nuevo in campos_controlados:
            anterior = str(valor_anterior or "")
            nuevo = str(valor_nuevo or "")

            if anterior != nuevo:
                cambios.append(
                    f"{campo}: "
                    f"'{anterior or 'Sin dato'}' → "
                    f"'{nuevo or 'Sin dato'}'"
                )

        cliente.apellido = apellido
        cliente.nombre = nombre
        cliente.dni = dni
        cliente.fecha_nacimiento = fecha_nacimiento
        cliente.whatsapp = whatsapp

        cliente.calle = request.POST.get(
            "calle",
            "",
        ).strip()

        cliente.numero = request.POST.get(
            "numero",
            "",
        ).strip()

        cliente.piso = request.POST.get(
            "piso",
            "",
        ).strip()

        cliente.departamento = request.POST.get(
            "departamento",
            "",
        ).strip()

        cliente.barrio = request.POST.get(
            "barrio",
            "",
        ).strip()

        cliente.codigo_postal = request.POST.get(
            "codigo_postal",
            "",
        ).strip()

        cliente.localidad = request.POST.get(
            "localidad",
            "",
        ).strip()

        cliente.provincia = request.POST.get(
            "provincia",
            "",
        ).strip()

        cliente.email = request.POST.get(
            "email",
            "",
        ).strip()

        cliente.telefono_alternativo = request.POST.get(
            "telefono_alternativo",
            "",
        ).strip()

        cliente.estado = request.POST.get(
            "estado",
            "Activo",
        )

        cliente.observaciones = request.POST.get(
            "observaciones",
            "",
        ).strip()

        cliente.save()

        if cambios:
            MovimientoCliente.objects.create(
                cliente=cliente,
                tipo="cliente",
                titulo="Datos del cliente actualizados",
                descripcion="\n".join(cambios),
                usuario=request.user,
            )

        return redirect(
            "detalle_cliente",
            cliente_id=cliente.id,
        )

    return render(
        request,
        "principal/editar_cliente.html",
        {
            "cliente": cliente,
        },
    )


@csrf_exempt
def crear_riesgo(request, cliente_id=None):
    clientes = Cliente.objects.all()
    cliente_preseleccionado = None

    if cliente_id:
       cliente_preseleccionado = Cliente.objects.get(id=cliente_id)

    marcas = MarcaVehiculo.objects.filter(activa=True).order_by("nombre")
    modelos = ModeloVehiculo.objects.filter(activa=True).select_related("marca").order_by("marca__nombre", "nombre")

    if request.method == "POST":
        
        cliente_id = request.POST.get("cliente")
        tipo = request.POST.get("tipo", "Auto").strip()

        patente = request.POST.get("patente", "").strip().upper()
        marca = request.POST.get("marca", "").strip()
        modelo = request.POST.get("modelo", "").strip()

        if marca == "OTRA":
            marca = request.POST.get("marca_manual", "").strip().upper()

        if modelo == "OTRO":
            modelo = request.POST.get("modelo_manual", "").strip().upper()

        anio = request.POST.get("anio", "").strip()
        motor = request.POST.get("motor", "").strip().upper()
        chasis = request.POST.get("chasis", "").strip().upper()
        uso = request.POST.get("uso", "").strip()

        errores = [] 

        if not cliente_id:
         errores.append("Debe seleccionar un cliente.")

        if not patente:
         errores.append("Debe ingresar la patente.")

        if not marca:
         errores.append("Debe ingresar la marca.")

        if not modelo:
         errores.append("Debe ingresar el modelo.")

        if not anio:
         errores.append("Debe ingresar el año.")

        if not motor:
         errores.append("Debe ingresar el número de motor.")

        if not chasis:
         errores.append("Debe ingresar el número de chasis.")

        if not uso:
         errores.append("Debe seleccionar el uso del vehículo.") 

        if Vehiculo.objects.filter(patente__iexact=patente).exists():
         errores.append("Ya existe un vehículo registrado con esa patente.")


        

        

        if errores:
           return render(
            request,
            "principal/crear_riesgo.html",
            {
              "clientes": clientes,
              "errores": errores,
              "marcas": marcas,
              "modelos": modelos,
              "datos": request.POST,
              "cliente_preseleccionado": cliente_preseleccionado,
              
            },
        )

        cliente = Cliente.objects.get(id=cliente_id)

        vehiculo = Vehiculo.objects.create(
          cliente=cliente,
          tipo=tipo,
          patente=patente,
          marca=marca,
          modelo=modelo,
          anio=anio or None,
          motor=motor,
          chasis=chasis,
          uso=uso,
        )
        

        MovimientoCliente.objects.create(
          cliente=cliente,
          tipo="riesgo",
          titulo="Riesgo agregado",
          descripcion=f"Se registró el vehículo {vehiculo.patente}.",
          usuario=request.user,
        )

        messages.success(
          request,
          f"Riesgo {vehiculo.patente} guardado correctamente."
)

        return redirect("detalle_cliente", cliente_id=cliente.id)

    return render(request, "principal/crear_riesgo.html", {
        "clientes": clientes,
        "marcas": marcas,
        "modelos": modelos,
        "cliente_preseleccionado": cliente_preseleccionado,
    })

def editar_riesgo(request, riesgo_id):
    riesgo = get_object_or_404(Vehiculo, id=riesgo_id)

    if request.method == "POST":
        patente = request.POST.get("patente", "").strip().upper()
        marca = request.POST.get("marca", "").strip()
        modelo = request.POST.get("modelo", "").strip()
        anio = request.POST.get("anio", "").strip()
        motor = request.POST.get("motor", "").strip()
        chasis = request.POST.get("chasis", "").strip()
        uso = request.POST.get("uso", "").strip()

        errores = []

        if not patente:
            errores.append("Debe ingresar la patente.")

        if not marca:
            errores.append("Debe ingresar la marca.")

        if not modelo:
            errores.append("Debe ingresar el modelo.")

        if not anio:
              errores.append("Debe ingresar el año.")
        elif not anio.isdigit():
              errores.append("El año debe contener solo números.")
        elif int(anio) < 1900 or int(anio) > 2100:
              errores.append("Debe ingresar un año válido.")
              

        if not motor:
            errores.append("Debe ingresar el número de motor.")

        if not chasis:
            errores.append("Debe ingresar el número de chasis.")

        if not uso:
            errores.append("Debe seleccionar el uso del vehículo.")

        if Vehiculo.objects.filter(
            patente__iexact=patente
        ).exclude(
            id=riesgo.id
        ).exists():
            errores.append(
                "Ya existe otro vehículo registrado con esa patente."
            )

        if errores:
            return render(
                request,
                "principal/editar_riesgo.html",
                {
                    "riesgo": riesgo,
                    "errores": errores,
                    "datos": request.POST,
                },
            )
        anio = int(anio)

        cambios = []

        campos = [
            ("Patente", riesgo.patente, patente),
            ("Marca", riesgo.marca, marca),
            ("Modelo", riesgo.modelo, modelo),
            ("Año", riesgo.anio, anio),
            ("Motor", riesgo.motor, motor),
            ("Chasis", riesgo.chasis, chasis),
            ("Uso", riesgo.uso, uso),
        ]

        for campo, anterior, nuevo in campos:
            anterior = str(anterior or "")
            nuevo = str(nuevo or "")

            if anterior != nuevo:
                cambios.append(
                    f"{campo}: "
                    f"'{anterior or 'Sin dato'}' → "
                    f"'{nuevo or 'Sin dato'}'"
                )

        riesgo.patente = patente
        riesgo.marca = marca
        riesgo.modelo = modelo
        riesgo.anio = anio
        riesgo.motor = motor
        riesgo.chasis = chasis
        riesgo.uso = uso
        riesgo.save()

        if cambios:
            MovimientoCliente.objects.create(
                cliente=riesgo.cliente,
                tipo="riesgo",
                titulo="Riesgo actualizado",
                descripcion="\n".join(cambios),
                usuario=request.user,
            )

        return redirect(
            "detalle_cliente",
            cliente_id=riesgo.cliente.id,
        )

    return render(
        request,
        "principal/editar_riesgo.html",
        {
            "riesgo": riesgo,
        },
    )

def lista_polizas(request):
    polizas = Poliza.objects.all().order_by("-id")

    return render(
        request,
        "principal/lista_polizas.html",
        {
            "polizas": polizas,
        },
    )

@csrf_exempt
def crear_poliza(request, cliente_id=None):
    clientes = Cliente.objects.all()
    cliente_seleccionado = None
    vehiculos = Vehiculo.objects.all()
    aseguradoras = Aseguradora.objects.filter(activa=True).order_by("nombre")

    if cliente_id:
        cliente_seleccionado = Cliente.objects.get(id=cliente_id)
        vehiculos = Vehiculo.objects.filter(
            cliente=cliente_seleccionado
        )

    if request.method == "POST":
        cliente_id = request.POST.get("cliente")
        vehiculo_id = request.POST.get("vehiculo")

        tipo_seguro = request.POST.get(
            "tipo_seguro",
            ""
        ).strip().upper()

        compania = request.POST.get(
            "compania",
            ""
        ).strip().upper()

        numero_poliza = request.POST.get(
            "numero_poliza",
            ""
        ).strip().upper()

        fecha_alta = request.POST.get("fecha_alta")
        periodicidad = request.POST.get("periodicidad", "").strip()
        estado = request.POST.get("estado")

        errores = []

        if not cliente_id:
          errores.append("Debe seleccionar un cliente.")

        if not tipo_seguro:
          errores.append("Debe seleccionar un tipo de seguro.")

        if not compania:
          errores.append("Debe ingresar la compañía.")

        if not fecha_alta:
          errores.append("Debe ingresar la fecha de alta.")

        if not periodicidad:
          errores.append("Debe seleccionar la periodicidad.")

        if not estado:
          errores.append("Debe seleccionar el estado.")

        if numero_poliza:
         if Poliza.objects.filter(numero_poliza__iexact=numero_poliza).exists():
          errores.append("Ya existe una póliza con ese número.")

         if errores:
            return render(
             request,
            "principal/crear_poliza.html",
            {
            "clientes": clientes,
            "vehiculos": vehiculos,
            "cliente_seleccionado": cliente_seleccionado,
            "errores": errores,
            "datos": request.POST,
            "aseguradoras":aseguradoras,
            },  
        ) 

    
        cliente = Cliente.objects.get(id=cliente_id)

        vehiculo = (
          Vehiculo.objects.get(id=vehiculo_id)
          if vehiculo_id else None
        )

        fecha_alta = request.POST.get("fecha_alta")
        fecha_alta = datetime.strptime(fecha_alta, "%Y-%m-%d").date()

        # El primer vencimiento de cuota siempre es un mes después del alta
        fecha_vencimiento = fecha_alta + relativedelta(months=1)

        if periodicidad == "Mensual":
          cantidad_cuotas = 1

        elif periodicidad == "Bimestral":
          cantidad_cuotas = 2

        elif periodicidad == "Trimestral":
          cantidad_cuotas = 3

        elif periodicidad == "Cuatrimestral":
          cantidad_cuotas = 4

        elif periodicidad == "Semestral":
          cantidad_cuotas = 6

        elif periodicidad == "Anual":
          cantidad_cuotas = 12

        else:
          cantidad_cuotas = 1 

        poliza = Poliza.objects.create(
          cliente=cliente,
          vehiculo=vehiculo,
          tipo_seguro=tipo_seguro,
          compania=compania,
          porcentaje_comision=request.POST.get("porcentaje_comision") or 0,
          numero_poliza=numero_poliza,
          fecha_alta=fecha_alta,
          fecha_vencimiento=fecha_vencimiento,
          periodicidad=periodicidad,
          cantidad_cuotas=cantidad_cuotas,
          numero_cuota=0,
          estado=request.POST.get("estado") or "Pendiente",
          observaciones=request.POST.get("observaciones"),
        )

        MovimientoCliente.objects.create(
           cliente=cliente,
           tipo="poliza",
           titulo="Póliza registrada",
           descripcion=f"Se registró la póliza N° {poliza.numero_poliza}.",
           usuario=request.user,
        )

        return redirect("detalle_cliente", cliente_id=cliente.id)
        

    return render(request, "principal/crear_poliza.html", {
        "clientes": clientes,
        "vehiculos": vehiculos,
        "cliente_seleccionado": cliente_seleccionado,
        "aseguradoras": aseguradoras,
    })

@login_required
def editar_poliza(request, poliza_id):
    poliza = get_object_or_404(Poliza, id=poliza_id)

    if poliza.estado == "Anulada":
        messages.warning(
        request,
        "Esta póliza está anulada y no puede ser modificada."
    )
    return redirect(
        "detalle_cliente",
        cliente_id=poliza.cliente.id,
    )

    if request.method == "POST":
        vehiculo_id = request.POST.get("vehiculo")
        tipo_seguro = request.POST.get("tipo_seguro", "").strip()
        compania = request.POST.get("compania", "").strip()
        numero_poliza = request.POST.get("numero_poliza", "").strip()
        fecha_alta_texto = request.POST.get("fecha_alta", "").strip()
        periodicidad = request.POST.get("periodicidad", "").strip()
        numero_cuota_texto = request.POST.get("numero_cuota", "").strip()
        estado = request.POST.get("estado", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()

        errores = []

        if not tipo_seguro:
            errores.append("Debe seleccionar un tipo de seguro.")

        if not compania:
            errores.append("Debe ingresar la compañía.")

        if not fecha_alta_texto:
            errores.append("Debe ingresar la fecha de alta.")

        if not periodicidad:
            errores.append("Debe seleccionar la periodicidad.")

        if not numero_cuota_texto:
            errores.append("Debe ingresar el número de cuota.")
        elif not numero_cuota_texto.isdigit():
            errores.append("El número de cuota debe contener solo números.")

        if not estado:
            errores.append("Debe seleccionar el estado.")

        if numero_poliza:
            existe_numero = (
                Poliza.objects
                .filter(numero_poliza__iexact=numero_poliza)
                .exclude(id=poliza.id)
                .exists()
            )

            if existe_numero:
                errores.append(
                    "Ya existe otra póliza con ese número."
                )

        vehiculo = None

        if vehiculo_id:
            vehiculo = Vehiculo.objects.filter(
                id=vehiculo_id,
                cliente=poliza.cliente,
            ).first()

            if not vehiculo:
                errores.append(
                    "El vehículo seleccionado no pertenece al cliente."
                )

        fecha_alta = None

        if fecha_alta_texto:
            try:
                fecha_alta = datetime.strptime(
                    fecha_alta_texto,
                    "%Y-%m-%d",
                ).date()
            except ValueError:
                errores.append(
                    "La fecha de alta no es válida."
                )

        if periodicidad == "Mensual":
            fecha_vencimiento = (
                fecha_alta + relativedelta(months=1)
                if fecha_alta else None
            )
            cantidad_cuotas = 1

        elif periodicidad == "Bimestral":
            fecha_vencimiento = (
                fecha_alta + relativedelta(months=1)
                if fecha_alta else None
            )
            cantidad_cuotas = 2

        elif periodicidad == "Trimestral":
            fecha_vencimiento = (
                fecha_alta + relativedelta(months=1)
                if fecha_alta else None
            )
            cantidad_cuotas = 3

        elif periodicidad == "Cuatrimestral":
            fecha_vencimiento = (
                fecha_alta + relativedelta(months=1)
                if fecha_alta else None
            )
            cantidad_cuotas = 4

        elif periodicidad == "Semestral":
            fecha_vencimiento = (
                fecha_alta + relativedelta(months=1)
                if fecha_alta else None
            )
            cantidad_cuotas = 6

        elif periodicidad == "Anual":
            fecha_vencimiento = (
                fecha_alta + relativedelta(months=1)
                if fecha_alta else None
            )
            cantidad_cuotas = 12

        else:
            fecha_vencimiento = fecha_alta
            cantidad_cuotas = 1

        if errores:
            return render(
                request,
                "principal/editar_poliza.html",
                {
                    "poliza": poliza,
                    "errores": errores,
                },
            )

        numero_cuota = int(numero_cuota_texto)

        cambios = []

        campos = [
            (
                "Vehículo",
                str(poliza.vehiculo or "Sin vehículo"),
                str(vehiculo or "Sin vehículo"),
            ),
            (
                "Tipo de seguro",
                poliza.tipo_seguro,
                tipo_seguro,
            ),
            (
                "Compañía",
                poliza.compania,
                compania,
            ),
            (
                "Número de póliza",
                poliza.numero_poliza,
                numero_poliza,
            ),
            (
                "Fecha de alta",
                poliza.fecha_alta,
                fecha_alta,
            ),
            (
                "Periodicidad",
                poliza.periodicidad,
                periodicidad,
            ),
            (
                "Cantidad de cuotas",
                poliza.cantidad_cuotas,
                cantidad_cuotas,
            ),
            (
                "Número de cuota",
                poliza.numero_cuota,
                numero_cuota,
            ),
            (
                "Estado",
                poliza.estado,
                estado,
            ),
            (
                "Observaciones",
                poliza.observaciones,
                observaciones,
            ),
        ]

        for campo, anterior, nuevo in campos:
            anterior_texto = str(anterior or "")
            nuevo_texto = str(nuevo or "")

            if anterior_texto != nuevo_texto:
                cambios.append(
                    f"{campo}: "
                    f"'{anterior_texto or 'Sin dato'}' → "
                    f"'{nuevo_texto or 'Sin dato'}'"
                )

        poliza.vehiculo = vehiculo
        poliza.tipo_seguro = tipo_seguro
        poliza.compania = compania
        poliza.porcentaje_comision = request.POST.get("porcentaje_comision") or 0
        poliza.numero_poliza = numero_poliza
        poliza.fecha_alta = fecha_alta
        poliza.fecha_vencimiento = fecha_vencimiento
        poliza.fecha_vencimiento = calcular_proximo_vencimiento(
            fecha_alta,
            numero_cuota,
        )
        poliza.cantidad_cuotas = cantidad_cuotas
        poliza.numero_cuota = numero_cuota
        poliza.estado = estado
        poliza.observaciones = observaciones

        # Primero guarda para recalcular fecha_fin_vigencia
        poliza.save()

        # Luego calcula el estado real según vencimiento y vigencia
        actualizar_estado_poliza(poliza)

        # Guarda el estado calculado
        poliza.save() 

        if cambios:
            MovimientoCliente.objects.create(
                cliente=poliza.cliente,
                tipo="poliza",
                titulo="Póliza actualizada",
                descripcion="\n".join(cambios),
                usuario=request.user,
            )

        return redirect(
            "detalle_cliente",
            cliente_id=poliza.cliente.id,
        )

    return render(
        request,
        "principal/editar_poliza.html",
        {
            "poliza": poliza,
        },
    )

@login_required
def anular_poliza(request, poliza_id):
    poliza = get_object_or_404(Poliza, id=poliza_id)

    if request.method == "POST":
        motivo = request.POST.get("motivo_anulacion", "").strip()

        if not motivo:
            messages.error(request, "Debés indicar el motivo de la anulación.")
            return render(
                request,
                "principal/anular_poliza.html",
                {"poliza": poliza},
            )

        if poliza.estado == "Anulada":
            messages.warning(request, "Esta póliza ya se encuentra anulada.")
            return redirect(
                "detalle_cliente",
                cliente_id=poliza.cliente.id,
            )

        poliza.estado = "Anulada"
        poliza.motivo_anulacion = motivo
        poliza.fecha_anulacion = timezone.now()
        poliza.anulada_por = request.user
        poliza.save()

        MovimientoCliente.objects.create(
            cliente=poliza.cliente,
            tipo="poliza",
            titulo="Póliza anulada",
            descripcion=(
                f"Se anuló la póliza N° {poliza.numero_poliza}. "
                f"Motivo: {motivo}"
            ),
            usuario=request.user,
        )

        messages.success(
            request,
            f"La póliza N° {poliza.numero_poliza} fue anulada correctamente.",
        )

        return redirect(
            "detalle_cliente",
            cliente_id=poliza.cliente.id,
        )

    return render(
        request,
        "principal/anular_poliza.html",
        {"poliza": poliza},
    )

def calcular_proximo_vencimiento(fecha, cantidad):
    mes_total = fecha.month - 1 + cantidad
    nuevo_anio = fecha.year + mes_total // 12
    nuevo_mes = mes_total % 12 + 1

    ultimo_dia = calendar.monthrange(
        nuevo_anio,
        nuevo_mes
    )[1]

    nuevo_dia = min(fecha.day, ultimo_dia)

    return fecha.replace(
        year=nuevo_anio,
        month=nuevo_mes,
        day=nuevo_dia,
    )


def actualizar_estado_poliza(poliza):
    if poliza.numero_cuota > poliza.cantidad_cuotas:
        poliza.numero_cuota = poliza.cantidad_cuotas

    hoy = date.today()
   
    if (
       poliza.fecha_fin_vigencia
       and hoy > poliza.fecha_fin_vigencia
    ):
       poliza.estado = "Vencida"
       return
   

    if poliza.fecha_vencimiento >= hoy:
        poliza.estado = "Al día"
        return

    dias_atraso = (
        hoy - poliza.fecha_vencimiento
    ).days

    if dias_atraso <= 30:
        poliza.estado = "Pendiente"
    else:
        poliza.estado = "Morosa"


def generar_numero_recibo():
    ultimo_recibo = (
        Recibo.objects
        .exclude(numero_recibo="")
        .order_by("-id")
        .first()
    )

    ultimo_numero = 0

    if ultimo_recibo:
        texto_numero = (
            ultimo_recibo.numero_recibo or ""
        )

        solo_numeros = "".join(
            caracter
            for caracter in texto_numero
            if caracter.isdigit()
        )

        if solo_numeros:
            ultimo_numero = int(solo_numeros)

    return f"R-{ultimo_numero + 1:06d}"

@csrf_exempt
@login_required
def crear_cobro_seguro(request, cliente_id=None):
    turno_abierto = TurnoCaja.objects.filter(
        usuario=request.user,
        abierto=True,
    ).first()

    if not turno_abierto:
        messages.warning(
            request,
            "Debés abrir un turno antes de registrar nuevos cobros."
        )
        return redirect("caja_diaria")

    return crear_cobro(request, cliente_id)

@csrf_exempt
def crear_cobro(request, cliente_id=None):
    cliente_seleccionado = None

    if cliente_id:
        cliente_seleccionado = Cliente.objects.get(id=cliente_id)
        polizas = Poliza.objects.filter(cliente=cliente_seleccionado)
    else:
        polizas = Poliza.objects.all()

    poliza_seleccionada = request.GET.get("poliza")

    if poliza_seleccionada:
       poliza_seleccionada = Poliza.objects.get(id=poliza_seleccionada)    

    if request.method == "POST":
        importe = request.POST.get("importe", "").strip()

        # Formato argentino: 40.000,50 -> 40000.50
        importe = importe.replace(".", "").replace(",", ".")
        plus = request.POST.get("plus", "0").strip()
        plus = plus.replace(".", "").replace(",", ".")
        fecha_pago = request.POST.get("fecha_pago") or date.today()
        poliza = Poliza.objects.get(
            id=request.POST.get("poliza")
        )

        importe_decimal = Decimal(importe or "0")
        plus_decimal = Decimal(plus or "0")

        base_comision = importe_decimal - plus_decimal

        porcentaje = poliza.porcentaje_comision or Decimal("0")

        comision = (
           base_comision * porcentaje / Decimal("100")
        )

        cuota_pagada = poliza.numero_cuota + 1

        cantidad = int(
           request.POST.get("cantidad_cuotas_pagadas", 1) or 1
        )

        if cantidad < 1:
           cantidad = 1

        cuota_final = cuota_pagada + cantidad - 1

        # No permitir pagar más cuotas de las que tiene la póliza
        if cuota_final > poliza.cantidad_cuotas:
            return render(request, "principal/crear_cobro.html", {
               "polizas": polizas,
               "cliente_seleccionado": cliente_seleccionado,
               "poliza_seleccionada": poliza,
               "hoy": date.today(),
               "formas_pago": Cobro.FORMAS_PAGO,
               "error": (
                  f"No se pueden cobrar las cuotas {cuota_pagada} a {cuota_final}. "
                  f"La póliza tiene {poliza.cantidad_cuotas} cuotas."
                ),
            })

        # Revisar si alguna de las cuotas solicitadas ya fue cobrada
        cuotas_solicitadas = set(
          range(cuota_pagada, cuota_final + 1)
        )

        for cobro_anterior in Cobro.objects.filter(
          poliza=poliza,
          anulado=False,
        ):
           inicio = cobro_anterior.cuota
           fin = inicio + cobro_anterior.cantidad_cuotas - 1

           cuotas_anteriores = set(range(inicio, fin + 1))

           repetidas = cuotas_solicitadas.intersection(
              cuotas_anteriores
           )

           if repetidas:
               cuotas_texto = ", ".join(
                 str(c) for c in sorted(repetidas)
                )

               return render(request, "principal/crear_cobro.html", {
                  "polizas": polizas,
                  "cliente_seleccionado": cliente_seleccionado,
                  "poliza_seleccionada": poliza,
                  "hoy": date.today(),
                  "formas_pago": Cobro.FORMAS_PAGO,
                  "error": (
                     f"La cuota {cuotas_texto} ya fue cobrada "
                     f"para esta póliza."
                    ),
                })
           
        turno_abierto = TurnoCaja.objects.filter(
          usuario=request.user,
          abierto=True,
        ).first()

        if not turno_abierto:
           messages.warning(
            request,
            "Debés abrir un turno antes de registrar cobros."
           )
           return redirect("caja_diaria")
           
        cobro = Cobro.objects.create(
          cliente=poliza.cliente,
          poliza=poliza,
          fecha_pago=fecha_pago,
          importe=importe,
          plus=plus,
          comision=comision,
          cuota=cuota_pagada,
          cantidad_cuotas=cantidad,
          forma_pago=request.POST.get("forma_pago"),
          observaciones=request.POST.get("observaciones"),
          registrado_por=request.user,
          turno=turno_abierto,
        )

        fecha = poliza.fecha_vencimiento or poliza.fecha_alta

        # Corrige datos antiguos dañados:
        # el vencimiento de pago no puede superar el fin de vigencia.
        if (
            poliza.fecha_fin_vigencia
            and fecha > poliza.fecha_fin_vigencia
        ):
            fecha = poliza.fecha_alta
            poliza.numero_cuota = 0

        print("Fecha alta:", poliza.fecha_alta)
        print("Fecha vencimiento antes del cobro:", poliza.fecha_vencimiento)
        print("Fecha usada para calcular:", fecha)

        # Actualizar cuota y vencimiento según las cuotas realmente pagadas
        if cuota_final >= poliza.cantidad_cuotas:
            # Se pagó la última cuota de la póliza
            poliza.numero_cuota = poliza.cantidad_cuotas

            poliza.fecha_vencimiento = calcular_proximo_vencimiento(
                poliza.fecha_alta,
                poliza.cantidad_cuotas,
            )
        else:
           # Quedan cuotas pendientes
           poliza.numero_cuota = cuota_final

           poliza.fecha_vencimiento = calcular_proximo_vencimiento(
                 poliza.fecha_alta,
                 poliza.numero_cuota + 1,
        )

        actualizar_estado_poliza(poliza)

        print("Nueva cuota:", poliza.numero_cuota)
        print("Nuevo vencimiento:", poliza.fecha_vencimiento)

        poliza.save()

        numero_recibo = generar_numero_recibo()

        recibo = Recibo.objects.create(
            poliza=poliza,
            numero_cuota=cuota_pagada,
            cantidad_cuotas=cantidad,
            importe=importe,
            forma_pago=request.POST.get("forma_pago"),
            observaciones=request.POST.get("observaciones"),
            numero_recibo=numero_recibo,

        )

        MovimientoCliente.objects.create(
            cliente=poliza.cliente,
            tipo="cobro",
            titulo="Cobro registrado",
            descripcion=(
                  f"Se registró el cobro de las cuotas {cuota_pagada} a {cuota_final}. "
                  f"Importe: ${cobro.importe}. "
                  f"Forma de pago: {cobro.forma_pago}. "
                  f"Recibo: {numero_recibo}."
            ),
        usuario=request.user,
    )
        return redirect("ver_recibo", recibo_id=recibo.id)

    return render(request, "principal/crear_cobro.html", {
           "polizas": polizas,
           "cliente_seleccionado": cliente_seleccionado,
           "poliza_seleccionada": poliza_seleccionada, 
           "hoy": date.today(),
           "formas_pago": Cobro.FORMAS_PAGO,
        })

def lista_recibos(request):
    recibos = Recibo.objects.all().order_by("-id")

    return render(
        request,
        "principal/lista_recibos.html",
        {
            "recibos": recibos,
        },
    )

def ver_recibo(request, recibo_id):
    recibo = Recibo.objects.get(id=recibo_id)

    return render(request, "principal/ver_recibo.html", {
        "recibo": recibo,
        "poliza": recibo.poliza,
        "cliente": recibo.poliza.cliente,
        "vehiculo": recibo.poliza.vehiculo,
    })

def recibo_pdf(request, recibo_id):
    recibo = Recibo.objects.get(id=recibo_id)
    poliza = recibo.poliza
    cliente = poliza.cliente
    vehiculo = poliza.vehiculo

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = f'inline; filename="Recibo_{recibo.id}.pdf"'

    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm

    p = canvas.Canvas(response, pagesize=A4)

    def dibujar_recibo(x, y, copia):
        p.setFont("Helvetica-Bold", 18)
        p.drawString(x, y, "FORTEX")

        p.setFont("Helvetica-Bold", 9)
        p.drawString(x, y - 12, "GESTIÓN INTEGRAL")

        p.setFont("Helvetica", 8)
        p.drawString(x, y - 24, "Administradores de Riesgos")

        p.setFont("Helvetica-Bold", 10)
        p.drawString(x + 6.8 * cm, y, "RECIBO DE PAGO")

        p.setFont("Helvetica", 9)
        p.drawString(x + 6.8 * cm, y - 16, f"N° {recibo.numero_recibo}")
        p.drawString(x + 6.8 * cm, y - 31, f"Fecha: {recibo.fecha}")

        p.rect(x - 0.2 * cm, y - 145, 9.2 * cm, 4.4 * cm)

        p.setFont("Helvetica-Bold", 7)
        p.drawString(x, y - 50, f"RECIBIMOS DE: {cliente.apellido}, {cliente.nombre}")
        p.drawString(x, y - 64, f"ASEGURADORA: {poliza.compania}")
        p.drawString(x, y - 78, f"PÓLIZA: {poliza.numero_poliza or 'PROVISORIA'}")
        p.drawString(x + 3.8 * cm, y - 78, f"CUOTA: {recibo.numero_cuota}")
        p.drawString(x + 6.2 * cm, y - 78, f"IMPORTE: ${recibo.importe}")

        p.setFont("Helvetica", 7)
        p.drawString(x, y - 94, f"VEHÍCULO: {vehiculo.marca} {vehiculo.modelo}")
        p.drawString(x, y - 108, f"PATENTE: {vehiculo.patente}")
        p.drawString(x + 3.2 * cm, y - 108, f"MOTOR: {vehiculo.motor}")
        p.drawString(x + 6.0 * cm, y - 108, f"CHASIS: {vehiculo.chasis}")

        p.drawString(x, y - 124, f"FORMA DE PAGO: {recibo.forma_pago}")

        p.setFont("Helvetica-Bold", 7)
        p.drawRightString(x + 8.6 * cm, y - 136, copia)

    dibujar_recibo_fortex(
    p,
    recibo,
    0.15 * cm,
    29.1 * cm,
    "ORIGINAL - OFICINA"
)

    dibujar_recibo_fortex(
    p,
    recibo,
    10.10 * cm,
    29.1 * cm,
    "COPIA - ASEGURADO"
)

    p.setFont("Helvetica", 18)
    p.drawCentredString(5.5 * cm, 18 * cm, "I N U T I L I Z A D O")
    p.drawCentredString(15.5 * cm, 18 * cm, "I N U T I L I Z A D O")
    p.drawCentredString(5.5 * cm, 9 * cm, "I N U T I L I Z A D O")
    p.drawCentredString(15.5 * cm, 9 * cm, "I N U T I L I Z A D O")

    p.showPage()
    p.save()

    return response



def ver_ultimo_recibo(request, cliente_id):

    cliente = Cliente.objects.get(id=cliente_id)

    recibo = Recibo.objects.filter(
        poliza__cliente=cliente
    ).order_by("-id").first()

    if not recibo:
        return HttpResponse(
            "<h2>Este cliente todavía no posee recibos.</h2>"
            "<br><a href='/clientes/%d/'>Volver</a>" % cliente.id
        )

    return redirect("ver_recibo", recibo_id=recibo.id)


def ver_poliza(request, poliza_id):
    poliza = Poliza.objects.get(id=poliza_id)

    return render(request, "principal/ver_poliza.html", {
        "poliza": poliza,
        "cliente": poliza.cliente,
        "vehiculo": poliza.vehiculo,
    })

@csrf_exempt
def completar_poliza(request, poliza_id):
    poliza = Poliza.objects.get(id=poliza_id)

    if request.method == "POST":
        poliza.numero_poliza = request.POST.get("numero_poliza")
        poliza.estado = "Vigente"
        poliza.save()

        return redirect("ver_poliza", poliza_id=poliza.id)

    return render(request, "principal/completar_poliza.html", {
        "poliza": poliza,
        "cliente": poliza.cliente,
    })


def imprimir_poliza(request, poliza_id):
    poliza = Poliza.objects.get(id=poliza_id)
    cliente = poliza.cliente
    vehiculo = poliza.vehiculo

    response = HttpResponse(content_type="application/pdf")
    response["Content-Disposition"] = (
        f'inline; filename="Poliza_Provisoria_{poliza.id}.pdf"'
    )

    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.lib import colors

    p = canvas.Canvas(response, pagesize=A4)
    ancho, alto = A4

    logo_path = os.path.join(
      settings.BASE_DIR,
     "principal",
     "static",
     "principal",
     "img",
     "fortex_logo.png"
    )

    azul = colors.HexColor("#0B3D91")
    gris = colors.HexColor("#4B5563")

    # Encabezado
    p.setStrokeColor(azul)
    p.roundRect(1 * cm, alto - 5 * cm, 19 * cm, 3.8 * cm, 8)

    p.drawImage(
      ImageReader(logo_path),
      1.10 * cm,
      alto - 4.10 * cm,
      width=2.80 * cm,
      height=2.80 * cm,
      preserveAspectRatio=True,
      mask="auto"
    )

    p.setFillColor(azul)
    p.setFont("Helvetica-Bold", 24)
    p.drawString(3.8 * cm, alto - 2.2 * cm, "FORTEX")

    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(3.8 * cm, alto - 2.7 * cm, "GESTIÓN INTEGRAL")

    p.setFillColor(gris)
    p.setFont("Helvetica", 9)
    p.drawString(3.8 * cm, alto - 3.15 * cm, "Administradores de Riesgos")
    p.drawString(3.8 * cm, alto - 3.60 * cm, "WhatsApp: 381-0000000")

    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 16)
    p.drawRightString(
        19.5 * cm,
        alto - 2.2 * cm,
        "PÓLIZA PROVISORIA"
    )

    p.setFont("Helvetica", 10)
    p.drawRightString(
        19.5 * cm,
        alto - 2.85 * cm,
        f"N° {poliza.id:07d}"
    )

    # Datos del asegurado
    y = alto - 6 * cm

    p.setStrokeColor(azul)
    p.roundRect(1 * cm, y - 4.2 * cm, 19 * cm, 4 * cm, 6)

    p.setFillColor(azul)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(1.4 * cm, y - 0.7 * cm, "DATOS DEL ASEGURADO")

    p.setFillColor(colors.black)
    p.setFont("Helvetica", 9)
    p.drawString(
        1.4 * cm,
        y - 1.4 * cm,
        f"Apellido y nombre: {cliente.apellido}, {cliente.nombre}"
    )
    p.drawString(
        1.4 * cm,
        y - 2.1 * cm,
        f"DNI: {cliente.dni}"
    )
    p.drawString(
        1.4 * cm,
        y - 2.8 * cm,
        f"WhatsApp: {cliente.whatsapp}"
    )
    p.drawString(
        1.4 * cm,
        y - 3.5 * cm,
        f"Domicilio: {cliente.calle or ''} {cliente.numero or ''}"
    )

    # Datos de póliza
    y2 = y - 5 * cm

    p.setStrokeColor(azul)
    p.roundRect(1 * cm, y2 - 4.6 * cm, 19 * cm, 4.4 * cm, 6)

    p.setFillColor(azul)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(1.4 * cm, y2 - 0.7 * cm, "DATOS DE LA COBERTURA")

    p.setFillColor(colors.black)
    p.setFont("Helvetica", 9)
    p.drawString(
        1.4 * cm,
        y2 - 1.4 * cm,
        f"Aseguradora: {poliza.compania}"
    )
    p.drawString(
        1.4 * cm,
        y2 - 2.1 * cm,
        f"Número de póliza: {poliza.numero_poliza or 'PROVISORIA'}"
    )
    p.drawString(
        1.4 * cm,
        y2 - 2.8 * cm,
        f"Fecha de alta: {poliza.fecha_alta.strftime('%d/%m/%Y')}"

    )
    p.drawString(
        10.5 * cm,
        y2 - 2.8 * cm,
        f"Vencimiento: {poliza.fecha_vencimiento.strftime('%d/%m/%Y')}"
    )
    p.drawString(
        1.4 * cm,
        y2 - 3.5 * cm,
        f"Estado: {poliza.estado}"
    )
    p.drawString(
        10.5 * cm,
        y2 - 3.5 * cm,
        f"Tipo de seguro: {poliza.tipo_seguro}"
    )

    # Datos del vehículo
    y3 = y2 - 5.4 * cm

    p.setStrokeColor(azul)
    p.roundRect(1 * cm, y3 - 4.6 * cm, 19 * cm, 4.4 * cm, 6)

    p.setFillColor(azul)
    p.setFont("Helvetica-Bold", 10)
    p.drawString(1.4 * cm, y3 - 0.7 * cm, "DATOS DEL VEHÍCULO")

    p.setFillColor(colors.black)
    p.setFont("Helvetica", 9)
    p.drawString(
        1.4 * cm,
        y3 - 1.4 * cm,
        f"Marca y modelo: {vehiculo.marca} {vehiculo.modelo}"
    )
    p.drawString(
        1.4 * cm,
        y3 - 2.1 * cm,
        f"Patente: {vehiculo.patente}"
    )
    p.drawString(
        7.5 * cm,
        y3 - 2.1 * cm,
        f"Uso: {vehiculo.uso}"
    )
    p.drawString(
        1.4 * cm,
        y3 - 2.8 * cm,
        f"Motor: {vehiculo.motor}"
    )
    p.drawString(
        1.4 * cm,
        y3 - 3.5 * cm,
        f"Chasis: {vehiculo.chasis}"
    )

    # Leyenda
    p.setFillColor(colors.black)
    p.setFont("Helvetica-Bold", 9)
    p.drawCentredString(
        ancho / 2,
        3.2 * cm,
        "DOCUMENTO PROVISORIO SUJETO A EMISIÓN DEFINITIVA"
    )

    p.setFont("Helvetica", 8)
    p.drawCentredString(
        ancho / 2,
        2.6 * cm,
        "Este documento acredita la solicitud de cobertura y debe conservarse."
    )

    p.showPage()
    p.save()

    return response

def vencimientos(request):
    hoy = date.today()
    en_15_dias = hoy + timedelta(days=15)

    por_vencer = Poliza.objects.filter(
        fecha_vencimiento__gte=hoy,
        fecha_vencimiento__lte=en_15_dias
    ).order_by("fecha_vencimiento")

    vencidas = Poliza.objects.filter(
        fecha_vencimiento__lt=hoy
    ).order_by("fecha_vencimiento")

    return render(request, "principal/vencimientos.html", {
        "por_vencer": por_vencer,
        "vencidas": vencidas,
    })

from datetime import date, timedelta

from django.db.models import Q
from django.shortcuts import render

from polizas.models import Poliza


def centro_vencimientos(request):
    hoy = date.today()
    en_7_dias = hoy + timedelta(days=7)
    en_15_dias = hoy + timedelta(days=15)

    buscar = request.GET.get("buscar", "").strip()

    vencidas = Poliza.objects.filter(
        fecha_vencimiento__lt=hoy
    ).select_related(
        "cliente",
        "vehiculo"
    ).order_by("fecha_vencimiento")

    vencen_hoy = Poliza.objects.filter(
        fecha_vencimiento=hoy
    ).select_related(
        "cliente",
        "vehiculo"
    ).order_by("fecha_vencimiento")

    proximos_7 = Poliza.objects.filter(
        fecha_vencimiento__gt=hoy,
        fecha_vencimiento__lte=en_7_dias
    ).select_related(
        "cliente",
        "vehiculo"
    ).order_by("fecha_vencimiento")

    proximos_15 = Poliza.objects.filter(
        fecha_vencimiento__gt=en_7_dias,
        fecha_vencimiento__lte=en_15_dias
    ).select_related(
        "cliente",
        "vehiculo"
    ).order_by("fecha_vencimiento")

    if buscar:
        filtro_busqueda = (
            Q(cliente__apellido__icontains=buscar)
            | Q(cliente__nombre__icontains=buscar)
            | Q(cliente__dni__icontains=buscar)
            | Q(vehiculo__patente__icontains=buscar)
        )

        vencidas = vencidas.filter(filtro_busqueda)
        vencen_hoy = vencen_hoy.filter(filtro_busqueda)
        proximos_7 = proximos_7.filter(filtro_busqueda)
        proximos_15 = proximos_15.filter(filtro_busqueda)

    contexto = {
        "vencidas": vencidas,
        "vencen_hoy": vencen_hoy,
        "proximos_7": proximos_7,
        "proximos_15": proximos_15,

        "total_avisos": vencidas.count() + vencen_hoy.count() + proximos_7.count() + proximos_15.count(),

        "buscar": buscar,
    }

    return render(
        request,
        "principal/vencimientos.html",
        contexto
    )

def avisos_del_dia(request):
    hoy = date.today()
    en_7_dias = hoy + timedelta(days=7)
    en_15_dias = hoy + timedelta(days=15)

    categoria = request.GET.get("categoria", "hoy")

    consultas = {
        "vencidas": Poliza.objects.filter(
            fecha_vencimiento__lt=hoy
        ),
        "hoy": Poliza.objects.filter(
            fecha_vencimiento=hoy
        ),
        "7_dias": Poliza.objects.filter(
            fecha_vencimiento__gt=hoy,
            fecha_vencimiento__lte=en_7_dias
        ),
        "15_dias": Poliza.objects.filter(
            fecha_vencimiento__gt=en_7_dias,
            fecha_vencimiento__lte=en_15_dias
        ),
    }

    polizas = consultas.get(
        categoria,
        consultas["hoy"]
    ).select_related(
        "cliente",
        "vehiculo"
    ).order_by(
        "fecha_vencimiento",
        "cliente__apellido",
        "cliente__nombre"
    )

    contexto = {
        "hoy": hoy,
        "categoria": categoria,
        "polizas": polizas,

        "total_vencidas": consultas["vencidas"].count(),
        "total_hoy": consultas["hoy"].count(),
        "total_7_dias": consultas["7_dias"].count(),
        "total_15_dias": consultas["15_dias"].count(),
    }

    return render(
        request,
        "principal/avisos_del_dia.html",
        contexto
    )

@login_required
def enviar_aviso_whatsapp(request, poliza_id):
    if request.method != "POST":
        return redirect("avisos_del_dia")

    poliza = get_object_or_404(
        Poliza.objects.select_related("cliente", "vehiculo"),
        id=poliza_id,
    )

    if not poliza.cliente.whatsapp:
       messages.error(
        request,
        "El cliente no tiene un número de WhatsApp registrado."
    )
    return redirect("avisos_del_dia")

    if not poliza.vehiculo or not poliza.vehiculo.patente:
        messages.error(
            request,
            "La póliza no tiene un vehículo o patente válida."
        )
    return redirect("avisos_del_dia")

    numero = str(poliza.cliente.whatsapp or "")
    numero = "".join(c for c in numero if c.isdigit())

    # Normalización para celulares argentinos
    if numero.startswith("0"):
        numero = numero[1:]

    if numero.startswith("54"):
        destinatario = numero
    else:
        destinatario = "549" + numero

    nombre = poliza.cliente.nombre.strip()
    patente = poliza.vehiculo.patente.strip()
    fecha = poliza.fecha_vencimiento.strftime("%d/%m/%Y")

    importe = obtener_importe_referencia(poliza)

    if importe is None:
        importe_texto = "Consultar con su asesor"
    else:
        importe_texto = f"{importe:,.0f}".replace(",", ".")

    try:
        if poliza.fecha_vencimiento < date.today():
            respuesta = enviar_cuota_vencida(
                destinatario=destinatario,
                nombre=nombre,
                patente=patente,
                fecha_vencimiento=fecha,
                importe=importe_texto,
            )
            tipo_aviso = "cuota vencida"
        else:
            respuesta = enviar_recordatorio_vencimiento(
                destinatario=destinatario,
                nombre=nombre,
                patente=patente,
                fecha_vencimiento=fecha,
                importe=importe_texto,
            )
            tipo_aviso = "recordatorio"

        if respuesta.ok:
            messages.success(
                request,
                f"WhatsApp de {tipo_aviso} enviado correctamente a {nombre}."
            )
        else:
            messages.error(
                request,
                f"Meta rechazó el envío: {respuesta.text}"
            )

    except Exception as error:
        messages.error(
            request,
            f"No se pudo enviar el WhatsApp: {error}"
        )

    return redirect("avisos_del_dia")

@login_required
def lista_clientes(request):
    busqueda = request.GET.get("q", "").strip()

    clientes = Cliente.objects.all().order_by("apellido", "nombre")

    if busqueda:
        clientes = clientes.filter(
            Q(apellido__icontains=busqueda)
            | Q(nombre__icontains=busqueda)
            | Q(dni__icontains=busqueda)
            | Q(whatsapp__icontains=busqueda)
        )

    contexto = {
        "clientes": clientes,
        "busqueda": busqueda,
        "cantidad_clientes": clientes.count(),
    }

    return render(
        request,
        "principal/lista_clientes.html",
        contexto,
    )

@login_required
def lista_riesgos(request):
    busqueda = request.GET.get("q", "").strip()

    riesgos = (
        Vehiculo.objects
        .select_related("cliente")
        .all()
        .order_by("cliente__apellido", "patente")
    )

    if busqueda:
        riesgos = riesgos.filter(
            Q(patente__icontains=busqueda)
            | Q(marca__icontains=busqueda)
            | Q(modelo__icontains=busqueda)
            | Q(cliente__apellido__icontains=busqueda)
            | Q(cliente__nombre__icontains=busqueda)
        )

    contexto = {
        "riesgos": riesgos,
        "busqueda": busqueda,
        "cantidad_riesgos": riesgos.count(),
    }

    return render(
        request,
        "principal/lista_riesgos.html",
        contexto,
    )

from django.db.models import Sum
from datetime import date


@login_required
def caja_diaria(request):
    turno_abierto = TurnoCaja.objects.filter(
        usuario=request.user,
        abierto=True,
    ).first()

    if turno_abierto:
        cobros = Cobro.objects.filter(
            turno=turno_abierto,
            anulado=False,
        )

        gastos = GastoCaja.objects.filter(
            turno=turno_abierto,
        )
    else:
        cobros = Cobro.objects.none()
        gastos = GastoCaja.objects.none()

    total = (
        cobros.aggregate(Sum("importe"))["importe__sum"] or 0
    )

    efectivo = (
        cobros.filter(forma_pago="Efectivo")
        .aggregate(Sum("importe"))["importe__sum"] or 0
    )

    tarjeta = (
        cobros.filter(forma_pago="Tarjeta")
        .aggregate(Sum("importe"))["importe__sum"] or 0
    )

    transferencia = (
        cobros.filter(forma_pago="Transferencia")
        .aggregate(Sum("importe"))["importe__sum"] or 0
    )

    debito = (
        cobros.filter(forma_pago="Debito")
        .aggregate(Sum("importe"))["importe__sum"] or 0
    )

    total_gastos = (
        gastos.aggregate(Sum("importe"))["importe__sum"] or 0
    )

    saldo_neto = total - total_gastos

    resumen_companias = (
        cobros
        .values("poliza__compania")
        .annotate(
            total_importe=Sum("importe"),
            cantidad_cobros=Count("id"),
        )
        .order_by("poliza__compania")
    )

    return render(
        request,
        "principal/caja_diaria.html",
        {
            "cobros": cobros,
            "total": total,
            "efectivo": efectivo,
            "tarjeta": tarjeta,
            "transferencia": transferencia,
            "debito": debito,
            "gastos": gastos,
            "total_gastos": total_gastos,
            "saldo_neto": saldo_neto,
            "resumen_companias": resumen_companias,
            "turno_abierto": turno_abierto,
            "es_admin": request.user.is_superuser,
        },
    )

from django.http import HttpResponse

@login_required
def caja_pdf(request):
    hoy = date.today()

    # Buscar el último turno del usuario.
    # Puede estar abierto o cerrado.
    turno = TurnoCaja.objects.filter(
        usuario=request.user,
    ).order_by("-id").first()

    if turno:
        cobros = Cobro.objects.filter(
            turno=turno,
            anulado=False,
        ).select_related(
            "cliente",
            "poliza",
        )

        gastos = GastoCaja.objects.filter(
            turno=turno,
        )
    else:
        cobros = Cobro.objects.none()
        gastos = GastoCaja.objects.none()

    total = cobros.aggregate(
        Sum("importe")
    )["importe__sum"] or 0

    efectivo = cobros.filter(
        forma_pago="Efectivo"
    ).aggregate(
        Sum("importe")
    )["importe__sum"] or 0

    tarjeta = cobros.filter(
        forma_pago="Tarjeta"
    ).aggregate(
        Sum("importe")
    )["importe__sum"] or 0

    transferencia = cobros.filter(
        forma_pago="Transferencia"
    ).aggregate(
        Sum("importe")
    )["importe__sum"] or 0

    debito = cobros.filter(
        forma_pago="Debito"
    ).aggregate(
        Sum("importe")
    )["importe__sum"] or 0

    total_gastos = gastos.aggregate(
        Sum("importe")
    )["importe__sum"] or 0

    saldo_neto = total - total_gastos

    return render(
        request,
        "principal/caja_pdf.html",
        {
            "hoy": hoy,
            "turno": turno,
            "cobros": cobros,
            "total": total,
            "efectivo": efectivo,
            "tarjeta": tarjeta,
            "transferencia": transferencia,
            "debito": debito,
            "gastos": gastos,
            "total_gastos": total_gastos,
            "saldo_neto": saldo_neto,
        },
    )



@login_required
def abrir_turno(request):
    turno_abierto = TurnoCaja.objects.filter(
        usuario=request.user,
        abierto=True,
    ).first()

    if turno_abierto:
        messages.warning(
            request,
            "Ya tenés un turno abierto."
        )
        return redirect("caja_diaria")

    try:
      perfil = request.user.perfil_fortex
    except PerfilUsuario.DoesNotExist:
        messages.error(
          request,
          "No podés abrir caja porque tu usuario no tiene un perfil asignado."
        )
        return redirect("caja_diaria")

    if not perfil.activo or not perfil.sucursal:
        messages.error(
         request,
        "No podés abrir caja porque no tenés una sucursal activa asignada."
       )
        return redirect("caja_diaria")

    TurnoCaja.objects.create(
      usuario=request.user,
      sucursal=perfil.sucursal,
    )

    messages.success(
        request,
        "Turno abierto correctamente. La caja inicia en $0."
    )

    return redirect("caja_diaria")

@login_required
def cerrar_caja(request):
    hoy = date.today()

    turno_abierto = TurnoCaja.objects.filter(
        usuario=request.user,
        abierto=True,
    ).first()

    if not turno_abierto:
        messages.warning(
            request,
            "No tenés un turno abierto para cerrar."
        )
        return redirect("caja_diaria")

    cobros = Cobro.objects.filter(
        turno=turno_abierto,
        anulado=False,
    )

    total = cobros.aggregate(
        Sum("importe")
    )["importe__sum"] or 0

    efectivo = cobros.filter(
        forma_pago="Efectivo"
    ).aggregate(
        Sum("importe")
    )["importe__sum"] or 0

    tarjeta = cobros.filter(
        forma_pago="Tarjeta"
    ).aggregate(
        Sum("importe")
    )["importe__sum"] or 0

    transferencia = cobros.filter(
    forma_pago="Transferencia"
    ).aggregate(
    Sum("importe")
    )["importe__sum"] or 0

    debito = cobros.filter(
    forma_pago="Debito"
    ).aggregate(
    Sum("importe")
    )["importe__sum"] or 0

    gastos = GastoCaja.objects.filter(
        turno=turno_abierto,
    )

    total_gastos = gastos.aggregate(
        Sum("importe")
    )["importe__sum"] or 0

    saldo_neto = total - total_gastos

    CierreCaja.objects.create(
    fecha=hoy,
    turno=turno_abierto,
    total_cobrado=total,
    total_gastos=total_gastos,
    saldo_neto=saldo_neto,
    efectivo=efectivo,
    tarjeta=tarjeta,
    transferencia=transferencia,
    debito=debito,
    usuario=request.user,
)

    turno_abierto.total_cobrado = total
    turno_abierto.total_gastos = total_gastos
    turno_abierto.saldo_neto = saldo_neto

    turno_abierto.abierto = False
    turno_abierto.fecha_cierre = timezone.now()

    turno_abierto.save(
       update_fields=[
        "total_cobrado",
        "total_gastos",
        "saldo_neto",
        "abierto",
        "fecha_cierre",
    ]
)

    script_backup = Path(settings.BASE_DIR) / "pas_control" / "backup_postgres.ps1"

    subprocess.run(
    [
        "powershell.exe",
        "-ExecutionPolicy",
        "Bypass",
        "-File",
        str(script_backup),
    ],
    check=True,
    )

    messages.success(
        request,
        "Turno cerrado correctamente."
    )

    return redirect("caja_diaria")

@login_required
def historial_turnos(request):

    if not (
        request.user.is_superuser
        or request.user.groups.filter(name="Administrador").exists()
    ):
        messages.warning(
            request,
            "No tenés permiso para acceder al historial de turnos."
        )
        return redirect("inicio")

    turnos = TurnoCaja.objects.select_related("usuario").order_by(
        "-fecha_apertura"
    )

    return render(
        request,
        "principal/historial_turnos.html",
        {
            "turnos": turnos,
        }
    )

@login_required
def crear_gasto(request):
    turno_abierto = TurnoCaja.objects.filter(
        usuario=request.user,
        abierto=True,
    ).first()

    if request.method == "POST":

        if not turno_abierto:
            messages.warning(
                request,
                "Debés abrir un turno antes de registrar gastos."
            )
            return redirect("caja_diaria")

        concepto = request.POST.get("concepto", "").strip()
        importe = request.POST.get("importe", "").strip()
        observaciones = request.POST.get("observaciones", "").strip()

        if concepto and importe:
            GastoCaja.objects.create(
                concepto=concepto,
                importe=importe,
                observaciones=observaciones,
                usuario=request.user,
                turno=turno_abierto,
            )

            messages.success(
                request,
                "Gasto registrado correctamente."
            )

            return redirect("caja_diaria")

    return render(
        request,
        "principal/crear_gasto.html",
        {
            "turno_abierto": turno_abierto,
        }
    )

@login_required
def reporte_comisiones(request):

    fecha_desde = request.GET.get("fecha_desde", "")
    fecha_hasta = request.GET.get("fecha_hasta", "")


    queryset = Cobro.objects.select_related("cliente", "poliza")

    if fecha_desde:
       queryset = queryset.filter(fecha_pago__gte=fecha_desde)

    if fecha_hasta:
       queryset = queryset.filter(fecha_pago__lte=fecha_hasta)

    cobros = list(
    queryset.order_by("-fecha_pago", "-id")
    )

    for cobro in cobros:
       cobro.base_comision = cobro.importe - cobro.plus

    total_importe = sum(c.importe for c in cobros)
    total_plus = sum(c.plus for c in cobros)
    total_comision = sum(c.comision for c in cobros)

    return render(
        request,
        "principal/reporte_comisiones.html",
        {
            "cobros": cobros,
            "total_importe": total_importe,
            "total_plus": total_plus,
            "total_comision": total_comision,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
        },
    )

@login_required
def reporte_ingresos(request):

    fecha_desde = request.GET.get("fecha_desde", "")
    fecha_hasta = request.GET.get("fecha_hasta", "")
    forma_pago = request.GET.get("forma_pago", "")

    queryset = Cobro.objects.select_related(
        "cliente",
        "poliza",
    )

    # No contar cobros anulados
    queryset = queryset.filter(anulado=False)

    if fecha_desde:
        queryset = queryset.filter(
            fecha_pago__gte=fecha_desde
        )

    if fecha_hasta:
        queryset = queryset.filter(
            fecha_pago__lte=fecha_hasta
        )

    if forma_pago:
        queryset = queryset.filter(
            forma_pago=forma_pago
        )

    cobros = list(
        queryset.order_by("-fecha_pago", "-id")
    )

    total_ingresos = sum(
        c.importe for c in cobros
    )

    total_efectivo = sum(
        c.importe for c in cobros
        if c.forma_pago == "Efectivo"
    )

    total_transferencia = sum(
        c.importe for c in cobros
        if c.forma_pago == "Transferencia"
    )

    total_debito = sum(
    c.importe for c in cobros
    if c.forma_pago == "Débito"
    )

    total_tarjeta = sum(
    c.importe for c in cobros
    if c.forma_pago == "Tarjeta"
    )

    return render(
        request,
        "principal/reporte_ingresos.html",
        {
            "cobros": cobros,
            "total_ingresos": total_ingresos,
            "total_efectivo": total_efectivo,
            "total_transferencia": total_transferencia,
            "total_debito": total_debito,
            "total_tarjeta": total_tarjeta,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "forma_pago": forma_pago,
            "formas_pago": Cobro.FORMAS_PAGO,
        },
    )

@login_required
def reporte_aseguradoras(request):

    fecha_desde = request.GET.get("fecha_desde", "")
    fecha_hasta = request.GET.get("fecha_hasta", "")
    compania_filtro = request.GET.get("compania", "")

    polizas = Poliza.objects.all()

    if fecha_desde:
        polizas = polizas.filter(
            fecha_alta__gte=fecha_desde
        )

    if fecha_hasta:
        polizas = polizas.filter(
            fecha_alta__lte=fecha_hasta
        )

    if compania_filtro:
        polizas = polizas.filter(
            compania=compania_filtro
        )

    companias = (
        Poliza.objects
        .values_list("compania", flat=True)
        .exclude(compania="")
        .distinct()
        .order_by("compania")
    )

    reporte = []

    nombres_companias = (
        polizas
        .values_list("compania", flat=True)
        .exclude(compania="")
        .distinct()
        .order_by("compania")
    )

    for compania in nombres_companias:

        polizas_compania = polizas.filter(
            compania=compania
        )

        cobros_compania = Cobro.objects.filter(
            poliza__in=polizas_compania,
            anulado=False,
        )

        if fecha_desde:
            cobros_compania = cobros_compania.filter(
                fecha_pago__gte=fecha_desde
            )

        if fecha_hasta:
            cobros_compania = cobros_compania.filter(
                fecha_pago__lte=fecha_hasta
            )

        reporte.append({
            "compania": compania,

            "cantidad_polizas":
                polizas_compania.count(),

            "cantidad_clientes":
                polizas_compania
                .values("cliente")
                .distinct()
                .count(),

            "al_dia":
                polizas_compania
                .filter(estado="Al día")
                .count(),

            "pendientes":
                polizas_compania
                .filter(estado="Pendiente")
                .count(),

            "morosas":
                polizas_compania
                .filter(estado="Morosa")
                .count(),

            "vencidas":
                polizas_compania
                .filter(estado="Vencida")
                .count(),

            "anuladas":
                polizas_compania
                .filter(estado="Anulada")
                .count(),

            "total_cobrado":
                cobros_compania
                .aggregate(
                    total=Sum("importe")
                )["total"] or 0,
        })

    return render(
        request,
        "principal/reporte_aseguradoras.html",
        {
            "reporte": reporte,
            "companias": companias,
            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "compania_filtro": compania_filtro,
        },
    )

@login_required
def reporte_vehiculos(request):

    tipo = request.GET.get("tipo", "")
    uso = request.GET.get("uso", "")
    marca = request.GET.get("marca", "")
    anio = request.GET.get("anio", "")

    vehiculos = Vehiculo.objects.select_related(
        "cliente"
    ).all()

    # Filtros
    if tipo:
        vehiculos = vehiculos.filter(tipo=tipo)

    if uso:
        vehiculos = vehiculos.filter(uso=uso)

    if marca:
        vehiculos = vehiculos.filter(marca=marca)

    if anio:
        vehiculos = vehiculos.filter(anio=anio)

    # Resumen por tipo
    resumen_tipos = (
        vehiculos
        .values("tipo")
        .annotate(
            cantidad=Count("id"),
            clientes=Count("cliente", distinct=True),
        )
        .order_by("tipo")
    )

    total_vehiculos = vehiculos.count()

    total_clientes = vehiculos.values(
        "cliente"
    ).distinct().count()

    # Opciones para filtros
    marcas = (
        Vehiculo.objects
        .exclude(marca="")
        .values_list("marca", flat=True)
        .distinct()
        .order_by("marca")
    )

    anios = (
        Vehiculo.objects
        .exclude(anio__isnull=True)
        .values_list("anio", flat=True)
        .distinct()
        .order_by("-anio")
    )

    return render(
        request,
        "principal/reporte_vehiculos.html",
        {
            "vehiculos": vehiculos.order_by(
                "tipo",
                "marca",
                "modelo"
            ),
            "resumen_tipos": resumen_tipos,
            "total_vehiculos": total_vehiculos,
            "total_clientes": total_clientes,

            "tipos": Vehiculo.TIPO_CHOICES,
            "usos": Vehiculo.USO_CHOICES,
            "marcas": marcas,
            "anios": anios,

            "tipo_seleccionado": tipo,
            "uso_seleccionado": uso,
            "marca_seleccionada": marca,
            "anio_seleccionado": anio,
        },
    )

@login_required
def reporte_polizas(request):

    estado = request.GET.get("estado", "")
    compania = request.GET.get("compania", "")
    tipo_seguro = request.GET.get("tipo_seguro", "")

    polizas = Poliza.objects.select_related(
        "cliente",
        "vehiculo",
    ).all()

    # Filtros
    if estado:
        polizas = polizas.filter(estado=estado)

    if compania:
        polizas = polizas.filter(compania=compania)

    if tipo_seguro:
        polizas = polizas.filter(tipo_seguro=tipo_seguro)

    # Totales generales según los filtros aplicados
    total_polizas = polizas.count()

    total_clientes = polizas.values(
        "cliente"
    ).distinct().count()

    al_dia = polizas.filter(
        estado="Al día"
    ).count()

    pendientes = polizas.filter(
        estado="Pendiente"
    ).count()

    morosas = polizas.filter(
        estado="Morosa"
    ).count()

    vencidas = polizas.filter(
        estado="Vencida"
    ).count()

    anuladas = polizas.filter(
        estado="Anulada"
    ).count()

    # Compañías existentes para el selector
    companias = (
        Poliza.objects
        .exclude(compania="")
        .values_list("compania", flat=True)
        .distinct()
        .order_by("compania")
    )

    return render(
        request,
        "principal/reporte_polizas.html",
        {
            "polizas": polizas.order_by(
                "compania",
                "cliente__apellido",
                "cliente__nombre",
            ),

            "total_polizas": total_polizas,
            "total_clientes": total_clientes,
            "al_dia": al_dia,
            "pendientes": pendientes,
            "morosas": morosas,
            "vencidas": vencidas,
            "anuladas": anuladas,

            "estados": Poliza.ESTADOS,
            "tipos_seguro": Poliza.TIPOS_SEGURO,
            "companias": companias,

            "estado_seleccionado": estado,
            "compania_seleccionada": compania,
            "tipo_seguro_seleccionado": tipo_seguro,
        },
    )

@login_required
def reporte_clientes(request):

    buscar = request.GET.get("buscar", "").strip()
    estado = request.GET.get("estado", "")
    provincia = request.GET.get("provincia", "")
    localidad = request.GET.get("localidad", "")

    clientes = Cliente.objects.all()

    # Búsqueda por nombre, apellido o DNI
    if buscar:
        clientes = clientes.filter(
            Q(nombre__icontains=buscar)
            | Q(apellido__icontains=buscar)
            | Q(dni__icontains=buscar)
        )

    # Filtro por estado
    if estado:
        clientes = clientes.filter(
            estado=estado
        )

    # Filtro por provincia
    if provincia:
        clientes = clientes.filter(
            provincia=provincia
        )

    # Filtro por localidad
    if localidad:
        clientes = clientes.filter(
            localidad=localidad
        )

    # Totales según filtros aplicados
    total_clientes = clientes.count()

    activos = clientes.filter(
        estado="Activo"
    ).count()

    inactivos = clientes.filter(
        estado="Inactivo"
    ).count()

    prospectos = clientes.filter(
        estado="Prospecto"
    ).count()

    # Clientes que poseen al menos una póliza
    clientes_con_poliza = clientes.filter(
        poliza__isnull=False
    ).distinct()

    total_con_poliza = clientes_con_poliza.count()

    # Clientes sin ninguna póliza
    clientes_sin_poliza = clientes.filter(
        poliza__isnull=True
    )

    total_sin_poliza = clientes_sin_poliza.count()

    # Valores disponibles para filtros
    provincias = (
        Cliente.objects
        .exclude(provincia="")
        .values_list("provincia", flat=True)
        .distinct()
        .order_by("provincia")
    )

    localidades = (
        Cliente.objects
        .exclude(localidad="")
        .values_list("localidad", flat=True)
        .distinct()
        .order_by("localidad")
    )

    # Datos para el detalle
    clientes = (
        clientes
        .annotate(
            cantidad_polizas=Count(
                "poliza",
                distinct=True
            ),
            cantidad_vehiculos=Count(
                "vehiculo",
                distinct=True
            ),
        )
        .order_by(
            "apellido",
            "nombre",
        )
    )

    return render(
        request,
        "principal/reporte_clientes.html",
        {
            "clientes": clientes,

            "total_clientes": total_clientes,
            "activos": activos,
            "inactivos": inactivos,
            "prospectos": prospectos,
            "total_con_poliza": total_con_poliza,
            "total_sin_poliza": total_sin_poliza,

            "estados": [
                ("Activo", "Activo"),
                ("Inactivo", "Inactivo"),
                ("Prospecto", "Prospecto"),
            ],

            "provincias": provincias,
            "localidades": localidades,

            "buscar": buscar,
            "estado_seleccionado": estado,
            "provincia_seleccionada": provincia,
            "localidad_seleccionada": localidad,
        },
    )

@login_required
def reporte_produccion(request):

    fecha_desde = request.GET.get("fecha_desde", "")
    fecha_hasta = request.GET.get("fecha_hasta", "")
    compania = request.GET.get("compania", "")
    tipo_seguro = request.GET.get("tipo_seguro", "")

    polizas = Poliza.objects.select_related(
        "cliente",
        "vehiculo",
    )

    # Filtros
    if fecha_desde:
        polizas = polizas.filter(
            fecha_alta__gte=fecha_desde
        )

    if fecha_hasta:
        polizas = polizas.filter(
            fecha_alta__lte=fecha_hasta
        )

    if compania:
        polizas = polizas.filter(
            compania=compania
        )

    if tipo_seguro:
        polizas = polizas.filter(
            tipo_seguro=tipo_seguro
        )

    # Totales generales
    total_altas = polizas.count()

    total_clientes = (
        polizas
        .values("cliente_id")
        .distinct()
        .count()
    )

    total_aseguradoras = (
        polizas
        .exclude(compania="")
        .values("compania")
        .distinct()
        .count()
    )

    total_vehiculos = (
        polizas
        .exclude(vehiculo__isnull=True)
        .values("vehiculo_id")
        .distinct()
        .count()
    )

    # Resumen por aseguradora
    resumen_aseguradoras = (
        polizas
        .values("compania")
        .annotate(
            cantidad=Count("id"),
            clientes=Count(
                "cliente_id",
                distinct=True
            ),
        )
        .order_by("-cantidad", "compania")
    )

    # Opciones para filtros
    companias = (
        Poliza.objects
        .exclude(compania="")
        .values_list("compania", flat=True)
        .distinct()
        .order_by("compania")
    )

    # Detalle
    polizas = polizas.order_by(
        "-fecha_alta",
        "-id",
    )

    return render(
        request,
        "principal/reporte_produccion.html",
        {
            "polizas": polizas,

            "total_altas": total_altas,
            "total_clientes": total_clientes,
            "total_aseguradoras": total_aseguradoras,
            "total_vehiculos": total_vehiculos,

            "resumen_aseguradoras": resumen_aseguradoras,

            "companias": companias,
            "tipos_seguro": Poliza.TIPOS_SEGURO,

            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "compania_seleccionada": compania,
            "tipo_seguro_seleccionado": tipo_seguro,
        },
    )

@login_required
def reporte_cobranza(request):

    fecha_desde = request.GET.get("fecha_desde", "")
    fecha_hasta = request.GET.get("fecha_hasta", "")
    compania = request.GET.get("compania", "")
    estado = request.GET.get("estado", "")
    forma_pago = request.GET.get("forma_pago", "")

    # ==========================================
    # COBROS VÁLIDOS
    # ==========================================

    cobros = Cobro.objects.select_related(
        "cliente",
        "poliza",
        "poliza__vehiculo",
    ).filter(
        anulado=False
    )

    if fecha_desde:
        cobros = cobros.filter(
            fecha_pago__gte=fecha_desde
        )

    if fecha_hasta:
        cobros = cobros.filter(
            fecha_pago__lte=fecha_hasta
        )

    if compania:
        cobros = cobros.filter(
            poliza__compania=compania
        )

    if estado:
        cobros = cobros.filter(
            poliza__estado=estado
        )

    if forma_pago:
        cobros = cobros.filter(
            forma_pago=forma_pago
        )

    cobros = cobros.order_by(
        "-fecha_pago",
        "-id"
    )

    # ==========================================
    # TOTALES DE COBRANZA
    # ==========================================

    total_cobrado = sum(
        c.importe for c in cobros
    )

    total_operaciones = cobros.count()

    clientes_cobrados = cobros.values(
        "cliente_id"
    ).distinct().count()

    # ==========================================
    # CARTERA
    # ==========================================

    polizas = Poliza.objects.select_related(
        "cliente",
        "vehiculo",
    )

    if compania:
        polizas = polizas.filter(
            compania=compania
        )

    if estado:
        polizas = polizas.filter(
            estado=estado
        )

    total_morosas = polizas.filter(
        estado="Morosa"
    ).count()

    total_vencidas = polizas.filter(
        estado="Vencida"
    ).count()

    total_pendientes = polizas.filter(
        estado="Pendiente"
    ).count()

    # Pólizas que requieren atención
    cartera_deuda = polizas.filter(
        estado__in=[
            "Pendiente",
            "Morosa",
            "Vencida",
        ]
    ).order_by(
        "fecha_vencimiento",
        "cliente__apellido",
        "cliente__nombre",
    )

    clientes_con_deuda = cartera_deuda.values(
        "cliente_id"
    ).distinct().count()

    # ==========================================
    # ÚLTIMO COBRO DE CADA PÓLIZA CON DEUDA
    # ==========================================

    detalle_deuda = []

    for poliza in cartera_deuda:

        ultimo_cobro = Cobro.objects.filter(
            poliza=poliza,
            anulado=False,
        ).order_by(
            "-fecha_pago",
            "-id"
        ).first()

        detalle_deuda.append({
            "poliza": poliza,
            "ultimo_cobro": ultimo_cobro,
        })

    # ==========================================
    # OPCIONES PARA FILTROS
    # ==========================================

    companias = Poliza.objects.exclude(
        compania=""
    ).values_list(
        "compania",
        flat=True
    ).distinct().order_by(
        "compania"
    )

    return render(
        request,
        "principal/reporte_cobranza.html",
        {
            "cobros": cobros,

            "total_cobrado": total_cobrado,
            "total_operaciones": total_operaciones,
            "clientes_cobrados": clientes_cobrados,

            "total_pendientes": total_pendientes,
            "total_morosas": total_morosas,
            "total_vencidas": total_vencidas,
            "clientes_con_deuda": clientes_con_deuda,

            "detalle_deuda": detalle_deuda,

            "companias": companias,
            "estados": Poliza.ESTADOS,
            "formas_pago": Cobro.FORMAS_PAGO,

            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "compania_seleccionada": compania,
            "estado_seleccionado": estado,
            "forma_pago_seleccionada": forma_pago,
        },
    )

@login_required
def reporte_plus(request):

    fecha_desde = request.GET.get("fecha_desde", "")
    fecha_hasta = request.GET.get("fecha_hasta", "")
    compania = request.GET.get("compania", "")
    operador = request.GET.get("operador", "")
    sucursal = request.GET.get("sucursal", "")
    estado = request.GET.get("estado", "")

    # Solo cobros que realmente tengan Plus
    cobros = Cobro.objects.select_related(
        "cliente",
        "poliza",
        "poliza__vehiculo",
        "registrado_por",
        "turno",
        "turno__sucursal",
        "anulado_por",
    ).filter(
        plus__gt=0
    )

    # ==========================================
    # FILTROS
    # ==========================================

    if fecha_desde:
        cobros = cobros.filter(
            fecha_pago__gte=fecha_desde
        )

    if fecha_hasta:
        cobros = cobros.filter(
            fecha_pago__lte=fecha_hasta
        )

    if compania:
        cobros = cobros.filter(
            poliza__compania=compania
        )

    if operador:
        cobros = cobros.filter(
            registrado_por_id=operador
        )

    if sucursal:
        cobros = cobros.filter(
            turno__sucursal_id=sucursal
        )

    if estado == "valido":
        cobros = cobros.filter(
            anulado=False
        )

    elif estado == "anulado":
        cobros = cobros.filter(
            anulado=True
        )

    # ==========================================
    # TOTALES DE AUDITORÍA
    # ==========================================

    total_plus_valido = cobros.filter(
        anulado=False
    ).aggregate(
        total=Sum("plus")
    )["total"] or 0

    total_plus_anulado = cobros.filter(
        anulado=True
    ).aggregate(
        total=Sum("plus")
    )["total"] or 0

    operaciones_validas = cobros.filter(
        anulado=False
    ).count()

    operaciones_anuladas = cobros.filter(
        anulado=True
    ).count()

    if operaciones_validas:
        promedio_plus = (
            total_plus_valido / operaciones_validas
        )
    else:
        promedio_plus = 0

    # ==========================================
    # OPCIONES DE FILTROS
    # ==========================================

    companias = (
        Poliza.objects
        .exclude(compania="")
        .values_list("compania", flat=True)
        .distinct()
        .order_by("compania")
    )

    operadores = (
        Cobro.objects
        .filter(
            plus__gt=0,
            registrado_por__isnull=False,
        )
        .values(
            "registrado_por_id",
            "registrado_por__username",
        )
        .distinct()
        .order_by("registrado_por__username")
    )

    sucursales = (
        Sucursal.objects
        .filter(activa=True)
        .order_by("provincia", "nombre")
    )

    # ==========================================
    # DETALLE
    # ==========================================

    cobros = cobros.order_by(
        "-fecha_pago",
        "-fecha_registro",
        "-id",
    )

    return render(
        request,
        "principal/reporte_plus.html",
        {
            "cobros": cobros,

            "total_plus_valido": total_plus_valido,
            "total_plus_anulado": total_plus_anulado,
            "operaciones_validas": operaciones_validas,
            "operaciones_anuladas": operaciones_anuladas,
            "promedio_plus": promedio_plus,

            "companias": companias,
            "operadores": operadores,
            "sucursales": sucursales,

            "fecha_desde": fecha_desde,
            "fecha_hasta": fecha_hasta,
            "compania_seleccionada": compania,
            "operador_seleccionado": operador,
            "sucursal_seleccionada": sucursal,
            "estado_seleccionado": estado,
        },
    )

@login_required
def reporte_caja(request):
    # Reportes exclusivos para administrador
    if not request.user.is_staff:
        return redirect("inicio")

    cierres = CierreCaja.objects.select_related(
        "usuario",
        "turno",
        "turno__sucursal",
    ).order_by("-fecha_hora_cierre")

    fecha_desde = request.GET.get("fecha_desde", "")
    fecha_hasta = request.GET.get("fecha_hasta", "")
    operador = request.GET.get("operador", "")
    sucursal = request.GET.get("sucursal", "")

    if fecha_desde:
        cierres = cierres.filter(fecha__gte=fecha_desde)

    if fecha_hasta:
        cierres = cierres.filter(fecha__lte=fecha_hasta)

    if operador:
        cierres = cierres.filter(usuario_id=operador)

    if sucursal:
        cierres = cierres.filter(turno__sucursal_id=sucursal)

    resumen = cierres.aggregate(
        total_cobrado=Sum("total_cobrado"),
        total_gastos=Sum("total_gastos"),
        saldo_neto=Sum("saldo_neto"),
        efectivo=Sum("efectivo"),
        tarjeta=Sum("tarjeta"),
        transferencia=Sum("transferencia"),
        cbu=Sum("cbu"),
    )

    operadores = (
        CierreCaja.objects
        .exclude(usuario=None)
        .values("usuario_id", "usuario__username")
        .distinct()
        .order_by("usuario__username")
    )

    sucursales = (
        Sucursal.objects
        .filter(activa=True)
        .order_by("nombre")
    )

    context = {
        "cierres": cierres,
        "resumen": resumen,
        "operadores": operadores,
        "sucursales": sucursales,
        "fecha_desde": fecha_desde,
        "fecha_hasta": fecha_hasta,
        "operador_seleccionado": operador,
        "sucursal_seleccionada": sucursal,
    }

    return render(
        request,
        "principal/reporte_caja.html",
        context,
    )

@login_required
def menu_reportes(request):
    if not request.user.is_staff:
        return redirect("inicio")

    return render(
        request,
        "principal/menu_reportes.html"
    )

@login_required
def agenda_telefonos(request):
    buscar = request.GET.get("buscar", "").strip()

    clientes = Cliente.objects.all().order_by("apellido", "nombre")

    if buscar:
        clientes = clientes.filter(
            Q(apellido__icontains=buscar) |
            Q(nombre__icontains=buscar) |
            Q(dni__icontains=buscar) |
            Q(whatsapp__icontains=buscar)
        )

    contexto = {
        "clientes": clientes,
        "buscar": buscar,
    }

    return render(
        request,
        "principal/agenda_telefonos.html",
        contexto
    )

from pathlib import Path
from django.conf import settings
from django.http import FileResponse


def service_worker(request):
    ruta = Path(settings.BASE_DIR) / "principal" / "static" / "principal" / "service-worker.js"

    response = FileResponse(
        open(ruta, "rb"),
        content_type="application/javascript"
    )
    response["Service-Worker-Allowed"] = "/"
    return response