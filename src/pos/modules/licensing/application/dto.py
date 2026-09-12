"""DTOs de lectura del módulo de licencias."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos.modules.licensing.domain.enums import (
    DeviceStatus,
    LicenseHistoryAction,
    LicenseStatus,
    LicenseType,
    LicenseVerificationResult,
)


@dataclass(frozen=True)
class LicenseDTO:
    id: int
    license_type: LicenseType
    issued_at: datetime
    expires_at: datetime | None
    status: LicenseStatus
    hardware_fingerprint: str
    company_name: str | None = None
    company_nit: str | None = None
    allowed_users: int | None = None
    allowed_branches: int | None = None
    allowed_registers: int | None = None
    max_devices: int = 1


@dataclass(frozen=True)
class LicenseVerificationDTO:
    result: LicenseVerificationResult
    license: LicenseDTO | None
    details: str | None


@dataclass(frozen=True)
class AuthorizedDeviceDTO:
    id: int
    hardware_fingerprint: str
    device_name: str | None
    ip_address: str | None
    first_seen_at: datetime
    last_seen_at: datetime
    status: DeviceStatus
    is_current_device: bool


@dataclass(frozen=True)
class LicenseHistoryEntryDTO:
    id: int
    occurred_at: datetime
    device_name: str | None
    ip_address: str | None
    status_at_time: LicenseStatus
    action: LicenseHistoryAction
    details: str | None
    company_name: str | None = None
    company_nit: str | None = None
    license_key: str | None = None
    license_type: LicenseType | None = None


@dataclass(frozen=True)
class LicenseSyncSnapshotDTO:
    """Todo lo que necesitará la futura app Android para mostrar/consultar
    una licencia, reunido en una sola llamada (`LicenseService.
    get_sync_snapshot`) — para que sincronizar no exija cruzar varias
    tablas ni cambiar el esquema otra vez cuando llegue el momento."""

    company_name: str | None
    company_nit: str | None
    license_key: str
    license_type: LicenseType
    status: LicenseStatus
    activated_at: datetime
    expires_at: datetime | None
    days_remaining: int | None
    hardware_fingerprint: str
    history: list[LicenseHistoryEntryDTO]


@dataclass(frozen=True)
class LicenseUsageDTO:
    users_used: int
    users_allowed: int | None
    branches_used: int
    branches_allowed: int | None
    registers_used: int
    registers_allowed: int | None
    devices_used: int
    devices_allowed: int
    days_remaining: int | None
    period_total_days: int | None
    period_elapsed_pct: float | None
    """`None` para licencias sin vencimiento (`PERMANENT`) — la UI oculta
    la barra de progreso en ese caso en vez de mostrar 0%."""
