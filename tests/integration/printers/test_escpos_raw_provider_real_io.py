"""Prueba de integración de `EscPosRawPrinterProvider` sin mocks: levanta
un servidor TCP real en `127.0.0.1` (puerto efímero) y verifica los bytes
exactos recibidos — evidencia real de E/S, mismo patrón que
`tests/integration/cash_drawers/test_generic_provider_real_io.py`.

Cubre `test_connection`/`print_test_page` (ASCII + corte, sin Qt) y la
detección de puerto/IP ausentes — no cubre `print_pdf` acá porque requiere
rasterizar un PDF con `QPdfDocument`, que sí necesita un entorno Qt gráfico
(ver `tests/integration/printers/test_printer_service.py` para esa vía,
condicionada a que el entorno lo soporte)."""

from __future__ import annotations

import socket
import threading

import pytest

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.printers.application.providers.base import (
    PrinterConnectionParams,
    PrinterTestPageContext,
)
from pos.modules.printers.application.providers.escpos_raw_provider import (
    EscPosRawPrinterProvider,
)
from pos.modules.printers.domain.escpos_raster import build_cut_command


def _run_echo_server_once(server: socket.socket, received: list[bytes]) -> None:
    connection, _address = server.accept()
    with connection:
        connection.settimeout(2)
        data = connection.recv(65536)
        received.append(data)


def _start_server() -> tuple[socket.socket, str, int]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()
    return server, host, port


def _params(host: str, port: int, *, auto_cut: bool = True) -> PrinterConnectionParams:
    return PrinterConnectionParams(
        system_printer_name=None, port=None, baud_rate=None,
        ip_address=host, ip_port=port, timeout_seconds=2, auto_cut=auto_cut,
    )


def test_connection_succeeds_against_real_open_socket() -> None:
    server, host, port = _start_server()

    def _accept_once() -> None:
        connection, _address = server.accept()
        connection.close()

    thread = threading.Thread(target=_accept_once)
    thread.start()

    provider = EscPosRawPrinterProvider()
    result = provider.test_connection(_params(host, port))

    thread.join(timeout=3)
    server.close()

    assert result is True


def test_connection_without_port_or_ip_raises() -> None:
    provider = EscPosRawPrinterProvider()
    params = PrinterConnectionParams(
        system_printer_name=None, port=None, baud_rate=None, ip_address=None, ip_port=None,
    )
    with pytest.raises(BusinessRuleViolationError):
        provider.test_connection(params)


def test_print_test_page_sends_expected_content_and_cut_over_real_socket() -> None:
    server, host, port = _start_server()
    received: list[bytes] = []
    thread = threading.Thread(target=_run_echo_server_once, args=(server, received))
    thread.start()

    provider = EscPosRawPrinterProvider()
    context = PrinterTestPageContext(
        brand="Xprinter", model="XP-58", system_label="Linux", port_label=f"{host}:{port}",
    )
    result = provider.print_test_page(_params(host, port), context)

    thread.join(timeout=3)
    server.close()

    assert result is True
    assert len(received) == 1
    payload = received[0]
    assert payload.endswith(build_cut_command())
    text = payload[: -len(build_cut_command())].decode("ascii")
    assert "PAGINA DE PRUEBA" in text
    assert "Xprinter" in text
    assert "XP-58" in text


def test_print_test_page_without_auto_cut_sends_no_cut_command() -> None:
    server, host, port = _start_server()
    received: list[bytes] = []
    thread = threading.Thread(target=_run_echo_server_once, args=(server, received))
    thread.start()

    provider = EscPosRawPrinterProvider()
    context = PrinterTestPageContext(
        brand=None, model=None, system_label="Linux", port_label=f"{host}:{port}",
    )
    provider.print_test_page(_params(host, port, auto_cut=False), context)

    thread.join(timeout=3)
    server.close()

    assert not received[0].endswith(build_cut_command())


def test_write_to_unreachable_ip_raises_business_rule_violation() -> None:
    provider = EscPosRawPrinterProvider()
    context = PrinterTestPageContext(
        brand=None, model=None, system_label="Linux", port_label="192.0.2.1:9100",
    )
    params = PrinterConnectionParams(
        system_printer_name=None, port=None, baud_rate=None,
        ip_address="192.0.2.1", ip_port=9100, timeout_seconds=1,
    )
    with pytest.raises(BusinessRuleViolationError):
        provider.print_test_page(params, context)
