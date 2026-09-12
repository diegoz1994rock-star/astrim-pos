"""Middleware de autenticación de la API HTTP de negocio.

Valida el encabezado `Authorization: Bearer <token>` en toda ruta bajo
`/api/v1`, salvo las explícitamente públicas (login, health) — así ningún
endpoint de negocio agregado en una fase futura puede quedar sin proteger
por simple olvido de un `Depends(...)` puntual: queda protegido por
default, no por convención.

La sesión resuelta se deja en `request.state.active_session` para que
`dependencies.get_current_session` (y de ahí, cualquier endpoint) la lea sin
repetir la validación."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from starlette.concurrency import run_in_threadpool
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response
from starlette.types import ASGIApp

from pos.modules.auth.application.authentication_service import AuthenticationService

PUBLIC_PATHS = frozenset({"/api/v1/auth/login", "/api/v1/health"})
"""Únicas rutas de `/api/v1` que no requieren token — ver docstring del
módulo. Cualquier ruta nueva bajo `/api/v1` queda protegida por default; si
alguna futura debe ser pública, se agrega acá explícitamente."""

_BEARER_PREFIX = "Bearer "


def _extract_bearer_token(authorization_header: str | None) -> str | None:
    if authorization_header is None or not authorization_header.startswith(_BEARER_PREFIX):
        return None
    token = authorization_header[len(_BEARER_PREFIX) :].strip()
    return token or None


class AuthMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: ASGIApp, *, auth_service: AuthenticationService) -> None:
        super().__init__(app)
        self._auth_service = auth_service

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        path = request.url.path
        if not path.startswith("/api/v1") or path in PUBLIC_PATHS:
            return await call_next(request)

        token = _extract_bearer_token(request.headers.get("authorization"))
        if token is None:
            return JSONResponse(
                {"detail": "Falta el encabezado 'Authorization: Bearer <token>'."},
                status_code=401,
            )

        # `get_session_for_token` hace consultas SQLAlchemy bloqueantes —
        # nunca directo en `dispatch` (correría en el loop de eventos de
        # asyncio y bloquearía toda otra conexión concurrente), mismo motivo
        # por el que `server/app.py` envuelve las llamadas de `SyncService`
        # en `asyncio.to_thread` dentro del websocket de sincronización.
        active_session = await run_in_threadpool(self._auth_service.get_session_for_token, token)
        if active_session is None:
            return JSONResponse({"detail": "Token inválido o expirado."}, status_code=401)

        request.state.active_session = active_session
        return await call_next(request)
