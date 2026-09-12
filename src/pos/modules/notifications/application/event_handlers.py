"""Manejadores de eventos de otros módulos consumidos por Notificaciones.

Notificaciones reacciona a que Restaurante (pantalla Vendedor) cree un
pedido nuevo, sin que ninguno de los dos módulos importe al otro más allá
de este archivo, que vive en `notifications` y solo conoce el *tipo* del
evento de `restaurant` (un dataclass inmutable, no su infraestructura).
"""

from __future__ import annotations

from pos.modules.notifications.application.notification_service import NotificationService
from pos.modules.restaurant.domain.events import OrderCreatedEvent


class NotificationEventHandlers:
    """Agrupa los manejadores de eventos de otros módulos que le interesan
    a Notificaciones, para registrarlos todos juntos desde `main.py`."""

    def __init__(self, notification_service: NotificationService) -> None:
        self._notification_service = notification_service

    def on_order_created(self, event: OrderCreatedEvent) -> None:
        # `recipient_user_id=None` = difundida a todos los usuarios
        # conectados (Caja y Despacho la ven por igual) — ver docstring de
        # `Notification.recipient_user_id`.
        self._notification_service.create(
            notification_type="order_created",
            title="Nuevo pedido recibido",
            message=f"Pedido #{event.order_id}",
            related_entity_type="order",
            related_entity_id=event.order_id,
        )
