"""Eventos de dominio publicados por el módulo de roles."""

from __future__ import annotations

from dataclasses import dataclass

from pos.core.events.event import DomainEvent


@dataclass(frozen=True, kw_only=True)
class RolePermissionsChangedEvent(DomainEvent):
    """Los permisos efectivos de un rol cambiaron.

    Relevante para `core.security.session.SessionManager`: si el usuario
    con la sesión activa tiene este rol, sus permisos en memoria quedan
    desactualizados hasta el siguiente login (documentado como limitación
    conocida; revisar en el módulo de Permisos si vale la pena refrescar
    la sesión activa en caliente)."""

    role_id: int
    permission_codes: frozenset[str]
