"""Reglas puras, sin dependencias ni llamadas a servicios externos."""
import re
import unicodedata
from difflib import SequenceMatcher


def normalizar(valor):
    if valor is None:
        return ""
    s = unicodedata.normalize("NFKD", str(valor).casefold())
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " ".join(s.upper().split())[:160]


TIPOS = ("Auto", "Moto", "Camioneta", "Furgón", "Camión", "Acoplado", "Tráiler")


def tipo_registral(texto):
    """Clasifica solo denominaciones reconocibles: nunca inventa 'Auto'."""
    v = normalizar(texto)
    if not v:
        return None
    if v in {normalizar(t) for t in TIPOS}:
        return next(t for t in TIPOS if normalizar(t) == v)
    reglas = (
        ("Acoplado", ("SEMIRREMOLQUE", "SEMI REMOLQUE", "ACOPLADO")),
        ("Tráiler", ("TRAILER", "TRAILERS", "CASA RODANTE REMOLCABLE", "REMOLQUE")),
        ("Moto", ("MOTOCICLETA", "MOTOVEHICULO", "CICLOMOTOR", "CUATRICICLO", "MOTONETA", "SCOOTER")),
        ("Camioneta", ("CAMIONETA", "PICKUP", "PICK UP", "UTILITARIO")),
        ("Camión", ("CAMION", "TRACTOR DE CARRETERA", "TRACTOCAMION")),
        ("Furgón", ("FURGON", "FURGONETA", "VAN CERRADA")),
        ("Auto", ("AUTOMOVIL", "SEDAN", "HATCHBACK", "COUPE", "RURAL", "FAMILIAR", "SUV")),
    )
    for tipo, palabras in reglas:
        if any(p in v for p in palabras):
            return tipo
    return None


def similitud(a, b):
    return round(SequenceMatcher(None, normalizar(a), normalizar(b)).ratio(), 4)


def anio_valido(valor):
    if valor in (None, ""):
        return None
    try:
        anio = int(valor)
    except (ValueError, TypeError):
        return None
    return anio if 1886 <= anio <= 2100 else None
