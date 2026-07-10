"""View model del panel de Restaurante (mesas y pedidos)."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.restaurant.application.dto import TableSessionDTO
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.restaurant.domain.enums import OrderType


class RestaurantViewModel(QObject):
    tables_loaded = Signal(list)
    products_loaded = Signal(list)
    session_opened = Signal(object)
    orders_loaded = Signal(list)
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        restaurant_service: RestaurantService,
        product_service: ProductManagementService,
        session_manager: SessionManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._restaurant_service = restaurant_service
        self._product_service = product_service
        self._session_manager = session_manager
        self._active_session: TableSessionDTO | None = None

    def load(self) -> None:
        self.tables_loaded.emit(self._restaurant_service.list_tables())
        self.products_loaded.emit(self._product_service.list_products())

    def create_table(self, name: str, capacity: int, zone: str) -> None:
        try:
            self._restaurant_service.create_table(name=name, capacity=capacity, zone=zone or None)
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Mesa creada.")
            self.load()

    def open_table(self, table_id: int) -> None:
        current_user = self._session_manager.current
        if current_user is None:
            self.error_occurred.emit("No hay una sesión activa.")
            return
        try:
            table_session = self._restaurant_service.open_table_session(
                table_id=table_id, waiter_user_id=current_user.user_id
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        self._active_session = table_session
        self.session_opened.emit(table_session)
        self._refresh_orders()
        self.load()

    def close_active_table(self) -> None:
        if self._active_session is None:
            self.error_occurred.emit("No hay una mesa abierta seleccionada.")
            return
        try:
            self._restaurant_service.close_table_session(self._active_session.id)
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        self._active_session = None
        self.orders_loaded.emit([])
        self.operation_succeeded.emit("Mesa cerrada.")
        self.load()

    def _refresh_orders(self) -> None:
        if self._active_session is None:
            self.orders_loaded.emit([])
            return
        self.orders_loaded.emit(
            self._restaurant_service.list_orders_for_session(self._active_session.id)
        )

    def send_order(self, items: list[tuple[int, int, str | None]]) -> None:
        if self._active_session is None:
            self.error_occurred.emit("Abre una mesa antes de enviar un pedido.")
            return
        try:
            self._restaurant_service.create_order(
                table_session_id=self._active_session.id,
                order_type=OrderType.DINE_IN,
                items=items,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.operation_succeeded.emit("Pedido enviado a cocina.")
            self._refresh_orders()
