"""Regresiones de la revisión de Victoria. Sólo fixtures sintéticos."""
import importlib.util
import os
import re
from pathlib import Path
from unittest.mock import patch

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.exceptions import ImproperlyConfigured
from django.test import Client, TestCase, SimpleTestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile

from cobros.models import Cobro
from principal.models import TurnoCaja, MovimientoCliente
from .models import Recibo, AutenticidadRecibo, AccesoRecibo
from . import test_autenticidad as base
from .autenticidad import emitir, verificar, AVISO
from .configuracion import configurar_autenticidad


class RevisionTests(TestCase):
    # Comparte preparación, no hereda ni duplica las 22 pruebas anteriores.
    setUp = base.AutenticidadTests.setUp

    def test_usuario_ajeno_no_descarga_ni_consulta_objeto(self):
        ajeno = get_user_model().objects.create_user(username='ajeno_sintetico')
        ajeno.user_permissions.add(Permission.objects.get(codename='view_recibo'))
        self.client.force_login(ajeno)
        for ruta in [f'/recibos/{self.recibo.pk}/pdf/', f'/recibos/{self.recibo.pk}/',
                     f'/clientes/{self.cliente.pk}/recibo/']:
            self.assertEqual(self.client.get(ruta).status_code, 404)
        from django.test import RequestFactory
        from django.http import HttpResponse
        from principal.views import lista_recibos
        req = RequestFactory().get('/recibos/'); req.user = ajeno
        with patch('principal.views.render', return_value=HttpResponse('')) as render:
            lista_recibos(req)
        self.assertFalse(render.call_args.args[2]['recibos'].exists())
        self.registro.refresh_from_db()
        self.assertIsNone(self.registro.fecha_emision)

    def test_permiso_explicito_y_revocacion(self):
        emitir(self.recibo.pk)
        user = get_user_model().objects.create_user(username='autorizado_sintetico')
        grant = AccesoRecibo.objects.create(recibo=self.recibo, usuario=user, otorgado_por=self.user)
        self.client.force_login(user)
        self.assertEqual(self.client.get(f'/recibos/{self.recibo.pk}/pdf/').status_code, 200)
        grant.delete()
        self.assertEqual(self.client.get(f'/recibos/{self.recibo.pk}/pdf/').status_code, 404)

    def test_permiso_global_separado(self):
        emitir(self.recibo.pk)
        user = get_user_model().objects.create_user(username='consulta_global_sintetica')
        user.user_permissions.add(Permission.objects.get(codename='ver_todos_recibos'))
        self.client.force_login(user)
        self.assertEqual(self.client.get(f'/recibos/{self.recibo.pk}/pdf/').status_code, 200)

    def test_staff_no_equivale_a_acceso_global(self):
        user = get_user_model().objects.create_user(username='staff_sintetico', is_staff=True)
        self.client.force_login(user)
        self.assertEqual(self.client.get(f'/recibos/{self.recibo.pk}/pdf/').status_code, 404)

    def test_superusuario_activo_y_usuario_inactivo(self):
        from .permisos import puede_ver_recibo
        user = get_user_model().objects.create_user(username='super_sintetico', is_superuser=True)
        self.assertTrue(puede_ver_recibo(user, self.recibo.pk))
        user.is_active = False
        self.assertFalse(puede_ver_recibo(user, self.recibo.pk))

    def test_detalle_y_ultimo_recibo_autorizados(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f'/recibos/{self.recibo.pk}/').status_code, 200)
        self.assertRedirects(self.client.get(f'/clientes/{self.cliente.pk}/recibo/'),
                             f'/recibos/{self.recibo.pk}/')

    def test_anulacion_exige_permiso_y_objeto(self):
        from django.core.exceptions import PermissionDenied
        from .autenticidad import anular_documento
        user = get_user_model().objects.create_user(username='anulador_ajeno_sintetico')
        user.user_permissions.add(Permission.objects.get(codename='anular_documento'))
        with self.assertRaises(PermissionDenied): anular_documento(self.registro, user, 'Prueba')

    def test_historico_sin_enlace_no_infiere_autorizacion(self):
        old = Recibo.objects.create(poliza=self.poliza, importe='42.00')
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(f'/recibos/{old.pk}/pdf/').status_code, 404)
        AccesoRecibo.objects.create(recibo=old, usuario=self.user, otorgado_por=self.user)
        self.assertEqual(self.client.get(f'/recibos/{old.pk}/pdf/').status_code, 200)

    def test_endpoint_emision_tambien_controla_objeto(self):
        ajeno = get_user_model().objects.create_user(username='directo_sintetico')
        self.client.force_login(ajeno)
        self.assertEqual(self.client.post(f'/recibos/{self.recibo.pk}/emitir/').status_code, 404)
        self.registro.refresh_from_db()
        self.assertIsNone(self.registro.fecha_emision)

    def test_admin_filtra_original_por_objeto(self):
        from django.contrib.admin.sites import AdminSite
        from django.test import RequestFactory
        from .admin import AutenticidadReciboAdmin
        user = get_user_model().objects.create_user(username='cotejo_sintetico', is_staff=True)
        user.user_permissions.add(Permission.objects.get(codename='view_autenticidadrecibo'))
        req = RequestFactory().get('/admin/'); req.user = user
        admin = AutenticidadReciboAdmin(AutenticidadRecibo, AdminSite())
        self.assertFalse(admin.has_view_permission(req, self.registro))
        self.assertFalse(admin.get_queryset(req).exists())
        AccesoRecibo.objects.create(recibo=self.recibo, usuario=user, otorgado_por=self.user)
        self.assertTrue(admin.has_view_permission(req, self.registro))

    def test_verificador_sin_texto_de_vigencia(self):
        pdf = emitir(self.recibo.pk)
        r = self.client.post('/recibos/verificar/', {'codigo': self.registro.codigo,
                             'archivo': SimpleUploadedFile('sintetico.pdf', pdf)})
        self.assertNotContains(r, 'vigente al consultar')
        self.assertContains(r, AVISO)
        self.assertEqual(r.context['resultado'], 'AUTENTICO')

    def post_cobro(self, client=None):
        c = client or self.client
        with patch('builtins.print'):
            return c.post('/cobros/nuevo/', {'poliza': self.poliza.pk, 'importe': '5.000,50',
                'plus': '100,00', 'fecha_pago': '2026-01-03', 'forma_pago': 'Efectivo',
                'observaciones': 'Cobro sintético', 'cantidad_cuotas_pagadas': '2'})

    def test_accidentes_personales_sin_vehiculo_protegido_una_copia(self):
        self.poliza.vehiculo = None
        self.poliza.tipo_seguro = 'Accidentes Personales'; self.poliza.save()
        TurnoCaja.objects.create(usuario=self.user)
        self.client.force_login(self.user)
        self.assertEqual(self.post_cobro().status_code, 302)
        r = AutenticidadRecibo.objects.exclude(pk=self.registro.pk).get()
        self.assertIsNone(r.original['poliza']['vehiculo'])
        pdf = emitir(r.recibo_id)
        self.assertEqual(len(re.findall(rb'/Type\s*/Page\b', pdf)), 1)
        self.assertEqual(verificar(r.codigo, pdf), 'AUTENTICO')
        self.assertEqual(self.client.get(f'/recibos/{r.recibo_id}/pdf/').content, pdf)

    def test_accidentes_personales_historico_una_copia(self):
        self.poliza.vehiculo = None; self.poliza.tipo_seguro = 'Accidentes Personales'; self.poliza.save()
        old = Recibo.objects.create(poliza=self.poliza, importe='42.00')
        AccesoRecibo.objects.create(recibo=old, usuario=self.user, otorgado_por=self.user)
        self.client.force_login(self.user)
        pdf = self.client.get(f'/recibos/{old.pk}/pdf/').content
        self.assertEqual(len(re.findall(rb'/Type\s*/Page\b', pdf)), 1)

    def test_csrf_cobro_exige_token(self):
        from principal.views import crear_cobro_seguro, crear_cobro
        self.assertFalse(getattr(crear_cobro_seguro, 'csrf_exempt', False))
        self.assertFalse(getattr(crear_cobro, 'csrf_exempt', False))
        c = Client(enforce_csrf_checks=True); c.force_login(self.user)
        TurnoCaja.objects.create(usuario=self.user)
        self.assertEqual(self.post_cobro(c).status_code, 403)
        self.assertEqual(MovimientoCliente.objects.count(), 0)

    def test_csrf_verificador_rechaza_post_sin_token(self):
        c = Client(enforce_csrf_checks=True)
        self.assertEqual(c.post('/recibos/verificar/', {}).status_code, 403)

    def test_cobro_con_proteccion_desactivada_conserva_acceso_emisor(self):
        TurnoCaja.objects.create(usuario=self.user); self.client.force_login(self.user)
        with override_settings(FORTEX_RECEIPT_SECURITY_ENABLED=False, FORTEX_RECEIPT_KEYS=[]):
            self.assertEqual(self.post_cobro().status_code, 302)
        new = Recibo.objects.exclude(pk=self.recibo.pk).get()
        self.assertFalse(AutenticidadRecibo.objects.filter(recibo=new).exists())
        self.assertEqual(self.client.get(f'/recibos/{new.pk}/pdf/').status_code, 200)

    def test_cobro_y_auditoria_mismos_resultados_activada_o_no(self):
        TurnoCaja.objects.create(usuario=self.user); self.client.force_login(self.user)
        outputs = []
        for enabled in [True, False]:
            # Mismo estado inicial sintético; los registros creados se eliminan por rollback.
            from django.db import transaction
            with transaction.atomic():
                with override_settings(FORTEX_RECEIPT_SECURITY_ENABLED=enabled):
                    self.assertEqual(self.post_cobro().status_code, 302)
                c = Cobro.objects.exclude(pk=self.cobro.pk).get()
                self.poliza.refresh_from_db()
                m = MovimientoCliente.objects.get()
                outputs.append((c.importe, c.plus, c.comision, c.fecha_pago, c.cuota,
                    c.cantidad_cuotas, c.forma_pago, c.estado, self.poliza.numero_cuota,
                    self.poliza.fecha_vencimiento, self.poliza.estado, m.tipo, m.titulo,
                    m.usuario_id, MovimientoCliente.objects.count()))
                transaction.set_rollback(True)
        self.assertEqual(outputs[0], outputs[1])

    def test_snapshot_v1_sigue_emitiendo(self):
        # El formato previo no contenía tipo_seguro; no se exige backfill.
        from .autenticidad import carga, firmar
        original = self.registro.original
        original['poliza'].pop('tipo_seguro')
        self.registro.original = original
        AutenticidadRecibo.objects.filter(pk=self.registro.pk).update(original=original,
            firma=firmar(carga(self.registro), self.registro.key_id))
        pdf = emitir(self.recibo.pk)
        self.assertEqual(verificar(self.registro.codigo, pdf), 'AUTENTICO')


