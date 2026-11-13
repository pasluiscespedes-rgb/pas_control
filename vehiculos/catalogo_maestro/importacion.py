"""Importación explícita y atómica de catálogos CSV, sin datos personales."""
from collections import defaultdict
from django.db import transaction
from .extractores import registros_csv
from vehiculos.models import MarcaVehiculo, ModeloVehiculo, ModeloAnio, FuenteCatalogoVehiculo, RegistroFuenteModelo


def resumir_archivo(archivo, tipo_por_defecto=None):
    entidades = defaultdict(set)
    leidas = rechazadas = 0
    for registro in registros_csv(archivo, tipo_por_defecto):
        leidas += 1
        if registro is None:
            rechazadas += 1
            continue
        entidades[(registro.marca, registro.modelo, registro.tipo)].add(registro.anio)
    return entidades, {"filas": leidas, "rechazadas": rechazadas,
                       "modelos_distintos": len(entidades), "marcas_distintas": len({k[0] for k in entidades})}


def importar_archivo(archivo, codigo_fuente, titulo_fuente, url_fuente='', licencia='',
                     tipo_por_defecto=None, dry_run=True):
    if not codigo_fuente or len(codigo_fuente) > 70:
        raise ValueError('Código de fuente inválido')
    entidades, informe = resumir_archivo(archivo, tipo_por_defecto)
    informe['modo'] = 'simulacion' if dry_run else 'aplicado'
    informe['creadas_marcas'] = informe['creados_modelos'] = informe['nuevos_anios'] = 0
    if dry_run:
        return informe
    # Sin modelos válidos: fallo cerrado, no generar una fuente vacía.
    if not entidades:
        raise ValueError('No hay registros vehiculares válidos')
    with transaction.atomic():
        fuente, creada = FuenteCatalogoVehiculo.objects.get_or_create(
            codigo=codigo_fuente, defaults={"titulo":titulo_fuente, "url":url_fuente, "licencia":licencia})
        if not creada and (fuente.url != url_fuente or fuente.licencia != licencia):
            raise ValueError('La fuente existente tiene otra procedencia/licencia')
        marcas = {}
        for marca_nombre in sorted({k[0] for k in entidades}):
            marca = MarcaVehiculo.objects.filter(nombre__iexact=marca_nombre).order_by('id').first()
            nueva = False
            if marca is None:
                marca, nueva = MarcaVehiculo.objects.get_or_create(nombre=marca_nombre, defaults={"activa": True})
            marcas[marca_nombre] = marca
            informe['creadas_marcas'] += bool(nueva)
        for (marca, modelo, tipo), anios in sorted(entidades.items()):
            entidad = ModeloVehiculo.objects.filter(
                marca=marcas[marca], nombre__iexact=modelo, tipo=tipo).order_by('id').first()
            nueva = False
            if entidad is None:
                entidad, nueva = ModeloVehiculo.objects.get_or_create(
                    marca=marcas[marca], nombre=modelo, tipo=tipo, defaults={"activa": True})
            informe['creados_modelos'] += bool(nueva)
            RegistroFuenteModelo.objects.get_or_create(fuente=fuente, modelo=entidad)
            # Solo dato año-modelo explícito; nunca inferir desde la fecha de inscripción.
            validos = sorted(a for a in anios if a is not None)
            for anio in validos:
                _, nuevo_anio = ModeloAnio.objects.get_or_create(modelo=entidad, anio=anio)
                informe['nuevos_anios'] += bool(nuevo_anio)
            if validos:
                primero = min(x for x in (entidad.anio_desde, min(validos)) if x is not None)
                ultimo = max(x for x in (entidad.anio_hasta, max(validos)) if x is not None)
                if (primero, ultimo) != (entidad.anio_desde, entidad.anio_hasta):
                    entidad.anio_desde, entidad.anio_hasta = primero, ultimo
                    entidad.save(update_fields=['anio_desde', 'anio_hasta'])
    return informe
