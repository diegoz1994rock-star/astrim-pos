"""Modelos SQLAlchemy de sincronización multi-estación: estaciones registradas,
log de eventos propagados y conflictos detectados (ver ARCHITECTURE.md §10)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from pos.core.database.base import Base, TimestampMixin, utc_now
from pos.core.database.types import UTCDateTime
from pos.modules.sync.domain.enums import (
    SyncConflictResolution,
    SyncLogStatus,
    SyncStationStatus,
)


class SyncStation(Base, TimestampMixin):
    """Estación registrada en la red de sincronización."""

    __tablename__ = "sync_stations"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    """Solo una estación de la red debe tener `is_primary=True` a la vez."""

    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    status: Mapped[SyncStationStatus] = mapped_column(
        Enum(SyncStationStatus, native_enum=False),
        default=SyncStationStatus.OFFLINE,
        nullable=False,
    )


class SyncLog(Base):
    """Evento de dominio propagado entre estaciones.

    `entity_uuid` (no el `id` local autoincremental) es la referencia
    estable entre estaciones distintas, según ARCHITECTURE.md §6.
    `payload_json` serializa el evento de dominio completo tal como se
    despachó en el bus de eventos local (ver ARCHITECTURE.md §5).
    """

    __tablename__ = "sync_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False)
    origin_station_id: Mapped[int] = mapped_column(ForeignKey("sync_stations.id"), nullable=False)
    status: Mapped[SyncLogStatus] = mapped_column(
        Enum(SyncLogStatus, native_enum=False), default=SyncLogStatus.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
    applied_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)


class SyncConflict(Base):
    """Conflicto detectado al aplicar un evento de sincronización sobre un
    registro que cambió localmente en simultáneo (ver ARCHITECTURE.md §10)."""

    __tablename__ = "sync_conflicts"

    id: Mapped[int] = mapped_column(primary_key=True)
    sync_log_id: Mapped[int] = mapped_column(ForeignKey("sync_log.id"), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False)
    entity_uuid: Mapped[str] = mapped_column(String(36), nullable=False)
    local_value_json: Mapped[str] = mapped_column(Text, nullable=False)
    remote_value_json: Mapped[str] = mapped_column(Text, nullable=False)
    resolution: Mapped[SyncConflictResolution] = mapped_column(
        Enum(SyncConflictResolution, native_enum=False),
        default=SyncConflictResolution.PENDING,
        nullable=False,
    )
    resolved_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utc_now, nullable=False)
