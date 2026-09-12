"""Caso de uso de autenticación: inicio y cierre de sesión.

Orquesta `core.security` (hashing, `SessionManager`), la persistencia de
`modules.auth.infrastructure` y el bus de eventos para que Auditoría y
Notificaciones puedan reaccionar sin acoplarse a este servicio.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

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
from pos.modules.job_positions.infrastructure.repository import JobPositionRepository
from pos.modules.users.infrastructure.models import User

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

    def _build_active_session(
        self, user: User, session: Session, *, logged_in_at: datetime
    ) -> ActiveSession:
        """Resuelve `is_admin`/`permission_codes` desde el cargo del usuario
        y arma el `ActiveSession` — compartido por `authenticate()` (login
        con contraseña) y `get_session_for_token()` (validación de un token
        ya emitido), para no repetir la resolución de permisos en dos
        sitios."""
        is_admin = False
        permission_codes: frozenset[str] = frozenset()
        if user.job_position_id is not None:
            job_position_repo = JobPositionRepository(session)
            position = job_position_repo.get_position(user.job_position_id)
            is_admin = position is not None and position.grants_full_access
            if not is_admin:
                permission_codes = frozenset(
                    job_position_repo.list_permission_codes(user.job_position_id)
                )
        return ActiveSession(
            user_id=user.id,
            username=user.username,
            full_name=user.full_name,
            is_admin=is_admin,
            permission_codes=permission_codes,
            logged_in_at=logged_in_at,
        )

    def authenticate(self, username: str, password: str) -> tuple[ActiveSession, str, datetime]:
        """Verifica `username`/`password`, registra el intento y — si son
        válidas — genera el token de sesión persistido (`UserSession`,
        reutilizado ahora también por la API HTTP de negocio).

        Deliberadamente NO activa `SessionManager` (a diferencia de
        `login()`): `SessionManager` es la sesión del *proceso* de
        escritorio — un cliente remoto autenticándose contra la API no debe
        poder pisar la sesión de quien esté usando el escritorio en ese
        mismo proceso. `login()` es un envoltorio de este método que sí la
        activa, para el único llamador que la necesita (la UI de escritorio).

        Lanza `AccountLockedError`/`AuthenticationError` en los mismos casos
        que antes lanzaba `login()`. Devuelve `(sesión, token, expira_en)`.
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
        token: str | None = None
        expires_at = now + _SESSION_DURATION

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
                    repo.create_user_session(user_id=user.id, token=token, expires_at=expires_at)
                    active_session = self._build_active_session(user, session, logged_in_at=now)

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
        assert token is not None
        self._event_bus.publish(
            LoginSucceededEvent(user_id=active_session.user_id, username=active_session.username)
        )
        return active_session, token, expires_at

    def login(self, username: str, password: str) -> ActiveSession:
        """Autentica a `username` con `password` para la UI de escritorio.

        Lanza `AccountLockedError` si superó el máximo de intentos
        fallidos en la ventana configurada, o `AuthenticationError` si las
        credenciales son inválidas. En caso de éxito, deja la sesión
        activa en `SessionManager` y la devuelve — ver `authenticate()`
        para la variante sin efecto sobre `SessionManager` que usa la API.
        """
        active_session, _token, _expires_at = self.authenticate(username, password)
        self._session_manager.login(active_session)
        return active_session

    def get_session_for_token(self, token: str) -> ActiveSession | None:
        """Resuelve la `ActiveSession` de un token de la API HTTP, o `None`
        si el token no existe, ya expiró, fue invalidado, o el usuario que lo
        emitió ya no está activo — la validación de cada request de la API
        (ver `sync/server/api/middleware.py`), nunca la sesión del escritorio.
        """
        now = datetime.now(UTC)
        with session_scope() as session:
            repo = AuthRepository(session)
            user_session = repo.find_valid_session(token, now=now)
            if user_session is None:
                return None
            user = repo.find_active_user_by_id(user_session.user_id)
            if user is None:
                return None
            repo.touch_session_activity(user_session, now)
            return self._build_active_session(user, session, logged_in_at=user_session.created_at)

    def logout(self) -> None:
        """Cierra la sesión activa, si hay alguna."""
        current = self._session_manager.current
        self._session_manager.logout()
        if current is not None:
            self._event_bus.publish(
                LogoutEvent(user_id=current.user_id, username=current.username)
            )
