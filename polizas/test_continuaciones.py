"""Regresiones: las continuaciones nunca reescriben pólizas anteriores."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from clientes.models import Cliente
from polizas.models import Poliza


@override_settings(SECURE_SSL_REDIRECT=False)
class ContinuacionPolizaTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operador_prueba", password="test")
        self.client.force_login(self.user)
        self.cliente = Cliente.objects.create(nombre="PRUEBA", apellido="SINTETICO", dni="99900001")
        self.anterior = Poliza.objects.create(
            cliente=self.cliente, tipo_seguro="Moto", compania="ASEGURADORA A",
            numero_poliza="ANT-001", cobertura="RC", fecha_alta=date(2026, 1, 1),
            periodicidad="Trimestral", numero_cuota=2, importe_cuota=Decimal("12000"),
        )

    def enviar(self, accion, **changes):
        datos = {
            "compania": "ASEGURADORA A" if accion == "renovar" else "ASEGURADORA B",
            "numero_poliza": "NUEVA-002", "cobertura": "RC",
            "fecha_alta": "2026-04-01", "periodicidad": "Semestral",
            "importe_cuota": "25000,50", "porcentaje_comision": "15",
        }
        datos.update(changes)
        return self.client.post(reverse("renovar_poliza" if accion == "renovar" else "cambiar_aseguradora",
                                        args=[self.anterior.pk]), datos)

    def test_renovacion_conserva_anterior(self):
        respuesta = self.enviar("renovar")
        self.assertEqual(respuesta.status_code, 302)
        nueva = Poliza.objects.get(numero_poliza="NUEVA-002")
        self.assertEqual(nueva.poliza_anterior_id, self.anterior.id)
        self.assertEqual(nueva.cliente_id, self.anterior.cliente_id)
        self.assertEqual(nueva.vehiculo_id, self.anterior.vehiculo_id)
        self.assertEqual(nueva.numero_cuota, 0)
        self.assertEqual(nueva.cantidad_cuotas, 6)
        self.assertEqual(nueva.fecha_vencimiento, date(2026, 5, 1))
        self.anterior.refresh_from_db()
        self.assertEqual(self.anterior.numero_poliza, "ANT-001")
        self.assertEqual(self.anterior.numero_cuota, 2)
        self.assertEqual(self.anterior.importe_cuota, Decimal("12000"))

    def test_cambio_aseguradora_y_sin_duplicar(self):
        self.assertEqual(self.enviar("cambiar").status_code, 302)
        self.assertEqual(Poliza.objects.get(numero_poliza="NUEVA-002").compania, "ASEGURADORA B")
        self.assertEqual(self.enviar("cambiar").status_code, 200)
        self.assertEqual(Poliza.objects.count(), 2)

    def test_rechaza_mismo_numero_y_compania_incorrecta(self):
        self.assertEqual(self.enviar("renovar", numero_poliza="ANT-001").status_code, 200)
        self.assertEqual(self.enviar("cambiar", compania="ASEGURADORA A").status_code, 200)
        self.assertEqual(Poliza.objects.count(), 1)

    def test_no_modifica_registro_con_get(self):
        respuesta = self.client.get(reverse("renovar_poliza", args=[self.anterior.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Poliza.objects.count(), 1)

    def test_selector_cambio_incluye_aseguradoras_y_nre(self):
        respuesta = self.client.get(reverse("cambiar_aseguradora", args=[self.anterior.pk]))
        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(respuesta, 'id="compania-selector"')
        self.assertContains(respuesta, "ASEGURADORA A")
        self.assertContains(respuesta, "NRE COMPAÑÍA DE SEGUROS")

    def test_cambio_con_otra_aseguradora_manual(self):
        respuesta = self.enviar("cambiar", compania="__otra__", compania_manual="ASEGURADORA NUEVA")
        self.assertEqual(respuesta.status_code, 302)
        self.assertEqual(Poliza.objects.get(numero_poliza="NUEVA-002").compania, "ASEGURADORA NUEVA")

    def test_rechaza_aseguradora_no_listada_sin_opcion_manual(self):
        respuesta = self.enviar("cambiar", compania="ASEGURADORA NO LISTADA")
        self.assertEqual(respuesta.status_code, 200)
        self.assertEqual(Poliza.objects.count(), 1)
