"""Pantalla de historial de ventas y anulación."""

from __future__ import annotations

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

from pos.modules.sales.application.dto import SaleDTO
from pos.modules.sales.domain.enums import SaleStatus
from pos.modules.sales.presentation.sales_history_view_model import SalesHistoryViewModel

_COLUMNS = ["#", "Fecha", "Estado", "Total"]


class SalesHistoryView(QWidget):
    def __init__(self, view_model: SalesHistoryViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._sales: list[SaleDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        title = QLabel("Historial de ventas")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        layout.addWidget(title)

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

    def _connect_signals(self) -> None:
        self._void_button.clicked.connect(self._on_void_clicked)
        self._invoice_button.clicked.connect(self._on_invoice_clicked)
        self._view_model.sales_loaded.connect(self._on_sales_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_sales_loaded(self, sales: list[SaleDTO]) -> None:
        self._sales = sales
        self._table.setRowCount(len(sales))
        for row, sale in enumerate(sales):
            self._table.setItem(row, 0, QTableWidgetItem(str(sale.id)))
            self._table.setItem(row, 1, QTableWidgetItem(f"{sale.created_at:%Y-%m-%d %H:%M}"))
            self._table.setItem(row, 2, QTableWidgetItem(sale.status.value))
            self._table.setItem(row, 3, QTableWidgetItem(f"{sale.total:.2f}"))

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
        QMessageBox.information(self, "Listo", message)
