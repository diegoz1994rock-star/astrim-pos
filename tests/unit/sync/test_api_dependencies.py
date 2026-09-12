"""Pruebas unitarias de las dependencias FastAPI de autenticación/
autorización (`sync/server/api/dependencies.py`) — sin DB ni Qt, con un
`ActiveSession` construido a mano y un `Request` mínimo simulado.

`require_permission` no la usa todavía ningún endpoint de la Fase 1 (ver su
docstring) — se prueba directo para no dejar código sin verificar."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from pos.core.security.session import ActiveSession
from pos.modules.sync.server.api.dependencies import get_current_session, require_permission


def _session(
    *, is_admin: bool = False, permission_codes: frozenset[str] = frozenset()
) -> ActiveSession:
    return ActiveSession(
        user_id=1,
        username="usuario",
        full_name="Usuario de Prueba",
        is_admin=is_admin,
        permission_codes=permission_codes,
    )


def _request_with_session(session: ActiveSession | None) -> SimpleNamespace:
    """Doble mínimo de `fastapi.Request`: `get_current_session` solo lee
    `request.state.active_session`, así que no hace falta un `Request` real."""
    return SimpleNamespace(state=SimpleNamespace(active_session=session))


def test_get_current_session_returns_the_session_set_by_the_middleware() -> None:
    session = _session()
    request = _request_with_session(session)

    assert get_current_session(request) is session  # type: ignore[arg-type]


def test_get_current_session_without_middleware_raises_runtime_error() -> None:
    request = _request_with_session(None)

    with pytest.raises(RuntimeError, match="AuthMiddleware"):
        get_current_session(request)  # type: ignore[arg-type]


def test_require_permission_allows_admin_regardless_of_permission_codes() -> None:
    dependency = require_permission("sales.create")
    admin_session = _session(is_admin=True, permission_codes=frozenset())

    assert dependency(admin_session) is admin_session


def test_require_permission_allows_user_with_the_exact_code() -> None:
    dependency = require_permission("sales.create")
    session = _session(is_admin=False, permission_codes=frozenset({"sales.create"}))

    assert dependency(session) is session


def test_require_permission_rejects_user_without_the_code() -> None:
    dependency = require_permission("sales.create")
    session = _session(is_admin=False, permission_codes=frozenset({"inventory.view"}))

    with pytest.raises(HTTPException) as exc_info:
        dependency(session)

    assert exc_info.value.status_code == 403
