"""Modelo SQLAlchemy de la bitácora de auditoría.

Tabla append-only: nunca se actualiza ni se borra una fila ya escrita.
Es el consumidor central del bus de eventos de dominio (ver
ARCHITECTURE.md §5 y §8).
"""

from __future__ import annotations

import uuid as uuid_lib
from datetime import datetime

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, utc_now
from pos.core.database.types import UTCDateTime
from pos.modules.audit.domain.enums import AuditAction


class AuditLog(Base):
    """Entrada de auditoría: quién hizo qué, sobre qué entidad, y cuándo.

    `changes_json` guarda un diff antes/después serializado en JSON cuando
    aplica (ej. `UPDATE`); para `LOGIN`/`LOGOUT` puede ser nulo.
    """

    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    uuid: Mapped[str] = mapped_column(
        String(36), unique=True, index=True, default=lambda: str(uuid_lib.uuid4())
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_id: Mapped[int | None] = mapped_column(nullable=True)
    action: Mapped[AuditAction] = mapped_column(
        Enum(AuditAction, native_enum=False), nullable=False
    )
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    changes_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
