"""Pruebas de las operaciones de bajo nivel sobre archivos de backup:
metadato embebido y checksum de integridad."""

from __future__ import annotations

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from pos.modules.backups.infrastructure.sqlite_file_ops import (
    compute_sha256,
    looks_like_pos_backup,
    read_backup_metadata,
    write_backup_metadata,
)


def _make_pos_like_db(path: Path) -> None:
    connection = sqlite3.connect(str(path))
    connection.execute("CREATE TABLE backup_history (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()


def test_write_and_read_backup_metadata_round_trips(tmp_path: Path) -> None:
    db_path = tmp_path / "backup.db"
    _make_pos_like_db(db_path)
    created_at = datetime(2026, 1, 15, 10, 9, 0, tzinfo=UTC)

    write_backup_metadata(db_path, app_version="0.1.0", created_at=created_at, origin="manual")

    metadata = read_backup_metadata(db_path)
    assert metadata["app_version"] == "0.1.0"
    assert metadata["origin"] == "manual"
    assert metadata["created_at"] == created_at.isoformat()


def test_read_backup_metadata_is_empty_for_a_db_without_it(tmp_path: Path) -> None:
    db_path = tmp_path / "plain.db"
    _make_pos_like_db(db_path)

    assert read_backup_metadata(db_path) == {}


def test_read_backup_metadata_is_empty_for_a_nonexistent_file(tmp_path: Path) -> None:
    assert read_backup_metadata(tmp_path / "no_existe.db") == {}


def test_compute_sha256_is_deterministic_and_detects_changes(tmp_path: Path) -> None:
    file_path = tmp_path / "data.bin"
    file_path.write_bytes(b"contenido original")

    first = compute_sha256(file_path)
    second = compute_sha256(file_path)
    assert first == second

    file_path.write_bytes(b"contenido modificado")
    assert compute_sha256(file_path) != first


def test_looks_like_pos_backup_accepts_a_db_with_backup_history_table(tmp_path: Path) -> None:
    db_path = tmp_path / "backup.db"
    _make_pos_like_db(db_path)

    assert looks_like_pos_backup(db_path) is True


def test_looks_like_pos_backup_rejects_a_foreign_sqlite_file(tmp_path: Path) -> None:
    db_path = tmp_path / "foreign.db"
    connection = sqlite3.connect(str(db_path))
    connection.execute("CREATE TABLE algo (id INTEGER PRIMARY KEY)")
    connection.commit()
    connection.close()

    assert looks_like_pos_backup(db_path) is False


def test_looks_like_pos_backup_rejects_a_non_sqlite_file(tmp_path: Path) -> None:
    file_path = tmp_path / "texto.db"
    file_path.write_text("esto no es sqlite")

    assert looks_like_pos_backup(file_path) is False
