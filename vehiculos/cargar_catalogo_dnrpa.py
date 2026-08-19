import csv
from collections import defaultdict
from pathlib import Path

from django.db import transaction

from vehiculos.models import MarcaVehiculo, ModeloVehiculo


TIPOS_VALIDOS = {
    "Auto",
    "Moto",
    "Camioneta",
    "Furgón",
    "Camión",
    "Acoplado",
    "Trailer",
    "Maquinaria",
}


def limpiar_texto(valor):
    if valor is None:
        return ""

    return " ".join(
        str(valor).strip().upper().split()
    )


def guardar_modelo(tipo, marca_nombre, modelo_nombre):
    tipo = limpiar_texto(tipo).title()
    marca_nombre = limpiar_texto(marca_nombre)
    modelo_nombre = limpiar_texto(modelo_nombre)

    if not tipo or not marca_nombre or not modelo_nombre:
        return False

    marca, _ = MarcaVehiculo.objects.get_or_create(
        nombre=marca_nombre
    )

    _, creado = ModeloVehiculo.objects.get_or_create(
        marca=marca,
        nombre=modelo_nombre,
        tipo=tipo,
    )

    return creado

def importar_csv(ruta, tipo):
    print(f"Leyendo archivo: {ruta}")

    creados = 0
    existentes = 0
    ignorados = 0

    with open(ruta, "r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)

        for fila in lector:
            marca = fila.get("automotor_marca_descripcion")
            modelo = fila.get("automotor_modelo_descripcion")

            marca = limpiar_texto(marca)
            modelo = limpiar_texto(modelo)

            if not marca or not modelo:
                ignorados += 1
                continue

            creado = guardar_modelo(
                tipo=tipo,
                marca_nombre=marca,
                modelo_nombre=modelo,
            )

            if creado:
                creados += 1
            else:
                existentes += 1

    print(f"Nuevos: {creados}")
    print(f"Ya existentes: {existentes}")
    print(f"Ignorados: {ignorados}")

def importar_catalogos():
    archivos = [
    (
        "Auto",
        f"vehiculos/datos_dnrpa/dnrpa-inscripciones-iniciales-autos-2025{mes:02d}.csv"
    )
    for mes in range(1, 13)
]
    if not archivos:
        print("No hay archivos configurados para importar.")
        return

    for tipo, ruta in archivos:
        print(f"\nImportando {tipo}...")
        importar_csv(ruta, tipo)


if __name__ == "__main__":
    importar_catalogos()