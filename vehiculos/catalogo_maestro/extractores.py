"""Extrae únicamente marca, modelo, clase y año; descarta identidad personal."""
import csv
import io
from dataclasses import dataclass
from .normalizacion import normalizar, tipo_registral, anio_valido, TIPOS


MARCAS = ("marca", "automotor_marca_descripcion", "motovehiculo_marca_descripcion", "make", "make_name")
MODELOS = ("modelo", "automotor_modelo_descripcion", "motovehiculo_modelo_descripcion", "model", "model_name")
CLASES = ("tipo_dnrpa", "tipo_sistema", "automotor_tipo_descripcion", "motovehiculo_tipo_descripcion", "vehicle_type", "tipo")
ANIOS = ("automotor_anio_modelo", "motovehiculo_anio_modelo", "modelo_anio", "model_year", "anio_modelo")


@dataclass(frozen=True)
class Registro:
    marca: str
    modelo: str
    tipo: str
    anio: int | None


def _columna(fila, opciones):
    # No tocar otros campos; pueden incluir datos personales de titulares.
    for nombre in opciones:
        if nombre in fila and fila[nombre] is not None:
            return str(fila[nombre]).strip()
    return ""


def extraer(fila, tipo_por_defecto=None):
    fila = {normalizar(k).lower().replace(" ", "_"): v for k, v in fila.items() if k}
    marca = normalizar(_columna(fila, MARCAS))
    modelo = normalizar(_columna(fila, MODELOS))
    if not marca or not modelo or len(marca) > 100 or len(modelo) > 100:
        return None
    clase = _columna(fila, CLASES)
    tipo = tipo_registral(clase)
    if not tipo and tipo_por_defecto in TIPOS and not clase:
        tipo = tipo_por_defecto
    # Si la fuente trae una clase desconocida, no falsear el tipo.
    if not tipo:
        return None
    return Registro(marca, modelo, tipo, anio_valido(_columna(fila, ANIOS)))


def registros_csv(archivo, tipo_por_defecto=None):
    """CSV o stream texto. Soporta , ; y BOM; sin descargar ni almacenar filas crudas."""
    muestra = archivo.read(4096)
    archivo.seek(0)
    try:
        delimitador = csv.Sniffer().sniff(muestra, delimiters=",;").delimiter
    except csv.Error:
        delimitador = ","
    lector = csv.DictReader(archivo, delimiter=delimitador)
    cabeceras = {normalizar(x).lower().replace(" ", "_") for x in (lector.fieldnames or []) if x}
    if not any(x in cabeceras for x in MARCAS) or not any(x in cabeceras for x in MODELOS):
        raise ValueError("El archivo no contiene columnas de marca y modelo reconocibles")
    for fila in lector:
        yield extraer(fila, tipo_por_defecto=tipo_por_defecto)
