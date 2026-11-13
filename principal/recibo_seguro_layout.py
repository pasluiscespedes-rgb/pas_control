"""Formato compacto del recibo seguro FORTEX (18 x 8,65 cm).

Sólo presentación. No consulta la base, ni genera firmas, ni altera registros.
El QR apunta al verificador oficial y el código coincide con el registro firmado.
"""
from decimal import Decimal, InvalidOperation
from pathlib import Path

from dateutil.relativedelta import relativedelta
from django.conf import settings
from reportlab.graphics import barcode
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader


NAVY = colors.HexColor("#092C52")
INK = colors.HexColor("#152B46")
BLUE = colors.HexColor("#0578CE")
LINE = colors.HexColor("#B9CFE3")
SOFT = colors.HexColor("#F1F6FB")
GREY = colors.HexColor("#506178")


def _fecha(valor):
    if hasattr(valor, "strftime"):
        return valor.strftime("%d/%m/%Y")
    return str(valor or "").split("T")[0]


def _dinero(valor):
    try:
        numero = Decimal(str(valor)).quantize(Decimal("0.01"))
        return "$ " + f"{numero:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    except (InvalidOperation, ValueError):
        return "$ " + str(valor or "")


def _texto(p, texto, x, y, ancho, tam=7.0, fuerte=False, minimo=4.7):
    fuente = "Helvetica-Bold" if fuerte else "Helvetica"
    texto = str(texto if texto is not None else "")
    while p.stringWidth(texto, fuente, tam) > ancho and tam > minimo:
        tam -= 0.15
    p.setFont(fuente, max(tam, minimo))
    p.drawString(x, y, texto)


def _campo(p, etiqueta, valor, pos_x, pos_y, ancho, tam_valor=7):
    p.setFillColor(NAVY)
    _texto(p, etiqueta, pos_x, pos_y, ancho, 6.0, True)
    p.setFillColor(INK)
    _texto(p, valor, pos_x, pos_y - 0.24 * cm, ancho, tam_valor, True)


def _marco(p, x, y, ancho, alto, radio=0.10):
    p.setStrokeColor(LINE)
    p.setLineWidth(0.65)
    p.roundRect(x, y, ancho, alto, radio * cm, fill=0, stroke=1)


