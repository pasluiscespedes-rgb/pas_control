from datetime import date
from decimal import Decimal
import json
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.db import connection, IntegrityError, transaction
from django.db.migrations.executor import MigrationExecutor
from django.test import Client, SimpleTestCase, TestCase, TransactionTestCase, override_settings
from django.urls import reverse
from reportlab.graphics.barcode import createBarcodeDrawing

from cobros.models import Cobro
from principal.models import CierreCaja, MovimientoCliente, PerfilUsuario, Sucursal, TurnoCaja
from .autenticidad import verificar
from .configuracion import configurar_autenticidad
from .models import AccesoRecibo, AnulacionDocumento, AutenticidadRecibo, Recibo, VentanaVerificacion
from . import test_autenticidad as base


class CorreccionesSeguridadTests(TestCase):
    setUp = base.AutenticidadTests.setUp

    def cliente_csrf(self, usuario):
        client = Client(enforce_csrf_checks=True)
        client.force_login(usuario)
        client.get(reverse('verificar_recibo'))
        return client, {'HTTP_X_CSRFTOKEN': client.cookies['csrftoken'].value}

    def estado(self):
        return tuple(list(model.objects.order_by('pk').values()) for model in (
            Cobro, Recibo, type(self.poliza), AutenticidadRecibo,
            AccesoRecibo, AnulacionDocumento, MovimientoCliente, TurnoCaja, CierreCaja,
        ))

    def test_fichas_ocultan_recibos_sin_acceso(self):
        ajeno = get_user_model().objects.create_user(username='solo-consulta', is_staff=True)
        ajeno.user_permissions.add(Permission.objects.get(content_type__app_label='recibos', codename='view_recibo'))
        self.client.force_login(ajeno)
        ficha = reverse('detalle_cliente', args=[self.cliente.pk])
        detalle = reverse('ver_recibo', args=[self.recibo.pk])
        MovimientoCliente.objects.create(cliente=self.cliente, usuario=self.user, tipo='cobro',
                                         titulo='Cobro de prueba', descripcion=f'Recibo: {self.recibo.numero_recibo}')
        before = self.estado()
        response = self.client.get(ficha)
        self.assertNotContains(response, detalle)
        self.assertNotContains(response, f'Recibo: {self.recibo.numero_recibo}')
        self.assertFalse(response.context['recibos'].exists())
        self.assertIsNone(list(response.context['polizas'])[0].ultimo_recibo)
        self.assertNotContains(self.client.get(reverse('ver_poliza', args=[self.poliza.pk])), detalle)
        self.assertEqual(self.estado(), before)
        AccesoRecibo.objects.create(recibo=self.recibo, usuario=ajeno, otorgado_por=self.user)
        self.assertContains(self.client.get(ficha), detalle)
        ajeno.user_permissions.add(Permission.objects.get(content_type__app_label='recibos',
                                                         codename='ver_todos_recibos'))
        self.assertContains(self.client.get(ficha), f'Recibo: {self.recibo.numero_recibo}')

    def test_anulacion_requiere_rol_objeto_y_csrf(self):
        url = reverse('cobros:anular_cobro', args=[self.cobro.pk])
        operador, token = self.cliente_csrf(self.user)
        ajeno = get_user_model().objects.create_user(username='anulador-ajeno')
        permiso = Permission.objects.get(content_type__app_label='cobros', codename='anular_cobro')
        ajeno.user_permissions.add(permiso)
        client, token_ajeno = self.cliente_csrf(ajeno)
        before = self.estado()
        self.assertEqual(operador.post(url, {'motivo': 'Sintético'}, **token).status_code, 403)
        self.assertEqual(client.get(url).status_code, 404)
        self.assertEqual(client.post(url, {'motivo': 'Sintético'}, **token_ajeno).status_code, 404)
        self.assertEqual(self.estado(), before)

        self.user.user_permissions.add(permiso)
        self.assertEqual(operador.get(url).status_code, 200)
        self.assertEqual(operador.post(url, {'motivo': 'Sintético'}).status_code, 403)
        self.assertEqual(self.estado(), before)
        self.assertEqual(operador.post(url, {'motivo': 'Sintético'}, **token).status_code, 302)
        self.cobro.refresh_from_db()
        self.assertEqual(self.cobro.anulado_por_id, self.user.pk)
        self.assertEqual(self.cobro.motivo_anulacion, 'Sintético')
        self.assertIsNotNone(self.cobro.fecha_anulacion)

    def test_admin_cobros_no_edita_campos_de_anulacion(self):
        from django.contrib import admin
        from django.test import RequestFactory

        self.user.is_staff = True
        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='cobros', codename='change_cobro'))
        request = RequestFactory().get('/')
        request.user = self.user
        form = admin.site.get_model_admin(Cobro).get_form(request, self.cobro)
        for campo in ('anulado', 'anulado_por', 'fecha_anulacion', 'motivo_anulacion'):
            self.assertNotIn(campo, form.base_fields)

    def test_emision_post_idempotente_qr_y_estado_publico(self):
        post = reverse('emitir_recibo_pdf', args=[self.recibo.pk])
        get = reverse('recibo_pdf', args=[self.recibo.pk])
        operador, token = self.cliente_csrf(self.user)
        ajeno = get_user_model().objects.create_user(username='lector')
        client, token_ajeno = self.cliente_csrf(ajeno)
        before = self.estado()
        self.assertEqual(operador.get(post).status_code, 405)
        self.assertEqual(operador.get(get).status_code, 409)
        self.assertEqual(operador.head(get).status_code, 409)
        self.assertEqual(operador.post(post).status_code, 403)
        self.assertEqual(client.post(post, **token_ajeno).status_code, 404)
        self.assertEqual(self.estado(), before)
        AccesoRecibo.objects.create(recibo=self.recibo, usuario=ajeno, otorgado_por=self.user)
        before = self.estado()
        self.assertEqual(client.post(post, **token_ajeno).status_code, 403)
        with override_settings(FORTEX_RECEIPT_VERIFIER_ORIGIN='https://fortex.example.invalid/?dato=1'):
            self.assertEqual(operador.post(post, **token).status_code, 409)
        self.assertEqual(self.estado(), before)

        with patch('reportlab.graphics.barcode.createBarcodeDrawing', wraps=createBarcodeDrawing) as qr:
            self.assertRedirects(operador.post(post, **token), get, fetch_redirect_response=False)
            pdf = operador.get(get).content
            self.assertEqual(client.get(get).content, pdf)
            issued = self.estado()
            self.assertRedirects(operador.post(post, **token), get, fetch_redirect_response=False)
            self.assertEqual(operador.get(get).content, pdf)
            self.assertEqual(self.estado(), issued)
            self.assertEqual(qr.call_count, 1)
            self.assertEqual(qr.call_args.args, ('QR',))
            self.assertEqual(qr.call_args.kwargs['value'],
                             'https://fortex.example.invalid' + reverse('verificar_recibo'))
        self.assertEqual(verificar(self.registro.codigo, pdf), 'AUTENTICO')

        self.user.user_permissions.add(Permission.objects.get(content_type__app_label='cobros', codename='anular_cobro'))
        self.assertEqual(operador.post(reverse('cobros:anular_cobro', args=[self.cobro.pk]),
                                      {'motivo': 'Sintético'}, **token).status_code, 302)
        interno = Client(enforce_csrf_checks=True)
        interno.force_login(self.user)
        ruta = reverse('verificar_recibo')
        interno.get(ruta)
        for archivo, expected in ((pdf + b'cambio', 'DOCUMENTO_NO_COINCIDE'), (pdf, 'ANULADO')):
            result = interno.post(ruta, {'codigo': self.registro.codigo,
                                        'archivo': SimpleUploadedFile('sintetico.pdf', archivo)},
                                  HTTP_X_CSRFTOKEN=interno.cookies['csrftoken'].value)
            self.assertEqual(result.context['resultado'], expected)
            self.assertNotContains(result, self.cliente.apellido)

    def test_apertura_y_cierre_caja_son_post_con_csrf(self):
        sucursal = Sucursal.objects.create(nombre='Sintética', provincia='Sintética', codigo='SINT')
        PerfilUsuario.objects.create(usuario=self.user, sucursal=sucursal, activo=True)
        client, token = self.cliente_csrf(self.user)
        for nombre in ('abrir_turno', 'cerrar_caja'):
            with self.subTest(nombre=nombre):
                ruta = reverse(nombre)
                before = self.estado()
                self.assertEqual(client.get(ruta).status_code, 405)
                self.assertEqual(client.head(ruta).status_code, 405)
                self.assertEqual(client.post(ruta).status_code, 403)
                self.assertEqual(self.estado(), before)
                self.assertEqual(client.post(ruta, **token).status_code, 302)
        self.assertEqual(TurnoCaja.objects.filter(usuario=self.user, abierto=False).count(), 1)
        self.assertEqual(CierreCaja.objects.filter(usuario=self.user).count(), 1)

    def test_identificador_invalido_en_captura_no_deja_firma_ni_acceso(self):
        from .autenticidad import capturar

        rec = Recibo.objects.create(poliza=self.poliza, importe=Decimal('12345.67'))
        invalido = 'x' * 41
        before = self.estado()
        with override_settings(FORTEX_RECEIPT_ACTIVE_KEY=invalido, FORTEX_RECEIPT_KEYS={invalido: 'x' * 64}):
            with self.assertRaises(ValidationError):
                capturar(rec, self.cobro)
        self.assertEqual(self.estado(), before)


