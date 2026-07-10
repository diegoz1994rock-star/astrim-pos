"""Pantalla de venta (POS): selección de producto, carrito, pagos y total."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.customers.application.dto import CustomerDTO
from pos.modules.products.application.dto import ProductDTO
from pos.modules.sales.application.dto import SalePaymentInput, SalePreviewDTO
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.sales.presentation.sale_view_model import SaleViewModel

_ITEM_COLUMNS = ["Producto", "Cantidad", "Precio", "Impuesto", "Total línea"]


class SaleView(QWidget):
    def __init__(self, view_model: SaleViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._products: list[ProductDTO] = []
        self._customers: list[CustomerDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Ventas")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        layout.addWidget(title)

        add_row = QHBoxLayout()
        self._product_combo = QComboBox(self)
        self._quantity_edit = QLineEdit(self)
        self._quantity_edit.setText("1")
        self._add_item_button = QPushButton("Agregar al carrito")
        add_row.addWidget(self._product_combo, stretch=2)
        add_row.addWidget(self._quantity_edit, stretch=1)
        add_row.addWidget(self._add_item_button)
        layout.addLayout(add_row)

        self._items_table = QTableWidget(0, len(_ITEM_COLUMNS), self)
        self._items_table.setHorizontalHeaderLabels(_ITEM_COLUMNS)
        layout.addWidget(self._items_table)

        self._remove_item_button = QPushButton("Quitar línea seleccionada")
        layout.addWidget(self._remove_item_button)

        self._totals_label = QLabel("Total: 0.00")
        totals_font = self._totals_label.font()
        totals_font.setBold(True)
        totals_font.setPointSize(13)
        self._totals_label.setFont(totals_font)
        layout.addWidget(self._totals_label)

        customer_row = QHBoxLayout()
        customer_row.addWidget(QLabel("Cliente (opcional para crédito):"))
        self._customer_combo = QComboBox(self)
        customer_row.addWidget(self._customer_combo)
        layout.addLayout(customer_row)

        payment_row = QHBoxLayout()
        self._payment_method_combo = QComboBox(self)
        for method in PaymentMethod:
            self._payment_method_combo.addItem(method.value, userData=method)
        self._payment_amount_edit = QLineEdit(self)
        self._add_payment_button = QPushButton("Agregar pago")
        payment_row.addWidget(self._payment_method_combo)
        payment_row.addWidget(self._payment_amount_edit)
        payment_row.addWidget(self._add_payment_button)
        layout.addLayout(payment_row)

        self._payments_list = QListWidget(self)
        layout.addWidget(self._payments_list)

        self._complete_button = QPushButton("Completar venta")
        layout.addWidget(self._complete_button)

    def _connect_signals(self) -> None:
        self._add_item_button.clicked.connect(self._on_add_item_clicked)
        self._remove_item_button.clicked.connect(self._on_remove_item_clicked)
        self._add_payment_button.clicked.connect(self._on_add_payment_clicked)
        self._complete_button.clicked.connect(self._on_complete_clicked)
        self._customer_combo.currentIndexChanged.connect(self._on_customer_selected)

        self._view_model.products_loaded.connect(self._on_products_loaded)
        self._view_model.customers_loaded.connect(self._on_customers_loaded)
        self._view_model.cart_changed.connect(self._on_cart_changed)
        self._view_model.payments_changed.connect(self._on_payments_changed)
        self._view_model.sale_completed.connect(self._on_sale_completed)
        self._view_model.error_occurred.connect(self._show_error)

    def _on_products_loaded(self, products: list[ProductDTO]) -> None:
        self._products = products
        self._product_combo.clear()
        for product in products:
            self._product_combo.addItem(f"{product.sku} — {product.name}", userData=product.id)

    def _on_customers_loaded(self, customers: list[CustomerDTO]) -> None:
        self._customers = customers
        self._customer_combo.clear()
        self._customer_combo.addItem("(sin cliente)", userData=None)
        for customer in customers:
            self._customer_combo.addItem(customer.full_name, userData=customer.id)

    def _on_customer_selected(self, index: int) -> None:
        self._view_model.set_customer(self._customer_combo.currentData())

    def _on_cart_changed(self, preview: SalePreviewDTO) -> None:
        self._items_table.setRowCount(len(preview.items))
        for row, line in enumerate(preview.items):
            values = [
                line.product_name,
                str(line.quantity),
                f"{line.unit_price:.2f}",
                f"{line.tax_amount:.2f}",
                f"{line.line_total:.2f}",
            ]
            for col, value in enumerate(values):
                self._items_table.setItem(row, col, QTableWidgetItem(value))
        self._totals_label.setText(
            f"Subtotal: {preview.subtotal:.2f}  Descuento: {preview.discount_total:.2f}  "
            f"Impuesto: {preview.tax_total:.2f}  Total: {preview.total:.2f}"
        )

    def _on_payments_changed(self, payments: list[SalePaymentInput]) -> None:
        self._payments_list.clear()
        for payment in payments:
            self._payments_list.addItem(
                f"{payment.payment_method.value} — {payment.amount}"
            )

    def _on_add_item_clicked(self) -> None:
        product_id = self._product_combo.currentData()
        if product_id is None:
            self._show_error("Selecciona un producto.")
            return
        try:
            quantity = Decimal(self._quantity_edit.text())
        except InvalidOperation:
            self._show_error("La cantidad debe ser un número válido.")
            return
        self._view_model.add_item(product_id, quantity)

    def _on_remove_item_clicked(self) -> None:
        selected_rows = self._items_table.selectionModel().selectedRows()
        if selected_rows:
            self._view_model.remove_item(selected_rows[0].row())

    def _on_add_payment_clicked(self) -> None:
        method = self._payment_method_combo.currentData()
        try:
            amount = Decimal(self._payment_amount_edit.text())
        except InvalidOperation:
            self._show_error("El monto del pago debe ser un número válido.")
            return
        self._view_model.add_payment(method, amount)
        self._payment_amount_edit.clear()

    def _on_complete_clicked(self) -> None:
        self._view_model.complete_sale()

    def _on_sale_completed(self, sale: object) -> None:
        QMessageBox.information(self, "Venta completada", "La venta se registró correctamente.")
        self._customer_combo.setCurrentIndex(0)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)
