"""Consulta central de nombres de aseguradoras sin alterar pólizas históricas.

Transitorio: los nombres existentes se conservan. La importación oficial SSN
requiere una fuente validada y una migración posterior a un catálogo persistente.
"""
from polizas.models import Poliza


def nombres_aseguradoras(*, incluir=()):
    """Lista única, deduplicada por comparación insensible a mayúsculas."""
    nombres = Poliza.objects.exclude(compania__isnull=True).exclude(
        compania=""
    ).values_list("compania", flat=True).distinct()
    canonicos = {}
    for nombre in (*nombres, *incluir):
        nombre = str(nombre or "").strip()
        if nombre:
            canonicos.setdefault(nombre.casefold(), nombre)
    return sorted(canonicos.values(), key=str.casefold)
