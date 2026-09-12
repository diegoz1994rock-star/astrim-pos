"""Pantalla de venta (POS): selección de producto, carrito, pagos y total."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtCore import QEvent, QStringListModel, Qt, QTimer
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QComboBox,
    QCompleter,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.barcode_scanners.application.dto import BarcodeReadResultDTO
from pos.modules.bre_b_payments.presentation.breb_payment_dialog import BreBPaymentDialog
from pos.modules.customers.application.dto import CustomerDTO
from pos.modules.nequi_payments.presentation.nequi_payment_dialog import NequiPaymentDialog
from pos.modules.products.application.dto import ProductDTO
from pos.modules.products.domain.enums import SaleUnit
from pos.modules.qr_payments.presentation.qr_payment_dialog import QrPaymentDialog
from pos.modules.restaurant.application.dto import OrderDTO
from pos.modules.restaurant.domain.enums import OrderItemStatus
from pos.modules.sales.application.dto import (
    SalePaymentInput,
    SalePreviewDTO,
    SalePreviewLineDTO,
)
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.sales.presentation.cart_item_edit_dialog import CartItemEditDialog
from pos.modules.sales.presentation.print_receipt_prompt_dialog import PrintReceiptPromptDialog
from pos.modules.sales.presentation.sale_view_model import HeldSaleSnapshot, SaleViewModel
from pos.modules.scales.presentation.scale_weight_dialog import ScaleWeightDialog
from pos.shared_ui.formatting import format_currency
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.table_utils import fit_list_to_contents, fit_table_to_contents
from pos.shared_ui.widgets.toast import show_toast

_GENERIC_PAYMENT_PAGE = 0
_QR_PAYMENT_PAGE = 1
_NEQUI_PAYMENT_PAGE = 2
_BREB_PAYMENT_PAGE = 3
_PAYMENT_METHOD_PAGES = {
    PaymentMethod.QR: _QR_PAYMENT_PAGE,
    PaymentMethod.NEQUI: _NEQUI_PAYMENT_PAGE,
    PaymentMethod.BRE_B: _BREB_PAYMENT_PAGE,
}
"""Qué página del `QStackedWidget` de pago corresponde a cada método —
cualquier método no listado usa la página genérica (monto/cambio). Agregar
una interfaz propia para otro método a futuro es sumar una página nueva al
stack y una entrada acá, sin reescribir Caja."""

_ITEM_COLUMNS = ["Producto", "Cantidad / Peso", "Precio", "Impuesto", "Total"]


def _format_cart_quantity(line: SalePreviewLineDTO) -> str:
    """`"2.350 kg"` en líneas por peso — nunca debe leerse como si fueran
    "2 unidades" (mismo criterio que `pdf_renderer._format_item_quantity`,
    duplicado acá porque el carrito trabaja con `SalePreviewLineDTO`, no
    con `SaleItemDTO`)."""
    if line.sale_unit is SaleUnit.WEIGHT:
        return f"{line.quantity} {line.unit_of_measure}"
    return str(line.quantity)


def _format_cart_unit_price(line: SalePreviewLineDTO) -> str:
    """`"$X / kg"` en líneas por peso, precio plano en líneas por unidad."""
    price = format_currency(line.unit_price)
    if line.sale_unit is SaleUnit.WEIGHT:
        return f"{price} / {line.unit_of_measure}"
    return price

_PAYMENT_METHOD_LABELS = {
    PaymentMethod.CASH: "Efectivo",
    PaymentMethod.CARD: "Tarjeta",
    PaymentMethod.TRANSFER: "Transferencia",
    PaymentMethod.NEQUI: "Nequi",
    PaymentMethod.DAVIPLATA: "Daviplata",
    PaymentMethod.QR: "QR",
    PaymentMethod.BRE_B: "Bre-B",
    PaymentMethod.CUSTOMER_CREDIT: "Agregar a la deuda",
    PaymentMethod.OTHER: "Otro",
}
"""Conserva una etiqueta para cada valor del enum (incluso los que ya no
son seleccionables en Caja) para poder mostrar el historial de ventas
antiguas sin errores."""

_SELECTABLE_PAYMENT_METHODS = [
    PaymentMethod.CASH,
    PaymentMethod.CARD,
    PaymentMethod.QR,
    PaymentMethod.NEQUI,
    PaymentMethod.BRE_B,
]
"""Únicos métodos que puede elegir el cajero sin un cliente registrado —
Daviplata/Transferencia/Otro se mantienen en el enum solo por compatibilidad
con ventas históricas, ver `sales/domain/enums.py`. `CUSTOMER_CREDIT`
("Agregar a la deuda") no está acá: `_rebuild_payment_method_combo` lo
agrega aparte, solo mientras hay un cliente seleccionado (ver
`_registered_customer_id`), para que no aparezca como opción elegible
cuando vender a crédito ni siquiera es posible (ver también el resguardo en
`_on_payment_method_changed`)."""


class SaleView(QWidget):
    def __init__(self, view_model: SaleViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._products: list[ProductDTO] = []
        self._customers: list[CustomerDTO] = []
        self._current_preview: SalePreviewDTO | None = None
        self._current_payments: list[SalePaymentInput] = []
        self._pending_scan_product: ProductDTO | None = None
        self._pending_change = Decimal(0)
        self._pending_orders: list[OrderDTO] = []
        self._held_sales: list[HeldSaleSnapshot] = []
        self._registered_customer_id: int | None = None
        """Cliente elegido desde el buscador (o restaurado de una venta en
        espera) — distinto de escribir un nombre a mano en
        `_customer_name_edit`. Solo con esto en `int` se puede usar
        "Agregar a la deuda"."""
        self._scan_idle_timer = QTimer(self)
        self._scan_idle_timer.setSingleShot(True)
        self._scan_idle_timer.timeout.connect(self._on_scan_idle_timeout)
        self._build_ui()
        self._connect_signals()
        self._view_model.load()
        self._scan_edit.setFocus()

    def reload(self) -> None:
        """Se llama al recuperar el foco de esta pestaña (ver `main.py`),
        para que el carrito refleje productos/clientes recién cambiados en
        otra pestaña sin tener que salir y volver a entrar al módulo. El
        foco vuelve automáticamente al campo de escaneo — el lector debe
        funcionar de inmediato sin que el cajero tenga que hacer clic."""
        self._view_model.load()
        self._scan_edit.setFocus()

    def eventFilter(self, watched: object, event: object) -> bool:
        if isinstance(event, QEvent) and event.type() == QEvent.Type.KeyPress:
            key = event.key()  # type: ignore[attr-defined]
            if watched is self._items_table and key == Qt.Key.Key_Space:
                self._payment_amount_edit.setFocus()
                return True
            if watched is self._scan_edit and key == Qt.Key.Key_Tab:
                if self._scan_edit.text().strip():
                    # Hay texto sin procesar: un lector configurado para
                    # terminar con Tab en vez de Enter (variante real de
                    # HID keyboard-wedge) debe resolverse igual que
                    # cualquier otro escaneo, no interpretarse como el
                    # atajo de "dejar en espera" de abajo.
                    self._on_scan_entered()
                    return True
                # Campo vacío: `Tab` es el atajo deliberado del cajero para
                # dejar la venta actual en espera y arrancar una nueva
                # vacía, en vez de mover el foco al siguiente campo
                # (comportamiento normal de `Tab` en cualquier otro campo
                # de esta pantalla, que no se toca).
                self._view_model.hold_current_sale()
                return True
        return super().eventFilter(watched, event)

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area, layout = build_scrollable_page(self)
        outer_layout.addWidget(scroll_area)

        title = make_section_title("Ventas")
        layout.addWidget(title)

        layout.addWidget(QLabel("Pedidos pendientes de cobro (Vendedor/Despacho):"))
        self._pending_orders_list = QListWidget(self)
        layout.addWidget(self._pending_orders_list)
        self._load_order_button = QPushButton("Cobrar pedido seleccionado")
        layout.addWidget(self._load_order_button)

        layout.addWidget(QLabel("Ventas en espera (Tab en el buscador para dejar una en espera):"))
        self._held_sales_list = QListWidget(self)
        layout.addWidget(self._held_sales_list)
        self._resume_held_sale_button = QPushButton("Reanudar venta en espera seleccionada")
        layout.addWidget(self._resume_held_sale_button)

        layout.addWidget(QLabel("Nombre del cliente"))
        name_row = QHBoxLayout()
        self._customer_name_edit = QLineEdit(self)
        self._customer_name_edit.setPlaceholderText("Opcional — Sin nombre si se deja vacío")
        name_row.addWidget(self._customer_name_edit, stretch=2)

        # Buscador de clientes registrados — NO es un segundo cliente, solo
        # autocompleta Nombre del cliente/Documento (arriba, sin mover ni
        # eliminar) y se vacía apenas se elige uno, ver
        # `_apply_registered_customer`. Reemplaza la combo "Cliente
        # (opcional para crédito)" que existía antes debajo del carrito —
        # esa era una segunda forma independiente de fijar el cliente.
        self._customer_search_edit = QLineEdit(self)
        self._customer_search_edit.setPlaceholderText(
            "Buscar cliente registrado (nombre o documento)..."
        )
        customer_completer = QCompleter(self)
        customer_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        customer_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._customer_completer_model = QStringListModel(self)
        customer_completer.setModel(self._customer_completer_model)
        self._customer_search_edit.setCompleter(customer_completer)
        customer_completer.activated[str].connect(self._on_customer_search_selected)
        name_row.addWidget(self._customer_search_edit, stretch=1)
        layout.addLayout(name_row)

        layout.addWidget(QLabel("Documento"))
        self._customer_document_edit = QLineEdit(self)
        self._customer_document_edit.setPlaceholderText("Opcional — Sin documento si se deja vacío")
        layout.addWidget(self._customer_document_edit)

        scan_row = QHBoxLayout()
        self._scan_edit = QLineEdit(self)
        self._scan_edit.setPlaceholderText(
            "Escanear código de barras (SKU) o buscar por nombre, y Enter"
        )
        scan_completer = QCompleter(self)
        scan_completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        scan_completer.setFilterMode(Qt.MatchFlag.MatchContains)
        self._scan_completer_model = QStringListModel(self)
        scan_completer.setModel(self._scan_completer_model)
        self._scan_edit.setCompleter(scan_completer)
        self._scan_edit.installEventFilter(self)
        self._scan_edit.textChanged.connect(self._on_scan_text_changed)
        scan_row.addWidget(self._scan_edit, stretch=2)
        self._scan_quantity_edit = QLineEdit(self)
        self._scan_quantity_edit.setPlaceholderText("Cantidad")
        self._scan_quantity_edit.setVisible(False)
        scan_row.addWidget(self._scan_quantity_edit, stretch=1)
        layout.addLayout(scan_row)

        self._scan_feedback_label = QLabel("")
        self._scan_feedback_label.setVisible(False)
        layout.addWidget(self._scan_feedback_label)

        self._scan_pending_label = QLabel("")
        self._scan_pending_label.setVisible(False)
        layout.addWidget(self._scan_pending_label)

        add_row = QHBoxLayout()
        self._product_combo = QComboBox(self)
        self._product_combo.setEditable(True)
        self._product_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        completer = QCompleter(self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchContains)
        completer.setModel(self._product_combo.model())
        self._product_combo.setCompleter(completer)
        self._quantity_edit = QLineEdit(self)
        self._quantity_edit.setText("1")
        self._add_item_button = QPushButton("Agregar al carrito")
        add_row.addWidget(self._product_combo, stretch=2)
        add_row.addWidget(self._quantity_edit, stretch=1)
        add_row.addWidget(self._add_item_button)
        layout.addLayout(add_row)

        self._items_table = QTableWidget(0, len(_ITEM_COLUMNS), self)
        self._items_table.setHorizontalHeaderLabels(_ITEM_COLUMNS)
        self._items_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._items_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._items_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._items_table.installEventFilter(self)
        layout.addWidget(self._items_table)

        cart_actions = QHBoxLayout()
        self._edit_item_button = QPushButton("Editar producto seleccionado")
        self._remove_item_button = QPushButton("Eliminar producto")
        self._edit_item_button.setEnabled(False)
        self._remove_item_button.setEnabled(False)
        cart_actions.addWidget(self._edit_item_button)
        cart_actions.addWidget(self._remove_item_button)
        layout.addLayout(cart_actions)

        self._totals_label = QLabel("Total: 0.00")
        self._totals_label.setProperty("emphasis", True)
        layout.addWidget(self._totals_label)

        method_row = QHBoxLayout()
        method_row.addWidget(QLabel("Método de pago:"))
        self._payment_method_combo = QComboBox(self)
        self._rebuild_payment_method_combo()
        method_row.addWidget(self._payment_method_combo)
        layout.addLayout(method_row)

        self._payment_stack = QStackedWidget(self)

        generic_page = QWidget()
        generic_row = QHBoxLayout(generic_page)
        generic_row.setContentsMargins(0, 0, 0, 0)
        self._payment_amount_edit = QLineEdit(self)
        self._payment_amount_edit.setPlaceholderText("Monto")
        self._add_payment_button = QPushButton("Agregar pago")
        generic_row.addWidget(self._payment_amount_edit)
        generic_row.addWidget(self._add_payment_button)
        self._payment_stack.addWidget(generic_page)

        qr_page = QWidget()
        qr_page_row = QHBoxLayout(qr_page)
        qr_page_row.setContentsMargins(0, 0, 0, 0)
        self._qr_pay_button = QPushButton("Cobrar con QR")
        qr_page_row.addWidget(self._qr_pay_button)
        self._payment_stack.addWidget(qr_page)

        nequi_page = QWidget()
        nequi_page_row = QHBoxLayout(nequi_page)
        nequi_page_row.setContentsMargins(0, 0, 0, 0)
        self._nequi_pay_button = QPushButton("Cobrar con Nequi")
        nequi_page_row.addWidget(self._nequi_pay_button)
        self._payment_stack.addWidget(nequi_page)

        breb_page = QWidget()
        breb_page_row = QHBoxLayout(breb_page)
        breb_page_row.setContentsMargins(0, 0, 0, 0)
        self._breb_pay_button = QPushButton("Cobrar con Bre-B")
        breb_page_row.addWidget(self._breb_pay_button)
        self._payment_stack.addWidget(breb_page)

        layout.addWidget(self._payment_stack)

        self._change_label = QLabel("")
        self._change_label.setProperty("role", "success")
        layout.addWidget(self._change_label)

        self._payments_list = QListWidget(self)
        layout.addWidget(self._payments_list)

        self._complete_button = QPushButton("Completar venta")
        layout.addWidget(self._complete_button)

        self._print_button = QPushButton("Imprimir ticket")
        layout.addWidget(self._print_button)

    def _connect_signals(self) -> None:
        self._scan_edit.returnPressed.connect(self._on_scan_entered)
        self._scan_quantity_edit.returnPressed.connect(self._on_scan_quantity_entered)
        self._add_item_button.clicked.connect(self._on_add_item_clicked)
        self._edit_item_button.clicked.connect(self._on_edit_item_clicked)
        self._remove_item_button.clicked.connect(self._on_remove_item_clicked)
        self._add_payment_button.clicked.connect(self._on_add_payment_clicked)
        self._payment_amount_edit.returnPressed.connect(self._on_add_payment_clicked)
        self._payment_method_combo.currentIndexChanged.connect(self._on_payment_method_changed)
        self._qr_pay_button.clicked.connect(self._on_qr_pay_clicked)
        self._nequi_pay_button.clicked.connect(self._on_nequi_pay_clicked)
        self._breb_pay_button.clicked.connect(self._on_breb_pay_clicked)
        self._complete_button.clicked.connect(self._on_complete_clicked)
        self._print_button.clicked.connect(self._on_print_clicked)
        self._customer_search_edit.returnPressed.connect(self._on_customer_search_entered)
        self._product_combo.currentIndexChanged.connect(self._on_product_selection_changed)
        self._items_table.itemSelectionChanged.connect(self._on_cart_selection_changed)
        self._load_order_button.clicked.connect(self._on_load_order_clicked)
        self._resume_held_sale_button.clicked.connect(self._on_resume_held_sale_clicked)
        self._held_sales_list.itemDoubleClicked.connect(self._on_resume_held_sale_clicked)
        self._customer_name_edit.textChanged.connect(self._view_model.set_customer_name)
        self._customer_document_edit.textChanged.connect(self._view_model.set_customer_document)

        self._view_model.held_sales_changed.connect(self._on_held_sales_changed)
        self._view_model.pending_orders_loaded.connect(self._on_pending_orders_loaded)
        self._view_model.customer_fields_loaded.connect(self._on_customer_fields_loaded)
        self._view_model.products_loaded.connect(self._on_products_loaded)
        self._view_model.customers_loaded.connect(self._on_customers_loaded)
        self._view_model.scan_resolved.connect(self._on_scan_resolved)
        self._view_model.cart_changed.connect(self._on_cart_changed)
        self._view_model.payments_changed.connect(self._on_payments_changed)
        self._view_model.sale_completed.connect(self._on_sale_completed)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_products_loaded(self, products: list[ProductDTO]) -> None:
        self._products = products
        self._product_combo.clear()
        for product in products:
            self._product_combo.addItem(f"{product.sku} — {product.name}", userData=product.id)
        self._scan_completer_model.setStringList(
            [f"{product.sku} — {product.name}" for product in products]
        )

    def _on_customers_loaded(self, customers: list[CustomerDTO]) -> None:
        self._customers = customers
        self._customer_completer_model.setStringList(
            [self._customer_search_label(c) for c in customers]
        )

    def _on_pending_orders_loaded(self, orders: list[OrderDTO]) -> None:
        self._pending_orders = orders
        self._pending_orders_list.clear()
        for order in orders:
            item_count = len(order.items)
            customer_name = order.customer_name or "Consumidor Final"
            statuses = {item.status for item in order.items}
            if statuses <= {OrderItemStatus.READY, OrderItemStatus.DELIVERED}:
                status_label = "Listo"
            elif OrderItemStatus.PREPARING in statuses:
                status_label = "En preparación"
            else:
                status_label = "Pendiente"
            ready_label = f"{order.ready_at.astimezone():%H:%M}" if order.ready_at else "—"
            self._pending_orders_list.addItem(
                f"{customer_name}  —  {item_count} producto(s)  —  "
                f"{status_label}  —  Listo: {ready_label}"
            )
        fit_list_to_contents(self._pending_orders_list)

    def _on_held_sales_changed(self, held_sales: list[HeldSaleSnapshot]) -> None:
        self._held_sales = held_sales
        self._held_sales_list.clear()
        for snapshot in held_sales:
            customer = (
                self._customer_by_id(snapshot.customer_id)
                if snapshot.customer_id is not None
                else None
            )
            customer_label = customer.full_name if customer is not None else "(sin cliente)"
            self._held_sales_list.addItem(
                f"{customer_label} — {snapshot.item_count} producto(s)"
            )
        fit_list_to_contents(self._held_sales_list)

    def _customer_by_id(self, customer_id: object) -> CustomerDTO | None:
        return next((c for c in self._customers if c.id == customer_id), None)

    def _on_resume_held_sale_clicked(self) -> None:
        row = self._held_sales_list.currentRow()
        if row < 0:
            self._show_error("Selecciona una venta en espera.")
            return
        customer_id = self._held_sales[row].customer_id
        self._view_model.resume_held_sale(row)
        self._registered_customer_id = customer_id
        self._rebuild_payment_method_combo()

    def _on_load_order_clicked(self) -> None:
        row = self._pending_orders_list.currentRow()
        if row < 0:
            self._show_error("Selecciona un pedido pendiente de cobro.")
            return
        self._view_model.load_from_order(self._pending_orders[row])

    def _on_customer_fields_loaded(self, name: str, document: str) -> None:
        """Sincronización con Vendedor: precarga nombre/documento del
        pedido cargado (ver `SaleViewModel.load_from_order`) sin que el
        cajero tenga que volver a escribirlos."""
        self._customer_name_edit.setText(name)
        self._customer_document_edit.setText(document)

    def _customer_search_label(self, customer: CustomerDTO) -> str:
        return f"{customer.full_name} — {customer.document_id or 's/doc'}"

    def _customer_by_search_label(self, label: str) -> CustomerDTO | None:
        return next(
            (c for c in self._customers if self._customer_search_label(c) == label), None
        )

    def _apply_registered_customer(self, customer: CustomerDTO) -> None:
        """Único punto donde el buscador toca el resto de la pantalla:
        llena Nombre del cliente/Documento (ya existentes), se vacía a sí
        mismo, y selecciona "Agregar a la deuda" automáticamente (punto 4
        del pedido) — el cajero puede cambiarlo después si prefiere cobrar
        normal."""
        self._registered_customer_id = customer.id
        self._view_model.set_customer(customer.id)
        self._customer_name_edit.setText(customer.full_name)
        self._customer_document_edit.setText(customer.document_id or "")
        self._customer_search_edit.clear()
        self._rebuild_payment_method_combo()
        index = self._payment_method_combo.findData(PaymentMethod.CUSTOMER_CREDIT)
        if index >= 0:
            self._payment_method_combo.setCurrentIndex(index)

    def _on_customer_search_selected(self, label: str) -> None:
        customer = self._customer_by_search_label(label)
        if customer is not None:
            self._apply_registered_customer(customer)

    def _on_customer_search_entered(self) -> None:
        raw = self._customer_search_edit.text().strip()
        if not raw:
            return
        customer = self._customer_by_search_label(raw)
        if customer is None:
            lowered = raw.lower()
            customer = next(
                (c for c in self._customers if lowered in self._customer_search_label(c).lower()),
                None,
            )
        if customer is None:
            self._show_error(f"No se encontró ningún cliente registrado para '{raw}'.")
            return
        self._apply_registered_customer(customer)

    def _on_product_selection_changed(self, index: int) -> None:
        product = self._product_by_id(self._product_combo.currentData())
        if product is not None and product.sale_unit is SaleUnit.WEIGHT:
            self._quantity_edit.setPlaceholderText(f"Peso ({product.unit_of_measure})")
        else:
            self._quantity_edit.setPlaceholderText("Cantidad")

    def _product_by_id(self, product_id: object) -> ProductDTO | None:
        return next((p for p in self._products if p.id == product_id), None)

    def _on_cart_changed(self, preview: SalePreviewDTO) -> None:
        self._current_preview = preview
        self._items_table.setRowCount(len(preview.items))
        for row, line in enumerate(preview.items):
            values = [
                line.product_name,
                _format_cart_quantity(line),
                _format_cart_unit_price(line),
                format_currency(line.tax_amount),
                format_currency(line.line_total),
            ]
            for col, value in enumerate(values):
                self._items_table.setItem(row, col, QTableWidgetItem(value))
        fit_table_to_contents(self._items_table)
        self._totals_label.setText(
            f"Subtotal: {format_currency(preview.subtotal)}  "
            f"Descuento: {format_currency(preview.discount_total)}  "
            f"Impuesto: {format_currency(preview.tax_total)}  "
            f"Total: {format_currency(preview.total)}"
        )
        self._on_cart_selection_changed()

    def _on_payments_changed(self, payments: list[SalePaymentInput]) -> None:
        self._current_payments = payments
        self._payments_list.clear()
        for payment in payments:
            label = _PAYMENT_METHOD_LABELS.get(payment.payment_method, payment.payment_method.value)
            self._payments_list.addItem(f"{label} — {format_currency(payment.amount)}")
        fit_list_to_contents(self._payments_list)

    def _on_scan_entered(self) -> None:
        raw = self._scan_edit.text().strip()
        if not raw:
            return
        self._scan_idle_timer.stop()
        self._view_model.scan_barcode(raw)

    def _on_scan_text_changed(self, text: str) -> None:
        """Respaldo para lectores configurados sin sufijo Enter (ajuste
        "Aceptar Enter automático: No", ver `BarcodeSettingsDTO`) — si pasa
        un instante corto sin ninguna tecla nueva, se resuelve igual que si
        hubiera llegado Enter. Un lector HID escribe mucho más rápido que
        cualquier persona, así que este umbral nunca interrumpe a un
        cajero escribiendo a mano salvo que se detenga justo ahí, que es
        exactamente cuando ya terminó de escribir. Con el ajuste en su
        valor por defecto (Sí) esto no hace nada — Enter sigue siendo el
        único disparador, sin cambiar el comportamiento existente."""
        if not text.strip():
            self._scan_idle_timer.stop()
            return
        if self._view_model.get_barcode_settings().auto_enter_enabled:
            return
        self._scan_idle_timer.start(100)

    def _on_scan_idle_timeout(self) -> None:
        self._on_scan_entered()

    def _on_scan_resolved(self, result: BarcodeReadResultDTO) -> None:
        """Reacciona a CADA lectura procesada por `SaleViewModel.scan_barcode`
        — encontrada, no encontrada o ignorada — limpiando y reenfocando el
        campo siempre, sin excepción (antes, un código no encontrado dejaba
        el campo sucio y sin foco, rompiendo el escaneo continuo)."""
        self._scan_edit.clear()
        if result.ignored:
            self._scan_edit.setFocus()
            return
        if result.found:
            assert result.product is not None
            if result.product.sale_unit is SaleUnit.WEIGHT:
                # El ViewModel no agregó nada al carrito para un producto
                # por peso (ver `scan_barcode`) — acá se abre la báscula
                # para leer/ingresar el peso real antes de agregarlo.
                self._open_scale_weight_dialog(result.product)
                return
            self._play_scan_feedback(success=True, message=f"Código {result.code} agregado.")
            self._scan_edit.setFocus()
            return

        # Sin coincidencia exacta de código de barras: se intenta la misma
        # búsqueda manual por SKU/nombre que ya existía, antes de mostrar
        # el error — la búsqueda manual siempre debe terminar agregando el
        # mismo producto que un código exacto (punto 7 del pedido).
        code = result.code
        product = next((p for p in self._products if p.sku == code), None)
        if product is None:
            lowered = code.lower()
            product = next(
                (p for p in self._products if lowered in f"{p.sku} — {p.name}".lower()), None
            )
        if product is None:
            self._play_scan_feedback(success=False, message=f"Código {code} no encontrado.")
            self._show_error(f"Código {code} no encontrado.")
            self._scan_edit.setFocus()
            return
        if product.sale_unit is SaleUnit.WEIGHT:
            self._open_scale_weight_dialog(product)
            return
        self._pending_scan_product = product
        self._scan_pending_label.setText(f"Cantidad para: {product.name}")
        self._scan_pending_label.setVisible(True)
        self._scan_quantity_edit.setPlaceholderText("Cantidad")
        self._scan_quantity_edit.setText("1")
        self._scan_quantity_edit.setVisible(True)
        self._scan_quantity_edit.setFocus()
        self._scan_quantity_edit.selectAll()

    def _play_scan_feedback(self, *, success: bool, message: str) -> None:
        settings = self._view_model.get_barcode_settings()
        should_beep = (
            settings.sound_on_success if success else settings.sound_on_not_found
        )
        if should_beep:
            QApplication.beep()
        if settings.show_visual_notification:
            self._scan_feedback_label.setText(("✅ " if success else "❌ ") + message)
            self._scan_feedback_label.setProperty("role", "success" if success else "danger")
            self._scan_feedback_label.style().unpolish(self._scan_feedback_label)
            self._scan_feedback_label.style().polish(self._scan_feedback_label)
            self._scan_feedback_label.setVisible(True)
        else:
            self._scan_feedback_label.setVisible(False)

    def _open_scale_weight_dialog(self, product: ProductDTO) -> None:
        """Se abre en vez del flujo normal de cantidad cuando el producto
        es por peso (ver `ScaleWeightDialog`) — intenta leer la báscula
        automáticamente y cae a ingreso manual si no hay conexión."""
        dialog = ScaleWeightDialog(
            product_name=product.name,
            unit_price=product.unit_price,
            unit_of_measure=product.unit_of_measure,
            scale_read_service=self._view_model.scale_read_service,
            min_weight=product.min_weight,
            max_weight=product.max_weight,
            parent=self,
        )
        if dialog.exec() != ScaleWeightDialog.DialogCode.Accepted:
            self._scan_edit.setFocus()
            return
        self._view_model.add_item(
            product.id, dialog.weight(), weight_entry_source=dialog.weight_entry_source()
        )
        self._scan_edit.setFocus()

    def _on_scan_quantity_entered(self) -> None:
        if self._pending_scan_product is None:
            return
        try:
            quantity = Decimal(self._scan_quantity_edit.text())
        except InvalidOperation:
            self._show_error("La cantidad debe ser un número válido.")
            return
        if quantity <= 0:
            self._show_error("La cantidad debe ser mayor que cero.")
            return
        self._view_model.add_item(self._pending_scan_product.id, quantity)
        self._pending_scan_product = None
        self._scan_quantity_edit.clear()
        self._scan_quantity_edit.setVisible(False)
        self._scan_pending_label.setVisible(False)
        self._scan_edit.setFocus()

    def _on_add_item_clicked(self) -> None:
        product_id = self._product_combo.currentData()
        if product_id is None:
            self._show_error("Selecciona un producto.")
            return
        product = self._product_by_id(product_id)
        if product is not None and product.sale_unit is SaleUnit.WEIGHT:
            self._open_scale_weight_dialog(product)
            return
        try:
            quantity = Decimal(self._quantity_edit.text())
        except InvalidOperation:
            self._show_error("La cantidad debe ser un número válido.")
            return
        self._view_model.add_item(product_id, quantity)

    def _selected_cart_row(self) -> int | None:
        selected_rows = self._items_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return selected_rows[0].row()

    def _on_cart_selection_changed(self) -> None:
        has_selection = self._selected_cart_row() is not None
        self._edit_item_button.setEnabled(has_selection)
        self._remove_item_button.setEnabled(has_selection)

    def _on_remove_item_clicked(self) -> None:
        row = self._selected_cart_row()
        if row is None:
            self._show_error("Selecciona un producto del carrito.")
            return
        product_name = (
            self._current_preview.items[row].product_name if self._current_preview else ""
        )
        confirmed = QMessageBox.question(
            self,
            "Eliminar producto",
            f"¿Seguro que deseas eliminar '{product_name}' del carrito?",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        self._view_model.remove_item(row)

    def _on_edit_item_clicked(self) -> None:
        row = self._selected_cart_row()
        if row is None or self._current_preview is None:
            self._show_error("Selecciona un producto del carrito.")
            return
        line = self._current_preview.items[row]
        dialog = CartItemEditDialog(line.product_name, line.quantity, line.note, parent=self)
        if dialog.exec() != CartItemEditDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        self._view_model.update_item(row, quantity=values["quantity"], note=values["note"])

    def _rebuild_payment_method_combo(self) -> None:
        current_method = self._payment_method_combo.currentData()
        self._payment_method_combo.blockSignals(True)
        self._payment_method_combo.clear()
        methods = _SELECTABLE_PAYMENT_METHODS
        if self._registered_customer_id is not None:
            methods = [*_SELECTABLE_PAYMENT_METHODS, PaymentMethod.CUSTOMER_CREDIT]
        for method in methods:
            self._payment_method_combo.addItem(_PAYMENT_METHOD_LABELS[method], userData=method)
        self._payment_method_combo.blockSignals(False)
        restore_index = self._payment_method_combo.findData(current_method)
        self._payment_method_combo.setCurrentIndex(restore_index if restore_index >= 0 else 0)

    def _confirm_credit_within_limit(self, amount: Decimal) -> bool:
        """Aviso previo de cupo (punto 5 del pedido) — la validación real y
        autoritativa sigue en `CustomerManagementService.register_credit_movement`
        (se dispara igual dentro de `complete_sale`), esto es solo para no
        hacer esperar al cajero a que la venta falle para enterarse."""
        if self._registered_customer_id is None:
            return True
        customer = self._view_model.customer_service.get_customer(self._registered_customer_id)
        if customer is None:
            return True
        available = customer.credit_limit - customer.current_debt
        if amount > available:
            QMessageBox.warning(
                self,
                "Cupo de crédito insuficiente",
                "No es posible agregar esta venta a la deuda porque el cliente supera "
                "el cupo de crédito asignado.\n\n"
                f"Cupo total: {format_currency(customer.credit_limit)}\n"
                f"Cupo disponible: {format_currency(available)}\n"
                f"Valor de la venta: {format_currency(amount)}",
            )
            return False
        return True

    def _on_payment_method_changed(self, index: int) -> None:
        method = self._payment_method_combo.currentData()
        if method is PaymentMethod.CUSTOMER_CREDIT and self._registered_customer_id is None:
            self._show_error("Para vender a crédito debe seleccionar un cliente registrado.")
            fallback_index = self._payment_method_combo.findData(PaymentMethod.CASH)
            self._payment_method_combo.setCurrentIndex(fallback_index if fallback_index >= 0 else 0)
            return
        self._payment_stack.setCurrentIndex(
            _PAYMENT_METHOD_PAGES.get(method, _GENERIC_PAYMENT_PAGE)
        )

    def _open_manual_payment_dialog(self, method: PaymentMethod, build_dialog) -> None:
        """Flujo compartido por QR/Nequi/Bre-B: calcula el saldo pendiente,
        abre la ventana de cobro correspondiente y, si el cajero confirma
        (`Accepted`), registra el pago y completa la venta si ya cubre el
        total — mismo comportamiento que tenía `_on_qr_pay_clicked`."""
        total_due = self._current_preview.total if self._current_preview is not None else Decimal(0)
        already_paid = sum((p.amount for p in self._current_payments), Decimal(0))
        remaining = total_due - already_paid
        if remaining <= 0:
            self._show_error("No hay ningún monto pendiente por cobrar.")
            return

        dialog = build_dialog(remaining)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        self._view_model.add_payment(method, remaining, reference=dialog.reference)

        new_total_paid = sum((p.amount for p in self._current_payments), Decimal(0))
        if self._current_preview is not None and new_total_paid >= self._current_preview.total:
            self._pending_change = Decimal(0)
            self._view_model.complete_sale()

    def _on_qr_pay_clicked(self) -> None:
        self._open_manual_payment_dialog(
            PaymentMethod.QR,
            lambda total: QrPaymentDialog(
                total=total,
                qr_payment_service=self._view_model.qr_payment_service,
                customer_name=self._customer_name_edit.text().strip(),
                parent=self,
            ),
        )

    def _on_nequi_pay_clicked(self) -> None:
        self._open_manual_payment_dialog(
            PaymentMethod.NEQUI,
            lambda total: NequiPaymentDialog(
                total=total,
                nequi_payment_service=self._view_model.nequi_payment_service,
                customer_name=self._customer_name_edit.text().strip(),
                parent=self,
            ),
        )

    def _on_breb_pay_clicked(self) -> None:
        self._open_manual_payment_dialog(
            PaymentMethod.BRE_B,
            lambda total: BreBPaymentDialog(
                total=total,
                breb_payment_service=self._view_model.breb_payment_service,
                customer_name=self._customer_name_edit.text().strip(),
                parent=self,
            ),
        )

    def _on_add_payment_clicked(self) -> None:
        method = self._payment_method_combo.currentData()
        try:
            entered_amount = Decimal(self._payment_amount_edit.text())
        except InvalidOperation:
            self._show_error("El monto debe ser un número válido.")
            return
        if entered_amount <= 0:
            self._show_error("El monto debe ser mayor que cero.")
            return

        total_due = self._current_preview.total if self._current_preview is not None else Decimal(0)
        already_paid = sum((p.amount for p in self._current_payments), Decimal(0))
        remaining = total_due - already_paid

        change = Decimal(0)
        if method is PaymentMethod.CASH and remaining > 0 and entered_amount > remaining:
            applied_amount = remaining
            change = entered_amount - remaining
        else:
            applied_amount = entered_amount

        if method is PaymentMethod.CUSTOMER_CREDIT and not self._confirm_credit_within_limit(
            applied_amount
        ):
            return

        self._change_label.setText(f"Cambio: {format_currency(change)}" if change > 0 else "")
        self._view_model.add_payment(method, applied_amount)
        self._payment_amount_edit.clear()

        new_total_paid = sum((p.amount for p in self._current_payments), Decimal(0))
        if self._current_preview is not None and new_total_paid >= self._current_preview.total:
            self._pending_change = change
            self._view_model.complete_sale()

    def _on_complete_clicked(self) -> None:
        method = self._payment_method_combo.currentData()
        total_due = self._current_preview.total if self._current_preview is not None else Decimal(0)
        already_paid = sum((p.amount for p in self._current_payments), Decimal(0))
        if (total_due - already_paid) > 0 and method in _PAYMENT_METHOD_PAGES:
            # QR/Nequi/Bre-B necesitan mostrar su ventana de cobro antes de
            # completar la venta — sin esto, `complete_sale()` fallaría
            # porque los pagos registrados no cubrirían el total.
            manual_handlers = {
                PaymentMethod.QR: self._on_qr_pay_clicked,
                PaymentMethod.NEQUI: self._on_nequi_pay_clicked,
                PaymentMethod.BRE_B: self._on_breb_pay_clicked,
            }
            manual_handlers[method]()
            return
        self._pending_change = Decimal(0)
        self._view_model.complete_sale()

    def _on_print_clicked(self) -> None:
        self._view_model.print_last_receipt()

    def _on_sale_completed(self, sale: object) -> None:
        change = self._pending_change
        self._pending_change = Decimal(0)
        self._registered_customer_id = None
        self._rebuild_payment_method_combo()
        self._customer_search_edit.clear()
        self._customer_name_edit.clear()
        self._customer_document_edit.clear()
        self._change_label.setText(f"Cambio: {format_currency(change)}" if change > 0 else "")
        self._view_model.open_drawer_if_applicable()
        if self._prompt_print_receipt(change):
            self._view_model.print_last_receipt(trigger_drawer_if_configured=True)

    def _prompt_print_receipt(self, change: Decimal) -> bool:
        dialog = PrintReceiptPromptDialog(change, parent=self)
        return dialog.exec() == PrintReceiptPromptDialog.DialogCode.Accepted

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
