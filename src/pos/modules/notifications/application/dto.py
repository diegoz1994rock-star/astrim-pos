"""DTOs del módulo de notificaciones."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class NotificationDTO:
    id: int
    recipient_user_id: int | None
    notification_type: str
    title: str
    message: str
    is_read: bool
    related_entity_type: str | None
    related_entity_id: int | None
    created_at: datetime
