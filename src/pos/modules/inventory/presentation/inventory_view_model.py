"""View model de la pantalla de inventario."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.application.product_service import ProductManagementService


class InventoryViewModel(QObject):
    stock_loaded = Signal(list)
    warehouses_loaded = Signal(list)
    products_loaded = Signal(list)
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
        self.warehouses_loaded.emit(self._inventory_service.list_warehouses())
        self.products_loaded.emit(self._product_service.list_products())
        self._reload_stock()

    def _reload_stock(self) -> None:
        self.stock_loaded.emit(self._inventory_service.list_stock_overview())

    def register_entry(
        self, product_id: int, warehouse_id: int, quantity: Decimal, reason: str
    ) -> None:
        self._run(
            lambda: self._inventory_service.register_entry(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=quantity,
                reason=reason or None,
                created_by_user_id=None,
            )
        )

    def register_exit(
        self, product_id: int, warehouse_id: int, quantity: Decimal, reason: str
    ) -> None:
        self._run(
            lambda: self._inventory_service.register_exit(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=quantity,
                reason=reason or None,
                created_by_user_id=None,
            )
        )

    def register_adjustment(
        self, product_id: int, warehouse_id: int, quantity: Decimal, increase: bool, reason: str
    ) -> None:
        self._run(
            lambda: self._inventory_service.register_adjustment(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=quantity,
                increase=increase,
                reason=reason or None,
                created_by_user_id=None,
            )
        )

    def transfer(
        self,
        product_id: int,
        source_warehouse_id: int,
        destination_warehouse_id: int,
        quantity: Decimal,
    ) -> None:
        self._run(
            lambda: self._inventory_service.transfer(
                product_id=product_id,
                source_warehouse_id=source_warehouse_id,
                destination_warehouse_id=destination_warehouse_id,
                quantity=quantity,
                created_by_user_id=None,
            )
        )

    def _run(self, action: Callable[[], None]) -> None:
        try:
            action()
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Movimiento registrado correctamente.")
            self._reload_stock()
