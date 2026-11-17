"""Consulta central de aseguradoras de FORTEX.

Fuente principal: catálogo persistente existente (principal.Aseguradora).
Se preservan denominaciones de pólizas históricas para evitar pérdida de datos.
"""
from principal.models import Aseguradora
from polizas.models import Poliza


def nombres_aseguradoras(*, incluir=()):
    canonicos = {}
    for nombre in Aseguradora.objects.filter(activa=True).values_list("nombre", flat=True):
        nombre = str(nombre or "").strip()
        if nombre:
            canonicos.setdefault(nombre.casefold(), nombre)
    for nombre in Poliza.objects.exclude(compania__isnull=True).exclude(
        compania=""
    ).values_list("compania", flat=True).distinct():
        nombre = str(nombre or "").strip()
        if nombre:
            canonicos.setdefault(nombre.casefold(), nombre)
    for nombre in incluir:
        nombre = str(nombre or "").strip()
        if nombre:
            canonicos.setdefault(nombre.casefold(), nombre)
    return sorted(canonicos.values(), key=str.casefold)
