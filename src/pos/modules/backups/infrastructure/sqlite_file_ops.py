"""Operaciones de archivo de bajo nivel sobre la base de datos SQLite.

Usa `sqlite3` directo (no el engine de SQLAlchemy) porque `VACUUM INTO` es
específico de SQLite y porque restaurar requiere manipular el archivo
mientras el engine de la aplicación está separado — mezclar esto con
sesiones ORM abiertas sería confuso y propenso a fugas de conexión.
"""

from __future__ import annotations

import shutil
import sqlite3
from pathlib import Path


def sqlite_path_from_url(database_url: str) -> Path:
    """Extrae la ruta de archivo de una URL `sqlite:///...`.

    Lanza `ValueError` para cualquier otro motor: los backups por copia de
    archivo son específicos de SQLite (ver ARCHITECTURE.md §6 — con
    PostgreSQL/MySQL el backup se hace con las herramientas nativas del
    motor, no con este módulo).
    """
    prefix = "sqlite:///"
    if not database_url.startswith(prefix):
        raise ValueError(
            f"Los backups por archivo solo son compatibles con SQLite, no con: {database_url}"
        )
    return Path(database_url[len(prefix) :])


def backup_database_to(source_db_path: Path, destination_file: Path) -> int:
    """Crea una copia consistente de la base de datos usando `VACUUM INTO`.

    A diferencia de una copia de archivo cruda, `VACUUM INTO` produce un
    snapshot consistente incluso si hay escrituras concurrentes (otra
    conexión del propio proceso, ej. la sesión de la UI) — SQLite se
    encarga de la consistencia internamente.
    """
    destination_file.parent.mkdir(parents=True, exist_ok=True)
    if destination_file.exists():
        destination_file.unlink()

    connection = sqlite3.connect(str(source_db_path))
    try:
        connection.execute("VACUUM INTO ?", (str(destination_file),))
    finally:
        connection.close()

    return destination_file.stat().st_size


def is_valid_sqlite_database(file_path: Path) -> bool:
    """Verifica que `file_path` sea una base de datos SQLite legible antes
    de restaurarla, para no reemplazar la BD activa por un archivo corrupto
    o ajeno."""
    if not file_path.exists():
        return False
    try:
        connection = sqlite3.connect(str(file_path))
        try:
            connection.execute("SELECT name FROM sqlite_master LIMIT 1")
        finally:
            connection.close()
        return True
    except sqlite3.DatabaseError:
        return False


def restore_database_from(backup_file: Path, target_db_path: Path) -> None:
    """Reemplaza la base de datos activa por el contenido de `backup_file`.

    El llamador es responsable de haber cerrado/liberado el engine de
    SQLAlchemy antes de llamar a esta función (ver `BackupService.restore`)
    — de lo contrario, conexiones abiertas pueden bloquear la escritura en
    Windows o corromper el estado en memoria de la sesión.
    """
    if not is_valid_sqlite_database(backup_file):
        raise ValueError(f"'{backup_file}' no es una base de datos SQLite válida.")

    target_db_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(backup_file, target_db_path)
