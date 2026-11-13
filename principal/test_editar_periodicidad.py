"""Regresión de edición de periodicidad en FORTEX (datos sintéticos)."""
from datetime import date
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente
from cobros.models import Cobro
from polizas.models import Poliza
from recibos.models import Recibo


class EditarPeriodicidadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operador_edicion")
        self.client.force_login(self.user)
        self.cliente = Cliente.objects.create(
            nombre="Cliente", apellido="SINTETICO", dni="EDICION-000"
        )
        self.poliza = Poliza.objects.create(
            cliente=self.cliente, compania="ASEGURADORA SINTETICA",
            numero_poliza="EDICION-TEST", fecha_alta=date(2026, 11, 1),
            tipo_seguro="Automotor", periodicidad="Mensual",
        )

    def cambiar_a_cuatrimestral(self, numero_cuota):
        return self.client.post(
            reverse("editar_poliza", args=[self.poliza.pk]),
            {
                "vehiculo": "", "tipo_seguro": "Automotor",
                "compania": "ASEGURADORA SINTETICA",
                "numero_poliza": "EDICION-TEST",
                "cobertura": "", "fecha_alta": "2026-11-01",
                "periodicidad": "Cuatrimestral",
                "numero_cuota": str(numero_cuota),
                "importe_cuota": "", "porcentaje_comision": "0",
                "estado": "Pendiente", "observaciones": "",
            },
        )

    def test_sin_cobros_guarda_cuatrimestral_y_cuota_cero(self):
        self.assertEqual(self.poliza.numero_cuota, 0)
        response = self.cambiar_a_cuatrimestral(numero_cuota=0)
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        self.poliza.refresh_from_db()
        self.assertEqual(self.poliza.periodicidad, "Cuatrimestral")
        self.assertEqual(self.poliza.cantidad_cuotas, 4)
        self.assertEqual(self.poliza.numero_cuota, 0)
        self.assertEqual(self.poliza.fecha_fin_vigencia, date(2027, 3, 1))
        self.assertEqual(self.poliza.fecha_vencimiento, date(2026, 11, 1))
        self.assertEqual(Cobro.objects.count(), 0)

    def test_cobro_y_recibo_anteriores_se_conservan(self):
        cobro = Cobro.objects.create(
            cliente=self.cliente, poliza=self.poliza,
            fecha_pago=date(2026, 11, 2), importe=Decimal("45000.00"),
            registrado_por=self.user,
        )
        recibo = Recibo.objects.create(
            poliza=self.poliza, importe=Decimal("45000.00")
        )
        self.poliza.numero_cuota = 1
        self.poliza.save()
        response = self.cambiar_a_cuatrimestral(numero_cuota=1)
        self.assertEqual(response.status_code, 302, response.content.decode()[:500])
        self.poliza.refresh_from_db()
        cobro.refresh_from_db()
        recibo.refresh_from_db()
        self.assertEqual(self.poliza.periodicidad, "Cuatrimestral")
        self.assertEqual(self.poliza.cantidad_cuotas, 4)
        self.assertEqual(self.poliza.numero_cuota, 1)
        self.assertEqual(self.poliza.fecha_fin_vigencia, date(2027, 3, 1))
        self.assertEqual(self.poliza.fecha_vencimiento, date(2026, 12, 1))
        self.assertEqual(cobro.importe, Decimal("45000.00"))
        self.assertEqual(recibo.importe, Decimal("45000.00"))
        self.assertEqual(Cobro.objects.count(), 1)
        self.assertEqual(Recibo.objects.count(), 1)
