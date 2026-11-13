"""Autenticidad v1. No lee configuración externa ni modifica cobros."""
import hashlib
import hmac
import io
import json
import re
import secrets
from datetime import date
from types import SimpleNamespace

from django.conf import settings
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from .configuracion import identificador_clave_valido, url_verificador

AVISO = 'Sólo coteja el documento. No certifica cobertura ni vigencia de la póliza.'


def codigo_seguro():
    return secrets.token_hex(16).upper()


def firmar(datos, key_id):
    if not identificador_clave_valido(key_id):
        raise ValidationError('Identificador de clave de autenticidad inválido.')
    keys = getattr(settings, 'FORTEX_RECEIPT_KEYS', {})
    key = keys.get(key_id) if isinstance(keys, dict) else None
    if not isinstance(key, str) or len(key.encode()) < 32:
        raise ValidationError('Falta una clave dedicada de autenticidad (mínimo 32 bytes).')
    raw = json.dumps(datos, sort_keys=True, separators=(',', ':'), ensure_ascii=True).encode()
    return hmac.new(key.encode(), raw, hashlib.sha256).hexdigest()


def carga(registro):
    return {'version': 1, 'codigo': registro.codigo, 'recibo_id': registro.recibo_id,
            'cobro_id': registro.cobro_id, 'original': registro.original}


def manifiesto(registro):
    return {**carga(registro), 'emision': registro.fecha_emision.isoformat(),
            'sha256_pdf': registro.sha256_pdf}


def integro(registro):
    try:
        return hmac.compare_digest(registro.firma, firmar(carga(registro), registro.key_id))
    except ValidationError:
        return False


@transaction.atomic
def capturar(recibo, cobro):
    """Sólo en la transacción del cobro nuevo; nunca inferir enlaces históricos."""
    from .models import AutenticidadRecibo
    if (recibo.poliza_id != cobro.poliza_id or recibo.importe != cobro.importe
            or recibo.numero_cuota != cobro.cuota
            or recibo.cantidad_cuotas != cobro.cantidad_cuotas
            or recibo.forma_pago != cobro.forma_pago or cobro.anulado):
        raise ValidationError('El recibo no corresponde al cobro.')
    p = recibo.poliza
    v = p.vehiculo
    original = {
        'id': recibo.pk, 'numero_recibo': recibo.numero_recibo,
        'fecha': recibo.fecha.isoformat(), 'importe': format(recibo.importe, '.2f'),
        'numero_cuota': recibo.numero_cuota, 'cantidad_cuotas': recibo.cantidad_cuotas,
        'forma_pago': recibo.forma_pago,
        'fecha_pago_declarada': cobro.fecha_pago.isoformat(),
        'fecha_registro': cobro.fecha_registro.isoformat() if cobro.fecha_registro else None,
        'poliza': {'id': p.pk, 'tipo_seguro': p.tipo_seguro,
                   'numero_poliza': p.numero_poliza, 'compania': p.compania,
                   'fecha_alta': p.fecha_alta.isoformat(),
                   'cliente': {'apellido': p.cliente.apellido, 'nombre': p.cliente.nombre},
                   'vehiculo': None if v is None else {k: getattr(v, k, '') for k in
                                ('marca', 'modelo', 'patente', 'motor', 'chasis', 'uso')}},
    }
    r = AutenticidadRecibo(recibo=recibo, cobro=cobro, original=original,
                          key_id=getattr(settings, 'FORTEX_RECEIPT_ACTIVE_KEY', ''))
    r.firma = firmar(carga(r), r.key_id)
    r.save(force_insert=True)
    from .permisos import autorizar_emisor
    autorizar_emisor(recibo, cobro)
    return r


def objeto_recibo(original):
    d = dict(original)
    d['fecha'] = date.fromisoformat(d['fecha'])
    p = dict(d['poliza'])
    p['fecha_alta'] = date.fromisoformat(p['fecha_alta'])
    p['cliente'] = SimpleNamespace(**p['cliente'])
    p['vehiculo'] = SimpleNamespace(**p['vehiculo']) if p['vehiculo'] is not None else None
    d['poliza'] = SimpleNamespace(**p)
    return SimpleNamespace(**d)


