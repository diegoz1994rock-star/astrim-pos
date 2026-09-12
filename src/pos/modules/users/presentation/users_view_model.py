"""View model de administración de usuarios."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.job_positions.application.job_position_management_service import (
    JobPositionManagementService,
)
from pos.modules.users.application.dto import UserDocumentDTO, UserDTO
from pos.modules.users.application.user_management_service import UserManagementService


class UsersViewModel(QObject):
    """Estado y comportamiento de la pantalla de administración de usuarios."""

    users_loaded = Signal(list)
    """Emite `list[UserDTO]` cada vez que se refresca la lista."""

    areas_loaded = Signal(list)
    """Emite `list[JobAreaDTO]`, usada para poblar los combos Área/Cargo del formulario."""

    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        user_service: UserManagementService,
        job_position_service: JobPositionManagementService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._user_service = user_service
        self._job_position_service = job_position_service

    def load(self) -> None:
        self.areas_loaded.emit(self._job_position_service.list_areas())
        self._reload_users()

    def _reload_users(self) -> None:
        self.users_loaded.emit(self._user_service.list_users())

    def create_user(
        self,
        *,
        username: str,
        password: str,
        full_name: str,
        email: str,
        phone: str,
        emergency_phone: str = "",
        blood_type: str = "",
        address: str = "",
        photo_source_path: str | None = None,
        job_area_id: int | None = None,
        job_position_id: int | None = None,
    ) -> None:
        """Puede lanzar `DomainError`: a diferencia del resto de los
        métodos de este view model, este y `update_user` los deja
        propagar en vez de convertirlos en `error_occurred` — los llama
        `UserFormDialog` de forma síncrona para poder mostrar el error
        junto al campo correspondiente sin cerrarse (ver
        `UserFormDialog._on_accept_clicked`)."""
        self._user_service.create_user(
            username=username,
            password=password,
            full_name=full_name,
            email=email or None,
            phone=phone or None,
            emergency_phone=emergency_phone or None,
            blood_type=blood_type or None,
            address=address or None,
            photo_source_path=photo_source_path,
            job_area_id=job_area_id,
            job_position_id=job_position_id,
        )
        self.operation_succeeded.emit(f"Usuario '{username}' creado correctamente.")
        self._reload_users()

    def update_user(
        self,
        user_id: int,
        *,
        username: str,
        full_name: str,
        email: str,
        phone: str,
        emergency_phone: str,
        blood_type: str,
        address: str,
        photo_source_path: str | None = None,
        job_area_id: int | None = None,
        job_position_id: int | None = None,
    ) -> None:
        """Puede lanzar `DomainError` — ver docstring de `create_user`."""
        self._user_service.update_user(
            user_id,
            username=username,
            full_name=full_name,
            email=email or None,
            phone=phone or None,
            emergency_phone=emergency_phone or None,
            blood_type=blood_type or None,
            address=address or None,
            photo_source_path=photo_source_path,
            job_area_id=job_area_id,
            job_position_id=job_position_id,
        )
        self.operation_succeeded.emit(f"Usuario '{username}' actualizado correctamente.")
        self._reload_users()

    def list_documents(self, user_id: int) -> list[UserDocumentDTO]:
        """Llamado directamente por `UserFormDialog` (diálogo modal con
        feedback inmediato): a diferencia del resto de los métodos, no
        pasa por `error_occurred` — el diálogo maneja sus propios errores."""
        return self._user_service.list_documents(user_id)

    def add_document(self, user_id: int, source_path: str) -> UserDocumentDTO:
        return self._user_service.add_document(user_id, source_path)

    def delete_document(self, document_id: int) -> None:
        self._user_service.delete_document(document_id)

    def set_active(self, user: UserDTO, is_active: bool) -> None:
        try:
            self._user_service.set_active(user.id, is_active)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            action = "activado" if is_active else "desactivado"
            self.operation_succeeded.emit(f"Usuario '{user.username}' {action}.")
            self._reload_users()

    def delete_user(self, user: UserDTO) -> None:
        try:
            self._user_service.delete_user(user.id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Usuario '{user.username}' eliminado correctamente.")
            self._reload_users()
