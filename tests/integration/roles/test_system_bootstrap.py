"""Pruebas de integración de `ensure_system_roles_and_permissions` (fuente
única de roles/permisos base, compartida por el script de sembrado y el
primer arranque real de la app — ver `installer/README.md`)."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.modules.roles.application.system_bootstrap import (
    SYSTEM_PERMISSIONS,
    SYSTEM_ROLES,
    ensure_system_roles_and_permissions,
)
from pos.modules.roles.infrastructure.repository import RoleRepository


def test_creates_all_system_roles_and_permissions(sqlite_engine: None) -> None:
    ensure_system_roles_and_permissions()

    with session_scope() as session:
        repo = RoleRepository(session)
        role_names = {role.name for role in repo.list_roles()}
        permission_codes = {permission.code for permission in repo.list_permissions()}

    assert role_names == {name for name, _ in SYSTEM_ROLES}
    assert permission_codes == set(SYSTEM_PERMISSIONS)


def test_admin_role_gets_every_system_permission(sqlite_engine: None) -> None:
    admin_role_id = ensure_system_roles_and_permissions()

    with session_scope() as session:
        repo = RoleRepository(session)
        codes = repo.get_permission_codes_for_role(admin_role_id)

    assert codes == frozenset(SYSTEM_PERMISSIONS)


def test_is_idempotent(sqlite_engine: None) -> None:
    first_id = ensure_system_roles_and_permissions()
    second_id = ensure_system_roles_and_permissions()

    assert first_id == second_id
    with session_scope() as session:
        repo = RoleRepository(session)
        assert len(repo.list_roles()) == len(SYSTEM_ROLES)
        assert len(repo.list_permissions()) == len(SYSTEM_PERMISSIONS)
