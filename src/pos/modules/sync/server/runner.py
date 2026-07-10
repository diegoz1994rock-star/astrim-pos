"""Arranca/detiene el servidor de sincronización embebido en un hilo aparte.

La app de escritorio (PySide6) tiene su propio bucle de eventos (Qt) en el
hilo principal; `uvicorn.Server.run()` es bloqueante y necesita su propio
bucle asyncio, así que corre en un hilo daemon dedicado — mismo patrón que
`BackupScheduler` (APScheduler) para el módulo de Backups.
"""

from __future__ import annotations

import threading

import uvicorn

from pos.modules.sync.application.sync_service import SyncService
from pos.modules.sync.server.app import create_sync_app


class SyncServer:
    def __init__(self, sync_service: SyncService, *, host: str = "0.0.0.0") -> None:
        self._sync_service = sync_service
        self._host = host
        self._thread: threading.Thread | None = None
        self._server: uvicorn.Server | None = None

    @property
    def is_running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self) -> None:
        """No-op si ya está corriendo (llamar dos veces es seguro)."""
        if self.is_running:
            return
        app = create_sync_app(self._sync_service)
        config = uvicorn.Config(
            app,
            host=self._host,
            port=self._sync_service.get_server_port(),
            log_level="warning",
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True, name="sync-server")
        self._thread.start()

    def stop(self) -> None:
        if self._server is None or self._thread is None:
            return
        self._server.should_exit = True
        self._thread.join(timeout=5)
        self._thread = None
        self._server = None
