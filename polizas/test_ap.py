from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from reportlab.pdfgen.canvas import Canvas

from clientes.models import Cliente
from cobros.models import Cobro
from polizas.models import Poliza
from principal.models import TurnoCaja
from recibos.models import Recibo
from vehiculos.models import Vehiculo


class PolizaAPTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="operador_test")
        self.client.force_login(self.user)
        self.tomador = Cliente.objects.create(nombre="Tomador", apellido="Prueba", dni="TEST-1")
        self.vehiculo = Vehiculo.objects.create(cliente=self.tomador, patente="TEST123", marca="Marca", modelo="Modelo", motor="MOTOR123", chasis="CHASIS123")
        self.turno = TurnoCaja.objects.create(usuario=self.user)
        self.data = dict(cliente=self.tomador.pk, vehiculo=self.vehiculo.pk,
                         tipo_seguro="Accidentes Personales", compania="ASEGURADORA PRUEBA",
                         numero_poliza="AP-TEST", cobertura="Muerte e invalidez accidental",
                         fecha_alta="2026-10-01", periodicidad="Trimestral", estado="Pendiente",
                         importe_cuota="10.000,50", porcentaje_comision="10", numero_cuota="0",
                         observaciones="Datos sintéticos", asegurado_nombre="Persona Asegurada",
                         asegurado_documento="TEST-2", actividad_declarada="Tareas administrativas")

    def crear(self, **changes):
        data = {**self.data, **changes}
        response = self.client.post(reverse("crear_poliza"), data)
        self.assertEqual(response.status_code, 302)
        return Poliza.objects.latest("pk")

    def cobrar(self, poliza, cantidad=1):
        return self.client.post(reverse("crear_cobro"), dict(
            poliza=poliza.pk, importe="10.000,50", plus="0", fecha_pago="2026-10-01",
            cantidad_cuotas_pagadas=cantidad, forma_pago="Efectivo", observaciones="Prueba"))

    def pdf_text(self, url):
        # Inspect actual text sent to ReportLab while still generating the real PDF.
        texts = []
        original = Canvas.drawString
        def record(canvas, x, y, text, *args, **kwargs):
            texts.append(str(text))
            return original(canvas, x, y, text, *args, **kwargs)
        from reportlab.pdfgen.textobject import PDFTextObject
        original_text = PDFTextObject._textOut
        def record_text(obj, text, *args, **kwargs):
            texts.append(str(text))
            return original_text(obj, text, *args, **kwargs)
        with patch.object(Canvas, "drawString", record), patch.object(PDFTextObject, '_textOut', record_text):
            response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'application/pdf')
        self.assertTrue(response.content.startswith(b'%PDF-'))
        return '\n'.join(texts), response.content

    def test_ap_alta_ignora_vehiculo_y_reutiliza_plan(self):
        poliza = self.crear()
        self.assertIsNone(poliza.vehiculo_id)
        self.assertEqual(poliza.cliente, self.tomador)
        self.assertEqual(poliza.asegurado_documento, 'TEST-2')
        self.assertEqual(poliza.actividad_declarada, self.data['actividad_declarada'])
        self.assertEqual(poliza.importe_cuota, Decimal('10000.50'))
        self.assertEqual(poliza.cantidad_cuotas, 3)
        self.assertEqual(poliza.fecha_fin_vigencia, date(2027, 1, 1))

    def test_ap_sin_vehiculo_y_ramo_historico(self):
        poliza = self.crear(vehiculo='', tipo_seguro='ACCIDENTES PERSONALES')
        self.assertTrue(poliza.es_ap)
        self.assertIsNone(poliza.vehiculo_id)

    def test_ap_requiere_datos_incluso_provisoria(self):
        for field in ('asegurado_nombre', 'asegurado_documento', 'actividad_declarada', 'cobertura'):
            with self.subTest(field=field):
                response = self.client.post(reverse('crear_poliza'), {**self.data, field:'', 'numero_poliza':''})
                self.assertEqual(response.status_code, 200)
                self.assertTrue(response.context['errores'])
                self.assertFalse(Poliza.objects.exists())

    def test_ap_limites_longitud(self):
        response = self.client.post(reverse('crear_poliza'), {**self.data, 'asegurado_nombre':'A'*201})
        self.assertTrue(response.context['errores'])
        self.assertFalse(Poliza.objects.exists())

    def test_modelo_valida_ap_y_admin(self):
        from django.core.exceptions import ValidationError
        poliza = self.crear()
        poliza.full_clean()
        poliza.vehiculo = self.vehiculo
        with self.assertRaises(ValidationError):
            poliza.full_clean()

    def test_edicion_reconoce_ap_historica_en_mayusculas(self):
        poliza = self.crear()
        Poliza.objects.filter(pk=poliza.pk).update(tipo_seguro='ACCIDENTES PERSONALES')
        response = self.client.get(reverse('editar_poliza', args=[poliza.pk]))
        self.assertContains(response, 'value="Accidentes Personales" selected')

    def test_ap_edicion_y_validacion(self):
        poliza = self.crear()
        url = reverse('editar_poliza', args=[poliza.pk])
        response = self.client.post(url, {**self.data, 'asegurado_nombre':'Otra Persona'})
        self.assertEqual(response.status_code, 302)
        poliza.refresh_from_db()
        self.assertEqual(poliza.asegurado_nombre, 'Otra Persona')
        self.assertIsNone(poliza.vehiculo_id)
        response = self.client.post(url, {**self.data, 'actividad_declarada':''})
        self.assertTrue(response.context['errores'])
        poliza.refresh_from_db()
        self.assertEqual(poliza.actividad_declarada, self.data['actividad_declarada'])

    def test_ap_cobro_recibo_html_pdf_y_poliza_pdf(self):
        poliza = self.crear()
        self.assertEqual(self.cobrar(poliza).status_code, 302)
        cobro = Cobro.objects.get()
        self.assertEqual(cobro.turno, self.turno)
        self.assertEqual(cobro.comision, Decimal('1000.05'))
        recibo = Recibo.objects.get()
        response = self.client.get(reverse('ver_recibo', args=[recibo.pk]))
        self.assertContains(response, 'Persona Asegurada')
        self.assertNotContains(response, 'TEST123')
        for url in (reverse('recibo_pdf', args=[recibo.pk]), reverse('imprimir_poliza', args=[poliza.pk])):
            text, pdf = self.pdf_text(url)
            self.assertNotIn('PATENTE', text.upper())
            self.assertNotIn('TEST123', text)
            for value in ('Persona Asegurada', 'TEST-2', 'Tareas administrativas', 'MUERTE E INVALIDEZ ACCIDENTAL'):
                self.assertIn(value, text)

    def test_limites_y_no_repetir_cuotas_ap_auto_moto(self):
        for i, ramo in enumerate(('Accidentes Personales', 'Automotor', 'Moto')):
            with self.subTest(ramo=ramo):
                poliza = self.crear(tipo_seguro=ramo, numero_poliza=f'P-{i}')
                self.assertEqual(self.cobrar(poliza, 2).status_code, 302)
                self.assertEqual(self.cobrar(poliza, 2).status_code, 200)
                self.assertEqual(self.cobrar(poliza, 1).status_code, 302)
                self.assertEqual(self.cobrar(poliza, 1).status_code, 200)
                self.assertEqual(list(Cobro.objects.filter(poliza=poliza).values_list('cuota','cantidad_cuotas')), [(1,2),(3,1)])
                self.assertEqual(Recibo.objects.filter(poliza=poliza).count(), 2)

    def test_cobro_sin_turno_no_escribe(self):
        poliza = self.crear()
        self.turno.abierto = False
        self.turno.save()
        response = self.cobrar(poliza)
        self.assertRedirects(response, reverse('caja_diaria'), fetch_redirect_response=False)
        self.assertFalse(Cobro.objects.exists())
        self.assertFalse(Recibo.objects.exists())

    def test_pdf_ap_campos_maximos_y_caracteres_especiales(self):
        poliza = self.crear(asegurado_nombre='W'*200, actividad_declarada='W'*200,
                            asegurado_documento='9'*20, cobertura='<Actividad & cobertura>')
        self.cobrar(poliza)
        recibo = Recibo.objects.get()
        text, _ = self.pdf_text(reverse('recibo_pdf', args=[recibo.pk]))
        self.assertIn('COBERTURA', text)
        self.assertNotIn('PATENTE', text)

    def test_automotor_moto_alta_edicion_y_pdf(self):
        for i, ramo in enumerate(('Automotor', 'Moto')):
            poliza = self.crear(tipo_seguro=ramo, numero_poliza=f'A-{i}')
            self.assertEqual(poliza.vehiculo, self.vehiculo)
            self.assertFalse(poliza.es_ap)
            response = self.client.post(reverse('editar_poliza', args=[poliza.pk]), {**self.data, 'tipo_seguro':ramo,'numero_poliza':f'A-{i}'})
            self.assertEqual(response.status_code, 302)
            self.cobrar(poliza)
            recibo = Recibo.objects.filter(poliza=poliza).get()
            text, _ = self.pdf_text(reverse('recibo_pdf', args=[recibo.pk]))
            for value in ('PATENTE', 'TEST123', 'MOTOR123', 'CHASIS123'):
                self.assertIn(value, text)

    def test_no_convertir_ramo_con_recibos(self):
        poliza = self.crear(tipo_seguro='Automotor')
        self.cobrar(poliza)
        response = self.client.post(reverse('editar_poliza', args=[poliza.pk]), self.data)
        self.assertTrue(response.context['errores'])
        poliza.refresh_from_db()
        self.assertFalse(poliza.es_ap)
        self.assertEqual(poliza.vehiculo, self.vehiculo)
