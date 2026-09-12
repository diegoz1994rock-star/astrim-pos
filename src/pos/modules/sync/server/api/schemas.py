"""Modelos Pydantic del contrato JSON de la API — traducen explícitamente
`ActiveSession` (dataclass de `core.security.session`, pensado para uso en
memoria dentro del proceso de escritorio) a la forma que ve un cliente
remoto, en vez de serializar esa dataclass directamente. Mantiene el
contrato de red estable aunque `ActiveSession` cambie de forma interna."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from pos.core.security.session import ActiveSession


class LoginRequest(BaseModel):
    username: str
    password: str


class SessionInfo(BaseModel):
    """Identidad y permisos resueltos — la misma forma se usa tanto en la
    respuesta de `/auth/login` como en `/auth/me`, para que un cliente
    pueda cachear una y validar contra la otra sin dos modelos distintos."""

    user_id: int
    username: str
    full_name: str
    is_admin: bool
    permission_codes: list[str]
    logged_in_at: datetime
    job_position_name: str | None = None
    """Nombre del cargo del usuario — mismo dato y misma resolución que
    `main.py::_current_job_position_name` del escritorio (una consulta de
    solo lectura vía `UserManagementService`, `ActiveSession` no lo carga).
    `None` para un usuario sin cargo asignado, igual que el escritorio
    muestra "Empleado" en ese caso (ver `build_welcome_widget`)."""

    @classmethod
    def from_active_session(
        cls, session: ActiveSession, *, job_position_name: str | None = None
    ) -> SessionInfo:
        return cls(
            user_id=session.user_id,
            username=session.username,
            full_name=session.full_name,
            is_admin=session.is_admin,
            permission_codes=sorted(session.permission_codes),
            logged_in_at=session.logged_in_at,
            job_position_name=job_position_name,
        )


class LoginResponse(BaseModel):
    token: str
    expires_at: datetime
    session: SessionInfo


class HealthResponse(BaseModel):
    status: str = Field(default="ok")
    server_time: datetime
    """Hora UTC del servidor en el momento de responder — permite que un
    cliente remoto detecte desfase de reloj de su propio dispositivo contra
    `LoginResponse.expires_at` (también UTC absoluto): un teléfono con la
    hora mal puesta podría creer que un token válido ya expiró, o al revés."""
