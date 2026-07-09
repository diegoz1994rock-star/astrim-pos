"""Fixtures de integración para el módulo de usuarios: SQLite real con
esquema completo y un rol base para asignar a los usuarios de prueba."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine, session_scope
from pos.modules.roles.infrastructure.models import Role


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Iterator[None]:
    db_path = tmp_path / "test.db"
    engine = init_engine(f"sqlite:///{db_path}")
    model_registry.metadata.create_all(engine)
    yield
    session_module._engine = None
    session_module._session_factory = None


@pytest.fixture
def base_role_id(sqlite_engine: None) -> int:
    with session_scope() as session:
        role = Role(name="Cajero", is_system_role=True)
        session.add(role)
        session.flush()
        return role.id
