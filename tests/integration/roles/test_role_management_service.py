"""Pruebas de integración de RoleManagementService contra SQLite real."""

from __future__ import annotations

import pytest

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.roles.application.role_management_service import RoleManagementService
from pos.modules.roles.domain.events import RolePermissionsChangedEvent
from pos.modules.roles.infrastructure.models import Permission, Role
from pos.modules.users.infrastructure.models import User


def _seed_permission(code: str) -> int:
    with session_scope() as session:
        permission = Permission(code=code, description=code)
        session.add(permission)
        session.flush()
        return permission.id


def test_create_role_with_permissions(sqlite_engine: None) -> None:
    _seed_permission("sales.create")
    service = RoleManagementService(EventBus())

    role = service.create_role(
        name="Supervisor de turno",
        description="Rol personalizado",
        permission_codes={"sales.create"},
    )

    assert role.name == "Supervisor de turno"
    assert role.is_system_role is False
    assert role.permission_codes == frozenset({"sales.create"})


def test_create_role_with_duplicate_name_raises_conflict(sqlite_engine: None) -> None:
    service = RoleManagementService(EventBus())
    service.create_role(name="Cajero Senior", description=None, permission_codes=set())

    with pytest.raises(ConflictError):
        service.create_role(name="Cajero Senior", description=None, permission_codes=set())


def test_create_role_publishes_permissions_changed_event(sqlite_engine: None) -> None:
    bus = EventBus()
    received: list[RolePermissionsChangedEvent] = []
    bus.subscribe(RolePermissionsChangedEvent, received.append)
    service = RoleManagementService(bus)

    role = service.create_role(name="Auditor", description=None, permission_codes=set())

    assert len(received) == 1
    assert received[0].role_id == role.id


def test_update_role_permissions_replaces_existing_set(sqlite_engine: None) -> None:
    _seed_permission("inventory.adjust")
    _seed_permission("reports.view")
    service = RoleManagementService(EventBus())
    role = service.create_role(
        name="Bodeguero Senior", description=None, permission_codes={"inventory.adjust"}
    )

    updated = service.update_role_permissions(role.id, {"reports.view"})

    assert updated.permission_codes == frozenset({"reports.view"})


def test_update_permissions_of_unknown_role_raises_not_found(sqlite_engine: None) -> None:
    service = RoleManagementService(EventBus())

    with pytest.raises(NotFoundError):
        service.update_role_permissions(9999, set())


def test_delete_role_removes_it(sqlite_engine: None) -> None:
    service = RoleManagementService(EventBus())
    role = service.create_role(name="Rol Temporal", description=None, permission_codes=set())

    service.delete_role(role.id)

    assert role.id not in {r.id for r in service.list_roles()}


def test_delete_system_role_is_forbidden(sqlite_engine: None) -> None:
    with session_scope() as session:
        role = Role(name="Administrador General", is_system_role=True)
        session.add(role)
        session.flush()
        role_id = role.id
    service = RoleManagementService(EventBus())

    with pytest.raises(BusinessRuleViolationError):
        service.delete_role(role_id)


def test_delete_role_with_assigned_users_is_forbidden(sqlite_engine: None) -> None:
    """Prueba end-to-end de que `PRAGMA foreign_keys=ON` realmente protege
    la integridad referencial en SQLite (ver core.database.session)."""
    service = RoleManagementService(EventBus())
    role = service.create_role(name="Cajero de Prueba", description=None, permission_codes=set())

    with session_scope() as session:
        session.add(
            User(
                username="cajero_x",
                password_hash="hash-no-relevante",
                full_name="Cajero X",
                role_id=role.id,
                is_active=True,
            )
        )

    with pytest.raises(BusinessRuleViolationError):
        service.delete_role(role.id)
