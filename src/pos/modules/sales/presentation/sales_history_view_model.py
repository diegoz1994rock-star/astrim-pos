"""View model del historial de ventas y anulación."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.sales.application.sale_service import SalesService


class SalesHistoryViewModel(QObject):
    sales_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        sales_service: SalesService,
        inventory_service: InventoryService,
        session_manager: SessionManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sales_service = sales_service
        self._inventory_service = inventory_service
        self._session_manager = session_manager

    def load(self) -> None:
        self.sales_loaded.emit(self._sales_service.list_recent_sales())

    def void_sale(self, sale_id: int, reason: str) -> None:
        default_warehouse = next(iter(self._inventory_service.list_warehouses()), None)
        if default_warehouse is None:
            self.error_occurred.emit("No hay ninguna bodega configurada.")
            return
        current_user = self._session_manager.current
        try:
            self._sales_service.void_sale(
                sale_id=sale_id,
                warehouse_id=default_warehouse.id,
                reason=reason or None,
                created_by_user_id=current_user.user_id if current_user is not None else None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Venta #{sale_id} anulada.")
            self.load()
