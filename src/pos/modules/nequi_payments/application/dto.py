"""DTOs de configuración de cobro por Nequi."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NequiPaymentConfigDTO:
    id: int
    number: str
    is_active: bool
    is_default: bool
