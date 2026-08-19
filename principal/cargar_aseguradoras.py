import csv
from pathlib import Path

from principal.models import Aseguradora


def cargar():
    archivo = Path(__file__).resolve().parent.parent / "entidades-activas.csv"

    creadas = 0
    actualizadas = 0
    reaseguradoras_omitidas = 0

    with open(archivo, "r", encoding="utf-8-sig", newline="") as csvfile:
        lector = csv.DictReader(csvfile)

        for fila in lector:
            actividad = fila["cia_actividad_principal"].strip()

            # No cargamos reaseguradoras
            if actividad in ("Reaseg. Admitida", "Reaseg. Local"):
                reaseguradoras_omitidas += 1
                continue

            codigo = fila["cia_id"].strip()
            nombre = fila["cia_denominacion"].strip()

            aseguradora, creada = Aseguradora.objects.update_or_create(
                codigo_ssn=codigo,
                defaults={
                    "nombre": nombre,
                    "activa": True,
                },
            )

            if creada:
                creadas += 1
            else:
                actualizadas += 1

    print("--------------------------------")
    print("IMPORTACION SSN FINALIZADA")
    print(f"Nuevas: {creadas}")
    print(f"Actualizadas: {actualizadas}")
    print(f"Reaseguradoras omitidas: {reaseguradoras_omitidas}")
    print("--------------------------------")