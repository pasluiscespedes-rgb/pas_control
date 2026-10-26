"""Contratos por ramo: sin acceso a base de datos ni dependencias cruzadas.

Registro incremental: los ramos aún no implementados no se habilitan por
estar listados aquí. Mantener los valores históricos de tipo_seguro.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ConfiguracionRamo:
    codigo: str
    requiere_vehiculo: bool
    campos_propios_obligatorios: tuple[str, ...] = ()


RAMOS = {
    "automotor": ConfiguracionRamo("Automotor", True),
    "moto": ConfiguracionRamo("Moto", True),
    "accidentes personales": ConfiguracionRamo(
        "Accidentes Personales", False,
        ("asegurado_nombre", "asegurado_documento", "actividad_declarada", "cobertura"),
    ),
    "hogar": ConfiguracionRamo("Hogar", False),
    "comercio": ConfiguracionRamo("Comercio", False),
    "agro": ConfiguracionRamo("Agro", False),
    "caución": ConfiguracionRamo("Caución", False),
    "otro": ConfiguracionRamo("Otro", False),
}


def configuracion_ramo(tipo_seguro: str) -> Optional[ConfiguracionRamo]:
    return RAMOS.get((tipo_seguro or "").strip().casefold())


def errores_ap(poliza) -> dict[str, str]:
    """Validación exclusiva de AP; no cambia la validación de otros ramos."""
    if (poliza.tipo_seguro or "").strip().casefold() != "accidentes personales":
        return {}
    configuracion = RAMOS["accidentes personales"]
    errores = {}
    for campo in configuracion.campos_propios_obligatorios:
        if not str(getattr(poliza, campo, "") or "").strip():
            errores[campo] = "Este dato es obligatorio para Accidentes Personales."
    if poliza.vehiculo_id:
        errores["vehiculo"] = "Una póliza AP no debe tener vehículo asociado."
    return errores
