# Integración sobre FORTEX en producción

Esta rama integra el catálogo en el código **exactamente desplegado** en Railway al 13/11/2026: `1322661a4e5c6f1a3f5675d07c6ec15bd9c05534` (rama `design/recibo-plateado-20261113`). Se preservan recibos seguros, diseño plateado, cobros y WhatsFORTEX. **No está desplegada ni modifica bases reales.**

# FORTEX | Catálogo Maestro de Vehículos, etapa técnica V1

Fecha: 13 de noviembre de 2026. **Entrega de código aislado, no desplegada.**

## Objetivo

Ampliar sin destruir el catálogo existente de marcas/modelos para autos, motos, camionetas, furgones, camiones, acoplados y tráileres. Admite DNRPA de inscripciones, transferencias, motovehículos, CSV curados por proveedores autorizados y equivalencias verificadas para el OCR. **No importa datos de titulares de registros** y no modifica `Vehiculo`, clientes, pólizas, recibos o WhatsFORTEX.

## Lo que incluye

- Normalización de marcas/modelos y reconocimiento conservador de categorías.
- Importación idempotente desde CSV local, con simulación por defecto y transacción en modo aplicar.
- Lotes con manifiestos SHA-256, validados *antes* de importar el primer archivo.
- Modelos de fuentes y procedencia de cada modelo, alias por marca/modelo aprobados manualmente.
- Sugeridor para OCR: `COINCIDENCIA` únicamente cuando hay una coincidencia exacta única; si falta, es ambigua o solo hay parecidos, devuelve `REVISAR`.
- Buscador autenticado con hasta 25 resultados por consulta para futuro selector asincrónico, sin entregar todo el catálogo al navegador.
- Auditoría estadística de cobertura histórica sin mostrar clientes, documentos ni patentes (`python manage.py fortex_catalogo_auditar`).
- Migración aditiva `vehiculos.0008_catalogo_maestro` y registro de equivalencias en Django Admin.
- Pruebas puras (`unittest`) y pruebas adicionales Django, aún no ejecutadas.

## Fuentes recomendadas

- DNRPA Inscripciones iniciales de automotores: https://datos.jus.gob.ar/dataset/inscripciones-iniciales-de-autos
- DNRPA Transferencias: https://datos.jus.gob.ar/es_AR/dataset/transferencias-de-autos
- NHTSA vPIC (complemento internacional): https://vpic.nhtsa.dot.gov/api/
- Otras fuentes comerciales solo con licencia/contrato explícito.

Atribución DNRPA: Ministerio de Justicia de Argentina, datos abiertos CC BY 4.0, según el portal. **Los CSV del organismo pueden contener datos personales:** descargarlos únicamente en el ámbito autorizado, procesar exclusivamente campos vehiculares y evitar conservarlos en Git o compartirlos.

## Integración del código (solo en copia aislada)

