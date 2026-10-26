"""Contratos de aislamiento entre ramos. Ejecutar solo con base de pruebas.

Estos tests protegen el modelo de cliente único y pólizas múltiples.
No certifican todavía los módulos de riesgo especializados.
"""
from datetime import date
from decimal import Decimal

from django.test import TestCase

from clientes.models import Cliente
from polizas.models import Poliza


class ClienteMultipolizaTests(TestCase):
    def setUp(self):
        self.cliente = Cliente.objects.create(
            nombre="CLIENTE",
            apellido="SINTETICO",
            dni="99000123",
            fecha_nacimiento=date(1990, 1, 1),
            whatsapp="3810000000",
        )

    def crear_poliza(self, ramo, numero, **extra):
        datos = {
            "cliente": self.cliente,
            "tipo_seguro": ramo,
            "compania": "ASEGURADORA DE PRUEBA",
            "numero_poliza": numero,
            "cobertura": "COBERTURA DE PRUEBA",
            "fecha_alta": date(2026, 10, 1),
            "importe_cuota": Decimal("1000.00"),
        }
        datos.update(extra)
        return Poliza.objects.create(**datos)

    def test_un_cliente_puede_tener_varias_polizas_y_ramos(self):
        ap_1 = self.crear_poliza(
            "Accidentes Personales", "AP-001",
            asegurado_nombre="CLIENTE SINTETICO",
            asegurado_documento=self.cliente.dni,
            actividad_declarada="ADMINISTRATIVO",
        )
        ap_2 = self.crear_poliza(
            "Accidentes Personales", "AP-002",
            asegurado_nombre="CLIENTE SINTETICO",
            asegurado_documento=self.cliente.dni,
            actividad_declarada="DOCENTE",
        )
        hogar = self.crear_poliza("Hogar", "HOG-001")

        self.assertEqual(Cliente.objects.filter(dni=self.cliente.dni).count(), 1)
        self.assertEqual(Poliza.objects.filter(cliente=self.cliente).count(), 3)
        self.assertEqual({ap_1.pk, ap_2.pk, hogar.pk}.__len__(), 3)
        self.assertEqual(ap_1.cliente_id, hogar.cliente_id)
        self.assertIsNone(ap_1.vehiculo_id)
        self.assertIsNone(ap_2.vehiculo_id)

    def test_editar_una_poliza_no_modifica_otra_del_mismo_cliente(self):
        primera = self.crear_poliza(
            "Accidentes Personales", "AP-101",
            asegurado_nombre="CLIENTE SINTETICO",
            asegurado_documento=self.cliente.dni,
            actividad_declarada="OFICINA",
        )
        segunda = self.crear_poliza(
            "Accidentes Personales", "AP-102",
            asegurado_nombre="CLIENTE SINTETICO",
            asegurado_documento=self.cliente.dni,
            actividad_declarada="COMERCIO",
        )
        primera.actividad_declarada = "DOCENCIA"
        primera.save()
        segunda.refresh_from_db()
        self.assertEqual(segunda.actividad_declarada, "COMERCIO")
        self.assertEqual(segunda.numero_poliza, "AP-102")
        self.assertEqual(Cliente.objects.filter(dni=self.cliente.dni).count(), 1)

    def test_anular_una_poliza_no_anula_las_demas(self):
        primera = self.crear_poliza("Hogar", "HOG-101")
        segunda = self.crear_poliza("Hogar", "HOG-102")
        primera.estado = "Anulada"
        primera.motivo_anulacion = "PRUEBA SINTETICA"
        primera.save()
        segunda.refresh_from_db()
        self.assertNotEqual(segunda.estado, "Anulada")
        self.assertEqual(Poliza.objects.filter(cliente=self.cliente).count(), 2)


class ContratosPorRamoTests(TestCase):
    def test_ap_exige_campos_propios_sin_vehiculo(self):
        from polizas.ramos import errores_ap
        ap = Poliza(
            cliente=self._cliente(),
            tipo_seguro="Accidentes Personales",
            compania="ASEGURADORA DE PRUEBA",
            fecha_alta=date(2026, 10, 1),
        )
        errores = errores_ap(ap)
        self.assertEqual(
            set(errores),
            {"asegurado_nombre", "asegurado_documento", "actividad_declarada", "cobertura"},
        )

    def test_validacion_ap_no_contamina_otros_ramos(self):
        from polizas.ramos import errores_ap
        poliza = Poliza(
            cliente=self._cliente(),
            tipo_seguro="Hogar",
            compania="ASEGURADORA DE PRUEBA",
            fecha_alta=date(2026, 10, 1),
        )
        self.assertEqual(errores_ap(poliza), {})

    def test_registro_ramos_reconoce_vehiculo_solo_en_automotor_y_moto(self):
        from polizas.ramos import configuracion_ramo
        self.assertTrue(configuracion_ramo("Automotor").requiere_vehiculo)
        self.assertTrue(configuracion_ramo("Moto").requiere_vehiculo)
        self.assertFalse(configuracion_ramo("ACCIDENTES PERSONALES").requiere_vehiculo)
        self.assertFalse(configuracion_ramo("Hogar").requiere_vehiculo)

    def _cliente(self):
        return Cliente.objects.create(
            nombre="CLIENTE", apellido="PRUEBA",
            dni=str(99010000 + Cliente.objects.count()),
        )
