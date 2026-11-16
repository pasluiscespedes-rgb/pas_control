# Victoria Bridge: fase 1 (NO DESPLEGAR)

## Objetivo
Consultar conversaciones WhatsFORTEX por solicitud explícita del propietario y analizar respuestas de NEXA, sin modificar mensajes ni estados de lectura.

## Implementado
- Ruta POST `/mensajeria/victoria/consultar/` protegida por sesión Django, CSRF, superusuario y coincidencia de `VICTORIA_BRIDGE_OWNER_USER_ID`.
- Búsqueda limitada por nombre o ID de conversación; hasta 10 conversaciones y 50 mensajes por conversación.
- Respuesta JSON sin teléfonos, adjuntos, payload original ni tokens de Meta; encabezado `Cache-Control: no-store`.
- No ejecuta `save()`, `update()`, llamadas a Meta ni acciones de envío.
- Registro básico de consultas sin contenido de mensajes.
- Pruebas unitarias propuestas en `mensajeria/test_victoria_bridge.py` (no ejecutadas).

## Pendiente crítico antes de producción
1. Ejecutar pruebas en PostgreSQL aislado y revisar permisos y regresiones.
2. Implementar auditoría persistente de accesos y retención controlada.
3. Verificar autorización real del propietario y protección de sesiones (incluyendo CSRF).
4. Incorporar atribución fiable del emisor (NEXA vs operador), ausente del modelo actual.
5. Crear y conectar un plugin/conector privado de ChatGPT con autenticación independiente, alcance mínimo y revocación. **La ruta de sesión Django no concede acceso a ChatGPT ni debe publicarse como API de máquina.**
6. Evitar acceso proactivo a mensajes reales sin autorización; cada lectura requiere petición explícita.
7. Revisar cumplimiento de privacidad y minimización de datos personales.
8. Obtener aprobación de despliegue tras pruebas y revisión de seguridad.

## Configuración
`VICTORIA_BRIDGE_OWNER_USER_ID`: ID numérico del usuario Django propietario. Si está ausente, el endpoint deniega todo acceso. Nunca almacenar contraseñas o tokens en el repositorio.

## Ejemplo (solo para sesión web Django autorizada)
`POST /mensajeria/victoria/consultar/` con CSRF y `buscar=Gabriel&limite=20`.
No habilitar este endpoint a terceros, no usarlo desde enlaces públicos ni compartir cookies de sesión con ChatGPT.

## Límites
Este prototipo es un mecanismo interno de consulta manual. **No es todavía el puente operativo entre Victoria y WhatsFORTEX.**
