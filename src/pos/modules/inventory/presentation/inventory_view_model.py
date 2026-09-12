"""View model de la pantalla de inventario."""

from __future__ import annotations

from collections.abc import Callable
from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.inventory.application.dto import StockLevelDTO
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.users.application.user_management_service import UserManagementService


class InventoryViewModel(QObject):
    stock_loaded = Signal(list)
    """Detalle por (producto, bodega) — `list_stock_overview()`, sin
    cambios; se conserva por si algo más lo necesita, aunque la tabla
    principal ahora usa `summary_loaded`."""
    summary_loaded = Signal(list)
    """Una fila por producto (existencia total) — alimenta la tabla
    principal de Existencias."""
    movements_loaded = Signal(list)
    warehouses_loaded = Signal(list)
    products_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        inventory_service: InventoryService,
        product_service: ProductManagementService,
        user_service: UserManagementService,
        session_manager: SessionManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._inventory_service = inventory_service
        self._product_service = product_service
        self._user_service = user_service
        self._session_manager = session_manager
        self._users_by_id: dict[int, str] = {}

    def _current_user_id(self) -> int | None:
        current = self._session_manager.current
        return current.user_id if current is not None else None

    def load(self) -> None:
        self.warehouses_loaded.emit(self._inventory_service.list_warehouses())
        self.products_loaded.emit(self._product_service.list_products_for_inventory())
        self._reload_stock()

    def _reload_stock(self) -> None:
        self.stock_loaded.emit(self._inventory_service.list_stock_overview())
        self.summary_loaded.emit(self._inventory_service.list_stock_summary())

    def get_stock_detail(self, product_id: int) -> list[StockLevelDTO]:
        return self._inventory_service.get_stock_detail(product_id)

    def load_movements(self) -> None:
        self._users_by_id = {u.id: u.full_name for u in self._user_service.list_users()}
        self.movements_loaded.emit(self._inventory_service.list_movements())

    def user_name(self, user_id: int | None) -> str:
        if user_id is None:
            return "—"
        return self._users_by_id.get(user_id, "—")

    def register_entry(
        self, product_id: int, warehouse_id: int, quantity: Decimal, reason: str
    ) -> None:
        self._run(
            lambda: self._inventory_service.register_entry(
                product_id=product_id,
                warehouse_id=warehouse_id,
                quantity=quantity,
                reason=reason or None,
                created_by_user_id=self._current_user_id(),
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
                created_by_user_id=self._current_user_id(),
            )
        )

    def register_adjustment(
        self, product_id: int, warehouse_id: int, new_quantity: Decimal, reason: str
    ) -> None:
        self._run(
            lambda: self._inventory_service.register_adjustment(
                product_id=product_id,
                warehouse_id=warehouse_id,
                new_quantity=new_quantity,
                reason=reason or None,
                created_by_user_id=self._current_user_id(),
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
                created_by_user_id=self._current_user_id(),
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
