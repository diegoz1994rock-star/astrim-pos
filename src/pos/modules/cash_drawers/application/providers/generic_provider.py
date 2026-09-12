"""Adaptador genérico de cajón monedero: verifica conectividad real por
puerto serie/socket TCP y envía el comando ESC/POS estándar de apertura de
cajón (`ESC p m t1 t2`, ampliamente soportado por controladores directos y
por impresoras térmicas con salida de cajón — ver
`domain/escpos_command.py`). Éxito = se escribió sin error de E/S — no hay
ACK de hardware real para un pulso de apertura."""

from __future__ import annotations

import socket

import serial

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.cash_drawers.application.providers.base import DrawerConnectionParams
from pos.modules.cash_drawers.domain.escpos_command import build_kick_command


class GenericCashDrawerProvider:
    def test_connection(self, params: DrawerConnectionParams) -> bool:
        if params.ip_address:
            try:
                with socket.create_connection(
                    (params.ip_address, params.ip_port), timeout=params.timeout_seconds
                ):
                    return True
            except OSError as error:
                raise BusinessRuleViolationError(
                    f"No se pudo conectar a {params.ip_address}:{params.ip_port}: {error}"
                ) from error
        if params.port:
            try:
                with serial.Serial(
                    params.port, params.baud_rate or 9600, timeout=params.timeout_seconds
                ):
                    return True
            except serial.SerialException as error:
                raise BusinessRuleViolationError(
                    f"No se pudo abrir el puerto '{params.port}': {error}"
                ) from error
        raise BusinessRuleViolationError(
            "El adaptador genérico requiere un puerto o una dirección IP configurados."
        )

    def open_drawer(self, params: DrawerConnectionParams) -> bool:
        command = build_kick_command(
            pulse_count=params.pulse_count,
            pulse_duration_ms=params.pulse_duration_ms,
            custom_command_hex=params.custom_command_hex,
        )
        if params.ip_address:
            try:
                with socket.create_connection(
                    (params.ip_address, params.ip_port), timeout=params.timeout_seconds
                ) as connection:
                    connection.sendall(command)
                    return True
            except OSError as error:
                raise BusinessRuleViolationError(
                    f"No se pudo abrir el cajón en {params.ip_address}:{params.ip_port}: {error}"
                ) from error
        if params.port:
            try:
                with serial.Serial(
                    params.port, params.baud_rate or 9600, timeout=params.timeout_seconds
                ) as connection:
                    connection.write(command)
                    return True
            except serial.SerialException as error:
                raise BusinessRuleViolationError(
                    f"No se pudo abrir el cajón en el puerto '{params.port}': {error}"
                ) from error
        raise BusinessRuleViolationError(
            "El adaptador genérico requiere un puerto o una dirección IP configurados."
        )
