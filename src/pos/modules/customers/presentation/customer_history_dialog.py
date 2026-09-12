"""Historial completo de un cliente — Cuentas por Cobrar (se abre con
doble clic sobre una fila de la tabla de Clientes, nunca una edición del
cliente). Dos pestañas: "Historial de facturas" (pendientes y pagadas,
doble clic abre el PDF igual que el historial de Ventas, "Registrar
abono" sobre la factura seleccionada) e "Historial de abonos" (extracto
permanente de todo lo cobrado, nunca se borra). "Borrar historial" solo
oculta lo ya saldado para empezar de nuevo — nunca elimina facturas,
ventas ni recibos reales (ver `CustomerManagementService.
clear_credit_history`)."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.billing.application.billing_service import BillingService
from pos.modules.billing.application.dto import DebtPaymentReceiptEntryDTO, InvoiceHistoryEntryDTO
from pos.modules.billing.application.print_helper import (
    print_debt_payment_receipt,
    print_invoice_for_sale,
)
from pos.modules.billing.application.receipt_printer import ReceiptPrinter
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.customers.application.dto import CustomerDTO
from pos.modules.customers.presentation.register_payment_dialog import RegisterPaymentDialog
from pos.modules.printers.application.printer_service import PrinterService
from pos.shared_ui.formatting import format_currency, format_datetime_local
from pos.shared_ui.theme.theme_manager import get_active_tokens
from pos.shared_ui.widgets.status_badge import StatusBadge
from pos.shared_ui.widgets.toast import show_toast

_INVOICE_COLUMNS = [
    "Factura",
    "Fecha",
    "Total factura",
    "Valor abonado",
    "Saldo pendiente",
    "Último abono",
    "Vencimiento",
    "Estado",
    "Usuario",
    "Caja",
    "Sucursal",
]
_RECEIPT_COLUMNS = [
    "Fecha",
    "Hora",
    "N.º de recibo",
    "Factura",
    "Valor abonado",
    "Usuario",
    "Caja",
    "Método de pago",
    "Observación",
]

_ROW_HEIGHT = 40
_MIN_COLUMN_WIDTH = 130


def _row_color(entry: InvoiceHistoryEntryDTO) -> QColor | None:
    """Antes eran 3 colores hex hardcodeados en este archivo (no
    reactivos a un cambio de tema) — ver DESIGN_SYSTEM.md §1.3/§12."""
    tokens = get_active_tokens()
    if entry.balance_due <= 0:
        return QColor(tokens.success_tint)
    if entry.is_overdue:
        return QColor(tokens.danger_tint)
    if entry.paid_amount > 0:
        return QColor(tokens.warning_tint)
    return None


def _status_role(entry: InvoiceHistoryEntryDTO) -> str:
    """Mismo criterio que `_row_color`, traducido a un `role` de
    `StatusBadge` — ver DESIGN_SYSTEM.md §14 (chips de estado en tabla)."""
    if entry.balance_due <= 0:
        return "success"
    if entry.is_overdue:
        return "danger"
    if entry.paid_amount > 0:
        return "warning"
    return "secondary"


def _configure_wide_table(table: QTableWidget) -> None:
    """Tabla ancha, de filas altas, con scroll horizontal y vertical real —
    a propósito NO usa `fit_table_to_contents` (esa función fija la altura
    al contenido y apaga el scroll vertical; acá se necesita justo lo
    contrario, ver punto 9 del pedido)."""
    table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
    table.horizontalHeader().setMinimumSectionSize(_MIN_COLUMN_WIDTH)
    table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
    table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
    table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)


class CustomerHistoryDialog(QDialog):
    def __init__(
        self,
        customer: CustomerDTO,
        billing_service: BillingService,
        customer_service: CustomerManagementService,
        cash_register_service: CashRegisterService,
        session_manager: SessionManager,
        receipt_printer: ReceiptPrinter,
        printer_service: PrinterService,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._customer = customer
        self._billing_service = billing_service
        self._customer_service = customer_service
        self._cash_register_service = cash_register_service
        self._session_manager = session_manager
        self._receipt_printer = receipt_printer
        self._printer_service = printer_service
        self._invoice_entries: list[InvoiceHistoryEntryDTO] = []
        self._receipt_entries: list[DebtPaymentReceiptEntryDTO] = []

        self.setWindowTitle(f"Historial del cliente — {customer.full_name}")
        self.resize(1400, 750)

        layout = QVBoxLayout(self)
        tabs = QTabWidget(self)
        layout.addWidget(tabs)

        invoices_page = QWidget(self)
        invoices_layout = QVBoxLayout(invoices_page)
        self._invoice_table = QTableWidget(0, len(_INVOICE_COLUMNS), invoices_page)
        self._invoice_table.setHorizontalHeaderLabels(_INVOICE_COLUMNS)
        _configure_wide_table(self._invoice_table)
        self._invoice_table.cellDoubleClicked.connect(self._on_invoice_double_clicked)
        self._invoice_table.itemSelectionChanged.connect(self._update_register_payment_button)
        invoices_layout.addWidget(self._invoice_table)

        self._register_payment_button = QPushButton("Registrar abono", invoices_page)
        self._register_payment_button.setEnabled(False)
        self._register_payment_button.setMinimumHeight(40)
        self._register_payment_button.clicked.connect(self._on_register_payment_clicked)
        invoices_layout.addWidget(self._register_payment_button)
        tabs.addTab(invoices_page, "Historial de facturas")

        receipts_page = QWidget(self)
        receipts_layout = QVBoxLayout(receipts_page)
        self._receipt_table = QTableWidget(0, len(_RECEIPT_COLUMNS), receipts_page)
        self._receipt_table.setHorizontalHeaderLabels(_RECEIPT_COLUMNS)
        _configure_wide_table(self._receipt_table)
        self._receipt_table.cellDoubleClicked.connect(self._on_receipt_double_clicked)
        receipts_layout.addWidget(self._receipt_table)
        tabs.addTab(receipts_page, "Historial de abonos")

        self._clear_history_button = QPushButton("Borrar historial", self)
        self._clear_history_button.setMinimumHeight(40)
        self._clear_history_button.clicked.connect(self._on_clear_history_clicked)
        layout.addWidget(self._clear_history_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self._load()

    # -- carga -----------------------------------------------------------

    def _load(self) -> None:
        self._customer = self._customer_service.get_customer(self._customer.id) or self._customer
        self._load_invoices()
        self._load_receipts()
        self._clear_history_button.setEnabled(self._customer.current_debt == 0)

    def _load_invoices(self) -> None:
        self._invoice_entries = self._billing_service.list_customer_debt_history(
            self._customer.id
        )
        self._invoice_table.setRowCount(len(self._invoice_entries))
        _status_column = _INVOICE_COLUMNS.index("Estado")
        for row, entry in enumerate(self._invoice_entries):
            values = [
                entry.invoice_number,
                format_datetime_local(entry.issued_at, "%Y-%m-%d"),
                format_currency(entry.original_amount),
                format_currency(entry.paid_amount),
                format_currency(entry.balance_due),
                format_datetime_local(entry.last_payment_at, "%Y-%m-%d")
                if entry.last_payment_at
                else "—",
                f"{entry.due_date:%Y-%m-%d}" if entry.due_date else "—",
                entry.status,
                entry.cashier_name,
                entry.cash_register_name,
                entry.branch_location,
            ]
            color = _row_color(entry)
            for col, value in enumerate(values):
                if col == _status_column:
                    self._invoice_table.setCellWidget(
                        row, col, StatusBadge(value, _status_role(entry))
                    )
                    continue
                item = QTableWidgetItem(value)
                if color is not None:
                    item.setBackground(color)
                self._invoice_table.setItem(row, col, item)
        self._update_register_payment_button()

    def _load_receipts(self) -> None:
        self._receipt_entries = self._billing_service.list_customer_payment_receipts(
            self._customer.id
        )
        self._receipt_table.setRowCount(len(self._receipt_entries))
        for row, entry in enumerate(self._receipt_entries):
            values = [
                format_datetime_local(entry.paid_at, "%Y-%m-%d"),
                format_datetime_local(entry.paid_at, "%H:%M"),
                entry.receipt_number,
                entry.invoice_number,
                format_currency(entry.amount),
                entry.cashier_name,
                entry.cash_register_name,
                entry.payment_method_label,
                entry.note or "",
            ]
            for col, value in enumerate(values):
                self._receipt_table.setItem(row, col, QTableWidgetItem(value))

    # -- selección / acciones ---------------------------------------------

    def _selected_invoice(self) -> InvoiceHistoryEntryDTO | None:
        selected_rows = self._invoice_table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        return self._invoice_entries[selected_rows[0].row()]

    def _update_register_payment_button(self) -> None:
        entry = self._selected_invoice()
        self._register_payment_button.setEnabled(entry is not None and entry.balance_due > 0)

    def _on_invoice_double_clicked(self, row: int, column: int) -> None:
        """Doble clic = reimprimir la factura, igual que el historial de
        Ventas (`SalesHistoryViewModel.open_invoice_pdf`): genera el PDF si
        aún no existe (idempotente, nunca regenera número ni contenido) y
        la envía a la impresora asignada a la caja activa — o al visor del
        sistema si no hay ninguna configurada."""
        entry = self._invoice_entries[row]
        current_user = self._session_manager.current
        try:
            outcome = print_invoice_for_sale(
                billing_service=self._billing_service,
                printer_service=self._printer_service,
                receipt_printer=self._receipt_printer,
                sale_id=entry.sale_id,
                cash_register_id=self._default_cash_register_id(),
                user_id=current_user.user_id if current_user is not None else None,
                username=current_user.username if current_user is not None else None,
            )
        except DomainError as error:
            QMessageBox.warning(self, "Error", str(error))
            return
        if not outcome.printed:
            QMessageBox.warning(
                self, "Error de impresión", outcome.error or "No se pudo imprimir la factura."
            )

    def _on_receipt_double_clicked(self, row: int, column: int) -> None:
        """Doble clic = reimprimir el recibo de abono — nunca modifica el
        abono ni regenera el PDF, solo reenvía el ya guardado (`entry.
        pdf_path`) a la impresora asignada."""
        entry = self._receipt_entries[row]
        if entry.pdf_path is None:
            QMessageBox.warning(self, "Error", "Este recibo no tiene un PDF disponible.")
            return
        current_user = self._session_manager.current
        outcome = print_debt_payment_receipt(
            printer_service=self._printer_service,
            receipt_printer=self._receipt_printer,
            pdf_path=Path(entry.pdf_path),
            receipt_number=entry.receipt_number,
            invoice_id=entry.invoice_id,
            cash_register_id=self._default_cash_register_id(),
            user_id=current_user.user_id if current_user is not None else None,
            username=current_user.username if current_user is not None else None,
        )
        if not outcome.printed:
            QMessageBox.warning(
                self, "Error de impresión", outcome.error or "No se pudo imprimir el recibo."
            )

    def _default_cash_register_id(self) -> int | None:
        default_register = next(iter(self._cash_register_service.list_registers()), None)
        return default_register.id if default_register is not None else None

    def _on_register_payment_clicked(self) -> None:
        entry = self._selected_invoice()
        if entry is None or entry.balance_due <= 0:
            return

        default_register = next(iter(self._cash_register_service.list_registers()), None)
        if default_register is None:
            QMessageBox.warning(self, "Error", "No hay ningún punto de caja configurado.")
            return
        open_session = self._cash_register_service.get_open_session(default_register.id)
        if open_session is None:
            QMessageBox.warning(
                self,
                "Error",
                "No hay un turno de caja abierto. Ábrelo antes de registrar el abono.",
            )
            return

        dialog = RegisterPaymentDialog(
            invoice_number=entry.invoice_number, balance_due=entry.balance_due, parent=self
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        current_user = self._session_manager.current
        created_by_user_id = current_user.user_id if current_user is not None else None
        try:
            self._billing_service.register_payment(
                invoice_id=entry.invoice_id,
                customer_id=self._customer.id,
                amount=dialog.amount,
                payment_method=dialog.payment_method,
                cash_session_id=open_session.id,
                note=dialog.note,
                created_by_user_id=created_by_user_id,
            )
        except DomainError as error:
            QMessageBox.warning(self, "Error", str(error))
            return

        show_toast(self, "Abono registrado correctamente.")
        self._load()

    def _on_clear_history_clicked(self) -> None:
        confirmed = QMessageBox.question(
            self,
            "Borrar historial",
            "¿Confirmas borrar el historial de crédito de este cliente?\n\n"
            "Las facturas, ventas y recibos reales NO se eliminan — solo se oculta el "
            "historial de deuda ya saldado para empezar de nuevo.",
        )
        if confirmed != QMessageBox.StandardButton.Yes:
            return
        try:
            self._customer_service.clear_credit_history(self._customer.id)
        except DomainError as error:
            QMessageBox.warning(self, "Error", str(error))
            return
        self._load()
