"""Detalle de un pedido/venta en Despacho — abierto con doble clic sobre
una tarjeta de `KitchenView`. Solo muestra los productos del pedido
seleccionado y permite marcarlo como entregado de una sola vez (no hay
avance ítem por ítem en esta pantalla, ver `KitchenService.list_queue`
para el detalle granular que se conserva sin exponer en la UI nueva)."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from pos.modules.restaurant.application.dto import DispatchOrderCardDTO
from pos.modules.restaurant.domain.enums import OrderOrigin, OrderStatus

_ORIGIN_LABELS = {
    OrderOrigin.VENDEDOR: "Vendedor",
    OrderOrigin.VENTAS: "Ventas",
}
_DISPATCH_STATUS_LABELS = {
    OrderStatus.PENDING: "Pendiente",
    OrderStatus.PREPARING: "Pendiente",
    OrderStatus.READY: "Pendiente",
    OrderStatus.DELIVERED: "Entregado",
    OrderStatus.CANCELLED: "Anulado",
}


def _info_row(label: str, value: str) -> QHBoxLayout:
    row = QHBoxLayout()
    label_widget = QLabel(label)
    label_widget.setProperty("role", "secondary")
    value_widget = QLabel(value)
    value_widget.setProperty("emphasis", True)
    row.addWidget(label_widget)
    row.addStretch()
    row.addWidget(value_widget)
    return row


class DispatchOrderDetailDialog(QDialog):
    def __init__(self, card: DispatchOrderCardDTO, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._card = card
        self._delivered = False
        self.setWindowTitle(f"Pedido #{card.order_id:06d}")
        self.setMinimumWidth(420)
        self._build_ui()

    def _build_ui(self) -> None:
        card = self._card
        layout = QVBoxLayout(self)
        layout.setSpacing(10)

        name_label = QLabel(card.customer_name)
        name_label.setProperty("role", "title")
        layout.addWidget(name_label)

        layout.addLayout(_info_row("Documento", card.customer_document or "Sin documento"))
        layout.addLayout(_info_row("Pedido", f"#{card.order_id:06d}"))
        layout.addLayout(_info_row("Caja", card.caja_name or "Sin caja asignada"))
        layout.addLayout(_info_row("Origen", _ORIGIN_LABELS[card.origin]))

        payment_row = _info_row("Estado del pago", "PAGADO" if card.is_paid else "NO PAGADO")
        payment_row.itemAt(2).widget().setProperty("role", "success" if card.is_paid else "danger")
        layout.addLayout(payment_row)

        layout.addLayout(
            _info_row("Estado del despacho", _DISPATCH_STATUS_LABELS[card.dispatch_status])
        )

        products_label = QLabel("Productos")
        products_label.setProperty("role", "secondary")
        layout.addWidget(products_label)

        table = QTableWidget(len(card.items), 2, self)
        table.setHorizontalHeaderLabels(["Producto", "Cantidad"])
        table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        table.verticalHeader().setVisible(False)
        for row, item in enumerate(card.items):
            table.setItem(row, 0, QTableWidgetItem(item.product_name))
            table.setItem(row, 1, QTableWidgetItem(str(item.quantity)))
        table.setFixedHeight(min(220, 36 * (len(card.items) + 1)))
        layout.addWidget(table)

        layout.addLayout(_info_row("Total de artículos", str(card.total_units)))

        notes = [item.notes for item in card.items if item.notes]
        observations_label = QLabel("Observaciones")
        observations_label.setProperty("role", "secondary")
        layout.addWidget(observations_label)
        layout.addWidget(QLabel(" · ".join(notes) if notes else "Sin observaciones"))

        self._deliver_button = QPushButton("Marcar como entregado")
        self._deliver_button.setMinimumHeight(44)
        self._deliver_button.setEnabled(card.dispatch_status is not OrderStatus.DELIVERED)
        self._deliver_button.clicked.connect(self._on_deliver_clicked)
        layout.addWidget(self._deliver_button)

    def _on_deliver_clicked(self) -> None:
        self._delivered = True
        self.accept()

    def was_marked_delivered(self) -> bool:
        return self._delivered
