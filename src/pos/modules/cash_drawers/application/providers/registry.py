"""Registro de adaptadores de cajón monedero — mismo patrón que
`scales/.../registry.py`."""

from __future__ import annotations

from pos.modules.cash_drawers.application.providers.base import CashDrawerProvider
from pos.modules.cash_drawers.application.providers.generic_provider import (
    GenericCashDrawerProvider,
)

_DEFAULT_KIND = "generic"

_PROVIDER_REGISTRY: dict[str, type[CashDrawerProvider]] = {
    _DEFAULT_KIND: GenericCashDrawerProvider,
}

DRAWER_KIND_LABELS: dict[str, str] = {
    "generic": "Genérico (comando ESC/POS estándar por puerto/red)",
}


def get_drawer_adapter(kind: str) -> CashDrawerProvider:
    provider_class = _PROVIDER_REGISTRY.get(kind, _PROVIDER_REGISTRY[_DEFAULT_KIND])
    return provider_class()
