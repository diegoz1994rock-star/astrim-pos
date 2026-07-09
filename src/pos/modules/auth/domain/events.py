"""Eventos de dominio publicados por el módulo de autenticación.

Consumidos, entre otros, por el módulo de Auditoría (bitácora de accesos)
y por el módulo de Notificaciones (alertar a un administrador ante un
bloqueo de cuenta).
"""

from __future__ import annotations

from dataclasses import dataclass

from pos.core.events.event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class LoginSucceededEvent(DomainEvent):
    """Un usuario inició sesión exitosamente."""

    user_id: int
    username: str


@dataclass(frozen=True, kw_only=True)
class LoginFailedEvent(DomainEvent):
    """Un intento de inicio de sesión falló. `username` es el valor
    ingresado por el usuario, que puede no corresponder a ninguna cuenta
    real (no se debe asumir que existe)."""

    username: str
    reason: str


@dataclass(frozen=True, kw_only=True)
class AccountLockedEvent(DomainEvent):
    """Una cuenta quedó bloqueada tras superar el máximo de intentos
    fallidos configurado."""

    username: str
    locked_until: str
    """ISO 8601; se serializa como string para que el evento sea trivial de
    propagar vía el módulo de Sincronización si en el futuro aplica."""


@dataclass(frozen=True, kw_only=True)
class LogoutEvent(DomainEvent):
    """Un usuario cerró sesión explícitamente."""

    user_id: int
    username: str
