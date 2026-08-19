from reportlab.lib.units import cm
from reportlab.lib.utils import ImageReader
from django.conf import settings
import os
from reportlab.lib import colors
from dateutil.relativedelta import relativedelta

AZUL = colors.HexColor("#0B3D91")
NEGRO = colors.HexColor("#111827")
GRIS = colors.HexColor("#4B5563")


def texto_ajustado(p, texto, x, y, ancho_max, fuente="Helvetica", tam=7):
    texto = str(texto or "")
    while p.stringWidth(texto, fuente, tam) > ancho_max and tam > 5:
        tam -= 0.3
    p.setFont(fuente, tam)
    p.drawString(x, y, texto)


def campo(p, titulo, valor, x, y, ancho, desplazar_valor=0):
    p.setFillColor(AZUL)
    p.setFont("Helvetica-Bold", 7)
    p.drawString(x, y, titulo)

    p.setFillColor(NEGRO)
    texto_ajustado(
    p,
    valor,
    x + desplazar_valor,
    y - 0.35 * cm,
    ancho,
    "Helvetica-Bold",
    7.5
)


def dibujar_marca_fortex(p, x, y):
    # Espacio para logo
    logo_path = os.path.join(
    settings.BASE_DIR,
    "principal",
    "static",
    "principal",
    "img",
    "fortex_logo.png"
)

    p.drawImage(
    ImageReader(logo_path),
    x - 0.15 * cm,
    y - 1.20 * cm,
    width=1.80 * cm,
    height=1.80* cm,
    preserveAspectRatio=True,
    mask="auto"
)

    texto_x = x + 1.55 * cm

    p.setFillColor(AZUL)
    p.setFont("Helvetica-Bold", 20)
    p.drawString(texto_x, y, "FORTEX")

    p.setFillColor(NEGRO)
    p.setFont("Helvetica-Bold", 7.5)
    p.drawString(texto_x, y - 0.45 * cm, "GESTIÓN INTEGRAL")

    p.setFillColor(GRIS)
    p.setFont("Helvetica", 7.5)
    p.drawString(texto_x, y - 0.78 * cm, "Administradores de Riesgos")

    p.setFillColor(AZUL)
    p.setFont("Helvetica-Bold", 7)
    p.drawString(texto_x, y - 1.10 * cm, "WhatsApp: 381-0000000")

    p.setFillColor(NEGRO)


