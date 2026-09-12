"""Enumeraciones de dominio del módulo de Impresoras (Administración →
Dispositivos → Impresoras). `ConnectionType`/`ConnectionStatus` duplicadas
deliberadamente — ver docstring en `pos.modules.scales.domain.enums`."""

from __future__ import annotations

import enum


class PrinterType(enum.Enum):
    """Tipo físico de impresora — puramente descriptivo/informativo, no
    determina el driver (eso lo hace `PrintMethod`). Una misma marca puede
    vender modelos térmicos o láser; el tipo no implica el método."""

    THERMAL_58 = "thermal_58"
    THERMAL_80 = "thermal_80"
    RECEIPT = "receipt"
    POS = "pos"
    LASER = "laser"
    INKJET = "inkjet"
    MATRIX = "matrix"
    A4 = "a4"
    LABEL = "label"
    OTHER = "other"


class PrintMethod(enum.Enum):
    """Cómo se envía de verdad el trabajo de impresión — el eje central de
    la arquitectura universal: nunca depende de una marca."""

    SYSTEM_DRIVER = "system_driver"
    """Vía el driver ya instalado en el sistema operativo (`QPrinter`) —
    funciona con cualquier impresora que Windows/macOS/Linux reconozca:
    láser, inyección, matricial, A4, etiquetas, térmicas con driver,
    compartidas en red."""
    RAW_ESCPOS = "raw_escpos"
    """Comando ESC/POS crudo por puerto (serie/USB-serie/Bluetooth-serie/
    Ethernet/Wi-Fi), sin depender de un driver de SO — para térmicas que
    solo exponen un puerto de datos."""


class ConnectionType(enum.Enum):
    USB = "usb"
    SERIAL = "serial"
    BLUETOOTH = "bluetooth"
    ETHERNET = "ethernet"
    WIFI = "wifi"
    SHARED_NETWORK = "shared_network"
    """Impresora compartida en red desde otro equipo — el SO ya la expone
    como una impresora instalada más (mismo camino que `SYSTEM_DRIVER`)."""


class ConnectionStatus(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class Orientation(enum.Enum):
    PORTRAIT = "portrait"
    LANDSCAPE = "landscape"


class PrinterEventType(enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TEST_CONNECTION_OK = "test_connection_ok"
    TEST_CONNECTION_FAILED = "test_connection_failed"
    TEST_PAGE_PRINTED = "test_page_printed"
    TEST_PAGE_FAILED = "test_page_failed"
    PRINT_SUCCESS = "print_success"
    PRINT_FAILED = "print_failed"


class PrintDocumentType(enum.Enum):
    INVOICE = "invoice"
    DEBT_RECEIPT = "debt_receipt"
    TEST_PAGE = "test_page"
