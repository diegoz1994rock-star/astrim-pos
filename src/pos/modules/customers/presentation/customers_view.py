"""Pantalla de administración de clientes."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.customers.application.dto import CustomerDTO
from pos.modules.customers.infrastructure.models import CreditMovementType
from pos.modules.customers.presentation.customer_form_dialog import CustomerFormDialog
from pos.modules.customers.presentation.customers_view_model import CustomersViewModel

_COLUMNS = ["Nombre", "Documento", "Teléfono", "Deuda", "Cupo", "Puntos"]


class CustomersView(QWidget):
    def __init__(self, view_model: CustomersViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._customers: list[CustomerDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        title = QLabel("Clientes")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
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
        self._charge_button = QPushButton("Registrar cargo")
        self._payment_button = QPushButton("Registrar abono")
        self._remove_button = QPushButton("Eliminar seleccionado")
        actions.addWidget(self._charge_button)
        actions.addWidget(self._payment_button)
        actions.addWidget(self._remove_button)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._new_button.clicked.connect(self._on_new_clicked)
        self._charge_button.clicked.connect(
            lambda: self._on_credit_movement(CreditMovementType.CHARGE)
        )
        self._payment_button.clicked.connect(
            lambda: self._on_credit_movement(CreditMovementType.PAYMENT)
        )
        self._remove_button.clicked.connect(self._on_remove_clicked)
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
                f"{customer.current_debt:.2f}",
                f"{customer.credit_limit:.2f}",
                str(customer.loyalty_points_balance),
            ]
            for col, value in enumerate(values):
                self._table.setItem(row, col, QTableWidgetItem(value))

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

    def _on_remove_clicked(self) -> None:
        customer = self._selected_customer()
        if customer is None:
            self._show_error("Selecciona un cliente de la tabla.")
            return
        self._view_model.remove_customer(customer.id)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Listo", message)
