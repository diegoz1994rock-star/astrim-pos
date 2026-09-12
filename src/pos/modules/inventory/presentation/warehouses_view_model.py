"""View model de administración de bodegas."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.application.product_service import ProductManagementService


class WarehousesViewModel(QObject):
    warehouses_loaded = Signal(list)
    warehouse_products_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        inventory_service: InventoryService,
        product_service: ProductManagementService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._inventory_service = inventory_service
        self._product_service = product_service

    def load(self) -> None:
        self.warehouses_loaded.emit(self._inventory_service.list_all_warehouses())

    def load_warehouse_products(self, warehouse_id: int) -> None:
        self.warehouse_products_loaded.emit(
            self._inventory_service.list_stock_by_warehouse(warehouse_id)
        )

    def create_warehouse(self, name: str, location: str | None) -> None:
        try:
            warehouse = self._inventory_service.create_warehouse(name=name, location=location)
            product_ids = [
                product.id for product in self._product_service.list_products_for_inventory()
            ]
            if product_ids:
                self._inventory_service.ensure_stock_levels(warehouse.id, product_ids)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Bodega '{name}' creada.")
            self.load()

    def update_warehouse(self, warehouse_id: int, name: str, location: str | None) -> None:
        try:
            self._inventory_service.update_warehouse(warehouse_id, name=name, location=location)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit(f"Bodega '{name}' actualizada.")
            self.load()

    def set_active(self, warehouse_id: int, is_active: bool) -> None:
        try:
            self._inventory_service.set_warehouse_active(warehouse_id, is_active)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()
