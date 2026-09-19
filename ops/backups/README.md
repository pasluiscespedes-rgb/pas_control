# FORTEX: backup independiente de producción

Servicio previsto: **fortex-backup-cron**, proyecto **artistic-nature**,
entorno **production**, Root Directory **/ops/backups**.
Estos archivos no crean servicios, no configuran variables ni habilitan cron.

## Imagen y ejecución

PostgreSQL **18.6-bookworm**, fijado por digest, con Python y dependencias
independientes de esta carpeta. El build y cada ejecución verifican pg_dump y
pg_restore 18.6. No usa el requirements.txt de la raíz ni carga Django.

El entrypoint heredado de PostgreSQL se reemplaza por tini; nunca se inicia un
servidor de base de datos. Se ejecuta sin privilegios, como usuario postgres.

Start Command (idéntico al CMD de la imagen):

    /usr/bin/timeout --signal=TERM --kill-after=30s 1800 /opt/venv/bin/python -u /app/backup.py

Una réplica, Restart Policy **Never**, sin dominio público, healthcheck HTTP,
migraciones ni pre-deploy command. No quitar el watchdog del Start Command:
limita la ejecución a 30 minutos, con hasta 30 segundos adicionales para terminar.
SIGTERM/SIGINT limpian procesos propios. Un timeout global devuelve código no cero,
aunque una terminación forzada impida escribir el evento ERROR.

## Variables del servicio

| Variable | Valor o referencia |
|---|---|
| PGHOST | ${{Postgres.RAILWAY_PRIVATE_DOMAIN}} |
| PGPORT | ${{Postgres.PGPORT}} |
| PGUSER | ${{Postgres.PGUSER}} |
| PGPASSWORD | ${{Postgres.PGPASSWORD}} |
| PGDATABASE | ${{Postgres.PGDATABASE}} |
| B2_APPLICATION_KEY_ID | Secreto del servicio |
| B2_APPLICATION_KEY | Secreto del servicio, preferentemente sellado |
| B2_BUCKET_NAME | fortex-pascontrol-backups-2026 |
| B2_PREFIX | backups/ (predeterminado) |

El único host permitido es **postgres.railway.internal**. Confirmar el dominio
privado antes de configurar el servicio. Otro dominio, localhost, una URL pública
o un sufijo parecido se rechazan. Si el servicio tuviera otro dominio privado,
revisar expresamente la allowlist del código; no relajarla para admitir cualquier host.

Las cinco variables PG son obligatorias. No se lee .env ni hay conexión de
respaldo local. Los procesos PostgreSQL reciben un entorno reducido, sin claves B2,
PGSERVICE ni opciones PG heredadas. El programa impone:

    PGCONNECT_TIMEOUT=20
    PGOPTIONS=-c default_transaction_read_only=on
    PGCLIENTENCODING=UTF8

No requiere Railway CLI, túneles, notebook, Public Access ni TCP Proxy de Postgres.
Las claves B2 no deben existir en Dockerfile, argumentos de proceso ni repositorio.
Se usa InMemoryAccountInfo; no se crea una caché persistente de autorización.
La clave B2 necesita identificar el bucket y listar, escribir y leer sus objetos
(listBuckets, listFiles, writeFiles, readFiles, según alcance). Restringir al bucket
y prefijo elegidos; no necesita permisos de eliminación.

## Flujo

1. Validar configuración, host exacto, versiones y autorización del bucket.
2. Crear directorio temporal exclusivo y nombre UTC con UUID:
   fortex_production_YYYY-MM-DD_HH-MM-SSZ_<uuid>.dump.partial.
3. Ejecutar pg_dump --format=custom --no-owner --no-password mediante variables PG.
4. Exigir salida 0 y archivo no vacío.
5. Validar con pg_restore --list; exigir éxito y al menos una entrada.
6. Calcular tamaño y SHA-1; solo entonces renombrar a .dump.
7. Subir exclusivamente ese archivo mediante b2sdk. No buscar el más reciente.
8. Consultar por el file ID devuelto: comprobar bucket, nombre, tamaño y SHA-1
   cuando esté disponible.
9. Descargar el mismo objeto por ID en streaming a un sumidero de hash (sin guardar
   otra copia). Comprobar tamaño y SHA-1 completos incluso en cargas multipartes.
10. Cerrar recursos y emitir SUCCESS; solo entonces devolver 0.

Hay hasta tres intentos de subida/verificación sobre el mismo archivo. Ante una
respuesta de subida perdida, se busca solamente el nombre exacto de esa ejecución
y se verifica antes de volver a subir. Una discrepancia de hash/metadatos falla sin
borrar ni reemplazar el objeto. El SDK tiene además reintentos internos, limitados
por el watchdog global. No hay política de retención ni eliminación de versiones.

El directorio temporal de ESTA ejecución se limpia al finalizar, también ante
fallos. No se inspeccionan ni borran backups existentes. Backblaze es el destino
persistente; un archivo que no logra subirse no se conserva entre despliegues.
No se necesita un volumen.

pg_restore --list valida la legibilidad del índice, no garantiza una restauración
completa. El servicio no restaura ni modifica datos.

## Recursos y logs

JSON en stdout: START, LOCAL_VALIDATED, RETRY, SUCCESS, ERROR.
Se registran UTC, run_id, etapa, nombre, bytes, SHA-1, entradas, objeto remoto,
file ID y duración según corresponda. Los errores usan códigos controlados.
No se imprimen salidas de comandos, excepciones externas, contraseñas, tokens,
URLs firmadas ni el entorno completo. Logs de librerías deshabilitados.

Se cierran respuestas HTTP, sesiones y pools, y se espera la terminación de
pg_dump/pg_restore. El adaptador de cierre usa la estructura LazyThreadPool de
b2sdk **2.12.0**, porque esa versión no ofrece close() público. Revisarlo al
actualizar el SDK; no quitar el pin de versión.

## Prueba manual futura (requiere autorización)

1. Construir la imagen con contexto ops/backups y verificar versiones / pip check.
2. Crear el servicio y configurar las referencias y secretos en production.
   Mantener Cron Schedule vacío y Restart Policy Never.
3. Desplegar manualmente UNA vez. Esta prueba genera un backup REAL: no es una
   comprobación estática y no debe ejecutarse sin autorización.
4. Comprobar SUCCESS, salida 0, entradas, tamaño y hash; consultar el objeto B2
   independientemente. No restaurar.
5. Confirmar que el proceso terminó y no quedó activo.
6. Solo después habilitar **30 1 * * ***: 01:30 UTC, equivalente a 22:30 de Argentina
   del día anterior. El programa no contiene un scheduler.
7. Una vez verificado el servicio, deshabilitar explícitamente la antigua tarea
   Windows para evitar respaldos locales duplicados. Este código no la modifica.

Caja queda desacoplada retirando su llamada a PowerShell. Los tres scripts legado
backup_postgres.ps1, backup_backblaze.py y backup_db.py se conservan intactos.
