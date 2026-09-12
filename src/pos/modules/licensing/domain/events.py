"""Eventos de dominio publicados por el módulo de Licencias.

Al ser subclases de `DomainEvent`, quedan capturadas automáticamente por
`event_bus.subscribe_all(sync_service.capture_event)` (cableado una sola
vez en `main.py`) — quedan en `sync_log` sin ningún wiring adicional. Esto
es lo que hace que el módulo esté "listo para sincronizar" con un futuro
servidor central: el evento ya existe y ya se registra, solo falta un
consumidor remoto real que hoy no existe.

`verify()` nunca publica nada acá — corre cada ~45s y saturaría el
outbox; solo las acciones administrativas discretas (activar, renovar,
suspender, etc.) publican eventos."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos.core.events.event import DomainEvent
from pos.modules.licensing.domain.enums import LicenseType


@dataclass(frozen=True, kw_only=True)
class LicenseActivatedEvent(DomainEvent):
    license_id: int
    license_type: LicenseType
    hardware_fingerprint: str


@dataclass(frozen=True, kw_only=True)
class LicenseRenewedEvent(DomainEvent):
    license_id: int
    previous_expires_at: datetime | None
    new_expires_at: datetime | None


@dataclass(frozen=True, kw_only=True)
class LicenseSuspendedEvent(DomainEvent):
    license_id: int
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class LicenseReactivatedEvent(DomainEvent):
    license_id: int


@dataclass(frozen=True, kw_only=True)
class LicenseBlockedEvent(DomainEvent):
    license_id: int
    reason: str | None = None


@dataclass(frozen=True, kw_only=True)
class LicenseDeviceRegisteredEvent(DomainEvent):
    license_id: int
    hardware_fingerprint: str
    device_name: str | None = None


@dataclass(frozen=True, kw_only=True)
class LicenseDeviceRevokedEvent(DomainEvent):
    license_id: int
    hardware_fingerprint: str
