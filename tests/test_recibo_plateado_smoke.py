"""Smoke test isolated for the approved receipt layout. Uses synthetic data only."""
from datetime import date
from decimal import Decimal
from io import BytesIO
from pathlib import Path
from types import ModuleType, SimpleNamespace
import sys

# Import only the visual module, not Django settings or the production database.
django = ModuleType("django")
conf = ModuleType("django.conf")
conf.settings = SimpleNamespace(BASE_DIR=Path(__file__).resolve().parents[1])
django.conf = conf
sys.modules["django"] = django
sys.modules["django.conf"] = conf

from dateutil.relativedelta import relativedelta
from pypdf import PdfReader
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from principal.recibo_seguro_layout import dibujar_recibo_seguro


def example(payment_method):
    cliente = SimpleNamespace(apellido="DE PRUEBA", nombre="CLIENTE SINTETICO")
    vehiculo = SimpleNamespace(
        marca="FORD", modelo="FOCUS", patente="ZZ999ZZ",
        motor="MOTOR-SINTETICO-001", chasis="CHASIS-SINTETICO-001", uso="Particular",
    )
    poliza = SimpleNamespace(
        cliente=cliente, vehiculo=vehiculo, numero_poliza="TEST-000159",
        compania="ASEGURADORA DE PRUEBA", fecha_alta=date(2026, 11, 1),
        tipo_seguro="Auto",
    )
    return SimpleNamespace(
        id=139, numero_recibo=139, poliza=poliza,
        numero_cuota=1, cantidad_cuotas=2, importe=Decimal("40000.00"),
        forma_pago=payment_method, fecha=date(2026, 11, 13),
    )


def main():
    target = Path("test-artifacts")
    target.mkdir(exist_ok=True)
    for method, watermark in [("Transferencia", True), ("Efectivo", False)]:
        output = BytesIO()
        p = canvas.Canvas(output, pagesize=A4)
        dibujar_recibo_seguro(
            p, example(method), 1.5 * cm, 29.1 * cm,
            "COMPROBANTE DEL ASEGURADO",
            {
                "codigo": "0123456789ABCDEF0123456789ABCDEF",
                "url": "https://fortex.example.invalid/recibos/verificar/",
                "fecha_pago_declarada": "2026-11-13",
                "fecha_registro": "2026-11-13T12:00:00-03:00",
                "fecha_emision": "2026-11-13T12:15:00-03:00",
                "importe_original": "40000.00",
            },
        )
        p.showPage()
        p.save()
        data = output.getvalue()
        assert data.startswith(b"%PDF")
        document = PdfReader(BytesIO(data))
        assert len(document.pages) == 1
        text = document.pages[0].extract_text()
        for expected in ("FORTEX", "VERIFICACIÓN INTERNA", "0123456789ABCDEF0123456789ABCDEF", "40000,00"):
            assert expected in text, (method, expected, text[:400])
        assert ("PAGADO" in text) == watermark, ("marca de agua", method)
        (target / f"recibo_sintetico_{method.lower()}.pdf").write_bytes(data)
        print(f"{method}: PASS, PDF bytes={len(data)}, PAGADO={watermark}")


if __name__ == "__main__":
    main()
