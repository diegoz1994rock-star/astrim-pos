"""Acceso a datos del módulo de autenticación.

Consulta directamente el modelo de `users` (no solo los propios
`user_sessions`/`login_attempts`) porque autenticar es, por definición,
una operación que cruza esos módulos — es una dependencia intencional y
documentada en MODULES.md ("Login depende de: users, job_positions"), no
una violación de ARCHITECTURE.md §12b (esa convención aplica a
declaraciones de columnas `ForeignKey`/`relationship`, no a consultas de
aplicación entre módulos con una dependencia reconocida).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos.modules.auth.infrastructure.models import LoginAttempt, UserSession
from pos.modules.users.infrastructure.models import User


class AuthRepository:
    """Operaciones de lectura/escritura necesarias para autenticar un usuario."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def find_active_user_by_username(self, username: str) -> User | None:
        """Busca un usuario activo y no eliminado por su `username`."""
        return self._session.scalar(
            select(User).where(
                User.username == username,
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        )

    def find_active_user_by_id(self, user_id: int) -> User | None:
        """Igual que `find_active_user_by_username` pero por `id` — usada al
        validar un token de sesión (`UserSession.user_id`): si el usuario fue
        desactivado/eliminado después de emitirse el token, debe dejar de
        resolver, aunque el token en sí no haya expirado todavía."""
        return self._session.scalar(
            select(User).where(
                User.id == user_id,
                User.is_active.is_(True),
                User.is_deleted.is_(False),
            )
        )

    def count_recent_failed_attempts(self, username: str, since: datetime) -> int:
        """Cantidad de intentos fallidos de `username` desde `since`, usada
        para el bloqueo por múltiples intentos fallidos."""
        count = self._session.scalar(
            select(func.count())
            .select_from(LoginAttempt)
            .where(
                LoginAttempt.username_attempted == username,
                LoginAttempt.success.is_(False),
                LoginAttempt.attempted_at >= since,
            )
        )
        return count or 0

    def record_attempt(
        self,
        *,
        username: str,
        user_id: int | None,
        success: bool,
        failure_reason: str | None,
    ) -> None:
        """Registra un intento de inicio de sesión, exitoso o fallido."""
        self._session.add(
            LoginAttempt(
                username_attempted=username,
                user_id=user_id,
                success=success,
                failure_reason=failure_reason,
            )
        )

    def create_user_session(self, *, user_id: int, token: str, expires_at: datetime) -> None:
        """Crea una sesión persistida para el usuario autenticado."""
        self._session.add(UserSession(user_id=user_id, token=token, expires_at=expires_at))

    def find_valid_session(self, token: str, *, now: datetime) -> UserSession | None:
        """Busca la sesión persistida por `token`, solo si sigue activa y no
        expiró — usada por la API HTTP para validar el encabezado
        `Authorization: Bearer` en cada request (ver
        `AuthenticationService.get_session_for_token`)."""
        return self._session.scalar(
            select(UserSession).where(
                UserSession.token == token,
                UserSession.is_active.is_(True),
                UserSession.expires_at > now,
            )
        )

    def touch_session_activity(self, user_session: UserSession, when: datetime) -> None:
        """Actualiza `last_activity_at` de una sesión persistida validada —
        mismo propósito que `touch_last_login`, pero por request de API en
        vez de por inicio de sesión."""
        user_session.last_activity_at = when

    def touch_last_login(self, user: User, when: datetime) -> None:
        """Actualiza la marca de último inicio de sesión del usuario."""
        user.last_login_at = when
