"""Provision local explicita, sin imprimir secretos ni modificar settings."""
import csv
import json
import os
from pathlib import Path
import secrets
import subprocess

from django.core.management.base import BaseCommand, CommandError
from recibos.configuracion import identificador_clave_valido


class Command(BaseCommand):
    help = 'Genera un JSON de clave dedicada en archivo nuevo privado; nunca sobrescribe ni activa.'

    def add_arguments(self, parser):
        parser.add_argument('--destino', required=True)
        parser.add_argument('--identificador', required=True)

    def handle(self, *args, **options):
        identifier = options['identificador']
        if not identificador_clave_valido(identifier):
            raise CommandError('Identificador invalido (maximo 40, letras, numeros, guion).')
        path = Path(options['destino']).resolve()
        # Primero crear VACIO, restringir ACL, luego escribir el secreto. Sin ventana de exposicion.
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError:
            raise CommandError('No se puede crear el archivo nuevo privado.') from None
        try:
            if os.name == 'nt':
                result = subprocess.run(['whoami', '/user', '/fo', 'csv', '/nh'],
                                        check=True, capture_output=True, text=True)
                sid = next(csv.reader([result.stdout.strip()]))[1]
                subprocess.run(['icacls', str(path), '/inheritance:r', '/grant:r', f'*{sid}:(F)'],
                               check=True, capture_output=True)
            with os.fdopen(fd, 'w', encoding='utf8') as stream:
                fd = None
                json.dump({identifier: secrets.token_hex(32)}, stream)
                stream.flush()
                os.fsync(stream.fileno())
        except Exception:
            raise CommandError('No se completo la provision privada; no activar ni usar ese archivo.') from None
        finally:
            if fd is not None:
                os.close(fd)
        self.stdout.write('Archivo de clave creado. No se activo la seguridad ni se mostraron sus valores.')
