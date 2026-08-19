import urllib.request
import json
import time
import urllib.error
import csv
from pathlib import Path

from .models import MarcaVehiculo, ModeloVehiculo


URL_MARCAS = "https://argautos.com/api/v1/brands"
URL_MODELOS = "https://argautos.com/api/v1/brands/{marca_id}/models"


def cargar():
    print("Iniciando carga del catálogo de vehículos...")

    try:
        peticion = urllib.request.Request(
          URL_MARCAS,
          headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))

        print("Conexión realizada correctamente.")
        print(f"Registros recibidos: {len(datos)}")
        marcas_api = datos.get("data", [])

        print(f"Marcas encontradas: {len(marcas_api)}")

        creadas = 0
        existentes = 0

        for item in marcas_api:
            nombre = item["name"].strip()

            marca, creada = MarcaVehiculo.objects.get_or_create(
              nombre=nombre,
              defaults={"activa": True},
            )

            if creada:
             creadas += 1
            else:
             existentes += 1

        print("-----------------------------")
        print("MARCAS CARGADAS")
        print(f"Nuevas: {creadas}")
        print(f"Ya existentes: {existentes}")
        print("-----------------------------")

    except Exception as error:
        print("No se pudo descargar el catálogo.")
        print(f"Error: {error}")
        return


def cargar_modelos_ford():
    marca = MarcaVehiculo.objects.filter(
        nombre__iexact="FORD"
    ).first()

    if not marca:
        print("ERROR: FORD no está cargada en la base de datos.")
        return

    marca_id_api = 19
    pagina = 1
    creados = 0
    existentes = 0

    print("Cargando modelos de FORD...")

    while True:
        url = URL_MODELOS.format(marca_id=marca_id_api)
        url = f"{url}?page={pagina}"

        peticion = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0"}
        )

        with urllib.request.urlopen(peticion, timeout=30) as respuesta:
            datos = json.loads(respuesta.read().decode("utf-8"))

        modelos_api = datos.get("data", [])

        if not modelos_api:
            break

        modelos_api = modelos_api[:3]

        for item in modelos_api:
            nombre = item["name"].strip()
            modelo_id_api = item["id"]
            
             

            modelo, creado = ModeloVehiculo.objects.get_or_create(
                marca=marca,
                nombre=nombre,
                tipo="Auto",
                defaults={"activa": True},
            )

            if creado:
                creados += 1
            else:
                existentes += 1

            cargar_anios_modelo(
                marca.nombre,
                nombre,
                modelo_id_api,
                
            ) 
            time.sleep(5)      

        if not datos.get("next_page_url"):
            break

        pagina += 1

    print("------------------------------")
    print("MODELOS FORD")
    print(f"Nuevos: {creados}")
    print(f"Ya existentes: {existentes}")
    print("------------------------------")   

def cargar_anios_modelo(marca_nombre, modelo_nombre, modelo_id_api):

    modelo = ModeloVehiculo.objects.filter(
      marca__nombre__iexact=marca_nombre,
      nombre__iexact=modelo_nombre,
    ).first()

    pagina = 1
    anios = set()

    print(f"Buscando versiones y años de {marca_nombre} {modelo_nombre}...")

    while True:
        url = (
            f"https://argautos.com/api/v1/models/"
            f"{modelo_id_api}/versions?page={pagina}"
        )

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

        versiones = datos.get("data", [])

        for version in versiones:
            version_id = version["id"]

            url_valuaciones = (
                f"https://argautos.com/api/v1/versions/"
                f"{version_id}/valuations"
            )

            peticion_val = urllib.request.Request(
                url_valuaciones,
                headers={"User-Agent": "Mozilla/5.0"},
            )

            while True:
              try:
                 with urllib.request.urlopen(
                   peticion_val,
                   timeout=30,
                 ) as respuesta:
                    valuaciones = json.loads(
                respuesta.read().decode("utf-8")
                    )
                 break

              except urllib.error.HTTPError as error:
                 if error.code == 429:
                     print("API ocupada. Esperando 5 segundos...")
                     time.sleep(5)
                     continue
                 raise

              except urllib.error.URLError as error:
                 print(f"Error de conexión: {error}. Reintentando en 10 segundos...")
                 time.sleep(10)
                 continue
                
                  
                                
                
        for valuacion in valuaciones.get("data", []):
                anio = valuacion.get("year")

                if anio:
                    anios.add(int(anio))
        time.sleep(2)

        if not datos.get("next_page_url"):
            break

        pagina += 1

    if not anios:
        print(f"No se encontraron años para {marca_nombre} {modelo_nombre}.")
        return

    modelo.anio_desde = min(anios)
    modelo.anio_hasta = max(anios)
    modelo.save(
        update_fields=["anio_desde", "anio_hasta"]
    )

    print("------------------------------")
    print(f"{marca_nombre} {modelo_nombre}")
    print(f"Años encontrados: {sorted(anios)}")
    print(f"Año desde: {modelo.anio_desde}")
    print(f"Año hasta: {modelo.anio_hasta}")
    print("------------------------------")  

def cargar_motos_dnrpa():
    ruta = Path(__file__).resolve().parent / "datos_dnrpa" / "catalogo_motos_dnrpa_2026.csv"

    if not ruta.exists():
        print(f"ERROR: no se encontró el archivo: {ruta}")
        return

    marcas_nuevas = 0
    modelos_nuevos = 0
    modelos_existentes = 0
    ignorados = 0

    print("Iniciando carga de motos DNRPA...")
    print(f"Archivo: {ruta}")

    with open(ruta, "r", encoding="utf-8-sig", newline="") as archivo:
        lector = csv.DictReader(archivo)

        for fila in lector:
            marca_nombre = (fila.get("marca") or "").strip().upper()
            modelo_nombre = (fila.get("modelo") or "").strip().upper()
            tipo_sistema = (fila.get("tipo_sistema") or "Moto").strip()

            if not marca_nombre or not modelo_nombre:
                ignorados += 1
                continue

            marca, marca_creada = MarcaVehiculo.objects.get_or_create(
                nombre=marca_nombre,
                defaults={"activa": True},
            )

            if marca_creada:
                marcas_nuevas += 1

            _, modelo_creado = ModeloVehiculo.objects.get_or_create(
                marca=marca,
                nombre=modelo_nombre,
                tipo=tipo_sistema,
                defaults={"activa": True},
            )

            if modelo_creado:
                modelos_nuevos += 1
            else:
                modelos_existentes += 1

    print("------------------------------")
    print("MOTOS DNRPA")
    print(f"Marcas nuevas: {marcas_nuevas}")
    print(f"Modelos nuevos: {modelos_nuevos}")
    print(f"Modelos ya existentes: {modelos_existentes}")
    print(f"Ignorados: {ignorados}")
    print("------------------------------")     