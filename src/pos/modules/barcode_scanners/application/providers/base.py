"""Adaptador de lector de códigos de barras — el punto de extensión del
módulo. Agregar soporte para una marca específica (Zebra, Honeywell,
Datalogic, Symbol/Motorola, Newland, Sunmi, CipherLab…) consiste en
implementar esta interfaz en un archivo nuevo bajo `providers/` y sumar
una entrada en `registry.py` — el resto del sistema nunca cambia, mismo
patrón ya usado en `scales`/`cash_drawers`/`printers`."""

from __future__ import annotations

from typing import NamedTuple, Protocol

from pos.modules.barcode_scanners.domain.enums import ConnectionType


class ScannerConnectionParams(NamedTuple):
    connection_type: ConnectionType
    port: str | None
    baud_rate: int | None
    data_bits: int
    stop_bits: float
    parity: str
    ip_address: str | None
    ip_port: int | None
    bluetooth_address: str | None


class BarcodeScannerDriver(Protocol):
    def test_connection(self, params: ScannerConnectionParams) -> bool: ...

    def read_code(self, params: ScannerConnectionParams) -> str:
        """Lee un código real desde el dispositivo. Los modos HID
        (keyboard-wedge, USB o Bluetooth, el modo dominante en retail) no
        exponen puerto ni permiten prueba por software — escriben directo
        donde esté el foco — el adaptador correspondiente falla honesto en
        vez de simular una lectura."""
        ...
