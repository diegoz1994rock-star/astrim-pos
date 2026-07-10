"""Modelo SQLAlchemy de notificaciones internas."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, utc_now
from pos.core.database.types import UTCDateTime


class Notification(Base):
    """Notificación interna dirigida a un usuario o difundida a todos.

    `related_entity_type` + `related_entity_id` permiten enlazar la
    notificación a su origen (ej. `"order_item"` + id, `"license"` + id)
    sin declarar una FK dura hacia un módulo específico, ya que el origen
    puede ser cualquiera de varios módulos (ver ARCHITECTURE.md §12b).
    """

    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(primary_key=True)
    recipient_user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    """Nulo = notificación difundida a todos los usuarios conectados."""

    notification_type: Mapped[str] = mapped_column(String(60), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    message: Mapped[str] = mapped_column(String(500), nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    related_entity_type: Mapped[str | None] = mapped_column(String(80), nullable=True)
    related_entity_id: Mapped[int | None] = mapped_column(nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
