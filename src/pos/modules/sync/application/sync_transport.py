"""Arranca/detiene el transporte de red (servidor o cliente WebSocket)
según el modo de sincronización configurado.

Único punto de verdad para esa decisión, usado tanto al arrancar la app
(`main.py`, para que una estación configurada como servidor/cliente quede
activa sin que nadie tenga que abrir el panel de Sincronización) como desde
el panel mismo cuando el usuario cambia de modo en caliente.
"""

from __future__ import annotations

from pos.modules.sync.application.sync_service import SyncService
from pos.modules.sync.domain.enums import SyncMode
from pos.modules.sync.infrastructure.ws_client import SyncClient
from pos.modules.sync.server.runner import SyncServer


class SyncTransport:
    def __init__(self, sync_service: SyncService) -> None:
        self.sync_service = sync_service
        self.server = SyncServer(sync_service)
        self.client = SyncClient(sync_service)

    def apply_persisted_mode(self) -> None:
        self.apply_mode(self.sync_service.get_mode())

    def apply_mode(self, mode: SyncMode) -> None:
        self.server.stop()
        self.client.stop()
        if mode is SyncMode.PRIMARY:
            self.server.start()
        elif mode is SyncMode.CLIENT:
            self.client.start()

    def shutdown(self) -> None:
        self.server.stop()
        self.client.stop()
