"""Propuestas OCR: nunca guardar un modelo por similitud aproximada."""
from .normalizacion import normalizar, similitud, anio_valido


def resolver_ocr(marca_texto, modelo_texto, tipo=None, anio=None, limite=5):
    """Contrato: COINCIDENCIA para exacto único; REVISAR en todo otro caso."""
    from vehiculos.models import MarcaVehiculo, ModeloVehiculo, AliasMarcaVehiculo, AliasModeloVehiculo

    nm = normalizar(marca_texto)
    nmodelo = normalizar(modelo_texto)
    if not nm or not nmodelo:
        return {"estado": "REVISAR", "motivo": "CAMPOS_INCOMPLETOS", "opciones": []}

    nombres = set()
    for m in MarcaVehiculo.objects.filter(activa=True).only('id','nombre'):
        if normalizar(m.nombre) == nm:
            nombres.add(m.pk)
    nombres.update(AliasMarcaVehiculo.objects.filter(normalizado=nm, aprobada=True).values_list('marca_id', flat=True))
    if not nombres:
        return {"estado": "REVISAR", "motivo": "MARCA_NO_ENCONTRADA", "opciones": []}

    qs = ModeloVehiculo.objects.select_related('marca').filter(marca_id__in=nombres, activa=True)
    if tipo:
        qs = qs.filter(tipo=tipo)
    # El año es señal adicional, no motivo para borrar un modelo histórico.
    candidatos = list(qs[:3001])
    if len(candidatos) > 3000:
        return {'estado': 'REVISAR', 'motivo': 'CATALOGO_EXCESIVO', 'opciones': []}
    exactos = {m.pk: m for m in candidatos if normalizar(m.nombre) == nmodelo}
    ids = list(AliasModeloVehiculo.objects.filter(modelo__in=candidatos, normalizado=nmodelo, aprobada=True)
               .values_list('modelo_id', flat=True))
    exactos.update({m.pk: m for m in candidatos if m.pk in ids})
    if len(exactos) > 1 and anio_valido(anio):
        anio_int = anio_valido(anio)
        compatibles = {id_:m for id_,m in exactos.items()
                       if m.anio_desde is not None and m.anio_hasta is not None
                       and m.anio_desde <= anio_int <= m.anio_hasta}
        if len(compatibles) == 1:
            exactos = compatibles
    if len(exactos) == 1:
        m = next(iter(exactos.values()))
        return {"estado": "COINCIDENCIA", "motivo": "EXACTA_APROBADA", "opciones": [_salida(m)]}
    if len(exactos) > 1:
        return {"estado": "REVISAR", "motivo": "AMBIGUA", "opciones": [_salida(m) for m in list(exactos.values())[:limite]]}
    cercanos = sorted(((similitud(m.nombre, nmodelo), m) for m in candidatos), reverse=True, key=lambda p:p[0])
    return {"estado": "REVISAR", "motivo": "SIN_EQUIVALENCIA_APROBADA",
            "opciones": [_salida(m, puntaje=score) for score, m in cercanos[:limite] if score >= 0.65]}


def _salida(modelo, puntaje=None):
    ret = {"modelo_id": modelo.pk, "marca": modelo.marca.nombre,
           "modelo": modelo.nombre, "tipo": modelo.tipo}
    if puntaje is not None:
        ret['similitud'] = puntaje
    return ret
