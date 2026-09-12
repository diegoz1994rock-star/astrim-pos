"""Cliente de sincronización: conecta por WebSocket a la estación principal.

Corre su propio bucle asyncio en un hilo daemon (mismo motivo que
`server/runner.py::SyncServer`). Reintenta la conexión indefinidamente con
un retardo fijo si el servidor no está disponible — pensado para redes
locales inestables (ver ARCHITECTURE.md §10, "offline-first").

Mide la latencia real de cada round-trip (`pull`) y la reporta al servidor
en el siguiente `push` — nunca inventa un número: si no hay medición
reciente, no manda el campo."""

from __future__ import annotations

import asyncio
import contextlib
import importlib.metadata
import json
import logging
import threading
import time
from datetime import datetime

import websockets

from pos.modules.sync.application.dto import WebSocketProbeResultDTO
from pos.modules.sync.application.sync_service import SyncService
from pos.modules.sync.server.event_log import SyncEventLog

logger = logging.getLogger(__name__)

_POLL_INTERVAL_SECONDS = 3.0
_RECONNECT_DELAY_SECONDS = 5.0


def _app_version() -> str:
    try:
        return importlib.metadata.version("pos-system")
    except importlib.metadata.PackageNotFoundError:
        return "desconocida"


class SyncClient:
    def __init__(self, sync_service: SyncService, *, event_log: SyncEventLog | None = None) -> None:
        self._sync_service = sync_service
        self.event_log = event_log or SyncEventLog()
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stop_event: asyncio.Event | None = None
        self._sync_now_event: asyncio.Event | None = None
        self._connected = False
        self._last_latency_ms: float | None = None

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def last_latency_ms(self) -> float | None:
        return self._last_latency_ms

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
        self._sync_service.mark_local_station_offline()

    def sync_now(self) -> None:
        """Fuerza un ciclo de sincronización inmediato, sin esperar al
        intervalo — no-op silencioso si no hay conexión activa (nada que
        forzar)."""
        if self._loop is None or not self._connected:
            return
        self._loop.call_soon_threadsafe(self._signal_sync_now)

    def _signal_stop(self) -> None:
        if self._stop_event is not None:
            self._stop_event.set()

    def _signal_sync_now(self) -> None:
        if self._sync_now_event is not None:
            self._sync_now_event.set()

    def _run(self) -> None:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        self._loop = loop
        self._stop_event = asyncio.Event()
        self._sync_now_event = asyncio.Event()
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
            except Exception as exc:
                logger.warning("Conexión de sincronización con %s perdida, reintentando", peer_url)
                self.event_log.log(f"Conexión con {peer_url} perdida ({exc}), reintentando…")
            if self._connected:
                self._connected = False
                self._sync_service.mark_local_station_offline()
            await self._sleep_or_stop(_RECONNECT_DELAY_SECONDS)

    async def _sleep_or_stop(self, seconds: float) -> None:
        """Duerme hasta `seconds`, pero se corta antes si llega una parada
        o un pedido de "Sincronizar ahora" (`sync_now()`)."""
        assert self._stop_event is not None and self._sync_now_event is not None
        stop_task = asyncio.ensure_future(self._stop_event.wait())
        sync_now_task = asyncio.ensure_future(self._sync_now_event.wait())
        try:
            done, pending = await asyncio.wait(
                {stop_task, sync_now_task}, timeout=seconds, return_when=asyncio.FIRST_COMPLETED
            )
            for task in pending:
                task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await task
            if sync_now_task in done:
                self._sync_now_event.clear()
        except asyncio.CancelledError:
            stop_task.cancel()
            sync_now_task.cancel()
            raise

    async def _connect_and_sync(self, peer_url: str) -> None:
        assert self._stop_event is not None
        station_name = self._sync_service.get_local_station_name()
        async with websockets.connect(peer_url, open_timeout=5) as websocket:
            await websocket.send(
                json.dumps(
                    {"type": "hello", "station_name": station_name, "app_version": _app_version()}
                )
            )
            await websocket.recv()
            self._connected = True
            self._sync_service.mark_local_station_online()
            self.event_log.log(f"Conectado al servidor principal en {peer_url}")
            while not self._stop_event.is_set():
                await self._sync_once(websocket)
                await self._sleep_or_stop(_POLL_INTERVAL_SECONDS)

    async def _sync_once(self, websocket: websockets.ClientConnection) -> None:
        await self._pull(websocket)
        await self._push(websocket)

    async def _pull(self, websocket: websockets.ClientConnection) -> None:
        since = self._sync_service.get_last_received_at()
        started_at = time.monotonic()
        await websocket.send(json.dumps({"type": "pull", "since": since.isoformat()}))
        backlog_raw = await websocket.recv()
        self._last_latency_ms = (time.monotonic() - started_at) * 1000
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
        message: dict[str, object] = {"type": "push", "entries": wire_entries}
        if self._last_latency_ms is not None:
            message["latency_ms"] = self._last_latency_ms
        await websocket.send(json.dumps(message))
        await websocket.recv()
        self._sync_service.set_last_pushed_at(max(entry.created_at for entry in outbound))


def probe_websocket(url: str, *, timeout: float = 5.0) -> WebSocketProbeResultDTO:
    """Diagnóstico de un solo uso ("Probar conexión WebSocket"): conecta,
    hace el handshake `hello`/`hello_ack` real y mide el round-trip, sin
    dejar ninguna conexión abierta. Corre su propio bucle asyncio efímero
    — no interfiere con el bucle del `SyncClient` normal, que vive en su
    propio hilo daemon."""
    try:
        return asyncio.run(_probe_websocket_async(url, timeout))
    except Exception as exc:  # noqa: BLE001 - se reporta como resultado, no se propaga
        return WebSocketProbeResultDTO(success=False, detail=f"No se pudo conectar: {exc}")


async def _probe_websocket_async(url: str, timeout: float) -> WebSocketProbeResultDTO:
    started_at = time.monotonic()
    async with websockets.connect(url, open_timeout=timeout) as websocket:
        # "__probe__" debe coincidir con `server/app.py::PROBE_STATION_NAME`
        # — el servidor lo reconoce y NO lo registra como estación real.
        await websocket.send(
            json.dumps(
                {
                    "type": "hello",
                    "station_name": "__probe__",
                    "app_version": _app_version(),
                }
            )
        )
        raw = await asyncio.wait_for(websocket.recv(), timeout=timeout)
        ack = json.loads(raw)
        if ack.get("type") != "hello_ack":
            return WebSocketProbeResultDTO(success=False, detail=f"Respuesta inesperada: {ack!r}")
        latency_ms = (time.monotonic() - started_at) * 1000
        return WebSocketProbeResultDTO(
            success=True, detail="El WebSocket respondió correctamente.", latency_ms=latency_ms
        )
