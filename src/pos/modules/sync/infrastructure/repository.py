"""Acceso a datos de estaciones registradas y del log de eventos de sincronización."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.sync.domain.enums import SyncLogStatus, SyncStationStatus
from pos.modules.sync.infrastructure.models import SyncLog, SyncStation


class SyncRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_station(self, station_id: int) -> SyncStation | None:
        return self._session.get(SyncStation, station_id)

    def get_station_by_name(self, name: str) -> SyncStation | None:
        return self._session.scalar(select(SyncStation).where(SyncStation.name == name))

    def get_local_station(self) -> SyncStation | None:
        return self._session.scalar(select(SyncStation).where(SyncStation.is_local))

    def create_station(
        self, *, name: str, is_primary: bool, is_local: bool = False
    ) -> SyncStation:
        station = SyncStation(
            name=name, is_primary=is_primary, is_local=is_local, status=SyncStationStatus.OFFLINE
        )
        self._session.add(station)
        self._session.flush()
        return station

    def list_stations(self) -> list[SyncStation]:
        return list(self._session.scalars(select(SyncStation).order_by(SyncStation.name)))

    def set_station_status(
        self, station: SyncStation, *, status: SyncStationStatus, seen_at: datetime
    ) -> None:
        station.status = status
        station.last_seen_at = seen_at

    def append_log(
        self,
        *,
        event_type: str,
        entity_type: str,
        entity_uuid: str,
        payload_json: str,
        origin_station_id: int,
        created_at: datetime,
        status: SyncLogStatus,
    ) -> SyncLog:
        """Inserta una entrada de log.

        `status=PENDING` para un evento de origen local (todavía no se sabe
        si ya llegó al otro extremo — no se rastrea *ack* por estación
        remota en esta primera versión, ver `SyncService`); `status=APPLIED`
        para un evento recibido de un par remoto (esta estación ya lo
        procesó/registró).
        """
        applied_at = created_at if status is SyncLogStatus.APPLIED else None
        entry = SyncLog(
            event_type=event_type,
            entity_type=entity_type,
            entity_uuid=entity_uuid,
            payload_json=payload_json,
            origin_station_id=origin_station_id,
            status=status,
            created_at=created_at,
            applied_at=applied_at,
        )
        self._session.add(entry)
        self._session.flush()
        return entry

    def has_entry_with_uuid(self, entity_uuid: str) -> bool:
        return (
            self._session.scalar(select(SyncLog.id).where(SyncLog.entity_uuid == entity_uuid))
            is not None
        )

    def list_local_origin_since(self, *, origin_station_id: int, since: datetime) -> list[SyncLog]:
        return list(
            self._session.scalars(
                select(SyncLog)
                .where(SyncLog.origin_station_id == origin_station_id)
                .where(SyncLog.created_at > since)
                .order_by(SyncLog.created_at)
            )
        )

    def list_since_excluding_origin(
        self, *, since: datetime, excluded_origin_station_id: int | None
    ) -> list[SyncLog]:
        query = select(SyncLog).where(SyncLog.created_at > since)
        if excluded_origin_station_id is not None:
            query = query.where(SyncLog.origin_station_id != excluded_origin_station_id)
        return list(self._session.scalars(query.order_by(SyncLog.created_at)))

    def list_recent(self, limit: int = 50) -> list[SyncLog]:
        return list(
            self._session.scalars(select(SyncLog).order_by(SyncLog.created_at.desc()).limit(limit))
        )

    def count_pending_local_origin(self, *, origin_station_id: int, since: datetime) -> int:
        return len(self.list_local_origin_since(origin_station_id=origin_station_id, since=since))
