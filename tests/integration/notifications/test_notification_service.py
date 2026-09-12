"""Pruebas de integración de NotificationService contra SQLite real."""

from __future__ import annotations

import pytest

from pos.core.exceptions import NotFoundError
from pos.modules.notifications.application.notification_service import NotificationService


def test_create_and_list_unread(sqlite_engine: None) -> None:
    service = NotificationService()

    service.create(
        notification_type="order_created",
        title="Nuevo pedido recibido",
        message="Pedido #1",
        related_entity_type="order",
        related_entity_id=1,
    )

    unread = service.list_unread()
    assert len(unread) == 1
    assert unread[0].title == "Nuevo pedido recibido"
    assert unread[0].is_read is False
    assert service.count_unread() == 1


def test_mark_as_read_removes_from_unread(sqlite_engine: None) -> None:
    service = NotificationService()
    notification = service.create(
        notification_type="order_created", title="Nuevo pedido", message="Pedido #2"
    )

    service.mark_as_read(notification.id)

    assert service.count_unread() == 0
    assert service.list_unread() == []


def test_mark_as_read_unknown_notification_raises_not_found(sqlite_engine: None) -> None:
    service = NotificationService()

    with pytest.raises(NotFoundError):
        service.mark_as_read(99999)


def test_mark_as_read_for_entity_marks_matching_notifications(sqlite_engine: None) -> None:
    service = NotificationService()
    service.create(
        notification_type="order_created",
        title="Nuevo pedido",
        message="Pedido #5",
        related_entity_type="order",
        related_entity_id=5,
    )
    service.create(
        notification_type="order_created",
        title="Nuevo pedido",
        message="Pedido #6",
        related_entity_type="order",
        related_entity_id=6,
    )

    service.mark_as_read_for_entity("order", 5)

    unread = service.list_unread()
    assert len(unread) == 1
    assert unread[0].related_entity_id == 6
