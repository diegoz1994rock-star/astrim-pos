"""Sesión activa del usuario autenticado en esta instancia de la aplicación.

Distinta de la tabla `user_sessions` (persistida, usada para tokens de
sesión de larga duración / API de sincronización): esto es el estado en
memoria de "quién está usando la aplicación de escritorio ahora mismo".
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class ActiveSession:
    """Snapshot inmutable del usuario autenticado y sus permisos efectivos."""

    user_id: int
    username: str
    full_name: str
    role_id: int
    permission_codes: frozenset[str]
    logged_in_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def has_permission(self, code: str) -> bool:
        """Indica si la sesión tiene el permiso `code` (ver `roles.permissions`)."""
        return code in self.permission_codes


class SessionManager:
    """Contenedor de la sesión activa única del proceso de escritorio.

    Un `SessionManager` por aplicación (no un singleton global): se
    registra en el contenedor de DI para poder sustituirlo fácilmente en
    pruebas.
    """

    def __init__(self) -> None:
        self._current: ActiveSession | None = None

    @property
    def current(self) -> ActiveSession | None:
        """La sesión activa, o `None` si no hay ningún usuario autenticado."""
        return self._current

    def is_authenticated(self) -> bool:
        """Indica si hay un usuario autenticado en este momento."""
        return self._current is not None

    def login(self, session: ActiveSession) -> None:
        """Establece la sesión activa tras una autenticación exitosa."""
        self._current = session

    def logout(self) -> None:
        """Cierra la sesión activa."""
        self._current = None
