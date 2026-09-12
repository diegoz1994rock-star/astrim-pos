"""Fixtures de integración para el módulo de autenticación: SQLite real con
esquema completo y un usuario de prueba con un cargo de acceso total."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine, session_scope
from pos.core.security.password import hash_password
from pos.modules.job_positions.infrastructure.models import (
    JobArea,
    JobPosition,
    JobPositionPermission,
)
from pos.modules.users.infrastructure.models import User

TEST_USERNAME = "cajero1"
TEST_PASSWORD = "clave-valida-123"


@pytest.fixture
def sqlite_engine(tmp_path: Path) -> Iterator[None]:
    db_path = tmp_path / "test.db"
    engine = init_engine(f"sqlite:///{db_path}")
    model_registry.metadata.create_all(engine)
    yield
    session_module._engine = None
    session_module._session_factory = None


@pytest.fixture
def seeded_user(sqlite_engine: None) -> int:
    """Crea un área/cargo con `grants_full_access=True` y un usuario
    activo asociado. Devuelve el `id` del usuario."""
    with session_scope() as session:
        area = JobArea(name="Administración")
        session.add(area)
        session.flush()

        position = JobPosition(
            area_id=area.id, name="Administrador General", grants_full_access=True
        )
        session.add(position)
        session.flush()

        user = User(
            username=TEST_USERNAME,
            password_hash=hash_password(TEST_PASSWORD),
            full_name="Cajero de Prueba",
            job_area_id=area.id,
            job_position_id=position.id,
            is_active=True,
        )
        session.add(user)
        session.flush()
        user_id = user.id

    return user_id


@pytest.fixture
def seeded_user_with_permissions(sqlite_engine: None) -> int:
    """Usuario activo con un cargo (no admin) que tiene un permiso
    otorgado (`sales.create`). Devuelve el `id` del usuario."""
    with session_scope() as session:
        area = JobArea(name="Ventas y Atención al Cliente")
        session.add(area)
        session.flush()

        position = JobPosition(area_id=area.id, name="Cajero", grants_full_access=False)
        session.add(position)
        session.flush()

        session.add(
            JobPositionPermission(job_position_id=position.id, permission_code="sales.create")
        )

        user = User(
            username="cajero_con_permiso",
            password_hash=hash_password(TEST_PASSWORD),
            full_name="Cajero Con Permiso",
            job_area_id=area.id,
            job_position_id=position.id,
            is_active=True,
        )
        session.add(user)
        session.flush()
        return user.id


@pytest.fixture
def seeded_non_admin_user(sqlite_engine: None) -> int:
    """Usuario activo sin ningún cargo asignado (`is_admin` debe dar `False`)."""
    with session_scope() as session:
        user = User(
            username="mesero_no_admin",
            password_hash=hash_password(TEST_PASSWORD),
            full_name="Mesero Sin Cargo",
            is_active=True,
        )
        session.add(user)
        session.flush()
        return user.id
