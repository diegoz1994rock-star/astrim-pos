"""Adaptador genérico de báscula: abre el puerto serie configurado, lee una
línea de texto y extrae el primer número — un protocolo de texto plano
(ej. "2.350kg\\r\\n" o "ST,GS,+002.350kg") común en básculas económicas.

No hay forma de probar contra hardware real en este entorno; cuando se
integre una marca específica con su propio protocolo binario, se agrega un
adaptador nuevo (ver `registry.py`) sin tocar este archivo ni Vendedor/
Ventas — si la conexión o la lectura fallan (lo esperable sin báscula
conectada), levanta un error claro que `ScaleWeightDialog` usa para caer a
ingreso manual del peso."""

from __future__ import annotations

import re
from decimal import Decimal, InvalidOperation

import serial

from pos.core.exceptions import BusinessRuleViolationError

_NUMBER_PATTERN = re.compile(r"[-+]?\d+(?:[.,]\d+)?")
_READ_TIMEOUT_SECONDS = 2


class GenericScaleProvider:
    supports_tare = False
    supports_calibration = False
    """El protocolo de texto plano genérico no define comandos de tara ni
    calibración (son específicos de cada fabricante) — un adaptador de
    marca futura que sí los soporte simplemente pone estos atributos en
    `True` y agrega `tare`/`calibrate` reales, sin tocar nada más."""

    def test_connection(
        self, *, port: str, baud_rate: int, simulated_target: Decimal | None = None
    ) -> bool:
        try:
            with serial.Serial(port, baud_rate, timeout=_READ_TIMEOUT_SECONDS):
                return True
        except serial.SerialException as error:
            raise BusinessRuleViolationError(
                f"No se pudo abrir el puerto '{port}': {error}"
            ) from error

    def read_weight(
        self, *, port: str, baud_rate: int, simulated_target: Decimal | None = None
    ) -> Decimal:
        try:
            with serial.Serial(port, baud_rate, timeout=_READ_TIMEOUT_SECONDS) as connection:
                raw_line = connection.readline().decode("ascii", errors="ignore")
        except serial.SerialException as error:
            raise BusinessRuleViolationError(
                f"No se pudo leer la báscula en el puerto '{port}': {error}"
            ) from error

        match = _NUMBER_PATTERN.search(raw_line)
        if match is None:
            raise BusinessRuleViolationError(
                f"La báscula no envió un peso reconocible: '{raw_line.strip()}'."
            )
        try:
            return Decimal(match.group().replace(",", "."))
        except InvalidOperation as error:
            raise BusinessRuleViolationError(
                f"Peso inválido recibido de la báscula: '{match.group()}'."
            ) from error

    def tare(self, *, port: str, baud_rate: int) -> None:
        raise BusinessRuleViolationError(
            "El adaptador genérico no soporta tara remota — requiere un adaptador "
            "específico del fabricante."
        )

    def calibrate(self, *, port: str, baud_rate: int) -> None:
        raise BusinessRuleViolationError(
            "El adaptador genérico no soporta calibración remota — requiere un "
            "adaptador específico del fabricante."
        )
