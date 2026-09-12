"""View model del panel "Vendedor": toma de pedidos genérica para
cualquier tipo de negocio (mesero, vendedor, cajero, auxiliar, personal de
mostrador/atención). Reutiliza `SalesService.preview_sale` (el mismo
motor de precios que usa Ventas) para mostrar subtotal/impuestos/
descuentos/total en vivo, sin duplicar esa lógica — el pedido en sí no
tiene precio propio (ver `restaurant_service.py`), solo se usa el cálculo
para que el vendedor vea el total antes de confirmar."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.application.category_service import CategoryManagementService
from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.restaurant.domain.enums import OrderType
from pos.modules.sales.application.dto import SaleItemInput
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.scales.application.scale_read_service import ScaleReadService


class RestaurantViewModel(QObject):
    products_loaded = Signal(list)
    categories_loaded = Signal(list)
    cart_changed = Signal(object)
    """Emite `SalePreviewDTO` (subtotal/descuento/impuesto/total) cada vez
    que cambia el pedido en curso."""
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        restaurant_service: RestaurantService,
        product_service: ProductManagementService,
        category_service: CategoryManagementService,
        inventory_service: InventoryService,
        sales_service: SalesService,
        session_manager: SessionManager,
        scale_read_service: ScaleReadService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._restaurant_service = restaurant_service
        self._product_service = product_service
        self._category_service = category_service
        self._inventory_service = inventory_service
        self._sales_service = sales_service
        self._session_manager = session_manager
        self.scale_read_service = scale_read_service
        """Público, mismo motivo que `SaleViewModel.scale_read_service`:
        `RestaurantView` lo pasa directo a `ScaleWeightDialog`."""
        self._items: list[SaleItemInput] = []
        self._products: list[ProductDTO] = []

    def load(self) -> None:
        self._products = self._product_service.list_products()
        self.products_loaded.emit(self._products)
        self.categories_loaded.emit(self._category_service.list_categories())
        self._refresh_preview()

    def get_available_quantity(self, product_id: int) -> Decimal:
        return self._inventory_service.get_total_available_quantity(product_id)

    def _refresh_preview(self) -> None:
        try:
            preview = self._sales_service.preview_sale(self._items)
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        self.cart_changed.emit(preview)

    def _check_stock(
        self, product_id: int, quantity: Decimal, exclude_index: int | None = None
    ) -> bool:
        """Valida la cantidad solicitada contra el stock disponible antes de
        agregarla/editarla en el pedido — el vendedor se entera de
        inmediato, sin esperar a que Caja intente cobrar (mismo patrón que
        `SaleViewModel._check_stock`)."""
        product = next((p for p in self._products if p.id == product_id), None)
        if product is None or not product.track_inventory:
            return True
        available = self._inventory_service.get_total_available_quantity(product_id)
        already_in_order = sum(
            (
                item.quantity
                for index, item in enumerate(self._items)
                if item.product_id == product_id and index != exclude_index
            ),
            Decimal(0),
        )
        if available <= 0:
            self.error_occurred.emit("No hay existencias disponibles para este producto.")
            return False
        if already_in_order + quantity > available:
            self.error_occurred.emit(f"Solo hay {available} unidades disponibles en inventario.")
            return False
        return True

    def add_item(self, product_id: int, quantity: Decimal, note: str | None = None) -> None:
        if quantity <= 0:
            self.error_occurred.emit("La cantidad debe ser mayor que cero.")
            return
        if not self._check_stock(product_id, quantity):
            return
        for index, item in enumerate(self._items):
            if item.product_id == product_id:
                self._items[index] = SaleItemInput(
                    product_id=product_id,
                    quantity=item.quantity + quantity,
                    note=note if note is not None else item.note,
                )
                self._refresh_preview()
                return
        self._items.append(SaleItemInput(product_id=product_id, quantity=quantity, note=note))
        self._refresh_preview()

    def remove_item(self, index: int) -> None:
        if 0 <= index < len(self._items):
            del self._items[index]
            self._refresh_preview()

    def update_item(self, index: int, *, quantity: Decimal, note: str | None) -> None:
        if not (0 <= index < len(self._items)):
            return
        if quantity <= 0:
            self.error_occurred.emit("La cantidad debe ser mayor que cero.")
            return
        item = self._items[index]
        if not self._check_stock(item.product_id, quantity, exclude_index=index):
            return
        self._items[index] = SaleItemInput(product_id=item.product_id, quantity=quantity, note=note)
        self._refresh_preview()

    def confirm_order(
        self, customer_name: str | None = None, customer_document: str | None = None
    ) -> bool:
        if not self._items:
            self.error_occurred.emit("Agrega al menos un producto al pedido.")
            return False
        current_user = self._session_manager.current
        items = [(item.product_id, int(item.quantity), item.note) for item in self._items]
        try:
            order = self._restaurant_service.create_order(
                table_session_id=None,
                order_type=OrderType.QUICK,
                items=items,
                created_by_user_id=current_user.user_id if current_user is not None else None,
                customer_name=customer_name,
                customer_document=customer_document,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return False
        self._items = []
        self.operation_succeeded.emit(f"Pedido de {order.customer_name} enviado a Despacho.")
        self._refresh_preview()
        return True