class ConfiguracionTests(SimpleTestCase):
    def test_arranque_settings_normal_desactivado_claves_invalidas(self):
        # Ejecuta el archivo real de settings aislado, sin dotenv, variables reales ni conexión.
        for value in ['{json-roto', '[]', 'null', '"texto"', '{"k":7}', '{"k":"corta"}']:
            with self.subTest(tipo=value):
                with patch.dict(os.environ, {'FORTEX_RECEIPT_SECURITY_ENABLED': 'false',
                     'FORTEX_RECEIPT_KEYS': value}, clear=True), patch('dotenv.load_dotenv'):
                    spec = importlib.util.spec_from_file_location('settings_revision_sintetica',
                                   settings.BASE_DIR / 'pas_control' / 'settings.py')
                    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
                    self.assertFalse(module.FORTEX_RECEIPT_SECURITY_ENABLED)
                    self.assertEqual(module.FORTEX_RECEIPT_KEYS, {})

    def test_activada_rechaza_error_sin_revelar_valores(self):
        for keys in ['{VALOR-SINTETICO-QUE-NO-DEBE-LOGUEARSE', '[]', '{"k":"corta"}', '{}']:
            with self.assertRaises(ImproperlyConfigured) as exc:
                configurar_autenticidad({'FORTEX_RECEIPT_SECURITY_ENABLED':'true',
                    'FORTEX_RECEIPT_ACTIVE_KEY':'k', 'FORTEX_RECEIPT_KEYS':keys})
            self.assertEqual(str(exc.exception), 'Configuración de autenticidad FORTEX inválida.')

    def test_desactivada_conserva_claves_validas_para_pdf_previo(self):
        enabled, active, keys = configurar_autenticidad({'FORTEX_RECEIPT_SECURITY_ENABLED':'false',
            'FORTEX_RECEIPT_KEYS':'{"anterior":"SYNTHETIC-ONLY-KEY-000000000000000000000"}'})
        self.assertFalse(enabled)
        self.assertIn('anterior', keys)
