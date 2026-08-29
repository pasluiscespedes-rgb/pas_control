$fecha = Get-Date -Format "yyyy-MM-dd_HH-mm-ss"

$carpeta = "C:\Users\Notebook\pas_control\backups_postgresql"
$archivo = Join-Path $carpeta "fortex_db_$fecha.dump"

$envFile = Join-Path (Split-Path $PSScriptRoot -Parent) ".env"
$dbPasswordLine = Get-Content $envFile | Where-Object { $_ -match '^DB_PASSWORD=' } | Select-Object -First 1

if (-not $dbPasswordLine) {
    Write-Error "No se encontró DB_PASSWORD en el archivo .env"
    exit 1
}

$env:PGPASSWORD = $dbPasswordLine.Substring("DB_PASSWORD=".Length)

& "C:\Program Files\PostgreSQL\17\bin\pg_dump.exe" `
    -U postgres `
    -h localhost `
    -p 5432 `
    -F c `
    -f $archivo `
    fortex_db

Remove-Item Env:PGPASSWORD

$codigo = $LASTEXITCODE

if ($codigo -eq 0 -and (Test-Path $archivo)) {
    "$(Get-Date) - OK - Backup creado: $archivo" | Add-Content "C:\Users\Notebook\pas_control\backup_postgres.log"

    python "$(Split-Path $PSScriptRoot -Parent)\backup_backblaze.py"

} else {
    "$(Get-Date) - ERROR - pg_dump termino con codigo $codigo - Archivo: $archivo" | Add-Content "C:\Users\Notebook\pas_control\backup_postgres.log"
}

exit $codigo