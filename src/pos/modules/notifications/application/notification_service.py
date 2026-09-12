"""Caso de uso de notificaciones internas: crear, listar sin leer, contar
y marcar como leídas — sobre la tabla `notifications` ya existente."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.core.exceptions import NotFoundError
from pos.modules.notifications.application.dto import NotificationDTO
from pos.modules.notifications.infrastructure.models import Notification
from pos.modules.notifications.infrastructure.repository import NotificationRepository


def _to_dto(notification: Notification) -> NotificationDTO:
    return NotificationDTO(
        id=notification.id,
        recipient_user_id=notification.recipient_user_id,
        notification_type=notification.notification_type,
        title=notification.title,
        message=notification.message,
        is_read=notification.is_read,
        related_entity_type=notification.related_entity_type,
        related_entity_id=notification.related_entity_id,
        created_at=notification.created_at,
    )


class NotificationService:
    def create(
        self,
        *,
        notification_type: str,
        title: str,
        message: str,
        recipient_user_id: int | None = None,
        related_entity_type: str | None = None,
        related_entity_id: int | None = None,
    ) -> NotificationDTO:
        with session_scope() as session:
            notification = NotificationRepository(session).create(
                notification_type=notification_type,
                title=title,
                message=message,
                recipient_user_id=recipient_user_id,
                related_entity_type=related_entity_type,
                related_entity_id=related_entity_id,
            )
            return _to_dto(notification)

    def list_unread(self) -> list[NotificationDTO]:
        with session_scope() as session:
            return [_to_dto(n) for n in NotificationRepository(session).list_unread()]

    def count_unread(self) -> int:
        with session_scope() as session:
            return NotificationRepository(session).count_unread()

    def mark_as_read(self, notification_id: int) -> None:
        with session_scope() as session:
            repo = NotificationRepository(session)
            notification = repo.get(notification_id)
            if notification is None:
                raise NotFoundError(f"No existe la notificación con id={notification_id}.")
            repo.mark_as_read(notification)

    def mark_as_read_for_entity(self, related_entity_type: str, related_entity_id: int) -> None:
        with session_scope() as session:
            NotificationRepository(session).mark_as_read_for_entity(
                related_entity_type, related_entity_id
            )
