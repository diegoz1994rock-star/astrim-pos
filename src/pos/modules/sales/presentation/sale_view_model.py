"""View model de la pantalla de venta (carrito)."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.promotions.application.dto import AppliedDiscountDTO
from pos.modules.promotions.application.promotion_service import PromotionService
from pos.modules.sales.application.dto import (
    SaleItemInput,
    SalePaymentInput,
    SalePreviewDTO,
)
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sales.domain.enums import PaymentMethod


class SaleViewModel(QObject):
    """Estado del carrito de venta en curso. Una instancia por venta; la
    vista crea una instancia nueva después de completar o cancelar."""

    products_loaded = Signal(list)
    customers_loaded = Signal(list)
    cart_changed = Signal(object)
    """Emite `SalePreviewDTO` cada vez que cambia el carrito o los pagos."""
    payments_changed = Signal(list)
    sale_completed = Signal(object)
    """Emite `SaleDTO` de la venta ya persistida."""
    error_occurred = Signal(str)

    def __init__(
        self,
        sales_service: SalesService,
        product_service: ProductManagementService,
        customer_service: CustomerManagementService,
        inventory_service: InventoryService,
        cash_register_service: CashRegisterService,
        promotion_service: PromotionService,
        session_manager: SessionManager,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sales_service = sales_service
        self._product_service = product_service
        self._customer_service = customer_service
        self._inventory_service = inventory_service
        self._cash_register_service = cash_register_service
        self._promotion_service = promotion_service
        self._session_manager = session_manager

        self._items: list[SaleItemInput] = []
        self._payments: list[SalePaymentInput] = []
        self._customer_id: int | None = None
        self._applied_discounts: list[AppliedDiscountDTO] = []

    def load(self) -> None:
        self.products_loaded.emit(self._product_service.list_products())
        self.customers_loaded.emit(self._customer_service.list_customers())
        self._refresh_preview()

    def _apply_automatic_discounts(self) -> None:
        """Recalcula los descuentos automáticos de promociones activas
        (ARCHITECTURE.md, módulo de Promociones) para el carrito actual y
        reescribe `discount_amount` de cada línea en consecuencia."""
        lines = [(item.product_id, item.quantity) for item in self._items]
        self._applied_discounts = self._promotion_service.compute_discounts(lines)
        discounts_by_product = {d.product_id: d.amount for d in self._applied_discounts}
        self._items = [
            SaleItemInput(
                product_id=item.product_id,
                quantity=item.quantity,
                discount_amount=discounts_by_product.get(item.product_id, Decimal(0)),
            )
            for item in self._items
        ]

    def _refresh_preview(self) -> None:
        self._apply_automatic_discounts()
        try:
            preview = self._sales_service.preview_sale(self._items)
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        self.cart_changed.emit(preview)
        self.payments_changed.emit(list(self._payments))

    def add_item(self, product_id: int, quantity: Decimal) -> None:
        if quantity <= 0:
            self.error_occurred.emit("La cantidad debe ser mayor que cero.")
            return
        self._items.append(SaleItemInput(product_id=product_id, quantity=quantity))
        self._refresh_preview()

    def remove_item(self, index: int) -> None:
        if 0 <= index < len(self._items):
            del self._items[index]
            self._refresh_preview()

    def set_customer(self, customer_id: int | None) -> None:
        self._customer_id = customer_id

    def add_payment(self, method: PaymentMethod, amount: Decimal, reference: str = "") -> None:
        if amount <= 0:
            self.error_occurred.emit("El monto del pago debe ser mayor que cero.")
            return
        self._payments.append(
            SalePaymentInput(payment_method=method, amount=amount, reference=reference or None)
        )
        self._refresh_preview()

    def remove_payment(self, index: int) -> None:
        if 0 <= index < len(self._payments):
            del self._payments[index]
            self._refresh_preview()

    def current_preview(self) -> SalePreviewDTO:
        return self._sales_service.preview_sale(self._items)

    def complete_sale(self) -> None:
        default_warehouse = next(iter(self._inventory_service.list_warehouses()), None)
        if default_warehouse is None:
            self.error_occurred.emit("No hay ninguna bodega configurada.")
            return
        default_register = next(iter(self._cash_register_service.list_registers()), None)
        if default_register is None:
            self.error_occurred.emit("No hay ningún punto de caja configurado.")
            return
        open_session = self._cash_register_service.get_open_session(default_register.id)
        if open_session is None:
            self.error_occurred.emit("No hay un turno de caja abierto. Ábrelo antes de vender.")
            return

        current_user = self._session_manager.current
        try:
            sale = self._sales_service.complete_sale(
                items=self._items,
                payments=self._payments,
                cash_session_id=open_session.id,
                warehouse_id=default_warehouse.id,
                customer_id=self._customer_id,
                created_by_user_id=current_user.user_id if current_user is not None else None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            if self._applied_discounts:
                sale_item_ids_by_product = {item.product_id: item.id for item in sale.items}
                self._promotion_service.record_applied_discounts(
                    sale_id=sale.id,
                    sale_item_ids_by_product=sale_item_ids_by_product,
                    discounts=self._applied_discounts,
                )
            self._items = []
            self._payments = []
            self._customer_id = None
            self._applied_discounts = []
            self.sale_completed.emit(sale)
            self._refresh_preview()
