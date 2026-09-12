"""Pantalla de administración de clientes."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.core.security.session import SessionManager
from pos.modules.billing.application.billing_service import BillingService
from pos.modules.billing.application.receipt_printer import ReceiptPrinter
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.customers.application.dto import CustomerDTO
from pos.modules.customers.infrastructure.models import CreditMovementType
from pos.modules.customers.presentation.customer_form_dialog import CustomerFormDialog
from pos.modules.customers.presentation.customer_history_dialog import CustomerHistoryDialog
from pos.modules.customers.presentation.customers_view_model import CustomersViewModel
from pos.modules.printers.application.printer_service import PrinterService
from pos.shared_ui.formatting import format_currency
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.table_utils import fit_table_to_contents
from pos.shared_ui.widgets.toast import show_toast

_COLUMNS = ["Nombre", "Documento", "Teléfono", "Deuda", "Cupo", "Puntos"]


class CustomersView(QWidget):
    def __init__(
        self,
        view_model: CustomersViewModel,
        billing_service: BillingService,
        customer_service: CustomerManagementService,
        cash_register_service: CashRegisterService,
        session_manager: SessionManager,
        receipt_printer: ReceiptPrinter,
        printer_service: PrinterService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._billing_service = billing_service
        self._customer_service = customer_service
        self._cash_register_service = cash_register_service
        self._session_manager = session_manager
        self._receipt_printer = receipt_printer
        self._printer_service = printer_service
        self._customers: list[CustomerDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def reload(self) -> None:
        """Se llama al recuperar el foco de esta pestaña (ver `main.py`)."""
        self._view_model.load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)
        toolbar = QHBoxLayout()
        title = make_section_title("Clientes")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._new_button = QPushButton("Nuevo cliente")
        toolbar.addWidget(self._new_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._payment_button = QPushButton("Registrar abono")
        self._remove_button = QPushButton("Eliminar seleccionado")
        actions.addWidget(self._payment_button)
        actions.addWidget(self._remove_button)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new_clicked)
        self._payment_button.clicked.connect(
            lambda: self._on_credit_movement(CreditMovementType.PAYMENT)
        )
        self._remove_button.clicked.connect(self._on_remove_clicked)
        self._table.doubleClicked.connect(self._on_row_double_clicked)
        self._view_model.customers_loaded.connect(self._on_customers_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_customers_loaded(self, customers: list[CustomerDTO]) -> None:
        self._customers = customers
        self._table.setRowCount(len(customers))
        for row, customer in enumerate(customers):
            values = [
                customer.full_name,
                customer.document_id or "",
                customer.phone or "",
                format_currency(customer.current_debt),
                format_currency(customer.credit_limit),
                str(customer.loyalty_points_balance),
            ]
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(value))
        fit_table_to_contents(self._table)

    def _on_new_clicked(self) -> None:
        dialog = CustomerFormDialog(self)
        if dialog.exec() == CustomerFormDialog.DialogCode.Accepted:
            self._view_model.create_customer(**dialog.values())

    def _selected_customer(self) -> CustomerDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._customers[selected_rows[0].row()]

    def _on_credit_movement(self, movement_type: CreditMovementType) -> None:
        customer = self._selected_customer()
        if customer is None:
            self._show_error("Selecciona un cliente de la tabla.")
            return
        amount_text, accepted = QInputDialog.getText(self, "Monto", "Monto:")
        if not accepted:
            return
        try:
            amount = Decimal(amount_text)
        except InvalidOperation:
            self._show_error("El monto debe ser un número válido.")
            return
        self._view_model.register_credit_movement(customer.id, movement_type, amount)

    def _on_row_double_clicked(self) -> None:
        """Abre el historial completo de facturas del cliente — nunca una
        edición del cliente (punto 8 del pedido; para editar sigue
        existiendo "Nuevo cliente"/el resto de la tabla, sin cambios)."""
        customer = self._selected_customer()
        if customer is None:
            return
        dialog = CustomerHistoryDialog(
            customer,
            self._billing_service,
            self._customer_service,
            self._cash_register_service,
            self._session_manager,
            self._receipt_printer,
            self._printer_service,
            self,
        )
        dialog.exec()
        self._view_model.load()

    def _on_remove_clicked(self) -> None:
        customer = self._selected_customer()
        if customer is None:
            self._show_error("Selecciona un cliente de la tabla.")
            return
        self._view_model.remove_customer(customer.id)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
