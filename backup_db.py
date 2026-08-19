import shutil
from datetime import datetime, timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
ORIGEN = BASE_DIR / "db.sqlite3"
CARPETA_BACKUPS = BASE_DIR / "backups"


def crear_backup():
    CARPETA_BACKUPS.mkdir(exist_ok=True)

    fecha_hora = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    destino = CARPETA_BACKUPS / f"db_backup_{fecha_hora}.sqlite3"

    shutil.copy2(ORIGEN, destino)

    limpiar_backups_antiguos()

    return destino


def limpiar_backups_antiguos():
    limite = datetime.now() - timedelta(days=30)

    for archivo in CARPETA_BACKUPS.glob("db_backup_*.sqlite3"):
        fecha_archivo = datetime.fromtimestamp(archivo.stat().st_mtime)

        if fecha_archivo < limite:
            archivo.unlink()


if __name__ == "__main__":
    destino = crear_backup()
    print(f"✅ Backup creado correctamente: {destino}")