"""Importa solo archivos locales revisados; prohibido bajar URL o abrir la BD de clientes."""
import json
from pathlib import Path
from django.core.management.base import BaseCommand, CommandError
from vehiculos.catalogo_maestro.importacion import importar_archivo
from vehiculos.catalogo_maestro.normalizacion import TIPOS


class Command(BaseCommand):
    help = 'Importador del catálogo FORTEX. Predeterminado: simulación sin escribir en BD.'

    def add_arguments(self, parser):
        parser.add_argument('--archivo', required=True)
        parser.add_argument('--codigo', required=True)
        parser.add_argument('--titulo', required=True)
        parser.add_argument('--url', default='')
        parser.add_argument('--licencia', default='')
        parser.add_argument('--tipo-defecto', choices=TIPOS)
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **opciones):
        ruta = Path(opciones['archivo']).resolve(strict=True)
        if not ruta.is_file() or ruta.suffix.lower() != '.csv':
            raise CommandError('Solo se acepta un archivo CSV local')
        try:
            with ruta.open('r', encoding='utf-8-sig', newline='') as f:
                informe = importar_archivo(f, opciones['codigo'], opciones['titulo'],
                           opciones['url'], opciones['licencia'], opciones['tipo_defecto'],
                           dry_run=not opciones['aplicar'])
        except (ValueError, OSError, UnicodeError) as ex:
            raise CommandError(str(ex)) from None
        self.stdout.write(json.dumps(informe, ensure_ascii=False, sort_keys=True))
