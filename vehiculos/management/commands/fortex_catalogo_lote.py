"""Actualización reproducible de archivos locales mediante manifiesto SHA-256."""
import hashlib
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from vehiculos.catalogo_maestro.importacion import importar_archivo


class Command(BaseCommand):
    help = 'Ejecuta manifiesto aprobado de CSV en modo simulación por defecto.'

    def add_arguments(self, parser):
        parser.add_argument('--manifiesto', required=True)
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **kw):
        ruta = Path(kw['manifiesto']).resolve(strict=True)
        data = json.loads(ruta.read_text(encoding='utf-8-sig'))
        if not isinstance(data, list) or not data:
            raise CommandError('El manifiesto debe ser una lista no vacía')
        informes = []
        # Prevalidar TODOS los archivos y hashes antes de escribir el primero.
        for entrada in data:
            try:
                fichero = (ruta.parent / entrada['archivo']).resolve(strict=True)
                if not fichero.is_relative_to(ruta.parent) or fichero.suffix.lower() != '.csv':
                    raise ValueError('Ruta fuera de directorio del manifiesto o no CSV')
                sha = hashlib.sha256()
                with fichero.open('rb') as raw:
                    for fragmento in iter(lambda: raw.read(1024 * 1024), b''):
                        sha.update(fragmento)
                if sha.hexdigest() != entrada['sha256'].lower():
                    raise ValueError('Hash SHA-256 diferente al manifiesto')
            except (KeyError, OSError, ValueError) as ex:
                raise CommandError(f'Manifiesto inválido: {ex}') from None
        for entrada in data:
            fichero = (ruta.parent / entrada['archivo']).resolve()
            with fichero.open('r', encoding='utf-8-sig', newline='') as f:
                r = importar_archivo(f, entrada['codigo'], entrada['titulo'],
                           entrada.get('url',''),entrada.get('licencia',''),
                           entrada.get('tipo_por_defecto'), dry_run=not kw['aplicar'])
            informes.append({'archivo':fichero.name,'resultado':r})
        self.stdout.write(json.dumps(informes, ensure_ascii=False))
