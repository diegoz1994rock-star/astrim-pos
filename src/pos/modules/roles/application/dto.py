"""DTOs de lectura del módulo de roles: desacoplan la presentación de los
modelos SQLAlchemy, que no deben cruzar hacia `presentation` directamente
(evita accesos a atributos perezosos fuera de una sesión activa)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PermissionDTO:
    """Vista de lectura de un permiso."""

    id: int
    code: str
    description: str | None


@dataclass(frozen=True)
class RoleDTO:
    """Vista de lectura de un rol, con los códigos de permiso asignados."""

    id: int
    name: str
    description: str | None
    is_system_role: bool
    permission_codes: frozenset[str]
