"""Fixtures compartidos para pruebas de integración contra SQLite real.

Se usa un archivo SQLite temporal (no `:memory:`) porque el engine global
de `core.database.session` puede abrir varias conexiones, y SQLite en
memoria no comparte datos entre conexiones distintas sin configuración
adicional de pool — un archivo temporal es igual de real y aislado por test.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Iterator[None]:
    db_path = tmp_path / "test.db"
    engine = init_engine(f"sqlite:///{db_path}")
    model_registry.metadata.create_all(engine)
    yield
    session_module._engine = None
    session_module._session_factory = None