1. Crear una rama privada desde el código **realmente vigente** en tu proyecto; no mezclar con un laboratorio de otra línea de historia.
2. Copiar la carpeta `vehiculos/catalogo_maestro/` y los archivos nuevos `vehiculos/management/commands/fortex_catalogo_*.py`, `vehiculos/migrations/0008_catalogo_maestro.py` y pruebas dentro del proyecto.
3. En la copia aislada ejecutar `python vehiculos/catalogo_maestro/patch_integracion.py RUTA_RAIZ_FORTEX` para anexar tres imports/rutas. **No correr directamente sobre producción.**
4. Con dependencias del proyecto instaladas: `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `python manage.py test vehiculos.tests_catalogo`. Verificar la migración y el esquema PostgreSQL en copia restaurada, sin modificar datos productivos.
5. Cargar CSV sintético de prueba: `python manage.py fortex_catalogo_importar --archivo vehiculos/catalogo_maestro/ejemplo_dnrpa_sintetico.csv --codigo DEMO --titulo 'Prueba sintética'` (simula). Para **una base descartable**, repetir agregando `--aplicar`.
6. La primera carga grande necesita interfaz de búsqueda progresiva y prueba del OCR end-to-end. No importar miles de opciones a la pantalla existente de `crear_riesgo.html`: el formulario actual renderiza cada modelo como `<option>` y perdería agilidad.
7. Solo después de aprobación funcional, respaldo/recuperación y ventana autorizada, considerar despliegue en Railway. Esta rama no modifica main, Railway ni datos reales.

## Cómo manejar fuentes reales

El comando reconoce campos como `automotor_marca_descripcion`, `automotor_modelo_descripcion`, `automotor_tipo_descripcion`, `automotor_anio_modelo`, `motovehiculo_marca_descripcion`, `motovehiculo_modelo_descripcion`, y también `marca,modelo,tipo_dnrpa,tipo_sistema`. Las filas de clasificación desconocida se rechazan (no se fuerzan como Auto). Si el archivo carece de tipo, se puede pasar `--tipo-defecto Moto` **solo cuando la procedencia demuestra que es un catálogo exclusivamente de motos**.

El año de inscripción **no es el año modelo**. Solo se admiten columnas explícitas de año-modelo.

Para cargar (en una base de pruebas primero):

```
python manage.py fortex_catalogo_importar --archivo archivo.csv --codigo DNRPA_2026_09 --titulo 'DNRPA septiembre 2026' --url 'https://datos.jus.gob.ar/dataset/inscripciones-iniciales-de-autos' --licencia 'CC BY 4.0'
# Mismo comando + --aplicar, únicamente después de revisar el resumen
```

El importador guarda fuentes, marca, modelo, tipo y años-modelo válidos. La base histórica no se borra. El reporte muestra filas rechazadas y nuevos objetos.

## Manifiesto de actualización mensual

`fortex_catalogo_lote --manifiesto manifiesto.json` simula de forma predeterminada. Usa entradas como:

```
[
  {
    "archivo": "dnrpa_limpio_2026_09.csv",
    "sha256": "REEMPLAZAR_POR_SHA256_REAL",
    "codigo": "DNRPA_2026_09",
    "titulo": "DNRPA septiembre 2026",
    "url": "https://datos.jus.gob.ar/dataset/inscripciones-iniciales-de-autos",
    "licencia": "CC BY 4.0"
  }
]
```

El lote aborta si falta algún archivo o cambió un SHA. Una vez aprobado, se usa `--aplicar`; las transacciones son **por archivo**, no por lote completo. No se ejecutan descargas desde la aplicación.

## Limitaciones explícitas

1. No están incluidas descargas reales de DNRPA, ni claves de APIs comerciales, ni un recuento de cobertura de modelos contra la base productiva.
2. No se ha ejecutado `manage.py test` ni migración real: este entorno carece de las dependencias Django 6/PostgreSQL del proyecto.
3. La interfaz actual de Riesgo y el OCR existente todavía no llaman al buscador nuevo; el endpoint está preparado para integrarlo y validar en navegador sin destruir la lógica anterior.
4. La cobertura de tráileres/remolques históricos no puede garantizarse solamente con DNRPA; se necesitará curación adicional y confirmación documental.
5. Una similitud OCR nunca equivale a identificación documental confirmada. No se modifica ningún cliente, póliza o vehículo hasta que un usuario revise y guarde los datos.
6. Los `nombre` históricos se conservan; posibles variantes anteriores ya existentes no se fusionan automáticamente. Hay que hacer una depuración supervisada antes de unir registros.

## Seguridad de datos y continuidad

Este paquete se basa en la versión GitHub `pasluiscespedes-rgb/pas_control` (rama `main`, commit `b2cf3abd2aaa2d79941787687078e56ddd734bc7`, consultado 13/11/2026). Puede ser distinto del árbol local más avanzado: cotejar antes de integrar. El código del catálogo se mantiene fuera de OCR, cobros, recibos y WhatsFORTEX. Ninguna actualización del catálogo debe bloquear el alta de un riesgo con revisión manual.
