"""Enumeraciones de dominio del módulo de Cajón monedero (Gaveta de
efectivo). `ConnectionType`/`ConnectionStatus` duplicadas deliberadamente
— ver docstring en `pos.modules.scales.domain.enums`."""

from __future__ import annotations

import enum


class ConnectionType(enum.Enum):
    USB = "usb"
    SERIAL = "serial"
    BLUETOOTH = "bluetooth"
    ETHERNET = "ethernet"
    WIFI = "wifi"


class ConnectionStatus(enum.Enum):
    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class OpeningType(enum.Enum):
    """Cómo se dispara físicamente la apertura del cajón."""

    PRINTER_KICKOUT = "printer_kickout"
    """Cable RJ11 desde una impresora térmica/fiscal que envía el pulso."""
    DIRECT_USB = "direct_usb"
    DIRECT_SERIAL = "direct_serial"
    DIRECT_ETHERNET = "direct_ethernet"


class CashDrawerEventType(enum.Enum):
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"
    TEST_CONNECTION_OK = "test_connection_ok"
    TEST_CONNECTION_FAILED = "test_connection_failed"
    OPENED = "opened"
    OPEN_FAILED = "open_failed"


class CashDrawerOpeningKind(enum.Enum):
    """Si la apertura fue disparada automáticamente por una venta/abono en
    efectivo, o manualmente por un usuario autorizado desde el botón
    "Abrir cajón" — se registra en cada evento de apertura para que el
    historial pueda distinguir una de otra."""

    AUTOMATIC = "automatic"
    MANUAL = "manual"
