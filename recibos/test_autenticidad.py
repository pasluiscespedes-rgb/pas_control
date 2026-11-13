import hashlib
import io
from datetime import date
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.test import TestCase, override_settings
from django.utils import timezone
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm

from clientes.models import Cliente
from vehiculos.models import Vehiculo
from polizas.models import Poliza
from cobros.models import Cobro
from principal.models import TurnoCaja, MovimientoCliente
from principal.fortex_pdf import dibujar_recibo_fortex
from .models import Recibo, AutenticidadRecibo
from .autenticidad import (capturar, emitir, verificar, objeto_recibo, anular_documento, integro)


class AutenticidadTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username='operador_sintetico')
        self.cliente = Cliente.objects.create(nombre='Cliente', apellido='SINTETICO', dni='TEST-000')
        self.vehiculo = Vehiculo.objects.create(cliente=self.cliente, patente='TEST000',
                marca='Sintetica', modelo='Prueba', motor='MOTOR-TEST', chasis='CHASIS-TEST')
        self.poliza = Poliza.objects.create(cliente=self.cliente, vehiculo=self.vehiculo,
                compania='ASEGURADORA SINTETICA', numero_poliza='POL-TEST',
                fecha_alta=date(2026, 1, 1), periodicidad='Anual')
        self.cobro = Cobro.objects.create(cliente=self.cliente, poliza=self.poliza,
                fecha_pago=date(2026, 1, 2), importe='12345.67', registrado_por=self.user)
        self.recibo = Recibo.objects.create(poliza=self.poliza, importe='12345.67')
        self.recibo.refresh_from_db()
        self.cobro.refresh_from_db()
        self.registro = capturar(self.recibo, self.cobro)

    def test_autentico_y_reimpresion_identica(self):
        pdf = emitir(self.recibo.pk)
        self.assertTrue(pdf.startswith(b'%PDF'))
        self.assertEqual(verificar(self.registro.codigo, pdf), 'AUTENTICO')
        self.assertEqual(emitir(self.recibo.pk), pdf)
        r = AutenticidadRecibo.objects.get(pk=self.registro.pk)
        self.assertEqual(r.original['fecha_pago_declarada'], '2026-01-02')
        self.assertEqual(r.original['fecha_registro'], self.cobro.fecha_registro.isoformat())
        self.assertGreaterEqual(r.fecha_emision, self.cobro.fecha_registro)

    def adulterado(self, campo, valor):
        emitir(self.recibo.pk)
        import copy
        datos = copy.deepcopy(self.registro.original)
        datos[campo] = valor
        out = io.BytesIO()
        p = canvas.Canvas(out, pagesize=A4)
        dibujar_recibo_fortex(p, objeto_recibo(datos), 1.5*cm, 29.1*cm, 'COMPROBANTE DEL ASEGURADO')
        p.setFont('Helvetica', 7)
        p.drawString(40, 550, 'Verificacion FORTEX: ' + self.registro.codigo)
        p.showPage(); p.save()
        return out.getvalue()

    def test_fecha_recibo_adulterada(self):
        self.assertEqual(verificar(self.registro.codigo, self.adulterado('fecha', '2025-12-01')),
                         'DOCUMENTO_NO_COINCIDE')

    def test_importe_adulterado(self):
        self.assertEqual(verificar(self.registro.codigo, self.adulterado('importe', '99999.99')),
                         'DOCUMENTO_NO_COINCIDE')

    def test_adulteraciones_puntuales_pdf_con_codigo_intacto(self):
        # Streams sin compresión sólo en esta prueba: reemplazos de igual longitud
        # conservan PDF válido, xref y código; cada caso altera un único campo.
        real_canvas = canvas.Canvas
        with patch('reportlab.pdfgen.canvas.Canvas', side_effect=lambda *a, **kw:
                   real_canvas(*a, **kw, pageCompression=0)):
            pdf = emitir(self.recibo.pk)
        r = AutenticidadRecibo.objects.get(pk=self.registro.pk)
        cambios = [
            (b'2026-01-02', b'2025-01-02'),
            (r.original['fecha_registro'].encode(),
             ('2025' + r.original['fecha_registro'][4:]).encode()),
            (r.fecha_emision.isoformat().encode(),
             ('2025' + r.fecha_emision.isoformat()[4:]).encode()),
            (b'12345.67', b'99999.99'),
        ]
        for anterior, nuevo in cambios:
            with self.subTest(campo=anterior):
                self.assertIn(anterior, pdf)
                alterado = pdf.replace(anterior, nuevo, 1)
                self.assertIn(r.codigo.encode(), alterado)
                self.assertEqual(len(alterado), len(pdf))
                self.assertEqual(verificar(r.codigo, alterado), 'DOCUMENTO_NO_COINCIDE')

    def test_rotacion_claves_retiene_verificacion(self):
        pdf = emitir(self.recibo.pk)
        keys = {**settings.FORTEX_RECEIPT_KEYS, 'synthetic-v2': 'SYNTHETIC-KEY-V2-' + '0'*32}
        with override_settings(FORTEX_RECEIPT_KEYS=keys, FORTEX_RECEIPT_ACTIVE_KEY='synthetic-v2'):
            self.assertEqual(verificar(self.registro.codigo, pdf), 'AUTENTICO')

    def test_cambio_byte_documento_detectado(self):
        pdf = emitir(self.recibo.pk)
        self.assertEqual(verificar(self.registro.codigo, pdf + b'\n% alterado'), 'DOCUMENTO_NO_COINCIDE')

    def test_cobro_anulado(self):
        pdf = emitir(self.recibo.pk)
        Cobro.objects.filter(pk=self.cobro.pk).update(anulado=True)
        self.assertEqual(verificar(self.registro.codigo, pdf), 'ANULADO')
        with self.assertRaises(ValidationError): emitir(self.recibo.pk)

    def test_poliza_anulada(self):
        pdf = emitir(self.recibo.pk)
        Poliza.objects.filter(pk=self.poliza.pk).update(estado='Anulada')
        # La autenticidad documental no expresa estado ni vigencia de la póliza.
        self.assertEqual(verificar(self.registro.codigo, pdf), 'AUTENTICO')

    def test_anulacion_documental_con_permiso(self):
        pdf = emitir(self.recibo.pk)
        with self.assertRaises(PermissionDenied): anular_documento(self.registro, self.user, 'Prueba')
        self.user.user_permissions.add(Permission.objects.get(codename='anular_documento'))
        user = get_user_model().objects.get(pk=self.user.pk)
        anular_documento(self.registro, user, 'Prueba sintética')
        self.assertEqual(verificar(self.registro.codigo, pdf), 'ANULADO')
        self.cobro.refresh_from_db()
        self.assertFalse(self.cobro.anulado)

    def test_snapshot_adulterado_en_db(self):
        pdf = emitir(self.recibo.pk)
        d = dict(self.registro.original); d['importe'] = '1.00'
        AutenticidadRecibo.objects.filter(pk=self.registro.pk).update(original=d)
        self.assertEqual(verificar(self.registro.codigo, pdf), 'REGISTRO_INCONSISTENTE')

    def test_hash_y_pdf_adulterados_en_db(self):
        pdf = emitir(self.recibo.pk) + b'\n% cambio'
        AutenticidadRecibo.objects.filter(pk=self.registro.pk).update(
            pdf=pdf, sha256_pdf=hashlib.sha256(pdf).hexdigest())
        self.assertEqual(verificar(self.registro.codigo, pdf), 'REGISTRO_INCONSISTENTE')

    def test_cambios_posteriores_no_reescriben_original(self):
        pdf = emitir(self.recibo.pk)
        Recibo.objects.filter(pk=self.recibo.pk).update(importe='1.00', fecha=date(2025, 1, 1))
        Cobro.objects.filter(pk=self.cobro.pk).update(fecha_pago=date(2025, 1, 1), importe='1.00')
        self.assertEqual(emitir(self.recibo.pk), pdf)

    def test_inmutabilidad_y_proteccion_borrado(self):
        with self.assertRaises(ValidationError): self.registro.save()
        with self.assertRaises(ValidationError): self.registro.delete()
        with self.assertRaises(ProtectedError): self.recibo.delete()

    def test_admin_original_solo_lectura_y_anulacion_restringida(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        from .admin import AutenticidadReciboAdmin, AnulacionDocumentoAdmin
        from .models import AnulacionDocumento
        request = RequestFactory().get('/admin/')
        request.user = self.user
        admin = AutenticidadReciboAdmin(AutenticidadRecibo, AdminSite())
        self.assertFalse(admin.has_add_permission(request))
        self.assertFalse(admin.has_change_permission(request, self.registro))
        self.assertFalse(admin.has_delete_permission(request, self.registro))
        self.assertFalse(admin.has_view_permission(request, self.registro))
        rev = AnulacionDocumentoAdmin(AnulacionDocumento, AdminSite())
        self.assertFalse(rev.has_add_permission(request))

    def test_cambio_enlace_poliza_no_oculta_anulacion_original(self):
        pdf = emitir(self.recibo.pk)
        otra = Poliza.objects.create(cliente=self.cliente, vehiculo=self.vehiculo,
                compania='Otra sintética', fecha_alta=date(2026, 1, 1))
        Recibo.objects.filter(pk=self.recibo.pk).update(poliza=otra)
        Cobro.objects.filter(pk=self.cobro.pk).update(anulado=True)
        self.assertEqual(verificar(self.registro.codigo, pdf), 'ANULADO')

    def test_clave_ausente_no_emite(self):
        with override_settings(FORTEX_RECEIPT_KEYS={}):
            with self.assertRaises(ValidationError): emitir(self.recibo.pk)
            self.assertFalse(integro(self.registro))

    def test_codigo_inventado_o_ajeno(self):
        pdf = emitir(self.recibo.pk)
        self.assertEqual(verificar('F'*32, pdf), 'NO_VERIFICABLE')
        self.assertEqual(verificar('invalido', pdf), 'NO_VERIFICABLE')

    def test_verificador_publico_no_revela_datos(self):
        pdf = emitir(self.recibo.pk)
        response = self.client.post('/recibos/verificar/', {'codigo': self.registro.codigo,
                        'archivo': SimpleUploadedFile('sintetico.pdf', pdf)})
        self.assertContains(response, 'AUTENTICO')
        self.assertNotContains(response, 'TEST000')
        self.assertNotContains(response, '12345.67')
        self.assertEqual(response['Cache-Control'], 'no-store')

    def test_solo_codigo_no_autentica(self):
        response = self.client.post('/recibos/verificar/', {'codigo': self.registro.codigo})
        self.assertIsNone(response.context['resultado'])

    def test_historico_compatible_y_acceso_pdf(self):
        old = Recibo.objects.create(poliza=self.poliza, importe='42.00')
        self.assertEqual(self.client.get(f'/recibos/{old.pk}/pdf/').status_code, 302)
        self.client.force_login(self.user)
        from .models import AccesoRecibo
        AccesoRecibo.objects.create(recibo=old, usuario=self.user, otorgado_por=self.user)
        response = self.client.get(f'/recibos/{old.pk}/pdf/')
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.content.startswith(b'%PDF'))
        self.assertFalse(AutenticidadRecibo.objects.filter(recibo=old).exists())

    def test_integracion_cobro_nuevo(self):
        TurnoCaja.objects.create(usuario=self.user)
        self.client.force_login(self.user)
        with patch('builtins.print'):
            response = self.client.post('/cobros/nuevo/', {'poliza': self.poliza.pk,
                'importe': '5.000,50', 'plus': '0', 'fecha_pago': '2026-01-03',
                'forma_pago': 'Efectivo', 'observaciones': 'Prueba sintética'})
        self.assertEqual(response.status_code, 302)
        r = AutenticidadRecibo.objects.exclude(pk=self.registro.pk).get()
        self.assertEqual(r.original['importe'], '5000.50')
        self.assertEqual(r.original['fecha_pago_declarada'], '2026-01-03')
        self.assertEqual(MovimientoCliente.objects.count(), 1)
        self.assertRedirects(self.client.post(f'/recibos/{r.recibo_id}/emitir/'),
                             f'/recibos/{r.recibo_id}/pdf/')

    def test_fallo_clave_revierte_transaccion_nueva(self):
        TurnoCaja.objects.create(usuario=self.user)
        self.client.force_login(self.user)
        before = (Cobro.objects.count(), Recibo.objects.count(), MovimientoCliente.objects.count())
        self.poliza.refresh_from_db(); cuota = self.poliza.numero_cuota
        with override_settings(FORTEX_RECEIPT_KEYS={}), patch('builtins.print'):
            with self.assertRaises(ValidationError):
                self.client.post('/cobros/nuevo/', {'poliza': self.poliza.pk,
                    'importe': '500,00', 'plus': '0', 'fecha_pago': '2026-01-03',
                    'forma_pago': 'Efectivo', 'observaciones': 'Prueba'})
        self.assertEqual(before, (Cobro.objects.count(), Recibo.objects.count(), MovimientoCliente.objects.count()))
        self.poliza.refresh_from_db(); self.assertEqual(cuota, self.poliza.numero_cuota)
