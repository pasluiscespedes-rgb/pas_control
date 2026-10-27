"""Pruebas unitarias puras de identidad y estados, sin base de datos."""
from django.test import SimpleTestCase

from polizas.identidades import (
    EstadoMovimiento, IdentidadTomador, TipoTomador,
    requiere_confirmacion_aseguradora, validar_cuit,
)


class IdentidadesTomadorTests(SimpleTestCase):
    def test_persona_fisica_no_necesita_empresa(self):
        tomador = IdentidadTomador(
            tipo=TipoTomador.PERSONA_FISICA,
            nombre="PEPITO", apellido="PEREZ", dni="12345678",
        )
        self.assertEqual(tomador.validar(), {})

    def test_empresa_necesita_razon_social_y_cuit(self):
        empresa = IdentidadTomador(
            tipo=TipoTomador.PERSONA_JURIDICA,
            nombre_fantasia="MI NEGOCIO",
        )
        self.assertEqual(set(empresa.validar()), {"razon_social", "cuit"})

    def test_cuit_digito_verificador(self):
        # CUIT sintético generado para la prueba; no identifica un contribuyente.
        base = "3099999999"
        digito = next(i for i in range(10) if validar_cuit(base + str(i)))
        valido = base + str(digito)
        self.assertTrue(validar_cuit(valido))
        self.assertFalse(validar_cuit(valido[:10] + str((digito + 1) % 10)))

    def test_baja_no_confirmada_no_se_considera_efectiva(self):
        self.assertTrue(requiere_confirmacion_aseguradora(EstadoMovimiento.PENDIENTE))
        self.assertTrue(requiere_confirmacion_aseguradora(EstadoMovimiento.ENVIADO))
        self.assertTrue(requiere_confirmacion_aseguradora(EstadoMovimiento.RECHAZADO))
        self.assertFalse(requiere_confirmacion_aseguradora(EstadoMovimiento.CONFIRMADO))
