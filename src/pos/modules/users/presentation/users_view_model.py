"""View model de administración de usuarios."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.roles.application.role_management_service import RoleManagementService
from pos.modules.users.application.dto import UserDTO
from pos.modules.users.application.user_management_service import UserManagementService


class UsersViewModel(QObject):
    """Estado y comportamiento de la pantalla de administración de usuarios."""

    users_loaded = Signal(list)
    """Emite `list[UserDTO]` cada vez que se refresca la lista."""

    roles_loaded = Signal(list)
    """Emite `list[RoleDTO]`, usada para poblar el combo de roles del formulario."""

    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        user_service: UserManagementService,
        role_service: RoleManagementService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_service = user_service
        self._role_service = role_service

    def load(self) -> None:
        self.roles_loaded.emit(self._role_service.list_roles())
        self._reload_users()

    def _reload_users(self) -> None:
        self.users_loaded.emit(self._user_service.list_users())

    def create_user(
        self,
        *,
        username: str,
        password: str,
        full_name: str,
        role_id: int,
        email: str,
        phone: str,
    ) -> None:
        try:
            self._user_service.create_user(
                username=username,
                password=password,
                full_name=full_name,
                role_id=role_id,
                email=email or None,
                phone=phone or None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Usuario '{username}' creado correctamente.")
            self._reload_users()

    def set_active(self, user: UserDTO, is_active: bool) -> None:
        try:
            self._user_service.set_active(user.id, is_active)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            action = "activado" if is_active else "desactivado"
            self.operation_succeeded.emit(f"Usuario '{user.username}' {action}.")
            self._reload_users()
