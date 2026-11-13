"""Carga sin valores de secretos en mensajes de error."""
import json
import os
from urllib.parse import urlsplit

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured, ValidationError
from django.core.validators import DomainNameValidator
from django.urls import reverse


def identificador_clave_valido(value):
    return (isinstance(value, str) and 1 <= len(value) <= 40
            and all(char.isalnum() or char in '-_' for char in value))


def url_verificador():
    origin = getattr(settings, 'FORTEX_RECEIPT_VERIFIER_ORIGIN', None)
    if origin is None:
        origin = os.environ.get('FORTEX_RECEIPT_VERIFIER_ORIGIN', '')
    try:
        host = urlsplit(origin).hostname
        if not host or origin not in (f'https://{host}', f'https://{host}/'):
            raise ValueError
        DomainNameValidator(accept_idna=False)(host)
    except (ValueError, ValidationError):
        raise ValidationError('Configurar el origen HTTPS oficial del verificador.') from None
    return f'https://{host}' + reverse('verificar_recibo')


def configurar_autenticidad(environ):
    enabled = environ.get('FORTEX_RECEIPT_SECURITY_ENABLED', 'false').lower() == 'true'
    active = environ.get('FORTEX_RECEIPT_ACTIVE_KEY', '')
    try:
        keys = json.loads(environ.get('FORTEX_RECEIPT_KEYS', '{}'))
        if not isinstance(keys, dict) or any(
            not identificador_clave_valido(k) or not isinstance(v, str) or len(v.encode()) < 32
            for k, v in keys.items()
        ):
            raise ValueError
        if enabled and (not active or active not in keys):
            raise ValueError
    except (ValueError, TypeError):
        if enabled:
            raise ImproperlyConfigured('Configuración de autenticidad FORTEX inválida.') from None
        # Desactivada: nunca bloquear el arranque por esta configuración nueva.
        # Documentos ya protegidos fallan cerrados si no pueden verificar su firma.
        keys = {}
    return enabled, active, keys
