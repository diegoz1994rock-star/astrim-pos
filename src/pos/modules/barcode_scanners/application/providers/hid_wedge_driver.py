"""Adaptador para lectores HID ("keyboard-wedge", USB o Bluetooth): el modo
dominante en retail — el dispositivo escribe el código directo donde esté
el foco del sistema operativo, como si se tecleara. No expone un puerto
que el software pueda abrir ni permite "probar conexión" por software; el
adaptador lo dice explícito en vez de simular una lectura falsa. Por eso
la prueba real de un lector HID ocurre escribiendo en el campo con foco
del panel de pruebas, no a través de este adaptador."""

from __future__ import annotations

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.barcode_scanners.application.providers.base import ScannerConnectionParams

_HID_MESSAGE = (
    "Los lectores HID (keyboard-wedge, USB o Bluetooth) no exponen un puerto que "
    "el software pueda abrir — el código se escribe directo donde esté el foco, "
    "como si se tecleara. No hay conexión que probar por software para este tipo; "
    "usa el panel de pruebas para verificar la lectura."
)


class HidWedgeDriver:
    def test_connection(self, params: ScannerConnectionParams) -> bool:
        raise BusinessRuleViolationError(_HID_MESSAGE)

    def read_code(self, params: ScannerConnectionParams) -> str:
        raise BusinessRuleViolationError(_HID_MESSAGE)
