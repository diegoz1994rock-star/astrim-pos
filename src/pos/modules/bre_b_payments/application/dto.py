"""DTOs de configuración de cobro por Bre-B."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BreBPaymentConfigDTO:
    id: int
    key: str
    is_active: bool
    is_default: bool
