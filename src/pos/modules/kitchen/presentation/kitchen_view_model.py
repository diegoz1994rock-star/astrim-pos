"""View model del panel "Despacho" (preparar/alistar/empacar/entregar
pedidos — genérico para cualquier tipo de negocio).

Se refresca de dos formas: al instante al publicarse `OrderCreatedEvent`
(Vendedor confirmó un pedido nuevo) y, como respaldo, cada 5 segundos —
igual que ya funcionaba antes de agregar el evento, por si alguna
suscripción se perdiera."""

from __future__ import annotations

from PySide6.QtCore import QObject, QTimer, Signal

from pos.core.events.bus import EventBus
from pos.core.exceptions import DomainError
from pos.core.security.session import SessionManager
from pos.modules.kitchen.application.kitchen_service import KitchenService
from pos.modules.restaurant.domain.events import OrderCreatedEvent

_REFRESH_MS = 5000


class KitchenViewModel(QObject):
    queue_loaded = Signal(list)
    error_occurred = Signal(str)

    def __init__(
        self,
        kitchen_service: KitchenService,
        session_manager: SessionManager,
        event_bus: EventBus,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._kitchen_service = kitchen_service
        self._session_manager = session_manager
        self._event_bus = event_bus
        self._timer = QTimer(self)
        self._timer.setInterval(_REFRESH_MS)
        self._timer.timeout.connect(self.load)
        self._event_bus.subscribe(OrderCreatedEvent, self._on_order_created_event)
        self.destroyed.connect(self._unsubscribe)

    def _on_order_created_event(self, event: OrderCreatedEvent) -> None:
        self.load()

    def _unsubscribe(self) -> None:
        self._event_bus.unsubscribe(OrderCreatedEvent, self._on_order_created_event)

    def start(self) -> None:
        self.load()
        self._timer.start()

    def stop(self) -> None:
        self._timer.stop()

    def load(self) -> None:
        self.queue_loaded.emit(self._kitchen_service.list_dispatch_queue())

    def mark_delivered(self, order_id: int) -> None:
        current_user = self._session_manager.current
        try:
            self._kitchen_service.mark_order_delivered(
                order_id,
                delivered_by_user_id=current_user.user_id if current_user is not None else None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()

    def advance_dispatch_status(self, order_id: int) -> None:
        """Botón "Siguiente proceso": Pendiente → En preparación →
        Entregado → desaparece de la cola, ver
        `KitchenService.advance_dispatch_status`."""
        current_user = self._session_manager.current
        try:
            self._kitchen_service.advance_dispatch_status(
                order_id,
                changed_by_user_id=current_user.user_id if current_user is not None else None,
            )
        except DomainError as error:
            self.error_occurred.emit(str(error))
        else:
            self.load()
