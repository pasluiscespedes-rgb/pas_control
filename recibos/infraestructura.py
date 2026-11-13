"""Limites antes de leer multipart y cuota compartida entre workers.

REMOTE_ADDR solo: no confiar en X-Forwarded-For suministrado por el visitante.
El proxy autorizado debe normalizar REMOTE_ADDR o imponer tambien su propia cuota.
"""
import hashlib
import hmac
import time
import io

from django.conf import settings
from django.db import DatabaseError, transaction
from django.http import HttpResponse
from django.core.files.uploadhandler import FileUploadHandler, StopUpload
from django.core.files.uploadedfile import InMemoryUploadedFile
from django.urls import Resolver404, resolve


def consumir(clave, ventana, limite):
    from .models import VentanaVerificacion
    with transaction.atomic():
        fila, _ = VentanaVerificacion.objects.select_for_update().get_or_create(
            clave=clave, defaults={'ventana': ventana, 'intentos': 0})
        if fila.ventana != ventana:
            fila.ventana, fila.intentos = ventana, 0
        # Saturar: un atacante no puede desbordar el contador.
        if fila.intentos >= limite:
            return False
        fila.intentos += 1
        fila.save(update_fields=['ventana', 'intentos'])
        return True


def rechazo(texto, estado, retry=None):
    response = HttpResponse(texto, status=estado, content_type='text/plain; charset=utf-8')
    response['Cache-Control'] = 'no-store'
    response['X-Robots-Tag'] = 'noindex, nofollow'
    if retry is not None:
        response['Retry-After'] = str(retry)
    return response


class PDFEnMemoria(FileUploadHandler):
    """Nunca escribe el archivo presentado a disco ni a MEDIA_ROOT."""
    def new_file(self, *args, **kwargs):
        super().new_file(*args, **kwargs)
        self.file = io.BytesIO()
        self.bytes_recibidos = 0

    def receive_data_chunk(self, raw_data, start):
        self.bytes_recibidos += len(raw_data)
        if self.bytes_recibidos > 5 * 1024 * 1024:
            raise StopUpload(connection_reset=True)
        self.file.write(raw_data)

    def file_complete(self, file_size):
        self.file.seek(0)
        return InMemoryUploadedFile(self.file, self.field_name, self.file_name,
                                    self.content_type, file_size, self.charset)


class VerificadorMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            target = resolve(request.path_info).url_name == 'verificar_recibo'
        except Resolver404:
            target = False
        if target and request.method == 'POST':
            # El middleware de autenticacion precede a este control.
            # Usuarios externos no verifican documentos ni consumen cuota.
            usuario = getattr(request, 'user', None)
            if not usuario or not usuario.is_authenticated or not usuario.is_active:
                return rechazo('Acceso interno FORTEX: iniciar sesion.', 403)
            # Exigir longitud conocida. El limite del reverse proxy sigue siendo necesario
            # para frenar el cuerpo antes de que WSGI/ASGI lo reciba o lo almacene.
            try:
                length = int(request.META['CONTENT_LENGTH'])
                if length < 0:
                    raise ValueError
            except (KeyError, TypeError, ValueError):
                return rechazo('Se requiere Content-Length valido.', 411)
            if length > getattr(settings, 'FORTEX_VERIFIER_MAX_BODY', 6 * 1024 * 1024):
                return rechazo('El cuerpo supera el limite permitido.', 413)
            seconds = getattr(settings, 'FORTEX_VERIFIER_WINDOW', 60)
            ventana = int(time.time()) // seconds
            ip = request.META.get('REMOTE_ADDR', '')
            # Seudonimo de vida corta; nunca registrar la IP ni el codigo presentado.
            clave = hmac.new(settings.SECRET_KEY.encode(),
                             f'{ventana}:{ip}'.encode(), hashlib.sha256).hexdigest()
            try:
                # Limite global antes del IP: acota creacion de filas por ventana.
                allowed = consumir('global', ventana, getattr(settings, 'FORTEX_VERIFIER_GLOBAL', 200))
                allowed = allowed and consumir(clave, ventana, getattr(settings, 'FORTEX_VERIFIER_PER_IP', 20))
            except DatabaseError:
                return rechazo('Verificacion temporalmente no disponible.', 503, seconds)
            if not allowed:
                return rechazo('Demasiadas solicitudes. Intente mas tarde.', 429, seconds)
            request.upload_handlers = [PDFEnMemoria(request)]
        return self.get_response(request)
