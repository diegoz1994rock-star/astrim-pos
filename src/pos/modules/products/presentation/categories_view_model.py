"""View model de administración de categorías."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.products.application.category_service import CategoryManagementService


class CategoriesViewModel(QObject):
    categories_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self, category_service: CategoryManagementService, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._category_service = category_service

    def load(self) -> None:
        self.categories_loaded.emit(self._category_service.list_categories())

    def create_category(self, name: str) -> None:
        try:
            self._category_service.create_category(name=name)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Categoría '{name}' creada.")
            self.load()

    def update_category(self, category_id: int, name: str) -> None:
        try:
            self._category_service.update_category(category_id, name=name)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Categoría '{name}' actualizada.")
            self.load()

    def set_active(self, category_id: int, is_active: bool) -> None:
        try:
            self._category_service.set_active(category_id, is_active)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()

    def delete_category(self, category_id: int) -> None:
        try:
            self._category_service.delete_category(category_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Categoría eliminada correctamente.")
            self.load()
