"""View model de administración de proveedores."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.suppliers.application.supplier_service import SupplierManagementService


class SuppliersViewModel(QObject):
    suppliers_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self, supplier_service: SupplierManagementService, parent: QObject | None = None
    ) -> None:
        super().__init__(parent)
        self._supplier_service = supplier_service

    def load(self) -> None:
        self.suppliers_loaded.emit(self._supplier_service.list_suppliers())

    def create_supplier(self, **kwargs: str | None) -> None:
        try:
            self._supplier_service.create_supplier(**kwargs)  # type: ignore[arg-type]
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Proveedor creado correctamente.")
            self.load()

    def remove_supplier(self, supplier_id: int) -> None:
        try:
            self._supplier_service.remove_supplier(supplier_id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()
