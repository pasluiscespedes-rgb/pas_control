"""Pruebas nuevas: URLs y middleware completos, PostgreSQL local sintetico.

No hereda las 43 pruebas anteriores. Reutiliza solo su preparacion sintetica.
"""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from decimal import Decimal
import hashlib
import io
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import threading
import time
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection, connections, close_old_connections, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, RequestFactory, TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from cobros.models import Cobro
from principal.models import MovimientoCliente, TurnoCaja, GastoCaja
from .autenticidad import emitir, verificar, anular_documento
from .infraestructura import consumir, VerificadorMiddleware
from .models import Recibo, AutenticidadRecibo, AccesoRecibo, VentanaVerificacion
from . import test_autenticidad as base


class FlujosIntegradosTests(TestCase):
    setUp = base.AutenticidadTests.setUp

    def cliente_csrf(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.user)
        TurnoCaja.objects.get_or_create(usuario=self.user, abierto=True)
        r = c.get(reverse('crear_cobro'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'csrfmiddlewaretoken')
        return c, c.cookies['csrftoken'].value

    def datos(self):
        return {'poliza': self.poliza.pk, 'importe': '5.000,50', 'plus': '100,00',
                'fecha_pago': '2026-01-03', 'forma_pago': 'Efectivo',
                'observaciones': 'INTEGRACION SINTETICA', 'cantidad_cuotas_pagadas': '2'}

    def postear(self, c, token, ruta=None):
        with patch('builtins.print'):
            return c.post(ruta or reverse('crear_cobro'), self.datos(), HTTP_X_CSRFTOKEN=token)

    def test_csrf_ausente_incorrecto_y_origen_ajeno_sin_efectos(self):
        c, token = self.cliente_csrf()
        before = (Cobro.objects.count(), Recibo.objects.count(), MovimientoCliente.objects.count())
        for ruta in [reverse('crear_cobro'), reverse('crear_cobro_cliente', args=[self.cliente.pk])]:
            self.assertEqual(c.post(ruta, self.datos()).status_code, 403)
            self.assertEqual(c.post(ruta, self.datos(), HTTP_X_CSRFTOKEN='x'*32).status_code, 403)
            self.assertEqual(c.post(ruta, self.datos(), HTTP_X_CSRFTOKEN=token,
                                    HTTP_ORIGIN='https://origen-ajeno.invalid').status_code, 403)
        self.assertEqual(before, (Cobro.objects.count(), Recibo.objects.count(), MovimientoCliente.objects.count()))

    def test_csrf_formulario_html_valido_ambas_rutas(self):
        c, token = self.cliente_csrf()
        for ruta in [reverse('crear_cobro'), reverse('crear_cobro_cliente', args=[self.cliente.pk])]:
            data = self.datos(); data['csrfmiddlewaretoken'] = token
            with patch('builtins.print'):
                response = c.post(ruta, data)
            self.assertEqual(response.status_code, 302)
            self.assertEqual(c.get(response.url).status_code, 200)
        self.assertEqual(MovimientoCliente.objects.count(), 2)

    def test_csrf_header_ap_cobro_caja_auditoria_pdf_y_adulteraciones(self):
        self.poliza.vehiculo = None
        self.poliza.tipo_seguro = 'Accidentes Personales'
        self.poliza.save()
        c, token = self.cliente_csrf()
        self.assertEqual(self.postear(c, token).status_code, 302)
        cobro = Cobro.objects.exclude(pk=self.cobro.pk).get()
        recibo = Recibo.objects.exclude(pk=self.recibo.pk).get()
        self.assertEqual(cobro.importe, Decimal('5000.50'))
        self.assertEqual(cobro.plus, Decimal('100.00'))
        self.assertEqual(cobro.cantidad_cuotas, 2)
        self.assertEqual(cobro.registrado_por_id, self.user.pk)
        m = MovimientoCliente.objects.get()
        self.assertEqual((m.tipo, m.usuario_id), ('cobro', self.user.pk))
        self.assertIn(recibo.numero_recibo, m.descripcion)
        GastoCaja.objects.create(concepto='GASTO SINTETICO', importe='50', usuario=self.user, turno=cobro.turno)
        caja = c.get(reverse('caja_diaria'))
        self.assertEqual(caja.status_code, 200)
        self.assertEqual(caja.context['total'], Decimal('5000.50'))
        self.assertEqual(caja.context['saldo_neto'], Decimal('4950.50'))
        # Sin compresion solo para adulterar campos reales sin romper xref del PDF.
        from reportlab.pdfgen import canvas
        real = canvas.Canvas
        with patch('reportlab.pdfgen.canvas.Canvas', side_effect=lambda *a, **kw: real(*a, **kw, pageCompression=0)):
            response = c.post(reverse('emitir_recibo_pdf', args=[recibo.pk]), HTTP_X_CSRFTOKEN=token)
            pdf = c.get(response.url).content
        registro = AutenticidadRecibo.objects.get(recibo=recibo)
        self.assertEqual(verificar(registro.codigo, pdf), 'AUTENTICO')
        self.assertEqual(c.get(reverse('recibo_pdf', args=[recibo.pk])).content, pdf)
        self.assertEqual(len(re.findall(rb'/Type\s*/Page\b', pdf)), 1)
        for old, new in [(b'2026-01-03', b'2025-01-03'), (b'5000.50', b'9999.99')]:
            self.assertIn(old, pdf)
            altered = pdf.replace(old, new, 1)
            self.assertEqual(verificar(registro.codigo, altered), 'DOCUMENTO_NO_COINCIDE')
        # Ruta publica real, CSRF real, ningun dato del cliente en la respuesta.
        public = Client(enforce_csrf_checks=True)
        public.get(reverse('verificar_recibo'))
        result = public.post(reverse('verificar_recibo'), {'codigo': registro.codigo,
            'archivo': SimpleUploadedFile('sintetico.pdf', pdf)},
            HTTP_X_CSRFTOKEN=public.cookies['csrftoken'].value)
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context['resultado'], 'AUTENTICO')
        self.assertNotContains(result, self.cliente.apellido)
        # Anulacion operativa por la ruta completa; mismo calculo preexistente.
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='cobros', codename='anular_cobro'))
        anulacion = c.post(reverse('cobros:anular_cobro', args=[cobro.pk]),
                           {'motivo': 'ANULACION SINTETICA'}, HTTP_X_CSRFTOKEN=token)
        self.assertEqual(anulacion.status_code, 302)
        self.assertEqual(verificar(registro.codigo, pdf), 'ANULADO')
        self.assertEqual(c.get(reverse('recibo_pdf', args=[recibo.pk])).status_code, 409)
        self.assertEqual(c.get(reverse('caja_diaria')).context['total'], 0)
        self.assertEqual(MovimientoCliente.objects.count(), 1)

    def test_rollback_si_firma_falla(self):
        from django.core.exceptions import ValidationError
        c, token = self.cliente_csrf()
        self.poliza.refresh_from_db()
        before = (Cobro.objects.count(), Recibo.objects.count(), MovimientoCliente.objects.count(),
                  self.poliza.numero_cuota, self.poliza.fecha_vencimiento, AccesoRecibo.objects.count())
        with override_settings(FORTEX_RECEIPT_KEYS={}):
            with self.assertRaises(ValidationError):
                self.postear(c, token)
        self.poliza.refresh_from_db()
        self.assertEqual(before, (Cobro.objects.count(), Recibo.objects.count(), MovimientoCliente.objects.count(),
                  self.poliza.numero_cuota, self.poliza.fecha_vencimiento, AccesoRecibo.objects.count()))

    def test_historico_autorizado_sin_cambios_y_sin_certificacion(self):
        viejo = Recibo.objects.create(poliza=self.poliza, importe='42.00')
        before = Recibo.objects.filter(pk=viejo.pk).values().get()
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse('recibo_pdf', args=[viejo.pk])).status_code, 404)
        AccesoRecibo.objects.create(recibo=viejo, usuario=self.user, otorgado_por=self.user)
        response = self.client.get(reverse('recibo_pdf', args=[viejo.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Cache-Control'], 'no-store')
        self.assertEqual(Recibo.objects.filter(pk=viejo.pk).values().get(), before)
        self.assertFalse(AutenticidadRecibo.objects.filter(recibo=viejo).exists())

    def test_permisos_lista_detalle_pdf_admin_y_revocacion(self):
        emitir(self.recibo.pk)
        ajeno = get_user_model().objects.create_user(username='STAFF-SINTETICO', is_staff=True)
        ajeno.user_permissions.add(Permission.objects.get(codename='view_recibo'),
                                  Permission.objects.get(codename='view_autenticidadrecibo'))
        self.client.force_login(ajeno)
        for name in ['ver_recibo', 'recibo_pdf']:
            self.assertEqual(self.client.get(reverse(name, args=[self.recibo.pk])).status_code, 404)
        listing = self.client.get(reverse('lista_recibos'))
        self.assertEqual(listing.status_code, 200)
        self.assertFalse(listing.context['recibos'].exists())
        url = reverse('admin:recibos_autenticidadrecibo_change', args=[self.registro.pk])
        self.assertNotContains(self.client.get(url, follow=True), 'POL-TEST')
        grant = AccesoRecibo.objects.create(recibo=self.recibo, usuario=ajeno, otorgado_por=self.user)
        self.assertEqual(self.client.get(reverse('recibo_pdf', args=[self.recibo.pk])).status_code, 200)
        grant.delete()
        self.assertEqual(self.client.get(reverse('recibo_pdf', args=[self.recibo.pk])).status_code, 404)

    def test_anulacion_documental_admin_real(self):
        self.user.is_staff = True; self.user.save()
        self.user.user_permissions.add(Permission.objects.get(codename='anular_documento'))
        pdf = emitir(self.recibo.pk)
        self.client.force_login(self.user)
        response = self.client.post(reverse('admin:recibos_anulaciondocumento_add'),
                                    {'registro': self.registro.pk, 'motivo': 'SINTETICO', '_save': 'Guardar'})
        self.assertEqual(response.status_code, 302)
        self.assertEqual(verificar(self.registro.codigo, pdf), 'ANULADO')
        self.cobro.refresh_from_db(); self.assertFalse(self.cobro.anulado)

    def test_desactivada_conserva_cobro_y_acceso_historico_explicito(self):
        c, token = self.cliente_csrf()
        with override_settings(FORTEX_RECEIPT_SECURITY_ENABLED=False):
            response = self.postear(c, token)
        self.assertEqual(response.status_code, 302)
        nuevo = Recibo.objects.exclude(pk=self.recibo.pk).get()
        self.assertFalse(AutenticidadRecibo.objects.filter(recibo=nuevo).exists())
        self.assertEqual(c.get(reverse('recibo_pdf', args=[nuevo.pk])).status_code, 200)


class InfraestructuraTests(TestCase):
    def post(self, ip='127.0.0.1'):
        return self.client.post(reverse('verificar_recibo'), {}, REMOTE_ADDR=ip)

    def test_limite_ip_compartido_y_no_confia_forwarded_for(self):
        with override_settings(FORTEX_VERIFIER_PER_IP=2):
            self.assertEqual(self.post().status_code, 200)
            other = Client()
            self.assertEqual(other.post(reverse('verificar_recibo'), {},
                                        HTTP_X_FORWARDED_FOR='1.2.3.4').status_code, 200)
            response = self.post()
            self.assertEqual(response.status_code, 429)
            self.assertIn('Retry-After', response)
            self.assertEqual(response['Cache-Control'], 'no-store')

    def test_limite_global_entre_ips(self):
        with override_settings(FORTEX_VERIFIER_GLOBAL=2):
            self.assertEqual(self.post('127.0.0.1').status_code, 200)
            self.assertEqual(self.post('127.0.0.2').status_code, 200)
            self.assertEqual(self.post('127.0.0.3').status_code, 429)

    def test_ventana_nueva_habilita_y_mantenimiento_solo_contadores(self):
        with override_settings(FORTEX_VERIFIER_PER_IP=1), patch('recibos.infraestructura.time.time', return_value=120000):
            self.assertEqual(self.post().status_code, 200)
            self.assertEqual(self.post().status_code, 429)
        with patch('recibos.infraestructura.time.time', return_value=120060):
            self.assertEqual(self.post().status_code, 200)
        before = Recibo.objects.count(), AutenticidadRecibo.objects.count()
        VentanaVerificacion.objects.create(clave='ANTIGUO', ventana=0)
        call_command('recibos_mantenimiento', stdout=io.StringIO())
        self.assertFalse(VentanaVerificacion.objects.filter(clave='ANTIGUO').exists())
        self.assertEqual(before, (Recibo.objects.count(), AutenticidadRecibo.objects.count()))

    def test_limite_http_antes_de_leer_archivo_y_longitud_obligatoria(self):
        middleware = VerificadorMiddleware(lambda request: self.fail('No debe leer ni continuar'))
        req = RequestFactory().post(reverse('verificar_recibo'))
        req.META['CONTENT_LENGTH'] = str(6*1024*1024 + 1)
        self.assertEqual(middleware(req).status_code, 413)
        del req.META['CONTENT_LENGTH']
        self.assertEqual(middleware(req).status_code, 411)

    def test_archivo_nunca_usa_temporales_y_rechaza_mas_de_5mb(self):
        # Forzar un umbral global minusculo no debe enviar el archivo a disco.
        with override_settings(FILE_UPLOAD_MAX_MEMORY_SIZE=1), patch(
                'django.core.files.uploadedfile.TemporaryUploadedFile.__init__',
                side_effect=AssertionError('No crear temporal')):
            r = self.client.post(reverse('verificar_recibo'), {
                'codigo': 'F'*32, 'archivo': SimpleUploadedFile('sintetico.pdf', b'x'*1024)})
            self.assertEqual(r.context['resultado'], 'NO_VERIFICABLE')
            r = self.client.post(reverse('verificar_recibo'), {
                'codigo': 'F'*32, 'archivo': SimpleUploadedFile('sintetico.pdf', b'x'*(5*1024*1024+1))})
            self.assertIsNone(r.context['resultado'])
            self.assertTrue(r.context['form'].errors)

    def test_base_no_disponible_falla_cerrada(self):
        from django.db import OperationalError
        with patch('recibos.infraestructura.consumir', side_effect=OperationalError('SINTETICO')):
            self.assertEqual(self.post().status_code, 503)

    def test_provision_clave_privada_sin_sobrescribir_ni_imprimir(self):
        with tempfile.TemporaryDirectory(prefix='fortex_clave_sintetica_') as folder:
            target = Path(folder) / 'clave.json'; out = io.StringIO()
            # Solo valor sintetico conocido; no se genera ni usa un secreto de produccion.
            with patch('recibos.management.commands.recibos_crear_clave.secrets.token_hex', return_value='SYNTHETIC'*8):
                call_command('recibos_crear_clave', destino=str(target), identificador='lab', stdout=out)
            self.assertEqual(json.loads(target.read_text(encoding='utf8')), {'lab': 'SYNTHETIC'*8})
            self.assertNotIn('SYNTHETIC'*8, out.getvalue())
            with self.assertRaises(CommandError):
                call_command('recibos_crear_clave', destino=str(target), identificador='lab', stdout=out)


class ConcurrenciaPostgreSQLTests(TransactionTestCase):
    setUp = base.AutenticidadTests.setUp

    def setUp(self):
        self.assertEqual(connection.vendor, 'postgresql', 'Requiere PostgreSQL real de prueba')
        self.assertEqual(connection.settings_dict['HOST'], '127.0.0.1')
        self.assertEqual(connection.settings_dict['NAME'], 'test_fortex_security_lab')
        base.AutenticidadTests.setUp(self)

    def worker(self, fn):
        close_old_connections()
        try:
            return fn()
        finally:
            connections.close_all()

    def test_dos_emisiones_simultaneas_guardan_mismos_bytes(self):
        import principal.fortex_pdf as drawing
        real = drawing.dibujar_recibo_fortex
        entered, release = threading.Event(), threading.Event()
        count = []
        def draw(*a, **kw):
            count.append(1); entered.set()
            if not release.wait(5):
                raise AssertionError('No se libero el primer emisor')
            return real(*a, **kw)
        with ThreadPoolExecutor(2) as pool, patch.object(drawing, 'dibujar_recibo_fortex', side_effect=draw):
            first = pool.submit(self.worker, lambda: emitir(self.recibo.pk))
            self.assertTrue(entered.wait(5))
            second = pool.submit(self.worker, lambda: emitir(self.recibo.pk))
            try:
                self.assertFalse(second.done())
            finally:
                release.set()
            self.assertEqual(first.result(timeout=10), second.result(timeout=10))
        self.assertEqual(len(count), 1)
        r = AutenticidadRecibo.objects.get(pk=self.registro.pk)
        self.assertEqual(verificar(r.codigo, bytes(r.pdf)), 'AUTENTICO')

    def test_anulacion_cobro_espera_emision_y_luego_invalida(self):
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='cobros', codename='anular_cobro'))
        import principal.fortex_pdf as drawing
        real = drawing.dibujar_recibo_fortex
        entered, release, trying = threading.Event(), threading.Event(), threading.Event()
        def draw(*a, **kw):
            entered.set()
            if not release.wait(5): raise AssertionError('No se libero emision')
            return real(*a, **kw)
        def cancel():
            c = Client(); c.force_login(get_user_model().objects.get(pk=self.user.pk))
            trying.set()
            return c.post(reverse('cobros:anular_cobro', args=[self.cobro.pk]), {'motivo':'SINTETICO'}).status_code
        with ThreadPoolExecutor(2) as pool, patch.object(drawing, 'dibujar_recibo_fortex', side_effect=draw):
            first = pool.submit(self.worker, lambda: emitir(self.recibo.pk))
            self.assertTrue(entered.wait(5))
            second = pool.submit(self.worker, cancel)
            self.assertTrue(trying.wait(5))
            try:
                # El servidor debe informar una espera real por lock, no solo un hilo pendiente.
                deadline = time.monotonic()+4
                waiting = False
                while time.monotonic()<deadline:
                    with connection.cursor() as cursor:
                        cursor.execute("SELECT EXISTS(SELECT 1 FROM pg_stat_activity WHERE datname=current_database() AND wait_event_type='Lock' AND pid<>pg_backend_pid())")
                        waiting = cursor.fetchone()[0]
                    if waiting: break
                    threading.Event().wait(0.02)
                self.assertTrue(waiting, 'No se observo bloqueo PostgreSQL')
            finally:
                release.set()
            pdf = first.result(timeout=10)
            self.assertEqual(second.result(timeout=10), 302)
        self.assertEqual(verificar(self.registro.codigo, pdf), 'ANULADO')

    def test_anulacion_documental_confirmada_bloquea_emision(self):
        self.user.user_permissions.add(Permission.objects.get(codename='anular_documento'))
        locked, release = threading.Event(), threading.Event()
        def cancel():
            with transaction.atomic():
                user = get_user_model().objects.get(pk=self.user.pk)
                anular_documento(self.registro, user, 'SINTETICO')
                locked.set()
                if not release.wait(5): raise AssertionError('No se libero anulacion')
        from django.core.exceptions import ValidationError
        with ThreadPoolExecutor(2) as pool:
            first = pool.submit(self.worker, cancel)
            self.assertTrue(locked.wait(5))
            second = pool.submit(self.worker, lambda: emitir(self.recibo.pk))
            release.set(); first.result(timeout=10)
            with self.assertRaises(ValidationError): second.result(timeout=10)
        self.registro.refresh_from_db(); self.assertIsNone(self.registro.fecha_emision)

    def test_contador_atomico_entre_conexiones(self):
        start = threading.Barrier(8)
        def count():
            start.wait(timeout=5)
            return consumir('CONCURRENTE-SINTETICO', 1, 3)
        with ThreadPoolExecutor(8) as pool:
            jobs = [pool.submit(self.worker, count) for _ in range(8)]
            results = [j.result(timeout=10) for j in jobs]
        self.assertEqual(sum(results), 3)
        self.assertEqual(VentanaVerificacion.objects.get(clave='CONCURRENTE-SINTETICO').intentos, 3)

    def test_dos_altas_concurrentes_serializan_cuotas_y_auditoria(self):
        TurnoCaja.objects.create(usuario=self.user)
        start = threading.Barrier(2)
        def create():
            c = Client(); c.force_login(get_user_model().objects.get(pk=self.user.pk))
            start.wait(timeout=5)
            with patch('builtins.print'):
                return c.post(reverse('crear_cobro'), {'poliza':self.poliza.pk, 'importe':'100,00',
                    'plus':'0', 'fecha_pago':'2026-01-03', 'forma_pago':'Efectivo',
                    'observaciones':'CONCURRENTE SINTETICO'}).status_code
        with ThreadPoolExecutor(2) as pool:
            jobs = [pool.submit(self.worker, create) for _ in range(2)]
            self.assertEqual([j.result(timeout=10) for j in jobs], [302,302])
        self.assertEqual(list(Cobro.objects.order_by('cuota').values_list('cuota',flat=True)), [1,2,3])
        self.assertEqual(MovimientoCliente.objects.count(), 2)
        self.assertEqual(AutenticidadRecibo.objects.count(), 3)

    def test_backup_restore_pdf_firmas_accesos_y_anulacion(self):
        # Dump y restauracion reales del cluster creado por el runner, sin leer archivos reales.
        import psycopg
        pdf = emitir(self.recibo.pk)
        self.user.user_permissions.add(Permission.objects.get(codename='anular_documento'))
        anular_documento(self.registro, get_user_model().objects.get(pk=self.user.pk), 'SINTETICO BACKUP')
        archive = Path(self.enterContext(tempfile.TemporaryDirectory(prefix='fortex-respaldo-'))) / 'respaldo.dump'
        database = connection.settings_dict
        env = {k:v for k,v in os.environ.items() if not k.startswith('PG')}
        env.update(PGHOST=database['HOST'], PGPORT=database['PORT'], PGUSER=database['USER'],
                   PGPASSWORD=database['PASSWORD'], PGCONNECT_TIMEOUT='5')
        subprocess.run(['pg_dump', '-d', database['NAME'], '-Fc', '-f', str(archive)],
                       env=env,check=True,capture_output=True,timeout=30)
        with connection.cursor() as cursor:
            cursor.execute('CREATE DATABASE fortex_lab_restore_sintetico')
        try:
            subprocess.run(['pg_restore', '-d','fortex_lab_restore_sintetico',
                            '--exit-on-error',str(archive)],env=env,check=True,capture_output=True,timeout=30)
            with psycopg.connect(host=database['HOST'], port=database['PORT'], user=database['USER'],
                                 password=database['PASSWORD'], dbname='fortex_lab_restore_sintetico',
                                 connect_timeout=5) as restored:
                with restored.cursor() as cursor:
                    cursor.execute('SELECT pdf, sha256_pdf, firma, firma_pdf FROM recibos_autenticidadrecibo WHERE id=%s',[self.registro.pk])
                    content, digest, signature, signature_pdf = cursor.fetchone()
                    self.registro.refresh_from_db()
                    self.assertEqual(bytes(content),pdf)
                    self.assertEqual(digest,hashlib.sha256(pdf).hexdigest())
                    self.assertEqual((signature,signature_pdf),(self.registro.firma,self.registro.firma_pdf))
                    cursor.execute('SELECT count(*) FROM recibos_accesorecibo')
                    self.assertEqual(cursor.fetchone()[0],AccesoRecibo.objects.count())
                    cursor.execute('SELECT count(*) FROM recibos_anulaciondocumento')
                    self.assertEqual(cursor.fetchone()[0],1)
        finally:
            with connection.cursor() as cursor:
                cursor.execute('DROP DATABASE fortex_lab_restore_sintetico')


class MigracionesHistoricasTests(TransactionTestCase):
    def test_migrar_0003_a_0006_preserva_recibo_sin_rellenar_historia(self):
        base.AutenticidadTests.setUp(self)
        executor = MigrationExecutor(connection)
        executor.migrate([('recibos','0003_recibo_cantidad_cuotas')])
        try:
            old = executor.loader.project_state([('recibos','0003_recibo_cantidad_cuotas')]).apps.get_model('recibos','Recibo')
            historical = old.objects.create(poliza_id=self.poliza.pk, importe='123.45',numero_recibo='HIST-SINTETICO')
            before = old.objects.filter(pk=historical.pk).values().get()
            executor = MigrationExecutor(connection)
            executor.migrate([('recibos','0006_ventanaverificacion')])
            self.assertEqual(Recibo.objects.filter(pk=historical.pk).values().get(),before)
            self.assertEqual(AutenticidadRecibo.objects.count(),0)
            self.assertEqual(AccesoRecibo.objects.count(),0)
        finally:
            MigrationExecutor(connection).migrate([('recibos','0006_ventanaverificacion')])