@transaction.atomic
def emitir(recibo_id, *, usuario=None):
    from .models import AutenticidadRecibo
    from principal.fortex_pdf import dibujar_recibo_fortex
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import cm
    from reportlab.graphics.barcode import createBarcodeDrawing
    from cobros.models import Cobro
    cobro_id = AutenticidadRecibo.objects.values_list("cobro_id", flat=True).get(recibo_id=recibo_id)
    cobro = Cobro.objects.select_for_update().get(pk=cobro_id)
    r = AutenticidadRecibo.objects.select_for_update().get(recibo_id=recibo_id)
    if usuario is not None:
        from .permisos import puede_emitir_recibo
        r.cobro = cobro
        if not puede_emitir_recibo(usuario, r):
            raise PermissionDenied
    if not integro(r):
        raise ValidationError('Registro de autenticidad inconsistente.')
    if estado_anulacion(r):
        raise ValidationError('Comprobante anulado; no se permite emitir.')
    if r.fecha_emision:
        if not pdf_integro(r):
            raise ValidationError('PDF almacenado inconsistente.')
        return bytes(r.pdf)
    verifier_url = url_verificador()
    r.fecha_emision = timezone.now()
    output = io.BytesIO()
    p = canvas.Canvas(output, pagesize=A4)
    dibujar_recibo_fortex(p, objeto_recibo(r.original), 1.50*cm, 29.1*cm,
                         'COMPROBANTE DEL ASEGURADO')
    p.setFont('Helvetica', 7)
    lines = [
        'Verificación FORTEX: ' + r.codigo,
        'Pago declarado: ' + r.original['fecha_pago_declarada'] + ' | Registro del cobro: ' +
        (r.original['fecha_registro'] or 'NO CONSTA'),
        'Emisión PDF: ' + r.fecha_emision.isoformat(),
        'Escanee el QR y presente el PDF completo con el código.',
        AVISO,
    ]
    for i, line in enumerate(lines):
        p.drawString(1.9*cm, (19.9-i*0.35)*cm, line)
    qr = createBarcodeDrawing('QR', value=verifier_url, width=3.2*cm, height=3.2*cm)
    qr.drawOn(p, 1.9*cm, 15*cm)
    p.showPage()
    p.save()
    r.pdf = output.getvalue()
    r.sha256_pdf = hashlib.sha256(r.pdf).hexdigest()
    r.firma_pdf = firmar(manifiesto(r), r.key_id)
    # Única transición de emisión; snapshot y firma original no se reescriben.
    AutenticidadRecibo.objects.filter(pk=r.pk, fecha_emision__isnull=True).update(
        fecha_emision=r.fecha_emision, pdf=r.pdf, sha256_pdf=r.sha256_pdf, firma_pdf=r.firma_pdf)
    return r.pdf


def pdf_integro(r):
    try:
        return bool(r.fecha_emision and r.pdf and
                    hmac.compare_digest(r.sha256_pdf, hashlib.sha256(bytes(r.pdf)).hexdigest()) and
                    hmac.compare_digest(r.firma_pdf, firmar(manifiesto(r), r.key_id)))
    except (ValidationError, ValueError, TypeError):
        return False


def estado_anulacion(r):
    from cobros.models import Cobro
    from .models import AnulacionDocumento
    return (AnulacionDocumento.objects.filter(registro=r).exists()
            or Cobro.objects.filter(pk=r.cobro_id, anulado=True).exists())


def verificar(codigo, archivo):
    """Resultado mínimo: jamás publica el snapshot ni datos del cliente."""
    from .models import AutenticidadRecibo
    if not re.fullmatch(r'[A-F0-9]{32}', codigo):
        return 'NO_VERIFICABLE'
    r = AutenticidadRecibo.objects.filter(codigo=codigo).first()
    if r is None:
        return 'NO_VERIFICABLE'
    if not integro(r) or not pdf_integro(r):
        return 'REGISTRO_INCONSISTENTE'
    if not hmac.compare_digest(hashlib.sha256(archivo).hexdigest(), r.sha256_pdf):
        return 'DOCUMENTO_NO_COINCIDE'
    if estado_anulacion(r):
        return 'ANULADO'
    return 'AUTENTICO'


@transaction.atomic
def anular_documento(registro, usuario, motivo):
    from .models import AnulacionDocumento
    from .permisos import puede_ver_recibo
    if not usuario.has_perm('recibos.anular_documento') or not puede_ver_recibo(usuario, registro.recibo_id):
        raise PermissionDenied
    if not motivo.strip():
        raise ValidationError('Indicar motivo de anulación.')
    from cobros.models import Cobro
    from .models import AutenticidadRecibo
    Cobro.objects.select_for_update().get(pk=registro.cobro_id)
    registro = AutenticidadRecibo.objects.select_for_update().get(pk=registro.pk)
    return AnulacionDocumento.objects.create(registro=registro, usuario=usuario, motivo=motivo)
