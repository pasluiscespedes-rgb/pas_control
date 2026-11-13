"""Endpoint de sugerencias, privado y sin escrituras de datos del cliente."""
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from .coincidencias import resolver_ocr


@login_required
@require_GET
def sugerir_vehiculo(request):
    marca = request.GET.get('marca', '')[:100]
    modelo = request.GET.get('modelo', '')[:100]
    tipo = request.GET.get('tipo') or None
    anio = request.GET.get('anio') or None
    if not marca or not modelo:
        return JsonResponse({'estado':'REVISAR','motivo':'CAMPOS_INCOMPLETOS','opciones':[]})
    respuesta = resolver_ocr(marca, modelo, tipo=tipo, anio=anio)
    result = JsonResponse(respuesta)
    result['Cache-Control'] = 'private, no-store'
    return result

@login_required
@require_GET
def buscar_modelos(request):
    """Autocomplete: máximo 25 resultados; nunca envía todos los modelos al cliente."""
    from vehiculos.models import ModeloVehiculo
    q = (request.GET.get('q') or '').strip()[:70]
    marca = (request.GET.get('marca') or '').strip()[:100]
    tipo = (request.GET.get('tipo') or '').strip()[:30]
    if len(q) < 2:
        return JsonResponse({'resultados': []})
    opciones = ModeloVehiculo.objects.filter(activa=True, nombre__icontains=q)
    if marca:
        opciones = opciones.filter(marca__nombre__iexact=marca)
    if tipo:
        opciones = opciones.filter(tipo=tipo)
    opciones = opciones.select_related('marca').order_by('marca__nombre', 'nombre')[:25]
    response = JsonResponse({'resultados': [
        {'id': v.pk,'marca': v.marca.nombre,'modelo':v.nombre,'tipo':v.tipo,
         'anio_desde':v.anio_desde,'anio_hasta':v.anio_hasta} for v in opciones
    ]})
    response['Cache-Control'] = 'private, no-store'
    return response
