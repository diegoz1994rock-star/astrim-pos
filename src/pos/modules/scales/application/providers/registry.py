"""Registro de adaptadores de báscula.

Agregar una marca/modelo nuevo: crear su adaptador en un archivo nuevo bajo
`providers/` (mismo contrato que `base.ScaleProvider`) y sumar una entrada
acá — nada más en el sistema (ni Vendedor, ni Ventas, ni el resto de este
módulo) necesita cambiar, mismo patrón que `qr_payments/.../registry.py`."""

from __future__ import annotations

from pos.modules.scales.application.providers.base import ScaleProvider
from pos.modules.scales.application.providers.generic_provider import GenericScaleProvider
from pos.modules.scales.application.providers.simulator_provider import SimulatorScaleProvider

_DEFAULT_KIND = "generic"
SIMULATOR_KIND = "simulator"

_PROVIDER_REGISTRY: dict[str, type[ScaleProvider]] = {
    _DEFAULT_KIND: GenericScaleProvider,
    SIMULATOR_KIND: SimulatorScaleProvider,
}

SCALE_KIND_LABELS: dict[str, str] = {
    "generic": "Genérica (protocolo de texto por puerto serie)",
    SIMULATOR_KIND: "Simulador (sin hardware — modo de pruebas)",
}


def get_scale_adapter(kind: str) -> ScaleProvider:
    provider_class = _PROVIDER_REGISTRY.get(kind, _PROVIDER_REGISTRY[_DEFAULT_KIND])
    return provider_class()
