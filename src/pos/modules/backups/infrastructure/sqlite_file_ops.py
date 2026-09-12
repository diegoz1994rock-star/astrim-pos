"""Operaciones de archivo de bajo nivel sobre la base de datos SQLite.

Usa `sqlite3` directo (no el engine de SQLAlchemy) porque `VACUUM INTO` es
específico de SQLite y porque restaurar requiere manipular el archivo
mientras el engine de la aplicación está separado — mezclar esto con
sesiones ORM abiertas sería confuso y propenso a fugas de conexión.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

_METADATA_TABLE = "_pos_backup_metadata"
_CHECKSUM_CHUNK_SIZE = 1024 * 1024


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


def looks_like_pos_backup(file_path: Path) -> bool:
    """Filtro real para "Buscar backups": no basta con ser un SQLite
    legible (`is_valid_sqlite_database`), cualquier archivo `.db` ajeno al
    sistema pasaría esa prueba. Además exige la tabla `backup_history` —
    propia de este sistema, presente en toda base de datos real (y en las
    de prueba, creadas con `metadata.create_all` en vez de migraciones
    Alembic, que nunca generan `alembic_version`)."""
    if not is_valid_sqlite_database(file_path):
        return False
    connection = sqlite3.connect(str(file_path))
    try:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = 'backup_history'"
        ).fetchone()
        return row is not None
    finally:
        connection.close()


def write_backup_metadata(
    destination_file: Path, *, app_version: str, created_at: datetime, origin: str
) -> None:
    """Escribe una tabla `_pos_backup_metadata` dentro del propio archivo
    de backup, para que la versión/origen del backup sobrevivan aunque el
    archivo se copie a otra instalación o se pierda el `BackupHistory`
    original (ver `BackupService.import_backup_file`)."""
    connection = sqlite3.connect(str(destination_file))
    try:
        connection.execute(
            f"CREATE TABLE IF NOT EXISTS {_METADATA_TABLE} (key TEXT PRIMARY KEY, value TEXT)"
        )
        connection.executemany(
            f"INSERT OR REPLACE INTO {_METADATA_TABLE} (key, value) VALUES (?, ?)",
            [
                ("app_version", app_version),
                ("created_at", created_at.isoformat()),
                ("origin", origin),
            ],
        )
        connection.commit()
    finally:
        connection.close()


def read_backup_metadata(file_path: Path) -> dict[str, str]:
    """Lee el metadato embebido por `write_backup_metadata`, si existe.
    Devuelve `{}` para backups anteriores a esta funcionalidad o archivos
    SQLite ajenos al sistema — nunca inventa un valor."""
    if not is_valid_sqlite_database(file_path):
        return {}
    connection = sqlite3.connect(str(file_path))
    try:
        row = connection.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table' AND name = ?",
            (_METADATA_TABLE,),
        ).fetchone()
        if row is None:
            return {}
        rows = connection.execute(f"SELECT key, value FROM {_METADATA_TABLE}").fetchall()
        return {key: value for key, value in rows}
    except sqlite3.DatabaseError:
        return {}
    finally:
        connection.close()


def compute_sha256(file_path: Path) -> str:
    """Checksum de integridad, calculado por bloques para no cargar
    archivos grandes en memoria."""
    digest = hashlib.sha256()
    with file_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(_CHECKSUM_CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()
