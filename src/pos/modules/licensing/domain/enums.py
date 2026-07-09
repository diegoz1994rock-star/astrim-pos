"""Enumeraciones de dominio del módulo de licencias."""

from __future__ import annotations

import enum


class LicenseType(enum.Enum):
    """Tipo de licencia comercial (PROJECT_SPEC.md, "LICENCIAS")."""

    TRIAL = "trial"
    MONTHLY = "monthly"
    ANNUAL = "annual"
    PERMANENT = "permanent"


class LicenseStatus(enum.Enum):
    """Estado actual de una licencia."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"


class LicenseVerificationResult(enum.Enum):
    """Resultado de una verificación de licencia (ver ARCHITECTURE.md §9)."""

    VALID = "valid"
    INVALID_SIGNATURE = "invalid_signature"
    EXPIRED = "expired"
    CLOCK_TAMPERING_DETECTED = "clock_tampering_detected"
    HARDWARE_MISMATCH = "hardware_mismatch"
