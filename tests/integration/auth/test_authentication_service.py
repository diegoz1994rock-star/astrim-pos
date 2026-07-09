"""Pruebas de integración de AuthenticationService contra SQLite real."""

from __future__ import annotations

from datetime import timedelta

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import AccountLockedError, AuthenticationError
from pos.core.security.session import SessionManager
from pos.modules.auth.application.authentication_service import AuthenticationService
from pos.modules.auth.domain.events import (
    AccountLockedEvent,
    LoginFailedEvent,
    LoginSucceededEvent,
    LogoutEvent,
)
from tests.integration.auth.conftest import TEST_PASSWORD, TEST_PERMISSION_CODE, TEST_USERNAME


def _make_service(*, max_failed_attempts: int = 5) -> AuthenticationService:
    return AuthenticationService(
        SessionManager(),
        EventBus(),
        max_failed_attempts=max_failed_attempts,
        lockout_window=timedelta(minutes=15),
    )


def test_login_with_valid_credentials_returns_active_session(seeded_user: int) -> None:
    service = _make_service()

    session = service.login(TEST_USERNAME, TEST_PASSWORD)

    assert session.user_id == seeded_user
    assert session.username == TEST_USERNAME
    assert TEST_PERMISSION_CODE in session.permission_codes


def test_login_sets_session_manager_current_session(seeded_user: int) -> None:
    session_manager = SessionManager()
    service = AuthenticationService(session_manager, EventBus())

    service.login(TEST_USERNAME, TEST_PASSWORD)

    assert session_manager.is_authenticated()
    assert session_manager.current is not None
    assert session_manager.current.username == TEST_USERNAME


def test_login_publishes_login_succeeded_event(seeded_user: int) -> None:
    bus = EventBus()
    received: list[LoginSucceededEvent] = []
    bus.subscribe(LoginSucceededEvent, received.append)
    service = AuthenticationService(SessionManager(), bus)

    service.login(TEST_USERNAME, TEST_PASSWORD)

    assert len(received) == 1
    assert received[0].username == TEST_USERNAME


def test_login_with_wrong_password_raises_generic_error(seeded_user: int) -> None:
    service = _make_service()

    with pytest.raises(AuthenticationError):
        service.login(TEST_USERNAME, "clave-incorrecta")


def test_login_with_unknown_username_raises_generic_error(seeded_user: int) -> None:
    service = _make_service()

    with pytest.raises(AuthenticationError):
        service.login("no_existe", "cualquier-clave")


def test_login_with_wrong_password_publishes_login_failed_event(seeded_user: int) -> None:
    bus = EventBus()
    received: list[LoginFailedEvent] = []
    bus.subscribe(LoginFailedEvent, received.append)
    service = AuthenticationService(SessionManager(), bus)

    with pytest.raises(AuthenticationError):
        service.login(TEST_USERNAME, "clave-incorrecta")

    assert len(received) == 1


def test_account_locks_after_max_failed_attempts(seeded_user: int) -> None:
    service = _make_service(max_failed_attempts=3)

    for _ in range(3):
        with pytest.raises(AuthenticationError):
            service.login(TEST_USERNAME, "clave-incorrecta")

    with pytest.raises(AccountLockedError):
        service.login(TEST_USERNAME, TEST_PASSWORD)


def test_account_lock_publishes_account_locked_event(seeded_user: int) -> None:
    bus = EventBus()
    received: list[AccountLockedEvent] = []
    bus.subscribe(AccountLockedEvent, received.append)
    service = AuthenticationService(SessionManager(), bus, max_failed_attempts=2)

    for _ in range(2):
        with pytest.raises(AuthenticationError):
            service.login(TEST_USERNAME, "clave-incorrecta")
    with pytest.raises(AccountLockedError):
        service.login(TEST_USERNAME, TEST_PASSWORD)

    assert len(received) == 1
    assert received[0].username == TEST_USERNAME


def test_logout_clears_session_and_publishes_event(seeded_user: int) -> None:
    session_manager = SessionManager()
    bus = EventBus()
    received: list[LogoutEvent] = []
    bus.subscribe(LogoutEvent, received.append)
    service = AuthenticationService(session_manager, bus)
    service.login(TEST_USERNAME, TEST_PASSWORD)

    service.logout()

    assert not session_manager.is_authenticated()
    assert len(received) == 1
    assert received[0].username == TEST_USERNAME


def test_logout_without_active_session_does_not_publish_event() -> None:
    bus = EventBus()
    received: list[LogoutEvent] = []
    bus.subscribe(LogoutEvent, received.append)
    service = AuthenticationService(SessionManager(), bus)

    service.logout()

    assert received == []
