from datetime import timedelta
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from clientes.models import Cliente
from polizas.models import Poliza
from principal.whatsapp import obtener_importe_referencia
from vehiculos.models import Vehiculo


class AvisosAutomaticosTests(TestCase):
    def setUp(self):
        self.hoy = timezone.localdate()

        self.cliente = Cliente.objects.create(
            nombre="CLIENTE",
            apellido="PRUEBA",
            dni="30111222",
            whatsapp="3815551234",
        )

        self.vehiculo = Vehiculo.objects.create(
            cliente=self.cliente,
            patente="AA123BB",
            marca="MARCA",
            modelo="MODELO",
            motor="MOTOR123",
            chasis="CHASIS123",
        )

    def crear_poliza(
        self,
        *,
        avisos_whatsapp=True,
        numero_cuota=0,
        periodicidad="Trimestral",
    ):
        return Poliza.objects.create(
            cliente=self.cliente,
            vehiculo=self.vehiculo,
            compania="ASEGURADORA",
            numero_poliza="POL-TEST",
            fecha_alta=self.hoy,
            fecha_vencimiento=(
                self.hoy
                + timedelta(days=1)
            ),
            periodicidad=periodicidad,
            numero_cuota=numero_cuota,
            importe_cuota=Decimal("25000.00"),
            avisos_whatsapp=avisos_whatsapp,
        )

    def ejecutar_simulacion(self):
        salida = StringIO()

        call_command(
            "enviar_avisos_automaticos",
            "--simular",
            stdout=salida,
        )

        return salida.getvalue()

    def test_incluye_poliza_habilitada_con_cuotas_pendientes(self):
        poliza = self.crear_poliza()

        salida = self.ejecutar_simulacion()

        self.assertIn(
            "Pólizas encontradas: 1",
            salida,
        )
        self.assertIn(
            f"Póliza {poliza.id}",
            salida,
        )
        self.assertIn(
            "recordatorio",
            salida,
        )

    def test_excluye_poliza_con_avisos_deshabilitados(self):
        self.crear_poliza(
            avisos_whatsapp=False,
        )

        salida = self.ejecutar_simulacion()

        self.assertIn(
            "Pólizas encontradas: 0",
            salida,
        )

    def test_excluye_poliza_totalmente_pagada(self):
        self.crear_poliza(
            numero_cuota=3,
        )

        salida = self.ejecutar_simulacion()

        self.assertIn(
            "Pólizas encontradas: 0",
            salida,
        )

    def test_importe_de_poliza_sirve_antes_del_primer_cobro(self):
        poliza = self.crear_poliza()

        importe = obtener_importe_referencia(
            poliza
        )

        self.assertEqual(
            importe,
            Decimal("25000.00"),
        )
