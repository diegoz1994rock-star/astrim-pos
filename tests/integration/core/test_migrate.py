"""Pruebas de integración de la migración automática al arrancar
(`core/database/migrate.py`), necesaria para que el instalador de Windows
entregue una app usable sin que el cliente ejecute `alembic upgrade head`
a mano (ver installer/README.md)."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from pos.core.database.migrate import run_pending_migrations


def _head_revision() -> str:
    config = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    config.set_main_option(
        "script_location", str(Path(__file__).resolve().parents[3] / "migrations")
    )
    script = ScriptDirectory.from_config(config)
    head = script.get_current_head()
    assert head is not None
    return head


def test_run_pending_migrations_creates_full_schema_from_scratch(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"

    run_pending_migrations(f"sqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    try:
        tables = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    finally:
        conn.close()

    assert "users" in tables
    assert "sync_stations" in tables
    assert version == _head_revision()


def test_run_pending_migrations_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "fresh.db"

    run_pending_migrations(f"sqlite:///{db_path}")
    run_pending_migrations(f"sqlite:///{db_path}")

    conn = sqlite3.connect(db_path)
    try:
        version = conn.execute("SELECT version_num FROM alembic_version").fetchone()[0]
    finally:
        conn.close()
    assert version == _head_revision()
