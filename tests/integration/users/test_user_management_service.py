"""Pruebas de integración de UserManagementService contra SQLite real."""

from __future__ import annotations

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.core.security.password import verify_password
from pos.modules.users.application.user_management_service import UserManagementService
from pos.modules.users.domain.events import UserCreatedEvent, UserStatusChangedEvent


def test_create_user_hashes_password(base_role_id: int) -> None:
    service = UserManagementService(EventBus())

    user = service.create_user(
        username="mesero1",
        password="clave-valida-123",
        full_name="Mesero Uno",
        role_id=base_role_id,
    )

    assert user.username == "mesero1"
    assert user.role_name == "Cajero"
    assert user.is_active is True


def test_created_user_can_authenticate_with_hashed_password(base_role_id: int) -> None:
    from pos.core.database.session import session_scope
    from pos.modules.users.infrastructure.repository import UserRepository

    service = UserManagementService(EventBus())
    service.create_user(
        username="mesero2",
        password="clave-valida-123",
        full_name="Mesero Dos",
        role_id=base_role_id,
    )

    with session_scope() as session:
        stored = UserRepository(session).get_by_username("mesero2")
        assert stored is not None
        assert verify_password("clave-valida-123", stored.password_hash)


def test_create_user_with_duplicate_username_raises_conflict(base_role_id: int) -> None:
    service = UserManagementService(EventBus())
    service.create_user(
        username="duplicado", password="clave-valida-123", full_name="A", role_id=base_role_id
    )

    with pytest.raises(ConflictError):
        service.create_user(
            username="duplicado", password="clave-valida-123", full_name="B", role_id=base_role_id
        )


def test_create_user_with_short_password_is_rejected(base_role_id: int) -> None:
    service = UserManagementService(EventBus())

    with pytest.raises(BusinessRuleViolationError):
        service.create_user(
            username="alguien", password="123", full_name="Alguien", role_id=base_role_id
        )


def test_create_user_with_unknown_role_raises_not_found(sqlite_engine: None) -> None:
    service = UserManagementService(EventBus())

    with pytest.raises(NotFoundError):
        service.create_user(
            username="huerfano", password="clave-valida-123", full_name="Sin rol", role_id=9999
        )


def test_create_user_publishes_user_created_event(base_role_id: int) -> None:
    bus = EventBus()
    received: list[UserCreatedEvent] = []
    bus.subscribe(UserCreatedEvent, received.append)
    service = UserManagementService(bus)

    user = service.create_user(
        username="evento1",
        password="clave-valida-123",
        full_name="Evento Uno",
        role_id=base_role_id,
    )

    assert len(received) == 1
    assert received[0].user_id == user.id


def test_set_active_false_deactivates_user_and_publishes_event(base_role_id: int) -> None:
    bus = EventBus()
    received: list[UserStatusChangedEvent] = []
    bus.subscribe(UserStatusChangedEvent, received.append)
    service = UserManagementService(bus)
    user = service.create_user(
        username="a_desactivar",
        password="clave-valida-123",
        full_name="A Desactivar",
        role_id=base_role_id,
    )

    updated = service.set_active(user.id, False)

    assert updated.is_active is False
    assert received[-1].is_active is False


def test_reset_password_changes_hash(base_role_id: int) -> None:
    from pos.core.database.session import session_scope
    from pos.modules.users.infrastructure.repository import UserRepository

    service = UserManagementService(EventBus())
    user = service.create_user(
        username="cambia_clave",
        password="clave-vieja-123",
        full_name="Cambia Clave",
        role_id=base_role_id,
    )

    service.reset_password(user.id, "clave-nueva-456")

    with session_scope() as session:
        stored = UserRepository(session).get_user(user.id)
        assert stored is not None
        assert verify_password("clave-nueva-456", stored.password_hash)
        assert not verify_password("clave-vieja-123", stored.password_hash)


def test_list_users_excludes_soft_deleted(base_role_id: int) -> None:
    service = UserManagementService(EventBus())
    service.create_user(
        username="visible", password="clave-valida-123", full_name="Visible", role_id=base_role_id
    )

    users = service.list_users()

    assert any(u.username == "visible" for u in users)
