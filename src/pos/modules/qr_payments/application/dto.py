"""DTOs de configuración de cobro por QR estático."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class QrPaymentConfigDTO:
    id: int
    name: str
    image_path: str | None
    is_active: bool
    is_default: bool
