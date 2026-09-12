"""View model de la pantalla de venta (carrito)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal

from PySide6.QtCore import QObject, Signal

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.barcode_scanners.application.barcode_read_service import BarcodeReadService
from pos.modules.barcode_scanners.application.dto import BarcodeSettingsDTO
from pos.modules.barcode_scanners.domain.enums import BarcodeReadSource
from pos.modules.billing.application.billing_service import BillingService
from pos.modules.billing.application.print_helper import print_invoice_for_sale
from pos.modules.billing.application.receipt_printer import ReceiptPrinter
from pos.modules.bre_b_payments.application.breb_payment_service import BreBPaymentService
from pos.modules.cash_drawers.application.cash_drawer_service import CashDrawerService
from pos.modules.cash_drawers.domain.enums import CashDrawerOpeningKind
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.cash_register.application.dto import CashRegisterDTO, CashSessionDTO
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.nequi_payments.application.nequi_payment_service import NequiPaymentService
from pos.modules.printers.application.printer_service import PrinterService
from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import SaleUnit
from pos.modules.qr_payments.application.qr_payment_service import QrPaymentService
from pos.modules.restaurant.application.dto import OrderDTO
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.sales.application.dto import (
    SaleItemInput,
    SalePaymentInput,
    SalePreviewDTO,
)
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.scales.application.scale_read_service import ScaleReadService
from pos.modules.scales.domain.enums import WeightEntrySource


@dataclass(frozen=True)
class HeldSaleSnapshot:
    """Foto de un carrito dejado en espera (`SaleViewModel.hold_current_sale`)
    — vive solo en memoria, se pierde si se cierra la app (no hay
    persistencia para esto, fuera de alcance)."""

    items: list[SaleItemInput] = field(default_factory=list)
    payments: list[SalePaymentInput] = field(default_factory=list)
    customer_id: int | None = None
    customer_name: str = ""
    customer_document: str = ""

    @property
    def item_count(self) -> int:
        return len(self.items)


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
    pending_orders_loaded = Signal(list)
    """Emite `list[OrderDTO]` con los pedidos de Vendedor sin cobrar
    todavía — ver `load_pending_orders`/`load_from_order`."""
    held_sales_changed = Signal(list)
    """Emite `list[HeldSaleSnapshot]` cada vez que se deja una venta en
    espera o se reanuda una."""
    customer_fields_loaded = Signal(str, str)
    """Emite `(nombre, documento)` al cargar un pedido de Vendedor
    (`load_from_order`), para que la vista precargue los campos de texto
    sin que el cajero tenga que volver a escribirlos."""
    scan_resolved = Signal(object)
    """Emite `BarcodeReadResultDTO` después de CADA lectura procesada por
    `scan_barcode` (encontrada, no encontrada o ignorada) — la vista usa
    esto para limpiar/reenfocar el campo de escaneo y dar la
    retroalimentación de sonido/aviso visual, siempre, sin excepción."""
    error_occurred = Signal(str)
    operation_succeeded = Signal(str)

    def __init__(
        self,
        sales_service: SalesService,
        product_service: ProductManagementService,
        customer_service: CustomerManagementService,
        inventory_service: InventoryService,
        cash_register_service: CashRegisterService,
        session_manager: SessionManager,
        billing_service: BillingService,
        receipt_printer: ReceiptPrinter,
        cash_drawer_service: CashDrawerService,
        qr_payment_service: QrPaymentService,
        restaurant_service: RestaurantService,
        scale_read_service: ScaleReadService,
        nequi_payment_service: NequiPaymentService,
        breb_payment_service: BreBPaymentService,
        barcode_read_service: BarcodeReadService,
        printer_service: PrinterService,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._sales_service = sales_service
        self._product_service = product_service
        self._customer_service = customer_service
        self.customer_service = customer_service
        """Público, mismo motivo que `qr_payment_service`/`scale_read_service`:
        `SaleView` lo consulta directamente para el aviso de cupo de
        crédito insuficiente antes de agregar un pago a la deuda."""
        self._inventory_service = inventory_service
        self._cash_register_service = cash_register_service
        self._session_manager = session_manager
        self._billing_service = billing_service
        self._barcode_read_service = barcode_read_service
        self._receipt_printer = receipt_printer
        self._printer_service = printer_service
        self._cash_drawer_service = cash_drawer_service
        self._restaurant_service = restaurant_service
        self.qr_payment_service = qr_payment_service
        """Público (no privado): `SaleView` lo pasa directamente a
        `QrPaymentDialog`/`NequiPaymentDialog`/`BreBPaymentDialog`, que
        consultan el medio de pago predeterminado de forma síncrona igual
        que cualquier otro diálogo modal del carrito (`CartItemEditDialog`,
        `PrintReceiptPromptDialog`)."""
        self.scale_read_service = scale_read_service
        """Público, mismo motivo que `qr_payment_service`: `SaleView` lo
        pasa directo a `ScaleWeightDialog` para productos por peso."""
        self.nequi_payment_service = nequi_payment_service
        self.breb_payment_service = breb_payment_service

        self._items: list[SaleItemInput] = []
        self._payments: list[SalePaymentInput] = []
        self._customer_id: int | None = None
        self._customer_name_text: str = ""
        self._customer_document_text: str = ""
        self._last_completed_sale_id: int | None = None
        self._last_completed_cash_register_id: int | None = None
        self._pending_drawer_open_after_print: bool = False
        """`True` justo entre `print_last_receipt(trigger_drawer_if_configured=
        True)` y el `open_drawer_if_applicable()` que lo sigue en el mismo
        manejador (`SaleView._on_sale_completed`) — nunca sobrevive más
        allá de esa llamada, así que una reimpresión manual posterior
        (`_on_print_clicked`, que no pasa `trigger_drawer_if_configured`)
        nunca reabre el cajón por error en una venta distinta."""
        self._products: list[ProductDTO] = []
        self._held_sales: list[HeldSaleSnapshot] = []
        self._loading_order_id: int | None = None
        """Pedido de Vendedor que se está cobrando en este carrito (ver
        `load_from_order`) — al completar la venta, se marca cobrado con
        `RestaurantService.link_order_to_sale` sin volver a escribir nada."""

    def load(self) -> None:
        self._products = self._product_service.list_products()
        self.products_loaded.emit(self._products)
        self.customers_loaded.emit(self._customer_service.list_customers())
        self._refresh_preview()
        self.load_pending_orders()

    def load_pending_orders(self) -> None:
        self.pending_orders_loaded.emit(self._restaurant_service.list_pending_payment_orders())

    def load_from_order(self, order: OrderDTO) -> None:
        """Llena el carrito con las líneas de un pedido de Vendedor ya
        recibido por Despacho, sin volver a escribirlas — el cajero solo
        elige el medio de pago y completa la venta como siempre. Nombre y
        documento del cliente también se sincronizan (`customer_fields_loaded`),
        sin que el cajero tenga que volver a escribirlos."""
        self._loading_order_id = order.id
        for item in order.items:
            self.add_item(item.product_id, Decimal(item.quantity), note=item.notes)
        self._customer_name_text = order.customer_name or ""
        self._customer_document_text = order.customer_document or ""
        self.customer_fields_loaded.emit(self._customer_name_text, self._customer_document_text)

    def set_customer_name(self, text: str) -> None:
        self._customer_name_text = text

    def set_customer_document(self, text: str) -> None:
        self._customer_document_text = text

    def hold_current_sale(self) -> None:
        """Guarda una foto del carrito activo en la lista de "ventas en
        espera" y deja el carrito vacío para empezar una nueva venta —
        nada se pierde, ver `resume_held_sale`."""
        self._held_sales.append(
            HeldSaleSnapshot(
                items=list(self._items),
                payments=list(self._payments),
                customer_id=self._customer_id,
                customer_name=self._customer_name_text,
                customer_document=self._customer_document_text,
            )
        )
        self._items = []
        self._payments = []
        self._customer_id = None
        self._customer_name_text = ""
        self._customer_document_text = ""
        self.held_sales_changed.emit(list(self._held_sales))
        self.customer_fields_loaded.emit("", "")
        self._refresh_preview()

    def resume_held_sale(self, index: int) -> None:
        """Repone una venta en espera como el carrito activo — reemplaza
        lo que hubiera en curso (la vista ya evita llamar esto sin razón,
        pero si el carrito activo tenía algo sin guardar, se pierde)."""
        if not (0 <= index < len(self._held_sales)):
            return
        snapshot = self._held_sales.pop(index)
        self._items = list(snapshot.items)
        self._payments = list(snapshot.payments)
        self._customer_id = snapshot.customer_id
        self._customer_name_text = snapshot.customer_name
        self._customer_document_text = snapshot.customer_document
        self.held_sales_changed.emit(list(self._held_sales))
        self.customer_fields_loaded.emit(self._customer_name_text, self._customer_document_text)
        self._refresh_preview()

    def _check_stock(
        self, product_id: int, quantity: Decimal, exclude_index: int | None = None
    ) -> bool:
        """Valida la cantidad solicitada contra el stock disponible antes de
        agregarla/editarla en el carrito — no espera a `complete_sale` para
        avisar que no hay suficiente inventario."""
        product = next((p for p in self._products if p.id == product_id), None)
        if product is None or not product.track_inventory:
            return True
        available = self._inventory_service.get_total_available_quantity(product_id)
        already_in_cart = sum(
            (
                item.quantity
                for index, item in enumerate(self._items)
                if item.product_id == product_id and index != exclude_index
            ),
            Decimal(0),
        )
        if already_in_cart + quantity > available:
            self.error_occurred.emit(
                f"Stock insuficiente. Disponibles: {available} {product.unit_of_measure}."
            )
            return False
        return True

    def _refresh_preview(self) -> None:
        try:
            preview = self._sales_service.preview_sale(self._items)
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        self.cart_changed.emit(preview)
        self.payments_changed.emit(list(self._payments))

    def get_barcode_settings(self) -> BarcodeSettingsDTO:
        return self._barcode_read_service.get_settings()

    def _current_register_and_session(
        self,
    ) -> tuple[CashRegisterDTO | None, CashSessionDTO | None]:
        """Punto de caja/turno abierto para esta estación — mismo criterio
        ya usado por `complete_sale`, reutilizado acá para que cada
        lectura de código de barras quede asociada a la caja correcta en
        el registro de auditoría (ver `BarcodeReadService.resolve_scan`)."""
        default_register = next(iter(self._cash_register_service.list_registers()), None)
        if default_register is None:
            return None, None
        open_session = self._cash_register_service.get_open_session(default_register.id)
        return default_register, open_session

    def scan_barcode(self, raw_text: str) -> None:
        """Único punto de entrada para resolver una lectura de código de
        barras en Ventas — delega toda la lógica (normalizar, evitar
        rebote, buscar el producto, registrar la lectura) en
        `BarcodeReadService`, la misma que usan "Probar lector" y
        Diagnóstico, para no repetir esta lógica en la vista."""
        session = self._session_manager.current
        register, _ = self._current_register_and_session()
        result = self._barcode_read_service.resolve_scan(
            raw_text,
            source=BarcodeReadSource.SALE,
            user_id=session.user_id if session is not None else None,
            username=session.full_name if session is not None else None,
            cash_register_id=register.id if register is not None else None,
            cash_register_name=register.name if register is not None else None,
        )
        self.scan_resolved.emit(result)
        if result.ignored or not result.found:
            return
        assert result.product is not None
        if result.product.sale_unit is SaleUnit.WEIGHT:
            # Producto por peso: la vista reacciona a `scan_resolved` para
            # abrir `ScaleWeightDialog` y agregar el peso real (ver
            # `sale_view.py::_on_scan_resolved`) — acá no se agrega nada
            # todavía, nunca 1 unidad, porque 1 no es un peso válido.
            return
        self.add_item(result.product.id, Decimal(1))

    def add_item(
        self,
        product_id: int,
        quantity: Decimal,
        note: str | None = None,
        weight_entry_source: WeightEntrySource | None = None,
    ) -> None:
        if quantity <= 0:
            self.error_occurred.emit("La cantidad debe ser mayor que cero.")
            return
        if not self._check_stock(product_id, quantity):
            return
        for index, item in enumerate(self._items):
            if item.product_id == product_id:
                # Ya está en el carrito: se suma la cantidad a esa misma
                # línea en vez de crear una línea duplicada, conservando la
                # nota que ya tuviera.
                self._items[index] = SaleItemInput(
                    product_id=product_id,
                    quantity=item.quantity + quantity,
                    discount_amount=item.discount_amount,
                    note=note if note is not None else item.note,
                    weight_entry_source=weight_entry_source or item.weight_entry_source,
                )
                self._refresh_preview()
                return
        self._items.append(
            SaleItemInput(
                product_id=product_id,
                quantity=quantity,
                note=note,
                weight_entry_source=weight_entry_source,
            )
        )
        self._refresh_preview()

    def remove_item(self, index: int) -> None:
        if 0 <= index < len(self._items):
            del self._items[index]
            self._refresh_preview()

    def update_item(
        self,
        index: int,
        *,
        quantity: Decimal,
        note: str | None,
    ) -> None:
        if not (0 <= index < len(self._items)):
            return
        if quantity <= 0:
            self.error_occurred.emit("La cantidad debe ser mayor que cero.")
            return
        item = self._items[index]
        if not self._check_stock(item.product_id, quantity, exclude_index=index):
            return
        self._items[index] = SaleItemInput(
            product_id=item.product_id,
            quantity=quantity,
            discount_amount=item.discount_amount,
            note=note,
            weight_entry_source=item.weight_entry_source,
        )
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
        created_by_user_id = current_user.user_id if current_user is not None else None
        try:
            sale = self._sales_service.complete_sale(
                items=self._items,
                payments=self._payments,
                cash_session_id=open_session.id,
                warehouse_id=default_warehouse.id,
                customer_id=self._customer_id,
                created_by_user_id=created_by_user_id,
                customer_name=self._customer_name_text.strip() or None,
                customer_document=self._customer_document_text.strip() or None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            credit_amount = sum(
                (
                    p.amount
                    for p in self._payments
                    if p.payment_method is PaymentMethod.CUSTOMER_CREDIT
                ),
                Decimal(0),
            )
            if credit_amount > 0:
                # Venta a crédito: la factura se genera automáticamente acá
                # (no hace falta que el cajero presione "Imprimir ticket")
                # para que nunca exista una deuda sin factura — ver punto 6
                # del pedido. Ventas normales (sin crédito) siguen exactamente
                # igual que antes: la factura se genera bajo demanda.
                try:
                    self._billing_service.generate_invoice(sale.id, credit_amount=credit_amount)
                except DomainError as error:
                    self.error_occurred.emit(
                        "La venta se completó, pero no se pudo generar la factura "
                        f"automáticamente: {error}"
                    )
            if self._loading_order_id is not None:
                self._restaurant_service.link_order_to_sale(self._loading_order_id, sale.id)
                self._loading_order_id = None
                self.load_pending_orders()
            else:
                # Venta creada directo en Ventas, sin pasar por un pedido de
                # Vendedor — la manda a Despacho automáticamente (Flujo 2,
                # ver `RestaurantService.create_order_from_sale`).
                self._restaurant_service.create_order_from_sale(
                    sale, created_by_user_id=created_by_user_id
                )
            self._items = []
            self._payments = []
            self._customer_id = None
            self._customer_name_text = ""
            self._customer_document_text = ""
            self._last_completed_sale_id = sale.id
            self._last_completed_cash_register_id = default_register.id
            self.sale_completed.emit(sale)
            self._refresh_preview()

    def open_drawer_if_applicable(self) -> None:
        """Único punto de apertura automática del cajón — se llama
        inmediatamente después de que la venta ya quedó completamente
        guardada, antes del cuadro "¿Desea imprimir la factura?" (nunca
        antes de guardar la venta, nunca en una venta cancelada o
        fallida, ver `SaleView._on_sale_completed`). Abre si la venta tuvo
        algún componente en efectivo — abrir el cajón físico para una venta
        100% electrónica (tarjeta/QR/Nequi/Bre-B/crédito) no tiene sentido
        operativo, aunque haya sido exitosa — o si el flujo de "¿Desea
        imprimir?" lo pidió explícitamente porque la impresora asignada
        tiene `open_drawer_after_print` (ver `_pending_drawer_open_after_
        print`), sin importar el medio de pago en ese caso."""
        if self._last_completed_sale_id is None or self._last_completed_cash_register_id is None:
            return
        current_user = self._session_manager.current
        if current_user is None:
            return
        triggered_by_print = self._pending_drawer_open_after_print
        self._pending_drawer_open_after_print = False
        if not triggered_by_print:
            sale = self._sales_service.get_sale(self._last_completed_sale_id)
            if not any(payment.payment_method is PaymentMethod.CASH for payment in sale.payments):
                return
        try:
            self._cash_drawer_service.open_drawer_for_cash_register(
                self._last_completed_cash_register_id,
                user_id=current_user.user_id,
                username=current_user.username,
                opening_kind=CashDrawerOpeningKind.AUTOMATIC,
                sale_id=self._last_completed_sale_id,
            )
        except DomainError as error:
            self.error_occurred.emit(f"No se pudo abrir el cajón monedero: {error}")

    def print_last_receipt(self, *, trigger_drawer_if_configured: bool = False) -> None:
        """Imprime (o reimprime) el ticket de la última venta completada,
        vía la impresora asignada a la caja activa — o el visor del
        sistema si no hay ninguna configurada. `trigger_drawer_if_configured`
        solo lo pasa `SaleView._on_sale_completed` en el flujo real de "¿Desea
        imprimir?"; una reimpresión manual (botón "Imprimir") nunca reabre
        el cajón."""
        if self._last_completed_sale_id is None:
            self.error_occurred.emit("No hay ninguna venta reciente para imprimir.")
            return
        current_user = self._session_manager.current
        try:
            outcome = print_invoice_for_sale(
                billing_service=self._billing_service,
                printer_service=self._printer_service,
                receipt_printer=self._receipt_printer,
                sale_id=self._last_completed_sale_id,
                cash_register_id=self._last_completed_cash_register_id,
                user_id=current_user.user_id if current_user is not None else None,
                username=current_user.username if current_user is not None else None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
            return
        if not outcome.printed:
            self.error_occurred.emit(outcome.error or "No se pudo imprimir el ticket.")
            return
        if trigger_drawer_if_configured and outcome.open_drawer_after_print:
            self._pending_drawer_open_after_print = True
        self.operation_succeeded.emit("Ticket enviado a impresión.")
