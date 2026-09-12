"""Confirma que Notificaciones reacciona a `OrderCreatedEvent` de
Restaurante creando una notificación difundida (sin acoplar los módulos
más allá de este manejador)."""

from __future__ import annotations

from pos.modules.notifications.application.event_handlers import NotificationEventHandlers
from pos.modules.notifications.application.notification_service import NotificationService
from pos.modules.restaurant.domain.events import OrderCreatedEvent


def test_on_order_created_creates_broadcast_notification(sqlite_engine: None) -> None:
    notification_service = NotificationService()
    handlers = NotificationEventHandlers(notification_service)

    handlers.on_order_created(OrderCreatedEvent(order_id=125, created_by_user_id=7))

    unread = notification_service.list_unread()
    assert len(unread) == 1
    assert unread[0].recipient_user_id is None
    assert unread[0].related_entity_type == "order"
    assert unread[0].related_entity_id == 125
    assert "125" in unread[0].message
