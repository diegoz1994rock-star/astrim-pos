"""Fixtures de integración para el módulo de autenticación: SQLite real con
esquema completo y un usuario de prueba con rol y permiso asignados."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

import pos.core.database.session as session_module
from pos.core.database import model_registry
from pos.core.database.session import init_engine, session_scope
from pos.core.security.password import hash_password
from pos.modules.roles.infrastructure.models import Permission, Role, RolePermission
from pos.modules.users.infrastructure.models import User

TEST_USERNAME = "cajero1"
TEST_PASSWORD = "clave-valida-123"
TEST_PERMISSION_CODE = "sales.create"


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
    """Crea un rol con un permiso y un usuario activo asociado. Devuelve el `id` del usuario."""
    with session_scope() as session:
        role = Role(name="Cajero", is_system_role=True)
        session.add(role)
        session.flush()

        permission = Permission(code=TEST_PERMISSION_CODE, description="Registrar ventas")
        session.add(permission)
        session.flush()

        session.add(RolePermission(role_id=role.id, permission_id=permission.id))

        user = User(
            username=TEST_USERNAME,
            password_hash=hash_password(TEST_PASSWORD),
            full_name="Cajero de Prueba",
            role_id=role.id,
            is_active=True,
        )
        session.add(user)
        session.flush()
        user_id = user.id

    return user_id
