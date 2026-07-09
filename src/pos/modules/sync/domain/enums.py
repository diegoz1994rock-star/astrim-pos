"""Enumeraciones de dominio del módulo de sincronización."""

from __future__ import annotations

import enum


class SyncStationStatus(enum.Enum):
    """Estado de conectividad de una estación registrada."""

    ONLINE = "online"
    OFFLINE = "offline"


class SyncLogStatus(enum.Enum):
    """Estado de aplicación de un evento de sincronización propagado."""

    PENDING = "pending"
    APPLIED = "applied"
    FAILED = "failed"


class SyncConflictResolution(enum.Enum):
    """Resolución de un conflicto detectado durante la sincronización
    (ver ARCHITECTURE.md §10, last-write-wins con registro para revisión)."""

    PENDING = "pending"
    LOCAL_WINS = "local_wins"
    REMOTE_WINS = "remote_wins"
    MANUAL = "manual"
