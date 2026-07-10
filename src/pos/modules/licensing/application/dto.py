"""DTOs de lectura del módulo de licencias."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from pos.modules.licensing.domain.enums import LicenseStatus, LicenseType, LicenseVerificationResult


@dataclass(frozen=True)
class LicenseDTO:
    id: int
    license_type: LicenseType
    issued_at: datetime
    expires_at: datetime | None
    status: LicenseStatus
    hardware_fingerprint: str


@dataclass(frozen=True)
class LicenseVerificationDTO:
    result: LicenseVerificationResult
    license: LicenseDTO | None
    details: str | None
