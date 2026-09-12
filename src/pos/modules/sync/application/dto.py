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
    local_ip: str
    websocket_url: str
    uptime_seconds: float | None
    last_error: str | None
    sent_count: int
    received_count: int
    failed_count: int
    connections_count: int
    auto_start_enabled: bool


@dataclass(frozen=True)
class SyncConnectionDTO:
    """Una conexión WebSocket viva (no un registro histórico — vive solo
    mientras dura la conexión, ver `server/connection_registry.py`)."""

    station_name: str
    ip: str
    port: int
    connected_at: datetime
    last_sync_at: datetime | None
    app_version: str | None
    latency_ms: float | None


@dataclass(frozen=True)
class SyncEventLogLineDTO:
    """Una línea del registro operacional en memoria de la sesión actual
    (arranque/parada/conexión/error) — distinto de `SyncLogEntryDTO`, que
    es el historial de negocio persistido en `sync_log`."""

    occurred_at: datetime
    message: str


@dataclass(frozen=True)
class DiagnosticStepDTO:
    label: str
    passed: bool
    detail: str | None = None


@dataclass(frozen=True)
class ServerProbeResultDTO:
    """Resultado de "Probar servidor": cada paso corrido en orden, se
    detiene en el primer paso que falla."""

    success: bool
    steps: tuple[DiagnosticStepDTO, ...]


@dataclass(frozen=True)
class WebSocketProbeResultDTO:
    """Resultado de "Probar conexión WebSocket": handshake real contra una
    URL, con el round-trip medido si tuvo éxito."""

    success: bool
    detail: str
    latency_ms: float | None = None
