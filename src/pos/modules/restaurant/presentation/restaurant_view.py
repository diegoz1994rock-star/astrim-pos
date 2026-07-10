"""Panel de Restaurante: mesas, apertura/cierre y envío de pedidos a cocina."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.products.application.dto import ProductDTO
from pos.modules.restaurant.application.dto import DiningTableDTO, OrderDTO, TableSessionDTO
from pos.modules.restaurant.domain.enums import TableStatus
from pos.modules.restaurant.presentation.restaurant_view_model import RestaurantViewModel

_TABLE_COLUMNS = ["Mesa", "Capacidad", "Zona", "Estado"]
_ORDER_COLUMNS = ["Producto", "Cantidad", "Notas", "Estado"]
_TABLE_STATUS_LABELS = {
    TableStatus.FREE: "Libre",
    TableStatus.OCCUPIED: "Ocupada",
    TableStatus.RESERVED: "Reservada",
}


class _NewTableDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Nueva mesa")
        form = QFormLayout(self)
        self.name_edit = QLineEdit(self)
        self.capacity_spin = QSpinBox(self)
        self.capacity_spin.setRange(1, 50)
        self.capacity_spin.setValue(4)
        self.zone_edit = QLineEdit(self)
        form.addRow("Nombre:", self.name_edit)
        form.addRow("Capacidad:", self.capacity_spin)
        form.addRow("Zona:", self.zone_edit)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)


class RestaurantView(QWidget):
    def __init__(self, view_model: RestaurantViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._tables: list[DiningTableDTO] = []
        self._products: list[ProductDTO] = []
        self._pending_items: list[tuple[int, int, str | None]] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.load()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        title = QLabel("Restaurante")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._new_table_button = QPushButton("Nueva mesa")
        self._open_table_button = QPushButton("Abrir mesa seleccionada")
        self._close_table_button = QPushButton("Cerrar mesa activa")
        toolbar.addWidget(self._new_table_button)
        toolbar.addWidget(self._open_table_button)
        toolbar.addWidget(self._close_table_button)
        layout.addLayout(toolbar)

        self._tables_table = QTableWidget(0, len(_TABLE_COLUMNS), self)
        self._tables_table.setHorizontalHeaderLabels(_TABLE_COLUMNS)
        self._tables_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._tables_table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._tables_table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._tables_table.setMaximumHeight(180)
        layout.addWidget(self._tables_table)

        self._active_label = QLabel("Ninguna mesa abierta.")
        layout.addWidget(self._active_label)

        add_row = QHBoxLayout()
        self._product_combo = QComboBox(self)
        self._quantity_spin = QSpinBox(self)
        self._quantity_spin.setRange(1, 99)
        self._notes_edit = QLineEdit(self)
        self._notes_edit.setPlaceholderText("Notas (opcional)")
        self._add_to_order_button = QPushButton("Agregar al pedido")
        add_row.addWidget(self._product_combo, stretch=2)
        add_row.addWidget(self._quantity_spin)
        add_row.addWidget(self._notes_edit, stretch=1)
        add_row.addWidget(self._add_to_order_button)
        layout.addLayout(add_row)

        self._send_order_button = QPushButton("Enviar pedido a cocina")
        layout.addWidget(self._send_order_button)

        layout.addWidget(QLabel("Pedidos de la mesa abierta:"))
        self._orders_table = QTableWidget(0, len(_ORDER_COLUMNS), self)
        self._orders_table.setHorizontalHeaderLabels(_ORDER_COLUMNS)
        self._orders_table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        layout.addWidget(self._orders_table)

    def _connect_signals(self) -> None:
        self._new_table_button.clicked.connect(self._on_new_table_clicked)
        self._open_table_button.clicked.connect(self._on_open_table_clicked)
        self._close_table_button.clicked.connect(self._view_model.close_active_table)
        self._add_to_order_button.clicked.connect(self._on_add_to_order_clicked)
        self._send_order_button.clicked.connect(self._on_send_order_clicked)

        self._view_model.tables_loaded.connect(self._on_tables_loaded)
        self._view_model.products_loaded.connect(self._on_products_loaded)
        self._view_model.session_opened.connect(self._on_session_opened)
        self._view_model.orders_loaded.connect(self._on_orders_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._view_model.operation_succeeded.connect(self._show_info)

    def _on_new_table_clicked(self) -> None:
        dialog = _NewTableDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._view_model.create_table(
            dialog.name_edit.text(), dialog.capacity_spin.value(), dialog.zone_edit.text()
        )

    def _on_open_table_clicked(self) -> None:
        rows = self._tables_table.selectionModel().selectedRows()
        if not rows:
            self._show_error("Selecciona una mesa.")
            return
        table = self._tables[rows[0].row()]
        self._view_model.open_table(table.id)

    def _on_session_opened(self, table_session: TableSessionDTO) -> None:
        table = next((t for t in self._tables if t.id == table_session.table_id), None)
        label = table.name if table is not None else str(table_session.table_id)
        self._active_label.setText(f"Mesa abierta: {label} (sesión #{table_session.id})")
        self._pending_items = []

    def _on_add_to_order_clicked(self) -> None:
        product_id = self._product_combo.currentData()
        if product_id is None:
            self._show_error("Selecciona un producto.")
            return
        self._pending_items.append(
            (product_id, self._quantity_spin.value(), self._notes_edit.text() or None)
        )
        self._notes_edit.clear()
        self._show_info(f"{self._quantity_spin.value()} línea(s) en el pedido por enviar.")

    def _on_send_order_clicked(self) -> None:
        if not self._pending_items:
            self._show_error("Agrega al menos un producto al pedido.")
            return
        self._view_model.send_order(self._pending_items)
        self._pending_items = []

    def _on_tables_loaded(self, tables: list[DiningTableDTO]) -> None:
        self._tables = tables
        self._tables_table.setRowCount(len(tables))
        for row, table in enumerate(tables):
            self._tables_table.setItem(row, 0, QTableWidgetItem(table.name))
            self._tables_table.setItem(row, 1, QTableWidgetItem(str(table.capacity)))
            self._tables_table.setItem(row, 2, QTableWidgetItem(table.zone or ""))
            self._tables_table.setItem(row, 3, QTableWidgetItem(_TABLE_STATUS_LABELS[table.status]))

    def _on_products_loaded(self, products: list[ProductDTO]) -> None:
        self._products = products
        self._product_combo.clear()
        for product in products:
            self._product_combo.addItem(f"{product.sku} — {product.name}", userData=product.id)

    def _on_orders_loaded(self, orders: list[OrderDTO]) -> None:
        rows = [(order, item) for order in orders for item in order.items]
        self._orders_table.setRowCount(len(rows))
        for row, (_order, item) in enumerate(rows):
            self._orders_table.setItem(row, 0, QTableWidgetItem(item.product_name))
            self._orders_table.setItem(row, 1, QTableWidgetItem(str(item.quantity)))
            self._orders_table.setItem(row, 2, QTableWidgetItem(item.notes or ""))
            self._orders_table.setItem(row, 3, QTableWidgetItem(item.status.value))

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        QMessageBox.information(self, "Restaurante", message)
