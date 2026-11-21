"""Regression checks for the desktop 'Abrir turno' access.

These checks inspect the real template and view without connecting to databases.
Run with: python -m unittest discover -s tests -p 'test_abrir_turno_escritorio.py'
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "principal/templates/principal/inicio.html"
STYLES = ROOT / "principal/static/principal/css/estilos.css"
VIEWS = ROOT / "principal/views.py"
CAJA_TEMPLATE = ROOT / "principal/templates/principal/caja_diaria.html"


class AbrirTurnoEscritorioTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html = TEMPLATE.read_text(encoding="utf-8")
        cls.styles = STYLES.read_text(encoding="utf-8")
        cls.views = VIEWS.read_text(encoding="utf-8")
        cls.caja = CAJA_TEMPLATE.read_text(encoding="utf-8")

    def test_dashboard_submits_post_with_csrf(self):
        forms = re.findall(r"<form\b[^>]*>.*?</form>", self.html, flags=re.S | re.I)
        turno_forms = [f for f in forms if "{% url 'abrir_turno' %}" in f]
        self.assertEqual(len(turno_forms), 1)
        form = turno_forms[0]
        self.assertRegex(form, r'(?i)method="post"')
        self.assertIn("{% csrf_token %}", form)
        self.assertRegex(form, r'(?i)<button\b[^>]*type="submit"')
        self.assertIn("fortex-acceso-rapido acceso-turno", form)
        self.assertIn("icono_abrir turno.png", form)
        self.assertNotRegex(self.html, r'<a\b[^>]*href="{% url \'abrir_turno\' %}"')

    def test_backend_requires_post_and_csrf(self):
        self.assertRegex(
            self.views,
            r"@login_required\s+@require_POST\s+@csrf_protect\s+def abrir_turno\(",
        )
        self.assertIn('method="post" action="{% url \'abrir_turno\' %}"', self.caja)
        self.assertIn("{% csrf_token %}", self.caja)

    def test_button_retains_circular_access_styling(self):
        self.assertIn(".fortex-form-abrir-turno > .fortex-acceso-rapido", self.styles)
        self.assertIn(".fortex-form-abrir-turno > .fortex-acceso-rapido:focus-visible", self.styles)


if __name__ == "__main__":
    unittest.main()
