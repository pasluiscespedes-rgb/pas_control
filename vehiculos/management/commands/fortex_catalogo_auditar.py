"""Diagnóstico agregado y de solo lectura; no muestra clientes ni patentes."""
import json
from collections import Counter
from django.core.management.base import BaseCommand
from vehiculos.catalogo_maestro.normalizacion import normalizar
from vehiculos.models import MarcaVehiculo, ModeloVehiculo, Vehiculo


class Command(BaseCommand):
    help = 'Cobertura del catálogo respecto a registros existentes; salida estadística sin datos personales.'

    def handle(self, *args, **kwargs):
        indices = set()
        tipos = Counter()
        for marca, modelo, tipo in ModeloVehiculo.objects.select_related('marca').values_list(
                'marca__nombre', 'nombre', 'tipo').iterator(chunk_size=2000):
            indices.add((normalizar(marca), normalizar(modelo)))
            tipos[tipo] += 1
        total = faltantes = 0
        modelos_faltantes = set()
        for marca, modelo in Vehiculo.objects.values_list('marca', 'modelo').iterator(chunk_size=2000):
            total += 1
            key = (normalizar(marca), normalizar(modelo))
            if key not in indices:
                faltantes += 1
                modelos_faltantes.add(key)
        informe = {
            'marcas_catalogo': MarcaVehiculo.objects.count(),
            'modelos_catalogo': sum(tipos.values()),
            'modelos_por_tipo': dict(sorted(tipos.items())),
            'vehiculos_existentes': total,
            'vehiculos_sin_coincidencia_exacta': faltantes,
            'modelos_distintos_sin_coincidencia': len(modelos_faltantes),
            'cobertura_porcentaje': round(100 * (total-faltantes) / total, 2) if total else None,
            'nota': 'Métrica solo por nombre normalizado; no equivale a OCR validado',
        }
        self.stdout.write(json.dumps(informe, ensure_ascii=False, sort_keys=True))
