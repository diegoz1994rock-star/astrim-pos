"""View model de administración de roles y permisos."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.roles.application.role_management_service import RoleManagementService


class RolesViewModel(QObject):
    """Estado y comportamiento de la pantalla de administración de roles."""

    roles_loaded = Signal(list)
    permissions_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(self, role_service: RoleManagementService, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._role_service = role_service

    def load(self) -> None:
        self.permissions_loaded.emit(self._role_service.list_permissions())
        self._reload_roles()

    def _reload_roles(self) -> None:
        self.roles_loaded.emit(self._role_service.list_roles())

    def create_role(self, name: str, description: str, permission_codes: set[str]) -> None:
        try:
            self._role_service.create_role(
                name=name, description=description or None, permission_codes=permission_codes
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Rol '{name}' creado correctamente.")
            self._reload_roles()

    def update_permissions(self, role_id: int, permission_codes: set[str]) -> None:
        try:
            self._role_service.update_role_permissions(role_id, permission_codes)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Permisos actualizados.")
            self._reload_roles()

    def delete_role(self, role_id: int) -> None:
        try:
            self._role_service.delete_role(role_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Rol eliminado.")
            self._reload_roles()
