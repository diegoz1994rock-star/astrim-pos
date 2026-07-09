"""Guardia de autorización: valida el permiso requerido antes de ejecutar un
caso de uso de `application` (ver ARCHITECTURE.md §8 — la UI puede además
ocultar controles, pero la autorización real vive aquí, no solo en la vista).
"""

from __future__ import annotations

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from pos.core.exceptions import AuthenticationError, PermissionDeniedError
from pos.core.security.session import SessionManager

F = TypeVar("F", bound=Callable[..., Any])


def require_permission(session_manager: SessionManager, code: str) -> Callable[[F], F]:
    """Decorador de fábrica: exige que la sesión activa de `session_manager`
    esté autenticada y tenga el permiso `code` antes de invocar la función.

    Uso típico en un caso de uso de `application`::

        @require_permission(session_manager, "sales.void")
        def void_sale(self, sale_id: int) -> None: ...
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            session = session_manager.current
            if session is None:
                raise AuthenticationError("No hay una sesión activa.")
            if not session.has_permission(code):
                raise PermissionDeniedError(
                    f"El usuario '{session.username}' no tiene el permiso '{code}'."
                )
            return func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator
