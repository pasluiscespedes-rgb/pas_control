import os
import shutil
import subprocess
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent
CARPETA_BACKUPS = BASE_DIR / "backups_postgresql"

BUCKET_NAME = os.environ.get(
    "B2_BUCKET_NAME",
    "fortex-pascontrol-backups-2026",
)


def subir_ultimo_backup():
    archivos = list(CARPETA_BACKUPS.glob("*.dump"))

    if not archivos:
        raise FileNotFoundError("No hay backups PostgreSQL para subir.")

    ultimo_backup = max(
        archivos,
        key=lambda archivo: archivo.stat().st_mtime
    )

    b2_exe = shutil.which("b2")

    if not b2_exe:
        raise RuntimeError(
            "No se encontró B2 CLI instalada en Windows."
        )

    nombre_remoto = f"backups/{ultimo_backup.name}"

    # La B2 CLI ya quedó autorizada en Windows.
    # Quitamos estas variables para evitar que interfieran
    # con la autorización guardada por 'b2 account authorize'.
    entorno = os.environ.copy()
    entorno.pop("B2_APPLICATION_KEY", None)
    entorno.pop("B2_APPLICATION_KEY_ID", None)

    subprocess.run(
        [
            b2_exe,
            "file",
            "upload",
            BUCKET_NAME,
            str(ultimo_backup),
            nombre_remoto,
        ],
        check=True,
        env=entorno,
    )

    print("OK - Backup subido correctamente a Backblaze")
    print(f"Archivo: {ultimo_backup.name}")
    print(f"Destino: {BUCKET_NAME}/{nombre_remoto}")

    return ultimo_backup


if __name__ == "__main__":
    subir_ultimo_backup()