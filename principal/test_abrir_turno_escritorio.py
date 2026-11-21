"""Regresión: acceso Abrir turno del escritorio, usando solo datos sintéticos."""
from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from principal.models import PerfilUsuario, Sucursal, TurnoCaja


@override_settings(SECURE_SSL_REDIRECT=False)
class AbrirTurnoDesdeEscritorioTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="operador_sintetico", password="clave-sintetica"
        )
        cls.sucursal = Sucursal.objects.create(
            nombre="Sucursal sintética",
            provincia="Tucumán",
            codigo="TEST-CAJA",
            activa=True,
        )
        PerfilUsuario.objects.create(usuario=cls.user, sucursal=cls.sucursal, activo=True)

    def setUp(self):
        self.client.force_login(self.user)

    def test_escritorio_usa_formulario_post_con_csrf(self):
        response = self.client.get(reverse("inicio"))
        self.assertEqual(response.status_code, 200)
        page = response.content.decode("utf-8")
        url = reverse("abrir_turno")
        self.assertIn(f'<form method="post" action="{url}"', page)
        self.assertIn('name="csrfmiddlewaretoken"', page)
        self.assertIn('type="submit"', page)
        self.assertNotIn(f'<a href="{url}"', page)

    def test_get_no_abre_turno(self):
        response = self.client.get(reverse("abrir_turno"))
        self.assertEqual(response.status_code, 405)
        self.assertFalse(TurnoCaja.objects.filter(usuario=self.user, abierto=True).exists())

    def test_post_abre_turno_y_segundo_post_no_duplicado(self):
        url = reverse("abrir_turno")
        response = self.client.post(url)
        self.assertRedirects(response, reverse("caja_diaria"), fetch_redirect_response=False)
        turno = TurnoCaja.objects.get(usuario=self.user, abierto=True)
        self.assertEqual(turno.sucursal, self.sucursal)
        self.assertEqual(turno.total_cobrado, 0)
        self.client.post(url)
        self.assertEqual(TurnoCaja.objects.filter(usuario=self.user, abierto=True).count(), 1)

    def test_post_sin_csrf_es_rechazado(self):
        cliente = Client(enforce_csrf_checks=True)
        cliente.force_login(self.user)
        response = cliente.post(reverse("abrir_turno"))
        self.assertEqual(response.status_code, 403)
        self.assertFalse(TurnoCaja.objects.filter(usuario=self.user).exists())
