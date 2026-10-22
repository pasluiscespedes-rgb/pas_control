from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse

from clientes.models import Cliente


class ClienteWhatsAppCompartidoTests(TestCase):
    def setUp(self):
        User = get_user_model()
        self.user = User.objects.create_user(
            username="tester",
            password="testpass123",
        )
        self.client.force_login(self.user)

    def _datos_cliente(self, dni, nombre):
        return {
            "apellido": "PRUEBA",
            "nombre": nombre,
            "dni": dni,
            "fecha_nacimiento": "1990-01-01",
            "whatsapp": "3815551234",
            "calle": "TEST",
            "numero": "1",
            "piso": "",
            "departamento": "",
            "barrio": "",
            "localidad": "SAN MIGUEL DE TUCUMAN",
            "provincia": "TUCUMAN",
            "codigo_postal": "4000",
            "email": "",
            "telefono_alternativo": "",
            "observaciones": "",
        }

    def test_dos_clientes_pueden_compartir_whatsapp(self):
        url = reverse("crear_cliente")

        respuesta_1 = self.client.post(
            url,
            self._datos_cliente("30111222", "UNO"),
        )
        respuesta_2 = self.client.post(
            url,
            self._datos_cliente("30999888", "DOS"),
        )

        self.assertEqual(respuesta_1.status_code, 302)
        self.assertEqual(respuesta_2.status_code, 302)
        self.assertEqual(
            Cliente.objects.filter(
                whatsapp="3815551234"
            ).count(),
            2,
        )

    def test_dni_sigue_siendo_unico(self):
        url = reverse("crear_cliente")

        self.client.post(
            url,
            self._datos_cliente("30111222", "UNO"),
        )
        respuesta = self.client.post(
            url,
            self._datos_cliente("30111222", "DOS"),
        )

        self.assertEqual(respuesta.status_code, 200)
        self.assertContains(
            respuesta,
            "Ya existe un cliente con ese DNI.",
        )
        self.assertEqual(
            Cliente.objects.filter(
                dni="30111222"
            ).count(),
            1,
        )
