"""Panel "Despacho": pedidos pendientes por despachar, organizados por
CLIENTE (una tarjeta por pedido/venta), no por producto — genérico para
cualquier tipo de negocio (restaurante, ferretería, farmacia, tienda,
supermercado, papelería, boutique, cafetería, veterinaria, etc.), no solo
cocina de restaurante. El detalle de productos de cada pedido se ve al
hacer doble clic sobre su tarjeta (`DispatchOrderDetailDialog`)."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from pos.modules.kitchen.presentation.dispatch_order_detail_dialog import (
    DispatchOrderDetailDialog,
)
from pos.modules.kitchen.presentation.kitchen_view_model import KitchenViewModel
from pos.modules.restaurant.application.dto import DispatchOrderCardDTO
from pos.modules.restaurant.domain.enums import OrderOrigin, OrderStatus
from pos.shared_ui.theme.spacing import SPACING_LG, SPACING_MD
from pos.shared_ui.widgets.scrollable_page import build_scrollable_page
from pos.shared_ui.widgets.section_title import make_section_title
from pos.shared_ui.widgets.toast import show_toast

_ORIGIN_LABELS = {
    OrderOrigin.VENDEDOR: "Vendedor",
    OrderOrigin.VENTAS: "Ventas",
}
_DISPATCH_STATUS_LABELS = {
    OrderStatus.PENDING: "Pendiente",
    OrderStatus.PREPARING: "En preparación",
    OrderStatus.READY: "En preparación",
    OrderStatus.DELIVERED: "Entregado",
    OrderStatus.CANCELLED: "Anulado",
    OrderStatus.ARCHIVED: "Archivado",
}
"""`PREPARING`/`READY` comparten etiqueta ("En preparación") — `READY` no
lo produce ningún flujo actual (ver `RestaurantService.advance_dispatch_status`),
se deja mapeado por completitud. `ARCHIVED` nunca debería mostrarse — un
pedido archivado ya no aparece en la cola (ver
`RestaurantRepository.list_dispatch_queue`), la etiqueta es solo defensiva."""

_STATUS_ROLES = {
    OrderStatus.PENDING: "warning",
    OrderStatus.PREPARING: "info",
    OrderStatus.READY: "info",
    OrderStatus.DELIVERED: "success",
    OrderStatus.CANCELLED: "danger",
    OrderStatus.ARCHIVED: "secondary",
}
"""Color del badge de estado — uno distinto por paso del flujo (Pendiente/
En preparación/Entregado) para que el cambio se note de un vistazo, tal
como pide el flujo de "Siguiente proceso"."""

_FILTERS = [
    "Todos",
    "Pendientes",
    "En preparación",
    "Entregados",
    "Pagados",
    "No pagados",
    "Pedidos del Vendedor",
    "Pedidos de Ventas",
]
_DEFAULT_FILTER = "Todos"
"""Debe ser "Todos", no "Pendientes": si el filtro por defecto mostrara
solo pendientes, la propia tarjeta "desaparecería" de la vista apenas el
cajero avanza su estado con "Siguiente proceso" (dejaría de cumplir ese
filtro) — exactamente el comportamiento que NO se quiere. Con "Todos" por
defecto, una tarjeta permanece visible durante Pendiente → En preparación
→ Entregado, y solo desaparece cuando de verdad se archiva (tercer clic),
sin importar el filtro activo: `list_dispatch_queue()` ya excluye
`ARCHIVED` a nivel de consulta, no de este filtro visual."""


def _matches_filter(card: DispatchOrderCardDTO, active_filter: str) -> bool:
    if active_filter == "Todos":
        return True
    if active_filter == "Pendientes":
        return card.dispatch_status is OrderStatus.PENDING
    if active_filter == "En preparación":
        return card.dispatch_status in (OrderStatus.PREPARING, OrderStatus.READY)
    if active_filter == "Entregados":
        return card.dispatch_status is OrderStatus.DELIVERED
    if active_filter == "Pagados":
        return card.is_paid
    if active_filter == "No pagados":
        return not card.is_paid
    if active_filter == "Pedidos del Vendedor":
        return card.origin is OrderOrigin.VENDEDOR
    if active_filter == "Pedidos de Ventas":
        return card.origin is OrderOrigin.VENTAS
    return True


def _matches_search(card: DispatchOrderCardDTO, query: str) -> bool:
    if not query:
        return True
    haystack = " ".join(
        filter(
            None,
            [
                card.customer_name,
                card.customer_document,
                f"{card.order_id:06d}",
                card.caja_name,
                card.created_by_user_name,
                card.dispatched_by_user_name,
            ],
        )
    ).lower()
    return query.lower() in haystack


class _OrderCard(QFrame):
    """Fila amplia con toda la información importante de un pedido/cliente
    visible sin necesidad de abrirlo — el detalle (productos) se ve con
    doble clic. Un clic simple la selecciona (borde resaltado), para que
    "Siguiente proceso" sepa sobre qué pedido actuar."""

    doubleClicked = Signal(int)
    """Emite `order_id`."""
    clicked = Signal(int)
    """Emite `order_id` — selecciona el pedido, no abre el detalle."""

    def __init__(self, card: DispatchOrderCardDTO, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.card = card
        self.setObjectName("surface")
        self.setProperty("selected", False)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._build_ui()

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", selected)
        self.style().unpolish(self)
        self.style().polish(self)

    def _build_ui(self) -> None:
        card = self.card
        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(18)

        # Izquierda: identidad del pedido/cliente — sin cambios.
        identity = QVBoxLayout()
        identity.setSpacing(2)
        order_label = QLabel(f"Pedido #{card.order_id:06d}  ·  {card.caja_name or 'Sin caja asignada'}")
        order_label.setProperty("role", "secondary")
        identity.addWidget(order_label)
        name_label = QLabel(card.customer_name)
        name_label.setProperty("emphasis", True)
        identity.addWidget(name_label)
        document_label = QLabel(f"Documento: {card.customer_document or 'Sin documento'}")
        document_label.setProperty("role", "secondary")
        identity.addWidget(document_label)
        layout.addLayout(identity, stretch=1)

        # Centro: estado del pedido, grande y coloreado — se actualiza con
        # cada clic en "Siguiente proceso" (PENDIENTE/EN PREPARACIÓN/
        # ENTREGADO — nunca ARCHIVED, ya excluido antes de llegar acá).
        status_label = QLabel(_DISPATCH_STATUS_LABELS[card.dispatch_status].upper())
        status_label.setProperty("sizeVariant", "status")
        """No se llama "size": `QWidget` ya tiene una property Qt real con
        ese nombre (el tamaño del widget) — `setProperty("size", ...)` no
        la sobrescribe (falla silenciosamente por tipo incompatible) y
        `property("size")` sigue devolviendo el `QSize` real, nunca
        "status"; el selector QSS tampoco matchearía nunca."""
        status_label.setProperty("role", _STATUS_ROLES.get(card.dispatch_status, "warning"))
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setWordWrap(True)
        layout.addWidget(status_label, stretch=1)

        # Derecha: pago + cantidades + origen — misma información de antes,
        # ahora agrupada en una sola columna (el estado ya no vive acá).
        right = QVBoxLayout()
        right.setSpacing(2)
        payment_label = QLabel("PAGADO" if card.is_paid else "NO PAGADO")
        payment_label.setProperty("emphasis", True)
        payment_label.setProperty("role", "success" if card.is_paid else "danger")
        right.addWidget(payment_label, alignment=Qt.AlignmentFlag.AlignRight)
        right.addWidget(
            QLabel(f"{card.item_count} productos"), alignment=Qt.AlignmentFlag.AlignRight
        )
        right.addWidget(
            QLabel(f"{card.total_units} unidades"), alignment=Qt.AlignmentFlag.AlignRight
        )
        origin_title = QLabel("Origen")
        origin_title.setProperty("role", "secondary")
        right.addWidget(origin_title, alignment=Qt.AlignmentFlag.AlignRight)
        right.addWidget(
            QLabel(_ORIGIN_LABELS[card.origin]), alignment=Qt.AlignmentFlag.AlignRight
        )
        layout.addLayout(right)

    def mousePressEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.clicked.emit(self.card.order_id)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self.doubleClicked.emit(self.card.order_id)
        super().mouseDoubleClickEvent(event)


class KitchenView(QWidget):
    def __init__(self, view_model: KitchenViewModel, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._view_model = view_model
        self._queue: list[DispatchOrderCardDTO] = []
        self._active_filter = _DEFAULT_FILTER
        self._filter_buttons: dict[str, QPushButton] = {}
        self._selected_order_id: int | None = None
        self._build_ui()
        self._connect_signals()
        self._view_model.start()

    def _build_ui(self) -> None:
        outer_layout = QVBoxLayout(self)
        outer_layout.setContentsMargins(0, 0, 0, 0)

        scroll_area, layout = build_scrollable_page(self)
        outer_layout.addWidget(scroll_area)
        layout.setSpacing(SPACING_MD)
        layout.setContentsMargins(SPACING_LG, SPACING_MD, SPACING_LG, SPACING_MD)

        header_row = QHBoxLayout()
        header_row.addWidget(make_section_title("Despacho"))
        header_row.addStretch()
        self._pending_count_label = QLabel("Pedidos pendientes (0)")
        self._pending_count_label.setProperty("emphasis", True)
        header_row.addWidget(self._pending_count_label)
        layout.addLayout(header_row)

        filters_row = QHBoxLayout()
        filters_row.setSpacing(8)
        for label in _FILTERS:
            button = QPushButton(label)
            button.setCheckable(True)
            button.setChecked(label == _DEFAULT_FILTER)
            filters_row.addWidget(button)
            self._filter_buttons[label] = button
        filters_row.addStretch()
        layout.addLayout(filters_row)

        self._search_edit = QLineEdit(self)
        self._search_edit.setPlaceholderText(
            "Buscar por nombre, documento, número de pedido, caja o usuario…"
        )
        layout.addWidget(self._search_edit)

        self._next_process_button = QPushButton("Siguiente proceso")
        self._next_process_button.setMinimumHeight(40)
        layout.addWidget(self._next_process_button)

        self._cards_layout = QVBoxLayout()
        self._cards_layout.setSpacing(10)
        layout.addLayout(self._cards_layout)
        self._empty_label = QLabel("No hay pedidos que coincidan con el filtro/búsqueda actual.")
        self._empty_label.setProperty("role", "secondary")
        self._empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self._empty_label)

        layout.addStretch()

    def _connect_signals(self) -> None:
        self._next_process_button.clicked.connect(self._on_next_process_clicked)
        self._view_model.queue_loaded.connect(self._on_queue_loaded)
        self._view_model.error_occurred.connect(self._show_error)
        self._search_edit.textChanged.connect(self._render_cards)
        for label, button in self._filter_buttons.items():
            button.clicked.connect(lambda _checked, label=label: self._on_filter_clicked(label))

    def _on_filter_clicked(self, label: str) -> None:
        self._active_filter = label
        for filter_label, button in self._filter_buttons.items():
            button.setChecked(filter_label == label)
        self._render_cards()

    def _on_next_process_clicked(self) -> None:
        if self._selected_order_id is None:
            self._show_info("Seleccione un pedido para continuar.")
            return
        self._view_model.advance_dispatch_status(self._selected_order_id)

    def _on_card_clicked(self, order_id: int) -> None:
        self._selected_order_id = order_id
        self._render_cards()

    def _on_queue_loaded(self, queue: list[DispatchOrderCardDTO]) -> None:
        self._queue = queue
        if self._selected_order_id is not None and not any(
            c.order_id == self._selected_order_id for c in queue
        ):
            # El pedido seleccionado ya no está en la cola (p.ej. se
            # archivó al presionar "Siguiente proceso" sobre uno
            # entregado) — no queda nada que seguir seleccionando.
            self._selected_order_id = None
        pending = [c for c in queue if c.dispatch_status is OrderStatus.PENDING]
        self._pending_count_label.setText(f"Pedidos pendientes ({len(pending)})")
        self._render_cards()

    def _render_cards(self) -> None:
        while self._cards_layout.count():
            item = self._cards_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        query = self._search_edit.text().strip()
        visible = [
            card
            for card in self._queue
            if _matches_filter(card, self._active_filter) and _matches_search(card, query)
        ]
        self._empty_label.setVisible(not visible)
        for card in visible:
            widget = _OrderCard(card)
            widget.set_selected(card.order_id == self._selected_order_id)
            widget.clicked.connect(self._on_card_clicked)
            widget.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            widget.doubleClicked.connect(self._open_detail)
            self._cards_layout.addWidget(widget)

    def _open_detail(self, order_id: int) -> None:
        card = next((c for c in self._queue if c.order_id == order_id), None)
        if card is None:
            return
        dialog = DispatchOrderDetailDialog(card, self)
        dialog.exec()
        if dialog.was_marked_delivered():
            self._view_model.mark_delivered(order_id)

    def _show_error(self, message: str) -> None:
        QMessageBox.warning(self, "Error", message)

    def _show_info(self, message: str) -> None:
        show_toast(self, message)
