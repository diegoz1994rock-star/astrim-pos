"""Enumeraciones de dominio del módulo de Lectores de códigos de barras
(hardware físico de lectura). `ConnectionType`/`ConnectionStatus` duplicadas
deliberadamente — ver docstring en `pos.modules.scales.domain.enums`."""

from __future__ import annotations

import enum


class ConnectionType(enum.Enum):
    USB_HID = "usb_hid"
    USB_SERIAL = "usb_serial"
    BLUETOOTH_HID = "bluetooth_hid"
    BLUETOOTH_SERIAL = "bluetooth_serial"
    RS232 = "rs232"
    TCP_IP = "tcp_ip"
    WIFI = "wifi"


class ConnectionStatus(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class BarcodeSymbology(enum.Enum):
    EAN13 = "ean13"
    EAN8 = "ean8"
    UPC_A = "upc_a"
    UPC_E = "upc_e"
    CODE39 = "code39"
    CODE93 = "code93"
    CODE128 = "code128"
    CODABAR = "codabar"
    ITF = "itf"
    MSI = "msi"
    GS1_128 = "gs1_128"
    DATAMATRIX = "datamatrix"
    PDF417 = "pdf417"
    QR = "qr"
    AZTEC = "aztec"
    UNKNOWN = "unknown"


class CaseConversion(enum.Enum):
    NONE = "none"
    UPPER = "upper"
    LOWER = "lower"


class ScanResult(enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class BarcodeScannerEventType(enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TEST_CONNECTION_OK = "test_connection_ok"
    TEST_CONNECTION_FAILED = "test_connection_failed"
    READ_SUCCESS = "read_success"
    READ_FAILED = "read_failed"


class BarcodeReadSource(enum.Enum):
    """Origen de una lectura centralizada (`BarcodeReadService.resolve_scan`)
    — no confundir con `BarcodeScannerEventType`, que pertenece al inventario
    de dispositivos por-lector."""

    SALE = "sale"
    PRODUCT_FORM = "product_form"
    TEST_PANEL = "test_panel"
