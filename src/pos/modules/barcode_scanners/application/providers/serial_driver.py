"""Adaptador de lector por puerto serie real (USB-Serial, Bluetooth-Serial
y RS232 se presentan los tres ante el sistema operativo como un puerto
serie — un único adaptador real, generalizado a los tres modos)."""

from __future__ import annotations

import serial

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.barcode_scanners.application.providers.base import ScannerConnectionParams

_TIMEOUT_SECONDS = 2

_BYTESIZE = {5: serial.FIVEBITS, 6: serial.SIXBITS, 7: serial.SEVENBITS, 8: serial.EIGHTBITS}
_STOPBITS = {1: serial.STOPBITS_ONE, 1.5: serial.STOPBITS_ONE_POINT_FIVE, 2: serial.STOPBITS_TWO}
_PARITY = {
    "N": serial.PARITY_NONE,
    "E": serial.PARITY_EVEN,
    "O": serial.PARITY_ODD,
    "M": serial.PARITY_MARK,
    "S": serial.PARITY_SPACE,
}


def _open_serial(params: ScannerConnectionParams) -> serial.Serial:
    if not params.port:
        raise BusinessRuleViolationError("El puerto es obligatorio para conexión Serial.")
    return serial.Serial(
        params.port,
        params.baud_rate or 9600,
        bytesize=_BYTESIZE.get(params.data_bits, serial.EIGHTBITS),
        stopbits=_STOPBITS.get(params.stop_bits, serial.STOPBITS_ONE),
        parity=_PARITY.get(params.parity, serial.PARITY_NONE),
        timeout=_TIMEOUT_SECONDS,
    )


class SerialPortDriver:
    def test_connection(self, params: ScannerConnectionParams) -> bool:
        try:
            with _open_serial(params):
                return True
        except serial.SerialException as error:
            raise BusinessRuleViolationError(
                f"No se pudo abrir el puerto '{params.port}': {error}"
            ) from error

    def read_code(self, params: ScannerConnectionParams) -> str:
        try:
            with _open_serial(params) as connection:
                raw = connection.readline().decode("ascii", errors="ignore").strip()
        except serial.SerialException as error:
            raise BusinessRuleViolationError(
                f"No se pudo leer el lector en el puerto '{params.port}': {error}"
            ) from error
        if not raw:
            raise BusinessRuleViolationError("El lector no envió ningún código.")
        return raw
