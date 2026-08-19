import json
import urllib.parse
import urllib.request

from .models import MarcaVehiculo, ModeloVehiculo, ModeloAnio


VPIC_BASE_URL = "https://vpic.nhtsa.dot.gov/api/vehicles"

def obtener_make_id(marca):
    url = (
        f"{VPIC_BASE_URL}/GetAllMakes"
        f"?format=json"
    )

    peticion = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    with urllib.request.urlopen(peticion, timeout=30) as respuesta:
        datos = json.loads(
            respuesta.read().decode("utf-8")
        )

    for item in datos.get("Results", []):
        if item.get("Make_Name", "").strip().upper() == marca.strip().upper():
            return item.get("Make_ID")

    return None


def obtener_modelos_por_marca_y_anio(marca, anio):
    marca_codificada = urllib.parse.quote(marca)

    make_id = obtener_make_id(marca)

    if make_id is None:
       return []

    url = (
      f"{VPIC_BASE_URL}/GetModelsForMakeIdYear/"
      f"makeId/{make_id}/modelyear/{anio}"
      f"?format=json"
    )

    print("URL ENVIADA:", url)

    peticion = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0"},
    )

    with urllib.request.urlopen(
        peticion,
        timeout=30,
    ) as respuesta:
        datos = json.loads(
            respuesta.read().decode("utf-8")
        )

    print("MARCA RECIBIDA:", repr(marca))    

    resultados = datos.get("Results", [])

    print("CANTIDAD API:", len(resultados))
    print("PRIMEROS 5:", resultados[:5])

    modelos_unicos = {}

    for item in resultados:
     if item.get("Make_Name", "").strip().upper() != marca.strip().upper():
        continue

        nombre_modelo = item.get("Model_Name", "").strip()

        if nombre_modelo:
            modelos_unicos[nombre_modelo.upper()] = item

    resultados = list(modelos_unicos.values())

    
    for item in resultados:
      print(
        "MARCA:", repr(item.get("Make_Name")),
        "| MODELO:", repr(item.get("Model_Name"))
    )

    return resultados