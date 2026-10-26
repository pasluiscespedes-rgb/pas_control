# FORTEX | Arquitectura modular independiente por ramo (propuesta V1)

Estado: DISEÑO, NO IMPLEMENTADO. Rama aislada. Prohibido fusionar o desplegar sin pruebas y aprobación humana.

## Invariantes obligatorias
1. Un Cliente único puede tener 0..N pólizas de 0..N ramos. Nunca imponer unicidad de póliza por cliente o por ramo.
2. Cliente es dueño de los datos comunes: nombre, apellido, DNI, domicilio, nacimiento y teléfono. No duplicar campos como fuente de verdad en módulos de riesgos.
3. Cada póliza tiene un ramo explícito, independiente del vehículo. Solo Automotor/Moto usan Vehiculo.
4. Cada póliza se vincula con exactamente un registro de riesgo de su ramo cuando ese ramo esté migrado; nunca con riesgos de otros ramos.
5. Cobros, recibos, caja, vencimientos y auditoría apuntan a Poliza (y Cliente vía Poliza), no al tipo de riesgo.
6. Los cambios en un ramo no pueden alterar validaciones, campos ni formularios de otro ramo.
7. Asegurado, tomador y beneficiarios pueden ser personas distintas; no sobrescribir Cliente para representarlos.
8. La eliminación de un cliente con pólizas históricas debe proteger la trazabilidad; revisar on_delete=CASCADE actual antes de migrar.
9. Datos históricos, importes y relaciones se preservan. Toda migración debe ser reversible o declarar pérdida y exigir respaldo verificado.
10. Sin deploy ni acceso a producción en esta etapa.

## Diseño lógico objetivo
- clientes.Cliente: identidad común, múltiples Poliza por FK.
- polizas.Poliza: cliente/tomador, ramo, aseguradora, nro póliza, fechas, estado, periodicidad, importes; núcleo administrativo común.
- riesgos_automotor.RiesgoAutomotor: FK/OneToOne con Poliza y Vehiculo, validaciones automotor.
- riesgos_moto.RiesgoMoto: FK/OneToOne con Poliza y Vehiculo, validaciones moto.
- riesgos_ap.RiesgoAP: OneToOne Poliza, asegurado, documento, actividad, coberturas y datos de producto.
- riesgos_vida.RiesgoVida: OneToOne Poliza, capital, beneficiarios y suscripción.
- riesgos_hogar.RiesgoHogar: OneToOne Poliza, inmueble y coberturas.
- riesgos_comercio.RiesgoComercio: OneToOne Poliza, actividad, local y bienes.
- riesgos_agro.RiesgoAgro: OneToOne Poliza, explotación/cultivo/maquinaria según subproducto.
- Los modelos específicos se incorporan solo al implementar cada ramo; evitar tablas vacías prematuras.

## Hallazgo concreto del código inspeccionado
En polizas/models.py del commit AP 2a7ebff, Poliza aún contiene:
- vehiculo FK nullable;
- asegurado_nombre, asegurado_documento y actividad_declarada específicos de AP;
- lógica de vencimiento/cuotas compartida;
- cliente FK con on_delete=CASCADE.

Por lo tanto AP funciona sin vehículo, pero NO está arquitectónicamente separado aún. El dictamen de AP no certifica esta modularidad.

## Plan incremental sin regresiones
Fase 0. Inventariar modelos, formularios, vistas, URLs, templates, servicios, recibos, caja, tests, migraciones y relaciones reales; documentar invariantes.
Fase 1. Añadir tests de aislamiento y multi-póliza con datos sintéticos: mismo DNI con auto+moto+AP+dos AP; cobros y recibos separados; ningún campo automotor exigido en AP.
Fase 2. Crear RiesgoAP como modelo específico vinculado 1:1 a Poliza; migración de datos desde tres campos AP actuales con verificación fila a fila, preservando temporalmente columnas anteriores.
Fase 3. Actualizar formularios/vistas AP para leer/escribir RiesgoAP mediante servicio transaccional, con compatibilidad temporal; validar PDFs y cobros.
Fase 4. Extraer automotor y moto en módulos específicos solo después de verificar relaciones históricas; mantener vehiculo FK legacy hasta migración completa.
Fase 5. Extender catálogo de ramos con pantallas propias y registro de formularios/validadores; habilitar Vida, Hogar, Comercio, Agro por separado con pruebas y aprobación.
Fase 6. Retirar campos legacy solo tras verificación completa de datos y restauración real del respaldo, nunca en el mismo deploy que la migración inicial.

## Pruebas de aceptación
- Un Cliente puede tener 2 autos, 1 moto, 3 AP y 1 vida sin duplicar Cliente ni cruzar datos.
- Editar AP no cambia datos de vehículos, pólizas o cobros de otro ramo.
- AP se crea sin Vehiculo y Automotor/Moto conservan sus validaciones.
- Cobro y recibo se atribuyen a la póliza correcta incluso con mismo cliente y aseguradora.
- Baja/anulación de una póliza no altera las demás.
- Los documentos PDF y vencimientos no incorporan campos de otro ramo.
- Tests SQLite + PostgreSQL 18 aislado; migración de ida y vuelta con conteos, hashes y pruebas de integridad; backup/restore real antes de producción.
- Sin cambios en Railway hasta autorización explícita.

## Política de despliegue
Ninguna de estas fases se fusiona o publica automáticamente. Primero revisar estado real de producción, backups recuperables, compatibilidad de versiones, ventana de mantenimiento y plan de rollback.
