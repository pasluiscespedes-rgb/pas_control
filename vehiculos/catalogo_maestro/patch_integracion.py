"""Aditivo e idempotente: usar en copia de código, nunca directamente en producción."""
from pathlib import Path

CHANGES = {
    'vehiculos/models.py': '\n# Extensión FORTEX catálogo maestro (no modifica Vehiculo).\nfrom .catalogo_maestro.modelos import FuenteCatalogoVehiculo, RegistroFuenteModelo, AliasMarcaVehiculo, AliasModeloVehiculo\n',
    'vehiculos/admin.py': '\n# Registro del catálogo maestro y sus equivalencias.\nfrom .catalogo_maestro import admin as catalogo_admin\n',
    'principal/urls.py': '\n# Buscador de catálogo FORTEX; no modifica el alta actual.\nfrom vehiculos.catalogo_maestro.views import sugerir_vehiculo, buscar_modelos\nurlpatterns.append(path("vehiculos/catalogo/sugerencias/", sugerir_vehiculo, name="fortex_catalogo_sugerencias"))\nurlpatterns.append(path("vehiculos/catalogo/buscar/", buscar_modelos, name="fortex_catalogo_buscar"))\n',
}


def aplicar(raiz):
    raiz = Path(raiz).resolve()
    faltantes = [p for p in CHANGES if not (raiz/p).is_file()]
    if faltantes:
        raise RuntimeError(f'Faltan archivos de FORTEX: {faltantes}')
    for nombre, bloque in CHANGES.items():
        ruta = raiz / nombre
        contenido = ruta.read_text(encoding='utf-8-sig')
        if bloque.strip() in contenido:
            continue
        if 'catalogo_maestro' in contenido:
            raise RuntimeError(f'Ya existe integración distinta en {nombre}; revisión manual obligatoria')
        ruta.write_text(contenido.rstrip() + '\n' + bloque, encoding='utf-8')


if __name__ == '__main__':
    import sys
    if len(sys.argv) != 2:
        raise SystemExit('Uso: python vehiculos/catalogo_maestro/patch_integracion.py RUTA_COPIA_FORTEX')
    aplicar(sys.argv[1])
