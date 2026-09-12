"""Endpoints `/api/v1/auth/*`.

`create_auth_router` es una fábrica (no un `router` a nivel de módulo)
porque necesita cerrar sobre la instancia de `AuthenticationService` de esta
estación — mismo patrón que ya usa `server/app.py::create_sync_app` con
`SyncService` para el websocket de sincronización.

`login` no envuelve `authenticate()` en `try/except`: `AccountLockedError`/
`AuthenticationError` (cuenta bloqueada → 423, credenciales inválidas →
401) las traduce el manejador global de `errors.py` — ver
`install_domain_error_handler`, instalado una vez en `create_sync_app`."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pos.core.security.session import ActiveSession
from pos.modules.auth.application.authentication_service import AuthenticationService
from pos.modules.sync.server.api.dependencies import get_current_session
from pos.modules.sync.server.api.schemas import LoginRequest, LoginResponse, SessionInfo
from pos.modules.users.application.user_management_service import UserManagementService


def _job_position_name(user_service: UserManagementService, user_id: int) -> str | None:
    """Mismo criterio que `main.py::_current_job_position_name` del
    escritorio: una consulta de solo lectura ya existente
    (`UserManagementService.list_users()`), sin agregar el campo a
    `ActiveSession` ni tocar el módulo de autenticación."""
    return next(
        (user.job_position_name for user in user_service.list_users() if user.id == user_id),
        None,
    )


def create_auth_router(
    auth_service: AuthenticationService, user_service: UserManagementService
) -> APIRouter:
    router = APIRouter(prefix="/auth", tags=["auth"])

    @router.post("/login", response_model=LoginResponse)
    def login(payload: LoginRequest) -> LoginResponse:
        session, token, expires_at = auth_service.authenticate(
            payload.username, payload.password
        )
        return LoginResponse(
            token=token,
            expires_at=expires_at,
            session=SessionInfo.from_active_session(
                session, job_position_name=_job_position_name(user_service, session.user_id)
            ),
        )

    @router.get("/me", response_model=SessionInfo)
    def me(session: ActiveSession = Depends(get_current_session)) -> SessionInfo:
        return SessionInfo.from_active_session(
            session, job_position_name=_job_position_name(user_service, session.user_id)
        )

    return router
