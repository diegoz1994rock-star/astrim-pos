"""Registro operacional en memoria de la sesión actual del transporte de
sincronización (arranque, parada, conexiones, errores) — lo que se ve en
la consola de eventos del panel de Sincronización.

Distinto de `sync_log` (el historial de negocio persistido, ver
`application/sync_service.py`): este es un buffer acotado en memoria, se
reinicia con la app. Escrito desde el hilo del servidor, el hilo del
cliente y el hilo principal (Qt) por igual — protegido con un lock."""

from __future__ import annotations

import threading
from collections import deque
from datetime import UTC, datetime

from pos.modules.sync.application.dto import SyncEventLogLineDTO

_MAX_LINES = 500


class SyncEventLog:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lines: deque[SyncEventLogLineDTO] = deque(maxlen=_MAX_LINES)

    def log(self, message: str) -> None:
        line = SyncEventLogLineDTO(occurred_at=datetime.now(UTC), message=message)
        with self._lock:
            self._lines.append(line)

    def list_recent(self) -> list[SyncEventLogLineDTO]:
        with self._lock:
            return list(self._lines)
