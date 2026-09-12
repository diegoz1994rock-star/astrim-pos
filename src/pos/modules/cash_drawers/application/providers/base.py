"""Adaptador de cajón monedero — el punto de extensión del módulo."""

from __future__ import annotations

from typing import NamedTuple, Protocol

_DEFAULT_TIMEOUT_SECONDS = 2


class DrawerConnectionParams(NamedTuple):
    port: str | None
    baud_rate: int | None
    ip_address: str | None
    ip_port: int | None
    pulse_count: int = 1
    pulse_duration_ms: int = 50
    custom_command_hex: str | None = None
    timeout_seconds: int = _DEFAULT_TIMEOUT_SECONDS


class CashDrawerProvider(Protocol):
    def test_connection(self, params: DrawerConnectionParams) -> bool: ...

    def open_drawer(self, params: DrawerConnectionParams) -> bool:
        """Envía el comando de apertura. Éxito significa "se escribió sin
        error de E/S" — no hay confirmación (ACK) de hardware real para un
        pulso de apertura, límite honesto documentado en el adaptador
        genérico."""
        ...
