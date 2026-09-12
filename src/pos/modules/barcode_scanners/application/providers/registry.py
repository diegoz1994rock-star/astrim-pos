"""Registro de adaptadores de lector de códigos de barras.

Selección en dos niveles: primero se busca un adaptador específico de
marca para `(kind, connection_type)` (vacío hoy — es el punto de
extensión para Zebra/Honeywell/Datalogic/Symbol-Motorola/Newland/Sunmi/
CipherLab a futuro); si no hay uno, se cae al adaptador genérico según el
tipo de conexión. Agregar una marca nueva es crear su adaptador bajo
`providers/` (mismo contrato que `base.BarcodeScannerDriver`) y sumar una
entrada en `_BRAND_REGISTRY` — nada más del sistema cambia."""

from __future__ import annotations

from pos.modules.barcode_scanners.application.providers.base import BarcodeScannerDriver
from pos.modules.barcode_scanners.application.providers.hid_wedge_driver import HidWedgeDriver
from pos.modules.barcode_scanners.application.providers.network_driver import NetworkSocketDriver
from pos.modules.barcode_scanners.application.providers.serial_driver import SerialPortDriver
from pos.modules.barcode_scanners.domain.enums import ConnectionType

_DEFAULT_KIND = "generic"

_BRAND_REGISTRY: dict[tuple[str, ConnectionType], type[BarcodeScannerDriver]] = {}

_DEFAULT_DRIVERS: dict[ConnectionType, type[BarcodeScannerDriver]] = {
    ConnectionType.USB_HID: HidWedgeDriver,
    ConnectionType.BLUETOOTH_HID: HidWedgeDriver,
    ConnectionType.USB_SERIAL: SerialPortDriver,
    ConnectionType.BLUETOOTH_SERIAL: SerialPortDriver,
    ConnectionType.RS232: SerialPortDriver,
    ConnectionType.TCP_IP: NetworkSocketDriver,
    ConnectionType.WIFI: NetworkSocketDriver,
}

CONNECTION_TYPE_LABELS: dict[ConnectionType, str] = {
    ConnectionType.USB_HID: "USB HID (teclado emulado)",
    ConnectionType.USB_SERIAL: "USB Serial (COM virtual)",
    ConnectionType.BLUETOOTH_HID: "Bluetooth HID (teclado emulado)",
    ConnectionType.BLUETOOTH_SERIAL: "Bluetooth Serial (SPP)",
    ConnectionType.RS232: "RS232",
    ConnectionType.TCP_IP: "TCP/IP",
    ConnectionType.WIFI: "Wi-Fi",
}

SCANNER_KIND_LABELS: dict[str, str] = {
    "generic": "Genérico (protocolo estándar por tipo de conexión)",
}


def get_scanner_driver(
    connection_type: ConnectionType, kind: str = _DEFAULT_KIND
) -> BarcodeScannerDriver:
    driver_class = _BRAND_REGISTRY.get((kind, connection_type))
    if driver_class is None:
        driver_class = _DEFAULT_DRIVERS[connection_type]
    return driver_class()
