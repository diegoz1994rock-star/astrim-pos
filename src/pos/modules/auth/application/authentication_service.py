"""Caso de uso de autenticación: inicio y cierre de sesión.

Orquesta `core.security` (hashing, `SessionManager`), la persistencia de
`modules.auth.infrastructure` y el bus de eventos para que Auditoría y
Notificaciones puedan reaccionar sin acoplarse a este servicio.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import AccountLockedError, AuthenticationError
from pos.core.security.password import verify_password
from pos.core.security.session import ActiveSession, SessionManager
from pos.modules.auth.domain.events import (
    AccountLockedEvent,
    LoginFailedEvent,
    LoginSucceededEvent,
    LogoutEvent,
)
from pos.modules.auth.infrastructure.repository import AuthRepository

_GENERIC_AUTH_ERROR_MESSAGE = "Usuario o contraseña incorrectos."
"""Mensaje deliberadamente genérico: no revela si el usuario existe o si
fue la contraseña la que falló, para no facilitar enumeración de cuentas."""

_SESSION_DURATION = timedelta(hours=12)


class AuthenticationService:
    """Autentica usuarios contra la base de datos y gestiona la sesión activa
    del proceso de escritorio (ver `core.security.session.SessionManager`)."""

    def __init__(
        self,
        session_manager: SessionManager,
        event_bus: EventBus,
        *,
        max_failed_attempts: int = 5,
        lockout_window: timedelta = timedelta(minutes=15),
    ) -> None:
        self._session_manager = session_manager
        self._event_bus = event_bus
        self._max_failed_attempts = max_failed_attempts
        self._lockout_window = lockout_window

    def login(self, username: str, password: str) -> ActiveSession:
        """Autentica a `username` con `password`.

        Lanza `AccountLockedError` si superó el máximo de intentos
        fallidos en la ventana configurada, o `AuthenticationError` si las
        credenciales son inválidas. En caso de éxito, deja la sesión
        activa en `SessionManager` y la devuelve.
        """
        now = datetime.now(UTC)

        # El intento (éxito o fracaso) siempre debe persistir, incluso cuando
        # el resultado final es una excepción para el llamador. Por eso el
        # error a lanzar se guarda en una variable y se lanza DESPUÉS de que
        # el bloque `with` haga commit — lanzarlo dentro del bloque haría que
        # `session_scope` revierta la transacción y perdiera el intento
        # registrado (el bloqueo por intentos fallidos nunca se activaría).
        error_to_raise: AccountLockedError | AuthenticationError | None = None
        active_session: ActiveSession | None = None

        with session_scope() as session:
            repo = AuthRepository(session)

            recent_failures = repo.count_recent_failed_attempts(
                username, since=now - self._lockout_window
            )
            if recent_failures >= self._max_failed_attempts:
                error_to_raise = AccountLockedError(
                    "Cuenta bloqueada temporalmente por múltiples intentos fallidos. "
                    "Intenta de nuevo más tarde o contacta a un administrador."
                )
            else:
                user = repo.find_active_user_by_username(username)
                if user is None or not verify_password(password, user.password_hash):
                    repo.record_attempt(
                        username=username,
                        user_id=user.id if user is not None else None,
                        success=False,
                        failure_reason="invalid_credentials",
                    )
                    error_to_raise = AuthenticationError(_GENERIC_AUTH_ERROR_MESSAGE)
                else:
                    repo.record_attempt(
                        username=username, user_id=user.id, success=True, failure_reason=None
                    )
                    repo.touch_last_login(user, now)

                    token = secrets.token_urlsafe(32)
                    repo.create_user_session(
                        user_id=user.id, token=token, expires_at=now + _SESSION_DURATION
                    )

                    permission_codes = repo.get_permission_codes_for_role(user.role_id)
                    active_session = ActiveSession(
                        user_id=user.id,
                        username=user.username,
                        full_name=user.full_name,
                        role_id=user.role_id,
                        permission_codes=frozenset(permission_codes),
                        logged_in_at=now,
                    )

        if isinstance(error_to_raise, AccountLockedError):
            locked_until = now + self._lockout_window
            self._event_bus.publish(
                AccountLockedEvent(username=username, locked_until=locked_until.isoformat())
            )
            raise error_to_raise
        if error_to_raise is not None:
            self._event_bus.publish(
                LoginFailedEvent(username=username, reason="invalid_credentials")
            )
            raise error_to_raise

        assert active_session is not None
        self._session_manager.login(active_session)
        self._event_bus.publish(
            LoginSucceededEvent(user_id=active_session.user_id, username=active_session.username)
        )
        return active_session

    def logout(self) -> None:
        """Cierra la sesión activa, si hay alguna."""
        current = self._session_manager.current
        self._session_manager.logout()
        if current is not None:
            self._event_bus.publish(
                LogoutEvent(user_id=current.user_id, username=current.username)
            )
