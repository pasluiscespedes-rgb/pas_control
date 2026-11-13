"""Se ejecuta con unittest estándar sin Django: python -m unittest discover..."""
import io
import unittest
from vehiculos.catalogo_maestro.normalizacion import normalizar, tipo_registral, similitud, anio_valido
from vehiculos.catalogo_maestro.extractores import registros_csv, extraer


class CatalogoReglasTest(unittest.TestCase):
    def test_normalizar_ocr(self):
        self.assertEqual(normalizar('  FÓRD  -   F-150  '), 'FORD F 150')
        self.assertEqual(normalizar('VW'), 'VW')

    def test_clases_sin_confundir_camioneta_camion(self):
        self.assertEqual(tipo_registral('CAMIONETA PICK UP'), 'Camioneta')
        self.assertEqual(tipo_registral('CAMION'), 'Camión')
        self.assertEqual(tipo_registral('SEMIRREMOLQUE'), 'Acoplado')
        self.assertEqual(tipo_registral('TRAILER'), 'Tráiler')
        self.assertEqual(tipo_registral('MOTOCICLETA'), 'Moto')
        self.assertIsNone(tipo_registral('SIN CLASIFICAR'))

    def test_anio(self):
        self.assertIsNone(anio_valido('abc'))
        self.assertIsNone(anio_valido('2026abc'))
        self.assertEqual(anio_valido('2022'), 2022)

    def test_sin_filtrar_personas(self):
        f = io.StringIO('automotor_marca_descripcion,automotor_modelo_descripcion,automotor_tipo_descripcion,automotor_anio_modelo,nombre_titular,dni_titular\nFORD,RANGER,CAMIONETA,2025,CLIENTE FICTICIO,12345678\n')
        datos = list(registros_csv(f))
        self.assertEqual(len(datos), 1)
        self.assertEqual(datos[0].modelo, 'RANGER')
        self.assertEqual(datos[0].anio, 2025)
        self.assertNotIn('CLIENTE FICTICIO', repr(datos))

    def test_motos_del_csv_actual(self):
        f = io.StringIO('marca,modelo,tipo_dnrpa,tipo_sistema\nBAJAJ,ROUSER NS 200,MOTOCICLETA,Moto\n')
        registro = next(registros_csv(f))
        self.assertEqual((registro.marca,registro.modelo,registro.tipo), ('BAJAJ','ROUSER NS 200','Moto'))

    def test_nombre_tipo_desconocido_no_infiere_auto(self):
        f = io.StringIO('marca;modelo;tipo_dnrpa\nFABRICA;VEHICULO;DESCONOCIDO\n')
        self.assertEqual(list(registros_csv(f)), [None])

    def test_rechaza_datos_incompletos(self):
        self.assertIsNone(extraer({'marca':'','modelo':'RANGER','tipo':'Auto'}))
        with self.assertRaises(ValueError):
            list(registros_csv(io.StringIO('dni,nombre\n11111111,ALGUIEN\n')))

    def test_similitud_no_autoriza_guardar(self):
        self.assertGreater(similitud('ROUSER NS 200','ROUSER NS200'),.7)

if __name__ == '__main__':
    unittest.main()