def dibujar_recibo_seguro(p, recibo, x, y, copia, verificacion):
    """x/y son la esquina superior izquierda. 'verificacion' no contiene secretos."""
    if not verificacion or not verificacion.get("codigo") or not verificacion.get("url"):
        raise ValueError("La presentación segura requiere código y URL reales.")

    poliza = recibo.poliza
    cliente = poliza.cliente
    vehiculo = poliza.vehiculo
    ancho, alto = 18.0 * cm, 8.65 * cm
    X = lambda n: x + n * cm
    Y = lambda n: y - n * cm

    p.saveState()
    try:
        p.setFillColor(colors.white)
        p.setStrokeColor(NAVY)
        p.setLineWidth(1)
        p.roundRect(x, Y(8.65), ancho, alto, 0.16 * cm, fill=1, stroke=1)

        # Encabezado plateado con cortes diagonales azul eléctrico.
        clip = p.beginPath()
        clip.roundRect(x + 0.5, Y(1.40), ancho - 1, 1.40 * cm - 0.5, 0.13 * cm)
        p.saveState()
        p.clipPath(clip, stroke=0, fill=0)
        for indice in range(22):
            gris = 0.94 + (indice / 21) * 0.055
            p.setFillColor(colors.Color(gris, gris + 0.005 if gris <= 0.995 else 1, 1))
            p.rect(x, Y(1.40) + indice * 1.40 * cm / 22,
                   ancho, 1.40 * cm / 22 + 1, fill=1, stroke=0)
        p.setFillColor(colors.HexColor("#E0E9F2"))
        trazado = p.beginPath()
        trazado.moveTo(X(8.65), Y(1.39)); trazado.lineTo(X(9.48), Y(1.39))
        trazado.lineTo(X(11.25), Y(0)); trazado.lineTo(X(10.56), Y(0))
        trazado.close()
        p.drawPath(trazado, fill=1, stroke=0)
        for izquierda in (True, False):
            p.setFillColor(BLUE)
            t = p.beginPath()
            if izquierda:
                t.moveTo(X(0.0), Y(1.40)); t.lineTo(X(0.50), Y(1.40))
                t.lineTo(X(0.0), Y(0.88))
            else:
                t.moveTo(X(18.0), Y(0.84)); t.lineTo(X(18.0), Y(1.40))
                t.lineTo(X(17.48), Y(1.40))
            t.close()
            p.drawPath(t, fill=1, stroke=0)
        p.restoreState()

        logo = Path(settings.BASE_DIR) / "principal" / "static" / "principal" / "img" / "fortex_logo_redondo.png"
        p.saveState()
        logo_clip = p.beginPath()
        logo_clip.circle(X(1.185), Y(0.755), 0.535 * cm)
        p.clipPath(logo_clip, stroke=0, fill=0)
        p.drawImage(ImageReader(str(logo)), X(0.65), Y(1.29),
                    width=1.07 * cm, height=1.07 * cm,
                    preserveAspectRatio=True, mask="auto")
        p.restoreState()

        p.setFillColor(INK)
        p.setFont("Helvetica-Bold", 21)
        p.drawString(X(2.0), Y(0.57), "FORTEX")
        p.setFont("Helvetica-Bold", 7.3)
        p.drawString(X(2.02), Y(0.85), "GESTIÓN INTEGRAL DE RIESGOS")
        p.setFont("Helvetica", 5.7)
        p.drawString(X(2.02), Y(1.08), "PRODUCTOR ASESOR DE SEGUROS")
        p.setStrokeColor(BLUE)
        p.setLineWidth(0.75)
        p.line(X(11.8), Y(0.13), X(11.8), Y(1.28))
        p.setFillColor(INK)
        p.setFont("Helvetica-Bold", 12)
        p.drawRightString(X(17.54), Y(0.54), "RECIBO DE PAGO")
        numero = str(getattr(recibo, "numero_recibo", None) or recibo.id)
        if numero.isdigit():
            numero = numero.zfill(7)
        p.setFont("Helvetica-Bold", 11)
        p.drawRightString(X(17.54), Y(1.02), "N.º " + numero)

        # Franja informativa de ancho completo.
        p.setFillColor(SOFT)
        p.rect(X(0.14), Y(1.73), 17.72 * cm, 0.29 * cm, fill=1, stroke=0)
        p.setFillColor(INK)
        _texto(p, "Administradores de Riesgos", X(0.3), Y(1.63), 5 * cm, 6.0, True)
        _texto(p, "WhatsFORTEX: +54 9 381 634-6504", X(6.25), Y(1.63), 6.4 * cm, 6.0, True)
        p.setFont("Helvetica-Bold", 6.0)
        p.drawRightString(X(17.75), Y(1.63), "Fecha del recibo: " + _fecha(recibo.fecha))

        # Asegurado y detalle del pago.
        _marco(p, X(0.14), Y(3.53), 17.72 * cm, 1.77 * cm)
        p.setFillColor(NAVY)
        p.roundRect(X(0.16), Y(2.10), 17.68 * cm, 0.31 * cm,
                    0.07 * cm, fill=1, stroke=0)
        p.setFillColor(colors.white)
        _texto(p, "RECIBIMOS DE:  " + str(cliente.apellido).upper() + ", " +
               str(cliente.nombre).upper(), X(0.34), Y(2.01),
               16.9 * cm, 7.2, True)
        _campo(p, "ASEGURADORA", str(poliza.compania).upper(),
               X(0.34), Y(2.34), 11.9 * cm, 7)
        _campo(p, "PÓLIZA N.º", poliza.numero_poliza or "PROVISORIA",
               X(0.34), Y(3.08), 11.9 * cm, 7.0)
        p.setStrokeColor(LINE)
        p.line(X(12.96), Y(2.13), X(12.96), Y(3.45))
        p.line(X(14.65), Y(2.13), X(14.65), Y(3.45))
        cuotas = (str(recibo.numero_cuota) if recibo.cantidad_cuotas <= 1 else
                  f"{recibo.numero_cuota} - {recibo.numero_cuota + recibo.cantidad_cuotas - 1}")
        _campo(p, "CUOTAS", cuotas, X(13.18), Y(2.38), 1.3 * cm, 9)
        _campo(p, "IMPORTE", _dinero(recibo.importe),
               X(14.9), Y(2.38), 2.75 * cm, 10)

        # Riesgo asegurado. No suponer que todas las pólizas tienen vehículo.
        _marco(p, X(0.14), Y(5.02), 17.72 * cm, 1.44 * cm)
        if str(recibo.forma_pago or "").strip().lower() in {"transferencia", "tarjeta", "cbu"}:
            p.saveState()
            marca_clip = p.beginPath()
            marca_clip.roundRect(X(0.19), Y(4.99), 17.62 * cm, 1.40 * cm, 0.08 * cm)
            p.clipPath(marca_clip, stroke=0, fill=0)
            p.translate(X(8.8), Y(4.48))
            p.rotate(22)
            p.setFillColor(colors.HexColor("#A7B4C3"))
            p.setFont("Helvetica-Bold", 27)
            p.drawCentredString(0, 0, "PAGADO")
            p.restoreState()
        p.setFillColor(SOFT)
        p.rect(X(0.19), Y(3.96), 17.62 * cm, 0.32 * cm, fill=1, stroke=0)
        p.setFillColor(NAVY)
        _texto(p, "VEHÍCULO:" if vehiculo else "RIESGO:",
               X(0.34), Y(3.85), 1.7 * cm, 6.8, True)
        descripcion = (f"{vehiculo.marca} {vehiculo.modelo}" if vehiculo else
                       getattr(poliza, "tipo_seguro", "Sin vehículo"))
        p.setFillColor(INK)
        _texto(p, descripcion, X(2.05), Y(3.85), 15.35 * cm, 7.2, True)
        p.setStrokeColor(LINE)
        p.line(X(5.18), Y(4.06), X(5.18), Y(4.97))
        p.line(X(10.30), Y(4.06), X(10.30), Y(4.97))
        _campo(p, "PATENTE", getattr(vehiculo, "patente", "No aplica"),
               X(0.34), Y(4.37), 4.55 * cm, 7)
        _campo(p, "MOTOR", getattr(vehiculo, "motor", "No aplica"),
               X(5.47), Y(4.37), 4.5 * cm, 7)
        _campo(p, "CHASIS", getattr(vehiculo, "chasis", "No aplica"),
               X(10.60), Y(4.37), 6.8 * cm, 7)

        _marco(p, X(0.14), Y(5.69), 17.72 * cm, 0.62 * cm)
        p.setStrokeColor(LINE)
        p.line(X(5.55), Y(5.1), X(5.55), Y(5.66))
        p.line(X(12.42), Y(5.1), X(12.42), Y(5.66))
        inicio = poliza.fecha_alta
        vencimiento = inicio + relativedelta(
            months=recibo.numero_cuota + recibo.cantidad_cuotas - 1)
        _campo(p, "FECHA DE ALTA", _fecha(inicio),
               X(0.34), Y(5.27), 4.75 * cm, 6.5)
        _campo(p, "VENCIMIENTO DE CUOTA", _fecha(vencimiento),
               X(5.84), Y(5.27), 6.05 * cm, 6.5)
        _campo(p, "USO", getattr(vehiculo, "uso", "No aplica"),
               X(12.70), Y(5.27), 4.75 * cm, 6.5)

        _marco(p, X(0.14), Y(6.35), 17.72 * cm, 0.61 * cm)
        p.setStrokeColor(LINE)
        p.line(X(5.05), Y(5.76), X(5.05), Y(6.32))
        _campo(p, "FORMA DE PAGO", recibo.forma_pago,
               X(0.34), Y(5.93), 4.35 * cm, 6.4)
        p.setFillColor(INK)
        _texto(p, "PAS RESPONSABLE: LUIS ERNESTO CÉSPEDES OCHOA",
               X(5.35), Y(6.02), 11.9 * cm, 6.1, True)
        p.setFillColor(NAVY)
        _texto(p, "MATRÍCULA SSN N.º 104752", X(5.35), Y(6.27), 10 * cm, 6.1, True)

        p.setFillColor(NAVY)
        p.roundRect(X(0.15), Y(6.68), 17.70 * cm, 0.34 * cm,
                    0.05 * cm, fill=1, stroke=0)
        p.setFillColor(colors.white)
        p.setFont("Helvetica-Bold", 7)
        p.drawCentredString(X(9), Y(6.60), copia)

        # Verificación real, dentro del formato. El QR NO incluye datos personales.
        _marco(p, X(0.14), Y(8.49), 17.72 * cm, 1.79 * cm)
        qr = barcode.createBarcodeDrawing(
            "QR", value=verificacion["url"],
            width=1.27 * cm, height=1.27 * cm)
        qr.drawOn(p, X(0.35), Y(8.24))
        p.setFillColor(NAVY)
        _texto(p, "VERIFICACIÓN INTERNA FORTEX",
               X(1.91), Y(6.98), 12 * cm, 7.2, True)
        p.setFillColor(INK)
        _texto(p, "Código: " + verificacion["codigo"],
               X(1.91), Y(7.25), 15.3 * cm, 6.5, True)
        _texto(p, "Pago declarado: " + str(verificacion["fecha_pago_declarada"]) +
               "  |  Registro del cobro: " + str(verificacion["fecha_registro"]),
               X(1.91), Y(7.48), 15.3 * cm, 5.65)
        _texto(p, "Emisión PDF: " + str(verificacion["fecha_emision"]),
               X(1.91), Y(7.69), 15.3 * cm, 5.65)
        _texto(p, "Importe asentado: " + str(verificacion["importe_original"]),
               X(1.91), Y(7.90), 15.3 * cm, 5.65)
        p.setFillColor(NAVY)
        _texto(p, "Escanee el QR y presente el PDF completo con el código.",
               X(1.91), Y(8.11), 15.3 * cm, 5.9)
        _texto(p, "Solo cotejo documental. No certifica cobertura ni vigencia de la póliza.",
               X(1.91), Y(8.33), 15.3 * cm, 5.8, True)
    finally:
        p.restoreState()
