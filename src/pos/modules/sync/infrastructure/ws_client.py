"""Cliente de sincronización: conecta por WebSocket a la estación principal.

Corre su propio bucle asyncio en un hilo daemon (mismo motivo que
`server/runner.py::SyncServer`). Reintenta la conexión indefinidamente con
un retardo fijo si el servidor no está disponible — pensado para redes
locales inestables (ver ARCHITECTURE.md §10, "offline-first").
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import threading
from datetime import datetime

import websockets

from pos.modules.sync.application.sync_service import SyncService

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 3.0
_RECONNECT_DELAY_SECONDS = 5.0


class SyncClient:
    def __init__(self, sync_service: SyncService) -> None:
        self._sync_service = sync_service
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(target=self._run, daemon=True, name="sync-client")
        self._thread.start()

    def stop(self) -> None:
        if self._thread is None or self._loop is None:
            return
        loop = self._loop
        loop.call_soon_threadsafe(self._signal_stop)
        self._thread.join(timeout=_POLL_INTERVAL_SECONDS + 5)
        self._thread = None
        self._loop = None
        self._connected = False

    def _signal_stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._stop_event = asyncio.Event()
        try:
            loop.run_until_complete(self._main_loop())
        finally:
            loop.close()

    async def _main_loop(self) -> None:
        assert self._stop_event is not None
        while not self._stop_event.is_set():
            peer_url = self._sync_service.get_peer_url()
            if not peer_url:
                await self._sleep_or_stop(_RECONNECT_DELAY_SECONDS)
                continue
            try:
                await self._connect_and_sync(peer_url)
            except Exception:
                logger.warning("Conexión de sincronización con %s perdida, reintentando", peer_url)
            self._connected = False
            await self._sleep_or_stop(_RECONNECT_DELAY_SECONDS)

    async def _sleep_or_stop(self, seconds: float) -> None:
        assert self._stop_event is not None
        with contextlib.suppress(TimeoutError):
            await asyncio.wait_for(self._stop_event.wait(), timeout=seconds)

    async def _connect_and_sync(self, peer_url: str) -> None:
        assert self._stop_event is not None
        station_name = self._sync_service.get_local_station_name()
        async with websockets.connect(peer_url, open_timeout=5) as websocket:
            await websocket.send(json.dumps({"type": "hello", "station_name": station_name}))
            await websocket.recv()
            self._connected = True
            while not self._stop_event.is_set():
                await self._sync_once(websocket)
                await self._sleep_or_stop(_POLL_INTERVAL_SECONDS)

    async def _sync_once(self, websocket: websockets.ClientConnection) -> None:
        await self._pull(websocket)
        await self._push(websocket)

    async def _pull(self, websocket: websockets.ClientConnection) -> None:
        since = self._sync_service.get_last_received_at()
        await websocket.send(json.dumps({"type": "pull", "since": since.isoformat()}))
        backlog_raw = await websocket.recv()
        backlog = json.loads(backlog_raw)
        newest_received = since
        for wire_entry in backlog.get("entries", []):
            created_at = datetime.fromisoformat(wire_entry["created_at"])
            self._sync_service.record_remote_event(
                event_type=wire_entry["event_type"],
                entity_type=wire_entry["entity_type"],
                entity_uuid=wire_entry["entity_uuid"],
                payload_json=wire_entry["payload_json"],
                origin_station_name=wire_entry["origin_station_name"],
                created_at=created_at,
            )
            newest_received = max(newest_received, created_at)
        if newest_received > since:
            self._sync_service.set_last_received_at(newest_received)

    async def _push(self, websocket: websockets.ClientConnection) -> None:
        last_pushed = self._sync_service.get_last_pushed_at()
        outbound = self._sync_service.list_local_origin_since(last_pushed)
        if not outbound:
            return
        wire_entries = [
            {
                "event_type": entry.event_type,
                "entity_type": entry.entity_type,
                "entity_uuid": entry.entity_uuid,
                "payload_json": entry.payload_json,
                "origin_station_name": entry.origin_station_name,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in outbound
        ]
        await websocket.send(json.dumps({"type": "push", "entries": wire_entries}))
        await websocket.recv()
        self._sync_service.set_last_pushed_at(max(entry.created_at for entry in outbound))
