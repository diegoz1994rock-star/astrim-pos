"""Casos de uso de administración de roles y permisos."""

from __future__ import annotations

from sqlalchemy.exc import IntegrityError

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.roles.application.dto import PermissionDTO, RoleDTO
from pos.modules.roles.application.system_bootstrap import ensure_system_roles_and_permissions
from pos.modules.roles.domain.events import RolePermissionsChangedEvent
from pos.modules.roles.infrastructure.models import Role
from pos.modules.roles.infrastructure.repository import RoleRepository


def _to_dto(repo: RoleRepository, role: Role) -> RoleDTO:
    return RoleDTO(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system_role=role.is_system_role,
        permission_codes=repo.get_permission_codes_for_role(role.id),
    )


class RoleManagementService:
    """CRUD de roles y asignación de permisos (PROJECT_SPEC.md, "TIPOS DE
    USUARIO": el sistema debe permitir crear roles personalizados)."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def ensure_system_defaults(self) -> int:
        """Crea los roles/permisos base si es el primer arranque (ver
        `system_bootstrap.py`). Devuelve el id de "Administrador General"."""
        return ensure_system_roles_and_permissions()

    def list_roles(self) -> list[RoleDTO]:
        with session_scope() as session:
            repo = RoleRepository(session)
            return [_to_dto(repo, role) for role in repo.list_roles()]

    def list_permissions(self) -> list[PermissionDTO]:
        with session_scope() as session:
            repo = RoleRepository(session)
            return [
                PermissionDTO(id=p.id, code=p.code, description=p.description)
                for p in repo.list_permissions()
            ]

    def create_role(
        self, *, name: str, description: str | None, permission_codes: set[str]
    ) -> RoleDTO:
        """Crea un rol personalizado (nunca del sistema) con el conjunto de
        permisos dado."""
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre del rol no puede estar vacío.")

        with session_scope() as session:
            repo = RoleRepository(session)
            if repo.get_role_by_name(name) is not None:
                raise ConflictError(f"Ya existe un rol llamado '{name}'.")

            role = repo.create_role(name=name, description=description, is_system_role=False)
            permissions = repo.get_permissions_by_codes(permission_codes)
            repo.replace_role_permissions(role, permissions)
            dto = _to_dto(repo, role)

        self._event_bus.publish(
            RolePermissionsChangedEvent(role_id=dto.id, permission_codes=dto.permission_codes)
        )
        return dto

    def update_role_permissions(self, role_id: int, permission_codes: set[str]) -> RoleDTO:
        """Reemplaza el conjunto de permisos asignados a un rol existente."""
        with session_scope() as session:
            repo = RoleRepository(session)
            role = repo.get_role(role_id)
            if role is None:
                raise NotFoundError(f"No existe el rol con id={role_id}.")

            permissions = repo.get_permissions_by_codes(permission_codes)
            repo.replace_role_permissions(role, permissions)
            dto = _to_dto(repo, role)

        self._event_bus.publish(
            RolePermissionsChangedEvent(role_id=dto.id, permission_codes=dto.permission_codes)
        )
        return dto

    def delete_role(self, role_id: int) -> None:
        """Elimina un rol personalizado. Lanza `BusinessRuleViolationError`
        si es un rol del sistema o si aún tiene usuarios asignados."""
        with session_scope() as session:
            repo = RoleRepository(session)
            role = repo.get_role(role_id)
            if role is None:
                raise NotFoundError(f"No existe el rol con id={role_id}.")
            if role.is_system_role:
                raise BusinessRuleViolationError("No se puede eliminar un rol del sistema.")

            try:
                repo.delete_role(role)
                session.flush()
            except IntegrityError as error:
                raise BusinessRuleViolationError(
                    "No se puede eliminar el rol: todavía tiene usuarios asignados."
                ) from error
