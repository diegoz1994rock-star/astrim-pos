"""Acceso a datos de roles y permisos."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.roles.infrastructure.models import Permission, Role, RolePermission


class RoleRepository:
    """Operaciones sobre `roles`, `permissions` y `role_permissions`."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_roles(self) -> list[Role]:
        return list(self._session.scalars(select(Role).order_by(Role.name)))

    def list_permissions(self) -> list[Permission]:
        return list(self._session.scalars(select(Permission).order_by(Permission.code)))

    def get_role(self, role_id: int) -> Role | None:
        return self._session.get(Role, role_id)

    def get_role_by_name(self, name: str) -> Role | None:
        return self._session.scalar(select(Role).where(Role.name == name))

    def get_permission_codes_for_role(self, role_id: int) -> frozenset[str]:
        rows = self._session.execute(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role_id)
        )
        return frozenset(row[0] for row in rows)

    def get_permissions_by_codes(self, codes: set[str]) -> list[Permission]:
        if not codes:
            return []
        return list(self._session.scalars(select(Permission).where(Permission.code.in_(codes))))

    def create_role(self, *, name: str, description: str | None, is_system_role: bool) -> Role:
        role = Role(name=name, description=description, is_system_role=is_system_role)
        self._session.add(role)
        self._session.flush()
        return role

    def replace_role_permissions(self, role: Role, permissions: list[Permission]) -> None:
        """Reemplaza el conjunto completo de permisos asignados al rol.

        Hace `flush()` explícito: la sesión se crea con `autoflush=False`
        (ver core.database.session), así que sin este flush una lectura
        posterior en la misma transacción (ej. `get_permission_codes_for_role`
        para construir el DTO de respuesta) no vería las filas recién
        agregadas todavía.
        """
        self._session.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
        for permission in permissions:
            self._session.add(RolePermission(role_id=role.id, permission_id=permission.id))
        self._session.flush()

    def delete_role(self, role: Role) -> None:
        """Elimina el rol. Si hay usuarios asignados, la restricción de
        clave foránea `users.role_id -> roles.id` (ON DELETE RESTRICT,
        ver ARCHITECTURE.md §6) hace fallar el `flush`/`commit` con
        `IntegrityError` — la capa de aplicación la traduce a
        `BusinessRuleViolationError` sin que este repositorio necesite
        importar el módulo `users` (ver ARCHITECTURE.md §12b)."""
        self._session.query(RolePermission).filter(RolePermission.role_id == role.id).delete()
        self._session.delete(role)