class ConfiguracionClavesTests(SimpleTestCase):
    def test_identificadores_validos_y_rechazo_sin_exponer_secreto(self):
        synthetic = 'sintetica-' * 8
        for invalido in ('', 'a' * 41, 'a b', 'a/b', 'a\n'):
            for activo in (invalido, 'vigente'):
                config = {'FORTEX_RECEIPT_SECURITY_ENABLED': 'true',
                          'FORTEX_RECEIPT_ACTIVE_KEY': activo,
                          'FORTEX_RECEIPT_KEYS': json.dumps({'vigente': synthetic, invalido: synthetic})}
                with self.assertRaises(ImproperlyConfigured) as error:
                    configurar_autenticidad(config)
                self.assertNotIn(synthetic, str(error.exception))
        ids = {'anterior': synthetic, 'a' * 40: synthetic}
        config = {'FORTEX_RECEIPT_SECURITY_ENABLED': 'true',
                  'FORTEX_RECEIPT_ACTIVE_KEY': 'a' * 40, 'FORTEX_RECEIPT_KEYS': json.dumps(ids)}
        self.assertEqual(configurar_autenticidad(config), (True, 'a' * 40, ids))


class MigracionPostgreSQLTests(TransactionTestCase):
    def test_recibos_0003_a_0006_y_cobros_0009_sobre_filas_historicas(self):
        self.assertEqual(connection.vendor, 'postgresql')
        self.assertEqual(connection.settings_dict['HOST'], '127.0.0.1')
        self.assertEqual(connection.settings_dict['NAME'], 'test_fortex_security_lab')
        executor = MigrationExecutor(connection)
        latest = executor.loader.graph.leaf_nodes()
        self.addCleanup(lambda: MigrationExecutor(connection).migrate(latest))
        old = [('recibos', '0003_recibo_cantidad_cuotas'), ('cobros', '0008_cobro_turno')]
        executor.migrate(old)
        permiso_anulacion = Permission.objects.filter(content_type__app_label='cobros',
                                                     codename='anular_cobro')
        # El test runner ya creó los permisos del estado final al inicializar la base sintética.
        permiso_anulacion.delete()
        baseline = [node for node in latest if node[0] not in {'cobros', 'recibos'}] + old
        apps = executor.loader.project_state(baseline).apps
        self.assertNotIn('recibos_autenticidadrecibo', connection.introspection.table_names())
        user = apps.get_model('auth', 'User').objects.create(username='historico-sintetico')
        cliente = apps.get_model('clientes', 'Cliente').objects.create(nombre='Histórico sintético')
        poliza = apps.get_model('polizas', 'Poliza').objects.create(cliente_id=cliente.pk, fecha_alta=date(2026, 1, 1))
        cobro = apps.get_model('cobros', 'Cobro').objects.create(
            poliza_id=poliza.pk, cliente_id=cliente.pk, registrado_por_id=user.pk,
            fecha_pago=date(2026, 1, 2), importe=Decimal('120.50'))
        recibo = apps.get_model('recibos', 'Recibo').objects.create(
            poliza_id=poliza.pk, importe=Decimal('120.50'), numero_recibo='HIST-SINT', emitido=True)
        apps.get_model('recibos', 'Recibo').objects.create(
            poliza_id=poliza.pk, importe=Decimal('12.35'), numero_recibo='HIST-SINT-02')

        def snapshot():
            with connection.cursor() as cur:
                records = {}
                for name in ('recibos_recibo', 'cobros_cobro', 'polizas_poliza', 'clientes_cliente', 'auth_user'):
                    cur.execute(f'SELECT * FROM {name} ORDER BY id')
                    records[name] = (cur.fetchall(), connection.introspection.get_constraints(cur, name))
                return records

        before = snapshot()
        executor = MigrationExecutor(connection)
        target = [('recibos', '0006_ventanaverificacion')]
        self.assertEqual([(m.name[:4], back) for m, back in executor.migration_plan(target)],
                         [('0004', False), ('0005', False), ('0006', False)])
        executor.migrate(target)
        self.assertEqual(snapshot(), before)
        for model in (AutenticidadRecibo, AnulacionDocumento, AccesoRecibo, VentanaVerificacion):
            self.assertFalse(model.objects.exists())

        executor = MigrationExecutor(connection)
        self.assertEqual([(m.name, back) for m, back in executor.migration_plan(
            [('cobros', '0009_alter_cobro_options')])],
            [('0009_alter_cobro_options', False)])
        call_command('migrate', 'cobros', '0009', interactive=False, verbosity=0)
        self.assertEqual(snapshot(), before)
        permiso = permiso_anulacion.get()
        self.assertFalse(permiso.user_set.exists())
        self.assertFalse(permiso.group_set.exists())

        with connection.cursor() as cur:
            def constraint(model, columns, kind, value=True):
                constraints = connection.introspection.get_constraints(cur, model._meta.db_table)
                self.assertTrue(any(c['columns'] == columns and c.get(kind) == value
                                    for c in constraints.values()), (model, columns, kind))

            for col in ('codigo', 'recibo_id', 'cobro_id'):
                constraint(AutenticidadRecibo, [col], 'unique')
            constraint(AutenticidadRecibo, ['recibo_id'], 'foreign_key', ('recibos_recibo', 'id'))
            constraint(AutenticidadRecibo, ['cobro_id'], 'foreign_key', ('cobros_cobro', 'id'))
            constraint(AnulacionDocumento, ['registro_id'], 'unique')
            constraint(AnulacionDocumento, ['registro_id'], 'foreign_key', ('recibos_autenticidadrecibo', 'id'))
            constraint(AnulacionDocumento, ['usuario_id'], 'foreign_key', ('auth_user', 'id'))
            constraint(AccesoRecibo, ['recibo_id', 'usuario_id'], 'unique')
            constraint(AccesoRecibo, ['recibo_id'], 'foreign_key', ('recibos_recibo', 'id'))
            for col in ('usuario_id', 'otorgado_por_id'):
                constraint(AccesoRecibo, [col], 'foreign_key', ('auth_user', 'id'))
            constraint(VentanaVerificacion, ['clave'], 'primary_key')
            constraint(VentanaVerificacion, ['ventana'], 'index')

        acceso = dict(recibo_id=recibo.pk, usuario_id=user.pk, otorgado_por_id=user.pk)
        AccesoRecibo.objects.create(**acceso)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AccesoRecibo.objects.create(**acceso)
        with self.assertRaises(IntegrityError), transaction.atomic():
            AccesoRecibo.objects.create(**{**acceso, 'usuario_id': user.pk + 1000})
            connection.check_constraints()
        self.assertTrue(Cobro.objects.filter(pk=cobro.pk, registrado_por_id=user.pk).exists())
