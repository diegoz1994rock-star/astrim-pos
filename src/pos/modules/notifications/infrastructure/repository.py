"""Acceso a datos de notificaciones internas."""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos.modules.notifications.infrastructure.models import Notification


class NotificationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        *,
        notification_type: str,
        title: str,
        message: str,
        recipient_user_id: int | None = None,
        related_entity_type: str | None = None,
        related_entity_id: int | None = None,
    ) -> Notification:
        notification = Notification(
            recipient_user_id=recipient_user_id,
            notification_type=notification_type,
            title=title,
            message=message,
            related_entity_type=related_entity_type,
            related_entity_id=related_entity_id,
        )
        self._session.add(notification)
        self._session.flush()
        return notification

    def get(self, notification_id: int) -> Notification | None:
        return self._session.get(Notification, notification_id)

    def list_unread(self) -> list[Notification]:
        return list(
            self._session.scalars(
                select(Notification)
                .where(Notification.is_read.is_(False))
                .order_by(Notification.created_at.desc())
            )
        )

    def count_unread(self) -> int:
        return (
            self._session.scalar(
                select(func.count())
                .select_from(Notification)
                .where(Notification.is_read.is_(False))
            )
            or 0
        )

    def mark_as_read(self, notification: Notification) -> None:
        notification.is_read = True

    def mark_as_read_for_entity(self, related_entity_type: str, related_entity_id: int) -> None:
        for notification in self._session.scalars(
            select(Notification).where(
                Notification.related_entity_type == related_entity_type,
                Notification.related_entity_id == related_entity_id,
                Notification.is_read.is_(False),
            )
        ):
            notification.is_read = True