def dibujar_recibo_fortex(p, recibo, x, y, copia):
    poliza = recibo.poliza
    cliente = poliza.cliente
    vehiculo = poliza.vehiculo

    ancho = 9.85 * cm
    alto = 8.65 * cm

    # Marca de agua PAGADO para pagos electrónicos
    if recibo.forma_pago in ("Transferencia", "Tarjeta", "CBU"):
     p.saveState()

     p.setFillColor(colors.lightgrey)
     p.setFont("Helvetica-Bold", 28)

     centro_x = x + ancho / 2
     centro_y = y - alto / 2

     p.translate(centro_x, centro_y)
     p.rotate(35)

     p.drawCentredString(0, 0, "PAGADO")

     p.restoreState()

    p.setStrokeColor(AZUL)
    p.roundRect(x, y - alto, ancho, alto, 6)

    # Encabezado
    dibujar_marca_fortex(p, x + 0.25 * cm, y - 0.85 * cm)

    p.setFillColor(NEGRO)
    p.setFont("Helvetica-Bold", 8)
    p.drawRightString(x + ancho - 0.25 * cm, y - 0.50 * cm, "RECIBO DE PAGO")

    p.setStrokeColor(AZUL)
    p.line(x + 7.05 * cm, y - 0.68 * cm, x + ancho - 0.25 * cm, y - 0.68 * cm)

    p.setFont("Helvetica", 8)
    p.drawRightString(x + ancho - 0.25 * cm, y - 1.20 * cm, f"N° {recibo.id:07d}")
    p.drawRightString(x + ancho - 0.25 * cm, y - 1.65 * cm, f"Fecha: {recibo.fecha}")

    # Caja cliente
    y1 = y - 2.25 * cm
    p.setStrokeColor(AZUL)
    p.roundRect(x + 0.18 * cm, y1 - 1.85 * cm, ancho - 0.36 * cm, 1.75 * cm, 5)

    campo(p, "RECIBIMOS DE:", f"{cliente.apellido}, {cliente.nombre}", x + 0.40 * cm, y1 - 0.35 * cm, 4.2 * cm)
    campo(p, "ASEGURADORA:", str(poliza.compania).upper(), x + 0.40 * cm, y1 - 0.95 * cm, 3.9 * cm)
    campo(p, "PÓLIZA N°:", poliza.numero_poliza or "PROVISORIA", x + 0.40 * cm, y1 - 1.50 * cm, 2.2 * cm)
    if recibo.cantidad_cuotas > 1:
        cuotas_texto = f"{recibo.numero_cuota} - {recibo.numero_cuota + recibo.cantidad_cuotas - 1}"
    else:
        cuotas_texto = str(recibo.numero_cuota)
    campo(p, "CUOTAS:", cuotas_texto, x + 6.20 * cm, y1 - 1.05 * cm, 1.0 * cm, 0.45*cm)
    campo(p, "IMPORTE:", f"$ {recibo.importe}", x + 7.55 * cm, y1 - 1.05 * cm, 2.0 * cm)

    # Caja vehículo
    y2 = y - 4.45 * cm
    p.roundRect(x + 0.18 * cm, y2 - 1.75 * cm, ancho - 0.36 * cm, 1.65 * cm, 5)

    p.setFillColor(AZUL)
    p.setFont("Helvetica-Bold", 7)
    p.drawString(x + 0.40 * cm, y2 - 0.45 * cm, "VEHÍCULO:")

    p.setFillColor(NEGRO)
    texto_ajustado(
        p,
        f"{vehiculo.marca} {vehiculo.modelo}",
        x + 1.85 * cm,
        y2 - 0.45 * cm,
        7.3 * cm,
        "Helvetica-Bold",
        7.5
    )

    p.setStrokeColor(colors.lightgrey)
    p.line(x + 0.40 * cm, y2 - 0.75 * cm, x + ancho - 0.40 * cm, y2 - 0.75 * cm)

    campo(p, "PATENTE", vehiculo.patente, x + 0.40 * cm, y2 - 1.10 * cm, 2.0 * cm)
    campo(p, "MOTOR", vehiculo.motor, x + 3.00 * cm, y2 - 1.10 * cm, 2.5 * cm)
    campo(p, "CHASIS", vehiculo.chasis, x + 6.20 * cm, y2 - 1.10 * cm, 3.2 * cm)

    # Caja fechas
    y3 = y - 6.45 * cm
    p.setStrokeColor(AZUL)
    p.roundRect(x + 0.18 * cm, y3 - 0.95 * cm, ancho - 0.36 * cm, 0.85 * cm, 5)

    campo(p, "FECHA DE ALTA:", poliza.fecha_alta, x + 0.40 * cm, y3 - 0.38 * cm, 2.4 * cm)
    vencimiento_recibo = poliza.fecha_alta + relativedelta(months=recibo.numero_cuota + recibo.cantidad_cuotas - 1)
    campo(p, "VENCIMIENTO:", vencimiento_recibo, x + 3.55 * cm, y3 - 0.38 * cm, 2.4 * cm)
    campo(p, "USO:", getattr(vehiculo, "uso", "Particular"), x + 6.75 * cm, y3 - 0.38 * cm, 2.3 * cm)

    # Caja pago
    y4 = y - 7.65 * cm
    p.roundRect(x + 0.18 * cm, y4 - 0.75 * cm, ancho - 0.36 * cm, 0.65 * cm, 5)

    p.setFillColor(AZUL)
    p.setFont("Helvetica-Bold", 7)
    p.drawString(x + 0.40 * cm, y4 - 0.30 * cm, "FORMA DE PAGO:")

    p.setFillColor(NEGRO)
    p.setFont("Helvetica-Bold", 7.5)
    p.drawString(x + 2.90 * cm, y4 - 0.30 * cm, str(recibo.forma_pago or ""))

    # Firma
    p.setStrokeColor(AZUL)
    p.line(x + 6.10 * cm, y4 - 0.35 * cm, x + 9.40 * cm, y4 - 0.35 * cm)

    p.setFillColor(NEGRO)
    p.setFont("Helvetica", 6)
    p.drawCentredString(x + 7.75 * cm, y4 - 0.60 * cm, "Firma y Aclaración")

    # Etiqueta
    p.setFillColor(AZUL)
    p.roundRect(x + 0.35 * cm, y - 8.55 * cm, 3.6 * cm, 0.42 * cm, 4, fill=1)

    p.setFillColor(colors.white)
    p.setFont("Helvetica-Bold", 8)
    p.drawCentredString(x + 2.15 * cm, y - 8.40 * cm, copia)

    p.setFillColor(NEGRO)