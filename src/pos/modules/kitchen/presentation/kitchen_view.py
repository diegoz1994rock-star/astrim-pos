"""Panel de Cocina: cola de ítems pendientes/en preparación con avance de estado."""

from __future__ import annotations

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

from pos.modules.kitchen.presentation.kitchen_view_model import KitchenViewModel
from pos.modules.restaurant.application.dto import KitchenQueueItemDTO
from pos.modules.restaurant.domain.enums import OrderItemStatus

_COLUMNS = ["Producto", "Cantidad", "Notas", "Mesa", "Tipo", "Estado"]
_STATUS_LABELS = {
    OrderItemStatus.PENDING: "Pendiente",
    OrderItemStatus.PREPARING: "Preparando",
    OrderItemStatus.READY: "Listo",
    OrderItemStatus.DELIVERED: "Entregado",
}


class KitchenView(QWidget):
    def __init__(self, view_model: KitchenViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._queue: list[KitchenQueueItemDTO] = []
        self._build_ui()
        self._connect_signals()
        self._view_model.start()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        toolbar = QHBoxLayout()
        title = QLabel("Cocina")
        title_font = title.font()
        title_font.setBold(True)
        title_font.setPointSize(14)
        title.setFont(title_font)
        toolbar.addWidget(title)
        toolbar.addStretch()
        self._advance_button = QPushButton("Avanzar estado del ítem seleccionado")
        self._refresh_button = QPushButton("Actualizar ahora")
        toolbar.addWidget(self._advance_button)
        toolbar.addWidget(self._refresh_button)
        layout.addLayout(toolbar)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(_COLUMNS)
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        layout.addWidget(self._table)

    def _connect_signals(self) -> None:
        self._advance_button.clicked.connect(self._on_advance_clicked)
        self._refresh_button.clicked.connect(self._view_model.load)
        self._view_model.queue_loaded.connect(self._on_queue_loaded)
        self._view_model.error_occurred.connect(self._show_error)

    def _on_advance_clicked(self) -> None:
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            self._show_error("Selecciona un ítem de la cola.")
            return
        item = self._queue[rows[0].row()]
        self._view_model.advance_item(item.order_item_id)

    def _on_queue_loaded(self, queue: list[KitchenQueueItemDTO]) -> None:
        self._queue = queue
        self._table.setRowCount(len(queue))
        for row, item in enumerate(queue):
            self._table.setItem(row, 0, QTableWidgetItem(item.product_name))
            self._table.setItem(row, 1, QTableWidgetItem(str(item.quantity)))
            self._table.setItem(row, 2, QTableWidgetItem(item.notes or ""))
            self._table.setItem(row, 3, QTableWidgetItem(item.table_name or "—"))
            self._table.setItem(row, 4, QTableWidgetItem(item.order_type.value))
            self._table.setItem(row, 5, QTableWidgetItem(_STATUS_LABELS[item.status]))

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)
