"""Estados del pool de códigos de licencia pre-generados (ver
`infrastructure/pool_models.py::LicensePoolEntry`) — distintos de
`LicenseStatus` (ese describe el estado de la licencia YA activada en
esta estación; este describe el ciclo de vida del CÓDIGO en el catálogo
del proveedor, antes y después de repartirlo a un cliente)."""

from __future__ import annotations

import enum


class LicensePoolStatus(enum.Enum):
    """Estado de un código dentro del pool pre-generado."""

    AVAILABLE = "available"
    """Recién generado, nunca activado — estado inicial de todo código."""
    ACTIVATED = "activated"
    """Ya en uso por un cliente (ver `LicenseService.activate`)."""
    EXPIRED = "expired"
    """La licencia local que originó este código venció (reflejo
    best-effort de `LicenseService.verify()`, ver ese módulo)."""
    BLOCKED = "blocked"
    """Bloqueado manualmente (reflejo best-effort de `LicenseService.block`)."""
