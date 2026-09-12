"""Pantalla de historial de ventas y anulación."""

from __future__ import annotations

from decimal import Decimal

from PySide6.QtWidgets import (
    QAbstractItemView,
    QGroupBox,
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

from pos.modules.sales.application.dto import SaleDTO
from pos.modules.sales.domain.enums import PaymentMethod, SaleStatus
from pos.modules.sales.presentation.sales_history_view_model import (
    DailyClosingSummaryDTO,
    NamedTotalDTO,
    SalesHistoryViewModel,
)
from pos.shared_ui.formatting import format_currency, format_datetime_local
from pos.shared_ui.widgets.kpi_card import KpiCard
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.table_utils import fit_table_to_contents
from pos.shared_ui.widgets.toast import show_toast

_NAMED_TOTAL_COLUMNS = ["Cajero", "Total"]
_PAYMENTS_TODAY_COLUMNS = [
    "Cliente",
    "Factura",
    "Valor abonado",
    "Hora",
    "Usuario",
    "Caja",
    "Método de pago",
]
_CLOSING_COLUMNS = ["Cajero", "Ventas", "Abonos", "Total recibido"]

_COLUMNS = ["#", "Fecha", "Medio de pago", "Total", "Nombre del cliente", "Documento"]

_PAYMENT_METHOD_LABELS = {
    PaymentMethod.CASH: "Efectivo",
    PaymentMethod.CARD: "Tarjeta",
    PaymentMethod.TRANSFER: "Transferencia",
    PaymentMethod.NEQUI: "Nequi",
    PaymentMethod.DAVIPLATA: "Daviplata",
    PaymentMethod.QR: "QR",
    PaymentMethod.BRE_B: "Bre-B",
    PaymentMethod.CUSTOMER_CREDIT: "Crédito del cliente",
    PaymentMethod.OTHER: "Otro",
}
"""Mismas etiquetas que `sale_view.py` — si se agrega un método de pago
nuevo al enum, agregar su etiqueta acá (y en `sale_view.py`) es lo único
que hace falta; el fallback de `_payment_summary` ya lo muestra aunque se
olvide, con el valor crudo del enum."""


def _payment_summary(sale: SaleDTO) -> str:
    """Medio de pago tal como se guardó al completar la venta — sin texto
    fijo ni simulado: lee directamente `SalePayment.payment_method` (vía
    `SaleDTO.payments`, la misma fuente que usa el resto del sistema).
    Una venta con pago mixto (varios métodos) los junta con "+"; una venta
    sin pagos registrados (solo posible en ventas históricas anteriores a
    esta columna) muestra "No registrado"."""
    if not sale.payments:
        return "No registrado"
    labels: list[str] = []
    for payment in sale.payments:
        label = _PAYMENT_METHOD_LABELS.get(payment.payment_method, payment.payment_method.value)
        if label not in labels:
            labels.append(label)
    return " + ".join(labels)


class SalesHistoryView(QWidget):
    def __init__(self, view_model: SalesHistoryViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._sales: list[SaleDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def reload(self) -> None:
        """Se llama al recuperar el foco de esta pestaña (ver `main.py`),
        para mostrar ventas recién completadas sin salir y volver a entrar
        al módulo."""
        self._view_model.load()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll_area, layout = build_scrollable_page(self)
        outer.addWidget(scroll_area)
        title = make_section_title("Historial de ventas")
        layout.addWidget(title)

        self._build_daily_summary_sections(layout)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._void_button = QPushButton("Anular venta seleccionada")
        self._invoice_button = QPushButton("Facturar venta seleccionada")
        actions.addWidget(self._void_button)
        actions.addWidget(self._invoice_button)
        layout.addLayout(actions)

    def _build_daily_summary_sections(self, layout: QVBoxLayout) -> None:
        """Resumen Diario de Caja: 5 secciones encima del historial —
        Ventas del día, Ventas por cajero, Abonos recibidos hoy, Abonos
        por cajero, y el cierre de caja combinado. Todas se llenan en
        `_on_daily_summary_loaded`, recalculadas cada vez que `load()`
        corre (mismo mecanismo de `reload()` que ya refresca la tabla de
        ventas — sin agregar ninguno nuevo)."""
        sales_box = QGroupBox("Ventas del día", self)
        sales_box_layout = QVBoxLayout(sales_box)
        self._sales_today_kpi = KpiCard("Total vendido", format_currency(Decimal(0)))
        sales_box_layout.addWidget(self._sales_today_kpi)
        layout.addWidget(sales_box)

        sales_by_cashier_box = QGroupBox("Ventas por cajero", self)
        sales_by_cashier_layout = QVBoxLayout(sales_by_cashier_box)
        self._sales_by_cashier_table = self._build_named_total_table(sales_by_cashier_box)
        sales_by_cashier_layout.addWidget(self._sales_by_cashier_table)
        layout.addWidget(sales_by_cashier_box)

        payments_box = QGroupBox("Abonos recibidos hoy", self)
        payments_box_layout = QVBoxLayout(payments_box)
        self._payments_today_table = QTableWidget(0, len(_PAYMENTS_TODAY_COLUMNS), payments_box)
        self._payments_today_table.setHorizontalHeaderLabels(_PAYMENTS_TODAY_COLUMNS)
        self._payments_today_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._payments_today_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._payments_today_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        payments_box_layout.addWidget(self._payments_today_table)
        layout.addWidget(payments_box)

        payments_by_cashier_box = QGroupBox("Abonos por cajero", self)
        payments_by_cashier_layout = QVBoxLayout(payments_by_cashier_box)
        self._payments_by_cashier_table = self._build_named_total_table(payments_by_cashier_box)
        payments_by_cashier_layout.addWidget(self._payments_by_cashier_table)
        layout.addWidget(payments_by_cashier_box)

        closing_box = QGroupBox("Cierre de caja", self)
        closing_layout = QVBoxLayout(closing_box)
        closing_kpi_row = QHBoxLayout()
        self._closing_sales_kpi = KpiCard("Ventas normales", format_currency(Decimal(0)))
        self._closing_payments_kpi = KpiCard("Abonos de clientes", format_currency(Decimal(0)))
        self._closing_total_kpi = KpiCard(
            "Dinero total ingresado", format_currency(Decimal(0)), value_role="success"
        )
        closing_kpi_row.addWidget(self._closing_sales_kpi)
        closing_kpi_row.addWidget(self._closing_payments_kpi)
        closing_kpi_row.addWidget(self._closing_total_kpi)
        closing_layout.addLayout(closing_kpi_row)

        self._closing_by_cashier_table = QTableWidget(0, len(_CLOSING_COLUMNS), closing_box)
        self._closing_by_cashier_table.setHorizontalHeaderLabels(_CLOSING_COLUMNS)
        self._closing_by_cashier_table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Stretch
        )
        self._closing_by_cashier_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self._closing_by_cashier_table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        closing_layout.addWidget(QLabel("Por cajero", closing_box))
        closing_layout.addWidget(self._closing_by_cashier_table)
        layout.addWidget(closing_box)

    def _build_named_total_table(self, parent: QWidget) -> QTableWidget:
        table = QTableWidget(0, len(_NAMED_TOTAL_COLUMNS), parent)
        table.setHorizontalHeaderLabels(_NAMED_TOTAL_COLUMNS)
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        return table

    def _connect_signals(self) -> None:
        self._void_button.clicked.connect(self._on_void_clicked)
        self._invoice_button.clicked.connect(self._on_invoice_clicked)
        self._table.cellDoubleClicked.connect(self._on_row_double_clicked)
        self._view_model.sales_loaded.connect(self._on_sales_loaded)
        self._view_model.daily_summary_loaded.connect(self._on_daily_summary_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_sales_loaded(self, sales: list[SaleDTO]) -> None:
        self._sales = sales
        self._table.setRowCount(len(sales))
        for row, sale in enumerate(sales):
            self._table.setItem(row, 0, QTableWidgetItem(str(sale.id)))
            self._table.setItem(
                row, 1, QTableWidgetItem(format_datetime_local(sale.created_at, "%Y-%m-%d %H:%M"))
            )
            self._table.setItem(row, 2, QTableWidgetItem(_payment_summary(sale)))
            self._table.setItem(row, 3, QTableWidgetItem(format_currency(sale.total)))
            self._table.setItem(row, 4, QTableWidgetItem(sale.customer_name or "Sin nombre"))
            self._table.setItem(row, 5, QTableWidgetItem(sale.customer_document or "Sin documento"))
        fit_table_to_contents(self._table)

    def _on_daily_summary_loaded(self, summary: DailyClosingSummaryDTO) -> None:
        self._sales_today_kpi.set_value(format_currency(summary.sales_total))
        self._fill_named_total_table(self._sales_by_cashier_table, summary.sales_by_cashier)

        self._payments_today_table.setRowCount(len(summary.payment_entries))
        for row, entry in enumerate(summary.payment_entries):
            values = [
                entry.customer_name,
                entry.invoice_number,
                format_currency(entry.amount),
                format_datetime_local(entry.paid_at, "%I:%M %p"),
                entry.cashier_name,
                entry.cash_register_name,
                entry.payment_method_label,
            ]
            for col, value in enumerate(values):
                self._payments_today_table.setItem(row, col, QTableWidgetItem(value))
        fit_table_to_contents(self._payments_today_table)

        self._fill_named_total_table(self._payments_by_cashier_table, summary.payments_by_cashier)

        self._closing_sales_kpi.set_value(format_currency(summary.sales_total))
        self._closing_payments_kpi.set_value(format_currency(summary.payments_total))
        self._closing_total_kpi.set_value(format_currency(summary.total_cash_in))

        self._closing_by_cashier_table.setRowCount(len(summary.by_cashier))
        for row, cashier_row in enumerate(summary.by_cashier):
            values = [
                cashier_row.cashier_name,
                format_currency(cashier_row.sales_total),
                format_currency(cashier_row.payments_total),
                format_currency(cashier_row.total_received),
            ]
            for col, value in enumerate(values):
                self._closing_by_cashier_table.setItem(row, col, QTableWidgetItem(value))
        fit_table_to_contents(self._closing_by_cashier_table)

    def _fill_named_total_table(self, table: QTableWidget, rows: list[NamedTotalDTO]) -> None:
        table.setRowCount(len(rows))
        for row, entry in enumerate(rows):
            table.setItem(row, 0, QTableWidgetItem(entry.name))
            table.setItem(row, 1, QTableWidgetItem(format_currency(entry.total)))
        fit_table_to_contents(table)

    def _on_row_double_clicked(self, row: int, column: int) -> None:
        """Doble clic sobre cualquier venta abre el PDF real de su factura
        (generándola si aún no existe) — nunca solo el registro, ver
        `SalesHistoryViewModel.open_invoice_pdf`."""
        sale = self._sales[row]
        self._view_model.open_invoice_pdf(sale.id)

    def _on_void_clicked(self) -> None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            self._show_error("Selecciona una venta de la tabla.")
            return
        sale = self._sales[selected_rows[0].row()]
        if sale.status is not SaleStatus.COMPLETED:
            self._show_error("Solo se pueden anular ventas completadas.")
            return
        reason, _ = QInputDialog.getText(self, "Anular venta", "Motivo (opcional):")
        self._view_model.void_sale(sale.id, reason)

    def _on_invoice_clicked(self) -> None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            self._show_error("Selecciona una venta de la tabla.")
            return
        sale = self._sales[selected_rows[0].row()]
        self._view_model.generate_invoice(sale.id)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
