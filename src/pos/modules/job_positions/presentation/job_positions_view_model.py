"""View model de administración del catálogo de áreas y cargos."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.job_positions.application.job_position_management_service import (
    JobPositionManagementService,
)


class JobPositionsViewModel(QObject):
    """Estado y comportamiento de la pantalla "Áreas y cargos"."""

    areas_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)
    permission_catalog_loaded = Signal(list)
    """Emite `list[tuple[str, str]]` (código, etiqueta) una sola vez, al cargar."""
    permissions_loaded = Signal(int, list)
    """Emite `(position_id, list[str])` con los códigos ya otorgados a ese cargo."""

    def __init__(
        self, job_position_service: JobPositionManagementService, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._service = job_position_service

    def load(self) -> None:
        self.areas_loaded.emit(self._service.list_areas())
        self.permission_catalog_loaded.emit(self._service.list_available_permissions())

    def load_permissions(self, position_id: int) -> None:
        try:
            codes = self._service.list_permission_codes(position_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.permissions_loaded.emit(position_id, codes)

    def save_permissions(self, position_id: int, codes: list[str]) -> None:
        try:
            self._service.set_permissions(position_id, codes)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Permisos guardados.")

    def create_area(self, name: str) -> None:
        try:
            self._service.create_area(name=name)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Área '{name}' creada correctamente.")
            self.load()

    def rename_area(self, area_id: int, name: str) -> None:
        try:
            self._service.rename_area(area_id, name)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Área renombrada.")
            self.load()

    def delete_area(self, area_id: int) -> None:
        try:
            self._service.delete_area(area_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Área eliminada.")
            self.load()

    def create_position(self, area_id: int, name: str) -> None:
        try:
            self._service.create_position(area_id=area_id, name=name)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Cargo '{name}' creado correctamente.")
            self.load()

    def rename_position(self, position_id: int, name: str) -> None:
        try:
            self._service.rename_position(position_id, name)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Cargo renombrado.")
            self.load()

    def delete_position(self, position_id: int) -> None:
        try:
            self._service.delete_position(position_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Cargo eliminado.")
            self.load()
