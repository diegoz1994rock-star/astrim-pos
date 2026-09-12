"""Prueba de integración de `GenericCashDrawerProvider` sin mocks: levanta
un servidor TCP real en `127.0.0.1` (puerto efímero) y verifica que los
bytes ESC/POS exactos lleguen por la red — evidencia real de E/S, no una
simulación del comportamiento de producción."""

from __future__ import annotations

import socket
import threading

from pos.modules.cash_drawers.application.providers.base import DrawerConnectionParams
from pos.modules.cash_drawers.application.providers.generic_provider import (
    GenericCashDrawerProvider,
)


def _run_echo_server_once(server: socket.socket, received: list[bytes]) -> None:
    connection, _address = server.accept()
    with connection:
        connection.settimeout(2)
        data = connection.recv(4096)
        received.append(data)


def _start_server() -> tuple[socket.socket, str, int]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()
    return server, host, port


def test_open_drawer_sends_default_escpos_command_over_real_socket() -> None:
    server, host, port = _start_server()
    received: list[bytes] = []
    thread = threading.Thread(target=_run_echo_server_once, args=(server, received))
    thread.start()

    provider = GenericCashDrawerProvider()
    params = DrawerConnectionParams(
        port=None, baud_rate=None, ip_address=host, ip_port=port, timeout_seconds=2,
    )
    result = provider.open_drawer(params)

    thread.join(timeout=3)
    server.close()

    assert result is True
    assert received == [b"\x1b\x70\x00\x19\xfa"]


def test_open_drawer_sends_custom_pulse_duration_over_real_socket() -> None:
    server, host, port = _start_server()
    received: list[bytes] = []
    thread = threading.Thread(target=_run_echo_server_once, args=(server, received))
    thread.start()

    provider = GenericCashDrawerProvider()
    params = DrawerConnectionParams(
        port=None, baud_rate=None, ip_address=host, ip_port=port,
        pulse_duration_ms=100, timeout_seconds=2,
    )
    provider.open_drawer(params)

    thread.join(timeout=3)
    server.close()

    assert received == [b"\x1b\x70\x00\x32\xfa"]


def test_open_drawer_sends_multiple_pulses_over_real_socket() -> None:
    server, host, port = _start_server()
    received: list[bytes] = []
    thread = threading.Thread(target=_run_echo_server_once, args=(server, received))
    thread.start()

    provider = GenericCashDrawerProvider()
    params = DrawerConnectionParams(
        port=None, baud_rate=None, ip_address=host, ip_port=port,
        pulse_count=3, timeout_seconds=2,
    )
    provider.open_drawer(params)

    thread.join(timeout=3)
    server.close()

    assert received == [b"\x1b\x70\x00\x19\xfa" * 3]


def test_open_drawer_sends_custom_command_over_real_socket() -> None:
    server, host, port = _start_server()
    received: list[bytes] = []
    thread = threading.Thread(target=_run_echo_server_once, args=(server, received))
    thread.start()

    provider = GenericCashDrawerProvider()
    params = DrawerConnectionParams(
        port=None, baud_rate=None, ip_address=host, ip_port=port,
        custom_command_hex="1b70001964", timeout_seconds=2,
    )
    provider.open_drawer(params)

    thread.join(timeout=3)
    server.close()

    assert received == [b"\x1b\x70\x00\x19\x64"]


def test_test_connection_succeeds_against_real_open_socket() -> None:
    server, host, port = _start_server()

    def _accept_once() -> None:
        connection, _address = server.accept()
        connection.close()

    thread = threading.Thread(target=_accept_once)
    thread.start()

    provider = GenericCashDrawerProvider()
    params = DrawerConnectionParams(
        port=None, baud_rate=None, ip_address=host, ip_port=port, timeout_seconds=2,
    )
    result = provider.test_connection(params)

    thread.join(timeout=3)
    server.close()

    assert result is True
