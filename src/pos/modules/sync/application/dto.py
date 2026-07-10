"""DTOs de salida del módulo de sincronización hacia `presentation/`."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos.modules.sync.domain.enums import SyncLogStatus, SyncMode, SyncStationStatus


@dataclass(frozen=True)
class SyncStationDTO:
    id: int
    name: str
    is_primary: bool
    status: SyncStationStatus
    last_seen_at: datetime | None


@dataclass(frozen=True)
class SyncLogEntryDTO:
    id: int
    event_type: str
    entity_type: str
    entity_uuid: str
    payload_json: str
    status: SyncLogStatus
    origin_station_name: str
    created_at: datetime
    applied_at: datetime | None


@dataclass(frozen=True)
class SyncStatusDTO:
    mode: SyncMode
    local_station_name: str
    peer_url: str | None
    server_port: int
    running: bool
    connected: bool
    pending_outbound_count: int
