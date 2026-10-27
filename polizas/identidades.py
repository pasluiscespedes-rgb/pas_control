"""Reglas de identidad de tomadores y asegurados para futuros módulos.

Sin tablas ni migraciones: contrato de dominio puro para implementar
la nómina de AP, Vida y Capitalización sin acoplarla a vehículos.
"""
from dataclasses import dataclass
from enum import Enum


class TipoTomador(str, Enum):
    PERSONA_FISICA = "PERSONA_FISICA"
    PERSONA_JURIDICA = "PERSONA_JURIDICA"


class EstadoMovimiento(str, Enum):
    PENDIENTE = "PENDIENTE"
    ENVIADO = "ENVIADO"
    CONFIRMADO = "CONFIRMADO"
    RECHAZADO = "RECHAZADO"


@dataclass(frozen=True)
class IdentidadTomador:
    tipo: TipoTomador
    nombre: str = ""
    apellido: str = ""
    dni: str = ""
    razon_social: str = ""
    cuit: str = ""
    nombre_fantasia: str = ""

    def validar(self) -> dict[str, str]:
        errores = {}
        if self.tipo == TipoTomador.PERSONA_FISICA:
            for campo in ("nombre", "apellido", "dni"):
                if not getattr(self, campo).strip():
                    errores[campo] = "Dato obligatorio de persona física."
        elif self.tipo == TipoTomador.PERSONA_JURIDICA:
            if not self.razon_social.strip():
                errores["razon_social"] = "La razón social legal es obligatoria."
            cuit = "".join(c for c in self.cuit if c.isdigit())
            if len(cuit) != 11 or not validar_cuit(cuit):
                errores["cuit"] = "CUIT inválido."
        else:
            errores["tipo"] = "Tipo de tomador desconocido."
        return errores


def validar_cuit(cuit: str) -> bool:
    """Valida longitud y dígito verificador, no existencia ante ARCA."""
    if len(cuit) != 11 or not cuit.isdigit():
        return False
    pesos = (5, 4, 3, 2, 7, 6, 5, 4, 3, 2)
    resto = sum(int(n) * p for n, p in zip(cuit[:10], pesos)) % 11
    verificador = 11 - resto
    if verificador == 11:
        verificador = 0
    elif verificador == 10:
        verificador = 9
    return int(cuit[-1]) == verificador


def requiere_confirmacion_aseguradora(estado: EstadoMovimiento) -> bool:
    """Un movimiento pendiente/enviado no debe tratarse como confirmado."""
    return estado != EstadoMovimiento.CONFIRMADO
