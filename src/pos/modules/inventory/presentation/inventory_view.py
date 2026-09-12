"""Pantalla de inventario: existencias por producto (una fila por producto,
con la suma de todas las bodegas) + movimientos."""

from __future__ import annotations

from decimal import Decimal
from typing import cast

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QHeaderView,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableView,
    QVBoxLayout,
    QWidget,
)

from pos.modules.inventory.application.dto import StockMovementDTO, StockSummaryDTO, WarehouseDTO
from pos.modules.inventory.presentation.inventory_table_model import COLUMNS, InventoryTableModel
from pos.modules.inventory.presentation.inventory_view_model import InventoryViewModel
from pos.modules.inventory.presentation.movement_dialog import MovementDialog, MovementMode
from pos.modules.inventory.presentation.movements_history_dialog import MovementsHistoryDialog
from pos.modules.inventory.presentation.stock_detail_dialog import StockDetailDialog
from pos.modules.products.application.dto import ProductDTO
from pos.shared_ui.theme.spacing import SPACING_LG, SPACING_MD
from pos.shared_ui.widgets.search_bar import SearchBar
from pos.shared_ui.widgets.search_filter_proxy_model import SearchFilterProxyModel
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.table_utils import ImageCellDelegate
from pos.shared_ui.widgets.toast import show_toast

_ROW_HEIGHT = 92
_IMAGE_COLUMN_WIDTH = 110
"""Ancho fijo de la columna "Imagen" — nunca se recalcula automáticamente
(ver `setSectionResizeMode(..., Fixed)` en `_build_ui`), inmune al modo
`Stretch` que aplica al resto del encabezado. Mismo valor que en
`products_view.py::_IMAGE_COLUMN_WIDTH` a propósito — ambas pantallas
deben verse idénticas."""


