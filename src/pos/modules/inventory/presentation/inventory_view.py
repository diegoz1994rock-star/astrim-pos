"""Pantalla de inventario: existencias por producto/bodega + movimientos."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.inventory.application.dto import StockLevelDTO, WarehouseDTO
from pos.modules.inventory.presentation.inventory_view_model import InventoryViewModel
from pos.modules.inventory.presentation.movement_dialog import MovementDialog, MovementMode
from pos.modules.products.application.dto import ProductDTO

_COLUMNS = ["SKU", "Producto", "Bodega", "Cantidad", "Mínimo"]
_ALERT_COLOR = QColor("#F9D8D8")


class InventoryView(QWidget):
    def __init__(self, view_model: InventoryViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._products: list[ProductDTO] = []
        self._warehouses: list[WarehouseDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        title = QLabel("Inventario")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        toolbar.addWidget(title)
        toolbar.addStretch()
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

        actions = QHBoxLayout()
        self._entry_button = QPushButton("Entrada")
        self._exit_button = QPushButton("Salida")
        self._adjustment_button = QPushButton("Ajuste")
        self._transfer_button = QPushButton("Transferencia")
        for button in (
            self._entry_button,
            self._exit_button,
            self._adjustment_button,
            self._transfer_button,
        ):
            actions.addWidget(button)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._entry_button.clicked.connect(lambda: self._open_dialog(MovementMode.ENTRY))
        self._exit_button.clicked.connect(lambda: self._open_dialog(MovementMode.EXIT))
        self._adjustment_button.clicked.connect(lambda: self._open_dialog(MovementMode.ADJUSTMENT))
        self._transfer_button.clicked.connect(lambda: self._open_dialog(MovementMode.TRANSFER))
        self._view_model.stock_loaded.connect(self._on_stock_loaded)
        self._view_model.products_loaded.connect(self._on_products_loaded)
        self._view_model.warehouses_loaded.connect(self._on_warehouses_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_products_loaded(self, products: list[ProductDTO]) -> None:
        self._products = products

    def _on_warehouses_loaded(self, warehouses: list[WarehouseDTO]) -> None:
        self._warehouses = warehouses

    def _on_stock_loaded(self, stock_levels: list[StockLevelDTO]) -> None:
        self._table.setRowCount(len(stock_levels))
        for row, stock in enumerate(stock_levels):
            values = [
                stock.product_sku,
                stock.product_name,
                stock.warehouse_name,
                str(stock.quantity),
                str(stock.min_quantity),
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(value)
                if stock.is_below_minimum:
                    item.setBackground(_ALERT_COLOR)
                self._table.setItem(row, col, item)

    def _open_dialog(self, mode: MovementMode) -> None:
        if not self._products or not self._warehouses:
            self._show_error("Debe existir al menos un producto y una bodega.")
            return
        dialog = MovementDialog(mode, self._products, self._warehouses, self)
        if dialog.exec() != MovementDialog.DialogCode.Accepted:
            return
        values = dialog.values()
        product_id = cast(int, values["product_id"])
        warehouse_id = cast(int, values["warehouse_id"])
        quantity = cast(Decimal, values["quantity"])
        reason = cast(str, values["reason"])

        if mode is MovementMode.ENTRY:
            self._view_model.register_entry(product_id, warehouse_id, quantity, reason)
        elif mode is MovementMode.EXIT:
            self._view_model.register_exit(product_id, warehouse_id, quantity, reason)
        elif mode is MovementMode.ADJUSTMENT:
            self._view_model.register_adjustment(
                product_id, warehouse_id, quantity, cast(bool, values["increase"]), reason
            )
        else:
            self._view_model.transfer(
                product_id,
                warehouse_id,
                cast(int, values["destination_warehouse_id"]),
                quantity,
            )

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Listo", message)
