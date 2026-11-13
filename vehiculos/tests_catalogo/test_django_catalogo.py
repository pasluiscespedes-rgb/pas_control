"""Pruebas Django: se ejecutan únicamente con el entorno del proyecto instalado."""
from io import StringIO
from django.test import TestCase, Client
from django.contrib.auth.models import User
from vehiculos.catalogo_maestro.importacion import importar_archivo
from vehiculos.catalogo_maestro.coincidencias import resolver_ocr
from vehiculos.models import AliasMarcaVehiculo, AliasModeloVehiculo, MarcaVehiculo, ModeloVehiculo, RegistroFuenteModelo, ModeloAnio

CSV = ('automotor_marca_descripcion,automotor_modelo_descripcion,automotor_tipo_descripcion,automotor_anio_modelo,nombre_titular\n'
       'VOLKSWAGEN,AMAROK,CAMIONETA,2023,NO_IMPORTAR\n'
       'VOLKSWAGEN,AMAROK,CAMIONETA,2023,OTRO_TITULAR\n')

class ImportacionTest(TestCase):
    def test_dry_run_sin_escrituras(self):
        r = importar_archivo(StringIO(CSV), 'DNRPA_TEST', 'Prueba', dry_run=True)
        self.assertEqual(r['filas'], 2)
        self.assertEqual(r['modelos_distintos'], 1)
        self.assertFalse(MarcaVehiculo.objects.exists())

    def test_importacion_idempotente_y_procedencia(self):
        kwargs = dict(codigo_fuente='DNRPA_TEST',titulo_fuente='Prueba', licencia='CC BY 4.0', dry_run=False)
        importar_archivo(StringIO(CSV), **kwargs)
        importar_archivo(StringIO(CSV), **kwargs)
        self.assertEqual(MarcaVehiculo.objects.count(),1)
        self.assertEqual(ModeloVehiculo.objects.count(),1)
        self.assertEqual(RegistroFuenteModelo.objects.count(),1)
        self.assertEqual(ModeloAnio.objects.count(),1)

    def test_alias_aprobado_y_no_aprobado(self):
        marca=MarcaVehiculo.objects.create(nombre='VOLKSWAGEN')
        modelo=ModeloVehiculo.objects.create(marca=marca,nombre='AMAROK',tipo='Camioneta')
        AliasMarcaVehiculo.objects.create(marca=marca,denominacion='VW',aprobada=False)
        self.assertEqual(resolver_ocr('VW','AMAROK','Camioneta')['estado'],'REVISAR')
        alias = AliasMarcaVehiculo.objects.get(marca=marca)
        alias.aprobada=True; alias.save()
        self.assertEqual(resolver_ocr('VW','AMAROK','Camioneta')['estado'],'COINCIDENCIA')
        AliasModeloVehiculo.objects.create(modelo=modelo,denominacion='AMAROK V6',aprobada=True)
        self.assertEqual(resolver_ocr('VW','AMAROK V6','Camioneta')['estado'],'COINCIDENCIA')

    def test_fuzzy_solo_sugerencias(self):
        marca=MarcaVehiculo.objects.create(nombre='TOYOTA')
        ModeloVehiculo.objects.create(marca=marca,nombre='HILUX',tipo='Camioneta')
        self.assertEqual(resolver_ocr('TOYOTA','HILUXX','Camioneta')['estado'],'REVISAR')

    def test_endpoint_requiere_login(self):
        respuesta=Client().get('/vehiculos/catalogo/buscar/?q=hilux', secure=True)
        self.assertEqual(respuesta.status_code,302)

    def test_busqueda_modelos_autenticada_y_filtrada(self):
        usuario = User.objects.create_user(username='catalogo_ci', password='clave-sintetica')
        marca = MarcaVehiculo.objects.create(nombre='FORD')
        ModeloVehiculo.objects.create(marca=marca, nombre='RANGER', tipo='Camioneta')
        ModeloVehiculo.objects.create(marca=marca, nombre='RANGER', tipo='Auto')
        navegador = Client()
        navegador.force_login(usuario)
        r = navegador.get('/vehiculos/catalogo/buscar/', {'q':'RAN','marca':'FORD','tipo':'Camioneta'}, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.json()['resultados']), 1)
        self.assertEqual(r.json()['resultados'][0]['tipo'], 'Camioneta')

    def test_ocr_no_elige_entre_dos_tipos_sin_categoria(self):
        marca = MarcaVehiculo.objects.create(nombre='FORD')
        ModeloVehiculo.objects.create(marca=marca, nombre='RANGER', tipo='Camioneta')
        ModeloVehiculo.objects.create(marca=marca, nombre='RANGER', tipo='Auto')
        r = resolver_ocr('FORD','RANGER')
        self.assertEqual(r['estado'], 'REVISAR')
        self.assertEqual(r['motivo'], 'AMBIGUA')

    def test_sugerencias_no_permiten_escritura(self):
        usuario = User.objects.create_user(username='lector_ci', password='clave-ci')
        c = Client()
        c.force_login(usuario)
        r = c.get('/vehiculos/catalogo/sugerencias/', {'marca':'INEXISTENTE','modelo':'XX'}, secure=True)
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.json()['estado'], 'REVISAR')
        self.assertFalse(MarcaVehiculo.objects.exists())
