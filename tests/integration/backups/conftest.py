"""Fixtures de integración para el módulo de backups: una base de datos
SQLite real en un archivo (no en memoria) — `VACUUM INTO` y la
restauración operan sobre archivos reales, no sobre `:memory:`."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine
from pos.modules.backups.application.backup_service import BackupService


@dataclass(frozen=True)
class BackupsFixtures:
    database_url: str
    db_path: Path
    backup_dir: Path
    service: BackupService


@pytest.fixture
def backups_env(tmp_path: Path) -> Iterator[BackupsFixtures]:
    db_path = tmp_path / "pos.db"
    database_url = f"sqlite:///{db_path}"
    engine = init_engine(database_url)
    model_registry.metadata.create_all(engine)

    backup_dir = tmp_path / "backups"
    service = BackupService(database_url, backup_dir)

    yield BackupsFixtures(
        database_url=database_url, db_path=db_path, backup_dir=backup_dir, service=service
    )

    session_module._engine = None
    session_module._session_factory = None
