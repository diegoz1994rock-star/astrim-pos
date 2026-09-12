"""Registro en memoria de las conexiones WebSocket vivas al servidor de
sincronización — lo que alimenta la tabla "Clientes conectados" del panel.

Vive solo mientras dura cada conexión (a diferencia de `sync_stations`,
que es el catálogo histórico de estaciones conocidas). Escrito desde el
hilo del servidor (uvicorn/asyncio) y leído desde el hilo principal (Qt)
— protegido con un lock."""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import UTC, datetime

from pos.modules.sync.application.dto import SyncConnectionDTO


@dataclass
class _MutableConnection:
    station_name: str
    ip: str
    port: int
    connected_at: datetime
    last_sync_at: datetime | None
    app_version: str | None
    latency_ms: float | None

    def to_dto(self) -> SyncConnectionDTO:
        return SyncConnectionDTO(
            station_name=self.station_name,
            ip=self.ip,
            port=self.port,
            connected_at=self.connected_at,
            last_sync_at=self.last_sync_at,
            app_version=self.app_version,
            latency_ms=self.latency_ms,
        )


class ConnectionRegistry:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._connections: dict[str, _MutableConnection] = {}

    def register(
        self, *, station_name: str, ip: str, port: int, app_version: str | None
    ) -> None:
        with self._lock:
            self._connections[station_name] = _MutableConnection(
                station_name=station_name,
                ip=ip,
                port=port,
                connected_at=datetime.now(UTC),
                last_sync_at=None,
                app_version=app_version,
                latency_ms=None,
            )

    def touch(self, station_name: str) -> None:
        with self._lock:
            connection = self._connections.get(station_name)
            if connection is not None:
                connection.last_sync_at = datetime.now(UTC)

    def update_latency(self, station_name: str, latency_ms: float) -> None:
        with self._lock:
            connection = self._connections.get(station_name)
            if connection is not None:
                connection.latency_ms = latency_ms
                connection.last_sync_at = datetime.now(UTC)

    def unregister(self, station_name: str) -> None:
        with self._lock:
            self._connections.pop(station_name, None)

    def clear(self) -> None:
        with self._lock:
            self._connections.clear()

    def list_connections(self) -> list[SyncConnectionDTO]:
        with self._lock:
            return [connection.to_dto() for connection in self._connections.values()]

    def __len__(self) -> int:
        with self._lock:
            return len(self._connections)
