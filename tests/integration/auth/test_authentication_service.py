"""Pruebas de integración de AuthenticationService contra SQLite real."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select

from pos.core.database.session import session_scope
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
from pos.modules.auth.infrastructure.models import UserSession
from pos.modules.users.infrastructure.models import User
from tests.integration.auth.conftest import TEST_PASSWORD, TEST_USERNAME


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
    assert session.is_admin is True


def test_login_resolves_permission_codes_from_cargo(
    seeded_user_with_permissions: int,
) -> None:
    service = _make_service()

    session = service.login("cajero_con_permiso", TEST_PASSWORD)

    assert session.is_admin is False
    assert session.permission_codes == frozenset({"sales.create"})


def test_login_of_user_without_cargo_is_not_admin(seeded_non_admin_user: int) -> None:
    service = _make_service()

    session = service.login("mesero_no_admin", TEST_PASSWORD)

    assert session.is_admin is False


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


# -- authenticate() / get_session_for_token() (API HTTP, Fase 1) -----------


def test_authenticate_does_not_touch_the_desktop_session_manager(seeded_user: int) -> None:
    """Regresión crítica: un login hecho vía la API HTTP (`authenticate()`)
    NO debe pisar la sesión del proceso de escritorio (`SessionManager`,
    singleton compartido por todo el proceso) — a diferencia de `login()`,
    que sí la activa a propósito para la UI de escritorio."""
    session_manager = SessionManager()
    service = AuthenticationService(session_manager, EventBus())

    service.authenticate(TEST_USERNAME, TEST_PASSWORD)

    assert not session_manager.is_authenticated()
    assert session_manager.current is None


def test_authenticate_returns_active_session_token_and_expiry(seeded_user: int) -> None:
    service = _make_service()

    active_session, token, expires_at = service.authenticate(TEST_USERNAME, TEST_PASSWORD)

    assert active_session.username == TEST_USERNAME
    assert isinstance(token, str) and len(token) > 20
    assert expires_at > datetime.now(UTC)


def test_authenticate_with_wrong_password_raises_generic_error(seeded_user: int) -> None:
    service = _make_service()

    with pytest.raises(AuthenticationError):
        service.authenticate(TEST_USERNAME, "clave-incorrecta")


def test_login_still_activates_session_manager_after_refactor(seeded_user: int) -> None:
    """`login()` debe seguir comportándose exactamente igual que antes de
    extraer `authenticate()` — mismo camino feliz que ya cubre
    `test_login_sets_session_manager_current_session`, repetido acá para
    dejar explícito que el refactor no cambió el contrato de `login()`."""
    session_manager = SessionManager()
    service = AuthenticationService(session_manager, EventBus())

    active_session = service.login(TEST_USERNAME, TEST_PASSWORD)

    assert session_manager.is_authenticated()
    assert session_manager.current == active_session


def test_get_session_for_token_with_valid_token_returns_active_session(seeded_user: int) -> None:
    service = _make_service()
    _active_session, token, _expires_at = service.authenticate(TEST_USERNAME, TEST_PASSWORD)

    resolved = service.get_session_for_token(token)

    assert resolved is not None
    assert resolved.username == TEST_USERNAME
    assert resolved.user_id == seeded_user


def test_get_session_for_token_with_unknown_token_returns_none(seeded_user: int) -> None:
    service = _make_service()

    assert service.get_session_for_token("token-que-no-existe") is None


def test_get_session_for_token_with_expired_token_returns_none(seeded_user: int) -> None:
    service = _make_service()
    _active_session, token, _expires_at = service.authenticate(TEST_USERNAME, TEST_PASSWORD)

    with session_scope() as session:
        user_session = session.scalar(select(UserSession).where(UserSession.token == token))
        assert user_session is not None
        user_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)

    assert service.get_session_for_token(token) is None


def test_get_session_for_token_with_revoked_token_returns_none(seeded_user: int) -> None:
    service = _make_service()
    _active_session, token, _expires_at = service.authenticate(TEST_USERNAME, TEST_PASSWORD)

    with session_scope() as session:
        user_session = session.scalar(select(UserSession).where(UserSession.token == token))
        assert user_session is not None
        user_session.is_active = False

    assert service.get_session_for_token(token) is None


def test_get_session_for_token_updates_last_activity_at(seeded_user: int) -> None:
    service = _make_service()
    _active_session, token, _expires_at = service.authenticate(TEST_USERNAME, TEST_PASSWORD)

    with session_scope() as session:
        user_session = session.scalar(select(UserSession).where(UserSession.token == token))
        assert user_session is not None
        user_session.last_activity_at = datetime(2000, 1, 1, tzinfo=UTC)

    service.get_session_for_token(token)

    with session_scope() as session:
        user_session = session.scalar(select(UserSession).where(UserSession.token == token))
        assert user_session is not None
        assert user_session.last_activity_at > datetime(2000, 1, 2, tzinfo=UTC)


def test_get_session_for_token_when_user_deactivated_returns_none(seeded_user: int) -> None:
    """Un token técnicamente no expirado no debe seguir sirviendo si el
    usuario que lo emitió fue desactivado después — ver
    `AuthRepository.find_active_user_by_id`."""
    service = _make_service()
    _active_session, token, _expires_at = service.authenticate(TEST_USERNAME, TEST_PASSWORD)

    with session_scope() as session:
        user = session.scalar(select(User).where(User.username == TEST_USERNAME))
        assert user is not None
        user.is_active = False

    assert service.get_session_for_token(token) is None
