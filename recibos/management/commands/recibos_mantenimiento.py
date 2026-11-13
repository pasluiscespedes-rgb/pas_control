import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from recibos.models import VentanaVerificacion


class Command(BaseCommand):
    help = 'Elimina solo contadores del verificador de mas de 24 horas. No elimina documentos.'

    def handle(self, *args, **options):
        cutoff = int((time.time() - 86400) // getattr(settings, 'FORTEX_VERIFIER_WINDOW', 60))
        count, _ = VentanaVerificacion.objects.filter(ventana__lt=cutoff).delete()
        self.stdout.write(f'Contadores eliminados: {count}. Documentos sin cambios.')
