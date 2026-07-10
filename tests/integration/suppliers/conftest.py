"""Fixtures de integración para el módulo de proveedores."""

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
