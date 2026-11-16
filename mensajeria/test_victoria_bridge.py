from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse


class VictoriaBridgeSecurityTests(TestCase):
    def setUp(self):
        user_model = get_user_model()
        self.owner = user_model.objects.create_superuser(
            username="victoria_owner", email="owner@example.test", password="test-pass"
        )
        self.other = user_model.objects.create_user(
            username="victoria_other", password="test-pass"
        )
        self.url = reverse("mensajeria:victoria_consultar")

    def test_anonymous_denied(self):
        self.assertNotEqual(self.client.post(self.url, {"buscar": "Gabriel"}).status_code, 200)

    def test_non_owner_denied(self):
        self.client.force_login(self.other)
        with override_settings(VICTORIA_BRIDGE_OWNER_USER_ID=self.owner.pk):
            self.assertEqual(self.client.post(self.url, {"buscar": "Gabriel"}).status_code, 403)

    def test_disabled_by_default(self):
        self.client.force_login(self.owner)
        with override_settings(VICTORIA_BRIDGE_OWNER_USER_ID=None):
            self.assertEqual(self.client.post(self.url, {"buscar": "Gabriel"}).status_code, 403)

    def test_owner_must_specify_search(self):
        self.client.force_login(self.owner)
        with override_settings(VICTORIA_BRIDGE_OWNER_USER_ID=self.owner.pk):
            self.assertEqual(self.client.post(self.url, {}).status_code, 400)

    def test_owner_empty_result(self):
        self.client.force_login(self.owner)
        with override_settings(VICTORIA_BRIDGE_OWNER_USER_ID=self.owner.pk):
            response = self.client.post(self.url, {"buscar": "Gabriel"})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), {"conversaciones": []})
            self.assertEqual(response["Cache-Control"], "no-store")
