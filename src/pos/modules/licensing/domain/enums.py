"""Enumeraciones de dominio del módulo de licencias."""

from __future__ import annotations

import enum


class LicenseType(enum.Enum):
    """Tipo de licencia comercial (PROJECT_SPEC.md, "LICENCIAS")."""

    TRIAL = "trial"
    MONTHLY = "monthly"
    SEMIANNUAL = "semiannual"
    """6 meses — usado por el pool de códigos pre-generados (ver
    `infrastructure/pool_models.py`), junto con `TRIAL` (30 días) y
    `ANNUAL` (1 año)."""
    ANNUAL = "annual"
    PERMANENT = "permanent"


class LicenseStatus(enum.Enum):
    """Estado actual de una licencia.

    `SUSPENDED`/`BLOCKED` son exclusivamente manuales (ver
    `LicenseService.suspend`/`block`/`reactivate`) — a diferencia de
    `ACTIVE`/`EXPIRED`, la verificación automática (`verify()`) nunca los
    asigna ni los retira por su cuenta."""

    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"


class LicenseVerificationResult(enum.Enum):
    """Resultado de una verificación de licencia (ver ARCHITECTURE.md §9)."""

    VALID = "valid"
    INVALID_SIGNATURE = "invalid_signature"
    EXPIRED = "expired"
    CLOCK_TAMPERING_DETECTED = "clock_tampering_detected"
    HARDWARE_MISMATCH = "hardware_mismatch"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"


class DeviceStatus(enum.Enum):
    """Estado de un equipo autorizado bajo una licencia (ver
    `infrastructure/models.py::AuthorizedDevice`)."""

    ACTIVE = "active"
    REVOKED = "revoked"


class LicenseHistoryAction(enum.Enum):
    """Acción registrada en `infrastructure/models.py::LicenseHistoryEntry`
    — historial legible por humanos, distinto del `LicenseVerificationLog`
    técnico (ese es de alta frecuencia, no pensado para mostrarse)."""

    ACTIVATED = "activated"
    RENEWED = "renewed"
    SUSPENDED = "suspended"
    REACTIVATED = "reactivated"
    BLOCKED = "blocked"
    UNBLOCKED = "unblocked"
    """Una licencia `BLOCKED` solo se recupera con un código nuevo del
    proveedor (ver `LicenseService.renew`) — cuando esa renovación
    encuentra la licencia bloqueada, se registra como `UNBLOCKED` en vez
    de `RENEWED` para que el historial diga exactamente qué pasó."""
    EXPIRED = "expired"
    """Vencimiento detectado automáticamente por `LicenseService.verify()`
    (transición ACTIVE→EXPIRED) — se registra una sola vez, en el momento
    de la transición, no en cada verificación posterior mientras siga
    vencida."""
    DEVICE_REGISTERED = "device_registered"
    DEVICE_REVOKED = "device_revoked"