class InventoryView(QWidget):
    def __init__(self, view_model: InventoryViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._products: list[ProductDTO] = []
        self._warehouses: list[WarehouseDTO] = []
        self._summaries: list[StockSummaryDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def reload(self) -> None:
        """Se llama al recuperar el foco de esta pestaña (ver `main.py`)."""
        self._view_model.load()

    def _build_ui(self) -> None:
        """Header (título/buscador) y footer (Entrada/Salida/Transferencia)
        quedan fijos — solo `self._table` tiene scroll propio (ver
        `QSizePolicy.Expanding` + stretch más abajo) — a diferencia del
        resto de pantallas de la app, que usan `build_scrollable_page`
        (un único `QScrollArea` de página completa). Con miles de
        productos, esa página única obligaba a desplazar toda la ventana
        para llegar a los botones de abajo; acá el layout reparte la
        pantalla en tres franjas (header/tabla/footer) igual que un
        DataGrid profesional, sin tocar ningún estilo visual."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(SPACING_LG, SPACING_LG, SPACING_LG, SPACING_LG)
        layout.setSpacing(SPACING_MD)
        toolbar = QHBoxLayout()
        title = make_section_title("Inventario")
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._movements_button = QPushButton("Movimientos")
        toolbar.addWidget(self._movements_button)
        layout.addLayout(toolbar)

        self._search_bar = SearchBar(
            "Buscar producto por nombre, código, SKU, código de barras o categoría...", self
        )
        layout.addWidget(self._search_bar)
        QShortcut(QKeySequence.StandardKey.Find, self).activated.connect(self._search_bar.focus)

        self._source_model = InventoryTableModel(self)
        self._proxy_model = SearchFilterProxyModel(self)
        self._proxy_model.setSourceModel(self._source_model)

        self._table = QTableView(self)
        self._table.setModel(self._proxy_model)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        image_column = COLUMNS.index("Imagen")
        self._image_delegate = ImageCellDelegate(cell_size=_IMAGE_COLUMN_WIDTH, parent=self._table)
        self._table.setItemDelegateForColumn(image_column, self._image_delegate)
        self._table.horizontalHeader().setSectionResizeMode(
            image_column, QHeaderView.ResizeMode.Fixed
        )
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.verticalHeader().setDefaultSectionSize(_ROW_HEIGHT)
        self._table.verticalHeader().setVisible(False)
        self._table.doubleClicked.connect(self._on_table_double_clicked)
        self._table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self._table.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        layout.addWidget(self._table, 1)

        actions = QHBoxLayout()
        self._entry_button = QPushButton("Entrada")
        self._exit_button = QPushButton("Salida")
        self._transfer_button = QPushButton("Transferencia")
        for button in (self._entry_button, self._exit_button, self._transfer_button):
            actions.addWidget(button, stretch=1)
        layout.addLayout(actions)

    def _connect_signals(self) -> None:
        self._entry_button.clicked.connect(lambda: self._open_dialog(MovementMode.ENTRY))
        self._exit_button.clicked.connect(lambda: self._open_dialog(MovementMode.EXIT))
        self._transfer_button.clicked.connect(lambda: self._open_dialog(MovementMode.TRANSFER))
        self._movements_button.clicked.connect(self._on_movements_clicked)
        self._search_bar.text_changed.connect(self._on_search_text_changed)
        self._view_model.summary_loaded.connect(self._on_summary_loaded)
        self._view_model.products_loaded.connect(self._on_products_loaded)
        self._view_model.warehouses_loaded.connect(self._on_warehouses_loaded)
        self._view_model.movements_loaded.connect(self._on_movements_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_search_text_changed(self, text: str) -> None:
        self._proxy_model.set_search_text(text)

    def _on_products_loaded(self, products: list[ProductDTO]) -> None:
        self._products = products

    def _on_warehouses_loaded(self, warehouses: list[WarehouseDTO]) -> None:
        self._warehouses = warehouses

    def _on_summary_loaded(self, summaries: list[StockSummaryDTO]) -> None:
        self._summaries = summaries
        self._source_model.set_data(summaries, self._product_by_id)
        self._table.resizeColumnsToContents()
        self._table.setColumnWidth(COLUMNS.index("Imagen"), _IMAGE_COLUMN_WIDTH)

    def _open_stock_detail(self, product_id: int) -> None:
        details = self._view_model.get_stock_detail(product_id)
        dialog = StockDetailDialog(details, parent=self)
        dialog.exec()

    def _on_table_double_clicked(self, index: QModelIndex) -> None:
        source_row = self._proxy_model.mapToSource(index).row()
        self._open_stock_detail(self._source_model.summary_at(source_row).product_id)

    def _selected_summary(self) -> StockSummaryDTO | None:
        selected_rows = self._table.selectionModel().selectedRows()
        if not selected_rows:
            return None
        source_row = self._proxy_model.mapToSource(selected_rows[0]).row()
        return self._source_model.summary_at(source_row)

    def _on_movements_clicked(self) -> None:
        self._view_model.load_movements()

    def _on_movements_loaded(self, movements: list[StockMovementDTO]) -> None:
        dialog = MovementsHistoryDialog(movements, self._view_model.user_name, parent=self)
        dialog.exec()

    def _open_dialog(self, mode: MovementMode) -> None:
        if not self._products:
            self._show_error(
                "No hay productos que controlen inventario. Verifica que el producto "
                "exista en Catálogo, esté activo y tenga marcada la opción "
                "'Controlar inventario'."
            )
            return
        if not self._warehouses:
            self._show_error(
                "No hay bodegas activas. Creá una bodega en la pestaña 'Bodegas' antes "
                "de registrar movimientos."
            )
            return
        selected = self._selected_summary()
        preselected_product = (
            self._product_by_id(selected.product_id) if selected is not None else None
        )
        dialog = MovementDialog(
            mode, self._products, self._warehouses, preselected_product, self
        )
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
            self._view_model.register_adjustment(product_id, warehouse_id, quantity, reason)
        else:
            self._view_model.transfer(
                product_id,
                warehouse_id,
                cast(int, values["destination_warehouse_id"]),
                quantity,
            )

    def _product_by_id(self, product_id: int) -> ProductDTO | None:
        return next((p for p in self._products if p.id == product_id), None)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
