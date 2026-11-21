"""Regresión: cambio de titular sin alterar las pólizas del vendedor.

Los registros y documentos usados en estas pruebas son completamente sintéticos.
"""
from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from clientes.models import Cliente
from polizas.models import Poliza
from vehiculos.models import Vehiculo


@override_settings(SECURE_SSL_REDIRECT=False)
class CambioTitularVehiculoTests(TestCase):
    def setUp(self):
        self.usuario = get_user_model().objects.create_user(
            username="operador_prueba", password="solo_para_pruebas"
        )
        self.client.force_login(self.usuario)
        self.vendedor = Cliente.objects.create(
            nombre="VENDEDOR", apellido="PRUEBA", dni="90000001"
        )
        self.comprador = Cliente.objects.create(
            nombre="COMPRADOR", apellido="PRUEBA", dni="90000002"
        )
        self.vehiculo_original = Vehiculo.objects.create(
            cliente=self.vendedor,
            tipo="Camioneta",
            patente="AB123CD",
            marca="TOYOTA",
            modelo="HILUX",
            anio=2021,
            motor="MOTORTEST123",
            chasis="CHASISTEST123",
            uso="Particular",
        )
        self.poliza_anulada = Poliza.objects.create(
            cliente=self.vendedor,
            vehiculo=self.vehiculo_original,
            tipo_seguro="Automotor",
            compania="ASEGURADORA PRUEBA",
            numero_poliza="TEST-ANULADA-001",
            fecha_alta=date(2026, 10, 1),
            periodicidad="Mensual",
            estado="Anulada",
        )

    def formulario_vehiculo(self, cliente, patente="AB123CD"):
        return self.client.post(
            reverse("crear_riesgo_cliente", args=[cliente.pk]),
            {
                "cliente": str(cliente.pk),
                "tipo": "Camioneta",
                "patente": patente,
                "marca": "TOYOTA",
                "modelo": "HILUX",
                "anio": "2021",
                "motor": "MOTORTEST123",
                "chasis": "CHASISTEST123",
                "uso": "Particular",
            },
        )

    def test_comprador_puede_registrar_misma_patente_sin_tocar_vendedor(self):
        respuesta = self.formulario_vehiculo(self.comprador)
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(
            Vehiculo.objects.filter(patente__iexact="AB123CD").count(), 2
        )
        nuevo = Vehiculo.objects.get(cliente=self.comprador)
        self.assertEqual((nuevo.marca, nuevo.modelo), ("TOYOTA", "HILUX"))
        self.assertNotEqual(nuevo.pk, self.vehiculo_original.pk)
        self.poliza_anulada.refresh_from_db()
        self.vehiculo_original.refresh_from_db()
        self.assertEqual(self.poliza_anulada.vehiculo_id, self.vehiculo_original.pk)
        self.assertEqual(self.poliza_anulada.cliente_id, self.vendedor.pk)
        self.assertEqual(self.vehiculo_original.cliente_id, self.vendedor.pk)

    def test_mismo_cliente_no_puede_duplicar_su_patente(self):
        respuesta = self.formulario_vehiculo(self.vendedor, "ab123cd")
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, "ya tiene un vehículo con esa patente")
        self.assertEqual(Vehiculo.objects.count(), 1)

    def test_poliza_nueva_se_vincula_a_comprador_y_conserva_datos_del_vehiculo(self):
        self.assertEqual(self.formulario_vehiculo(self.comprador).status_code, 302)
        nuevo = Vehiculo.objects.get(cliente=self.comprador)
        respuesta = self.client.post(
            reverse("crear_poliza_cliente", args=[self.comprador.pk]),
            {
                "cliente": str(self.comprador.pk),
                "vehiculo": str(nuevo.pk),
                "tipo_seguro": "Automotor",
                "compania": "ASEGURADORA PRUEBA",
                "numero_poliza": "TEST-NUEVA-002",
                "cobertura": "TERCEROS",
                "fecha_alta": "2026-11-21",
                "periodicidad": "Mensual",
                "estado": "Vigente",
                "importe_cuota": "25000,00",
            },
        )
        self.assertEqual(respuesta.status_code, 302)
        poliza_nueva = Poliza.objects.get(numero_poliza="TEST-NUEVA-002")
        self.assertEqual(poliza_nueva.cliente_id, self.comprador.pk)
        self.assertEqual(poliza_nueva.vehiculo_id, nuevo.pk)
        self.assertEqual(
            (poliza_nueva.vehiculo.patente, poliza_nueva.vehiculo.marca,
             poliza_nueva.vehiculo.modelo),
            ("AB123CD", "TOYOTA", "HILUX"),
        )
        self.poliza_anulada.refresh_from_db()
        self.assertEqual(self.poliza_anulada.vehiculo_id, self.vehiculo_original.pk)
        self.assertEqual(self.poliza_anulada.estado, "Anulada")
