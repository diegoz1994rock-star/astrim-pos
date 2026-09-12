"""Enumeraciones de dominio del módulo de básculas (Báscula electrónica).

`ConnectionType`/`ConnectionStatus` se duplican deliberadamente en cada
módulo de Administración → Dispositivos (scales, cash_drawers,
barcode_scanners, printers) en vez de vivir en un lugar compartido — un
enum de dominio compartido crearía una dependencia cruzada entre módulos
que no existe hoy en el proyecto (ver ARCHITECTURE.md §12b: los módulos
solo se referencian entre sí por FK en string o llamada directa a
servicio de aplicación, nunca importando tipos de dominio de otro
módulo). Duplicar un enum de 3-5 miembros es más barato que ese
acoplamiento."""

from __future__ import annotations

import enum


class ConnectionType(enum.Enum):
    """Cómo se conecta físicamente el dispositivo."""

    USB = "usb"
    SERIAL = "serial"
    BLUETOOTH = "bluetooth"
    ETHERNET = "ethernet"
    WIFI = "wifi"


class ConnectionStatus(enum.Enum):
    """Estado de conexión conocido de un dispositivo. Se resetea a
    `DISCONNECTED` para todos los dispositivos al arrancar la aplicación
    (`ScaleService.reset_stale_connections`) — ninguna conexión real puede
    sobrevivir un reinicio del proceso, así que el valor persistido nunca
    miente sobre "seguir conectado" después de un cierre/crash."""

    DISCONNECTED = "disconnected"
    CONNECTED = "connected"
    ERROR = "error"


class UnitOfMeasure(enum.Enum):
    KG = "kg"
    G = "g"
    LB = "lb"
    OZ = "oz"


class ScaleDeviceEventType(enum.Enum):
    """Tipo de evento en el historial/diagnóstico de una báscula."""

    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    RECONNECTED = "reconnected"
    """Reconexión automática lograda tras un fallo de lectura, con
    `auto_reconnect` activo — distinto de `CONNECTED` (conexión inicial
    manual) para que el diagnóstico pueda contar reconexiones por separado."""
    ERROR = "error"
    READ_SUCCESS = "read_success"
    READ_FAILED = "read_failed"
    TARE = "tare"
    CALIBRATION = "calibration"
    TEST_CONNECTION_OK = "test_connection_ok"
    TEST_CONNECTION_FAILED = "test_connection_failed"


class WeightReadingStatus(enum.Enum):
    """Clasificación de una lectura de peso — nunca se acepta una lectura
    corruda sin clasificar (ver `weight_reading.classify_reading`)."""

    STABLE = "stable"
    UNSTABLE = "unstable"
    ZERO = "zero"
    NEGATIVE = "negative"
    INVALID = "invalid"
    OUT_OF_RANGE = "out_of_range"


class WeightEntrySource(enum.Enum):
    """Cómo se obtuvo el peso final confirmado en `ScaleWeightDialog` — el
    módulo de Ventas guarda este valor como snapshot en `SaleItem` (ver
    `sales/infrastructure/models.py`) para trazabilidad en Historial, sin
    que Ventas necesite conocer nada más del hardware de báscula."""

    SCALE = "scale"
    """Lectura estable tomada automáticamente de la báscula conectada."""
    MANUAL = "manual"
    """El cajero escribió el peso a mano (sin báscula, o corrigiendo/
    reemplazando una lectura)."""
