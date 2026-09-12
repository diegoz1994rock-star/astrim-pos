"""Adaptador de lector por socket TCP real (TCP/IP y Wi-Fi son, desde el
software, indistinguibles — ambos son solo una IP y un puerto)."""

from __future__ import annotations

import socket

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.barcode_scanners.application.providers.base import ScannerConnectionParams

_TIMEOUT_SECONDS = 2


def _require_address(params: ScannerConnectionParams) -> tuple[str, int]:
    if not params.ip_address or not params.ip_port:
        raise BusinessRuleViolationError(
            "La dirección IP y el puerto son obligatorios para conexión TCP/IP o Wi-Fi."
        )
    return params.ip_address, params.ip_port


class NetworkSocketDriver:
    def test_connection(self, params: ScannerConnectionParams) -> bool:
        address, port = _require_address(params)
        try:
            with socket.create_connection((address, port), timeout=_TIMEOUT_SECONDS):
                return True
        except OSError as error:
            raise BusinessRuleViolationError(
                f"No se pudo conectar a {address}:{port}: {error}"
            ) from error

    def read_code(self, params: ScannerConnectionParams) -> str:
        address, port = _require_address(params)
        try:
            with socket.create_connection((address, port), timeout=_TIMEOUT_SECONDS) as connection:
                raw = connection.recv(1024).decode("ascii", errors="ignore").strip()
        except OSError as error:
            raise BusinessRuleViolationError(
                f"No se pudo leer el lector en {address}:{port}: {error}"
            ) from error
        if not raw:
            raise BusinessRuleViolationError("El lector no envió ningún código.")
        return raw
