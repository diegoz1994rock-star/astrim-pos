"""Pruebas de integración de `PrinterService` contra SQLite real: CRUD y
validaciones por método de impresión, impresión de página de prueba exige
usuario autenticado, historial de auditoría completo, diagnóstico,
reconexión, concurrencia entre impresoras distintas.

`print_test_page` con `PrintMethod.RAW_ESCPOS` es la única vía de impresión
que se ejercita de punta a punta acá (servidor TCP real, sin mocks) porque
no requiere Qt gráfico. `PrintMethod.SYSTEM_DRIVER` y `print_document`
(que rasteriza un PDF con `QPdfDocument`) requieren una `QApplication`
funcional — este entorno de sandbox no tiene un plugin de plataforma Qt
utilizable (confirmado: ni `offscreen` inicializa), así que esa vía se
certifica solo por lectura/compilación/lint, no por ejecución real acá."""

from __future__ import annotations

import contextlib
import socket
import threading

import pytest

from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.printers.domain.enums import (
    ConnectionStatus,
    ConnectionType,
    PrinterEventType,
    PrintMethod,
)
from tests.integration.printers.conftest import PrinterFixtures


def _start_server() -> tuple[socket.socket, str, int]:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    host, port = server.getsockname()
    return server, host, port


def _accept_and_discard(server: socket.socket) -> threading.Thread:
    def _run() -> None:
        with contextlib.suppress(OSError):
            connection, _address = server.accept()
            with connection:
                connection.settimeout(2)
                connection.recv(65536)

    thread = threading.Thread(target=_run)
    thread.start()
    return thread


# -- CRUD / validaciones -------------------------------------------------------


def test_create_device_rejects_empty_name(printer_env: PrinterFixtures) -> None:
    with pytest.raises(BusinessRuleViolationError):
        printer_env.service.create_device(name="  ")


def test_create_device_with_duplicate_name_raises_conflict(printer_env: PrinterFixtures) -> None:
    printer_env.service.create_device(
        name="Impresora 1", print_method=PrintMethod.SYSTEM_DRIVER,
        system_printer_name="EPSON-TM-T20",
    )
    with pytest.raises(ConflictError):
        printer_env.service.create_device(
            name="Impresora 1", print_method=PrintMethod.SYSTEM_DRIVER,
            system_printer_name="Otra",
        )


def test_create_device_system_driver_requires_system_printer_name(
    printer_env: PrinterFixtures,
) -> None:
    with pytest.raises(BusinessRuleViolationError):
        printer_env.service.create_device(
            name="Impresora 1", print_method=PrintMethod.SYSTEM_DRIVER, system_printer_name=None,
        )


def test_create_device_raw_escpos_usb_requires_port(printer_env: PrinterFixtures) -> None:
    with pytest.raises(BusinessRuleViolationError):
        printer_env.service.create_device(
            name="Impresora 1", print_method=PrintMethod.RAW_ESCPOS,
            connection_type=ConnectionType.USB, port=None,
        )


def test_create_device_raw_escpos_ethernet_requires_ip_address(
    printer_env: PrinterFixtures,
) -> None:
    with pytest.raises(BusinessRuleViolationError):
        printer_env.service.create_device(
            name="Impresora 1", print_method=PrintMethod.RAW_ESCPOS,
            connection_type=ConnectionType.ETHERNET, ip_address=None,
        )


def test_create_device_raw_escpos_ethernet_succeeds_and_becomes_default(
    printer_env: PrinterFixtures,
) -> None:
    printer = printer_env.service.create_device(
        name="Impresora 1", print_method=PrintMethod.RAW_ESCPOS,
        connection_type=ConnectionType.ETHERNET, ip_address="192.168.1.50", ip_port=9100,
    )
    assert printer.is_default is True


def test_multiple_printers_allowed_for_same_cash_register(printer_env: PrinterFixtures) -> None:
    """A diferencia de `cash_drawers`, una caja puede tener varias
    impresoras asignadas (recibos + etiquetas, por ejemplo) — sin
    restricción de unicidad."""
    printer_env.service.create_device(
        name="Recibos", print_method=PrintMethod.RAW_ESCPOS,
        connection_type=ConnectionType.ETHERNET, ip_address="192.168.1.50", ip_port=9100,
        cash_register_id=printer_env.register_id,
    )
    printer_env.service.create_device(
        name="Etiquetas", print_method=PrintMethod.RAW_ESCPOS,
        connection_type=ConnectionType.ETHERNET, ip_address="192.168.1.51", ip_port=9100,
        cash_register_id=printer_env.register_id,
    )
    # No debe lanzar — dos impresoras activas para la misma caja son válidas.


def test_update_device_to_duplicate_name_raises_conflict(printer_env: PrinterFixtures) -> None:
    printer_env.service.create_device(
        name="Impresora A", print_method=PrintMethod.RAW_ESCPOS,
        connection_type=ConnectionType.ETHERNET, ip_address="192.168.1.50", ip_port=9100,
    )
    other = printer_env.service.create_device(
        name="Impresora B", print_method=PrintMethod.RAW_ESCPOS,
        connection_type=ConnectionType.ETHERNET, ip_address="192.168.1.51", ip_port=9100,
    )

    with pytest.raises(ConflictError):
        printer_env.service.update_device(
            other.id, name="Impresora A", print_method=PrintMethod.RAW_ESCPOS,
            connection_type=ConnectionType.ETHERNET, ip_address="192.168.1.51", ip_port=9100,
        )


def test_delete_unknown_device_raises_not_found(printer_env: PrinterFixtures) -> None:
    with pytest.raises(NotFoundError):
        printer_env.service.delete_device(9999)


def test_set_default_requires_active_printer(printer_env: PrinterFixtures) -> None:
    printer = printer_env.service.create_device(
        name="Impresora 1", print_method=PrintMethod.RAW_ESCPOS,
        connection_type=ConnectionType.ETHERNET, ip_address="192.168.1.50", ip_port=9100,
    )
    printer_env.service.set_device_active(printer.id, False)

    with pytest.raises(BusinessRuleViolationError):
        printer_env.service.set_default_device(printer.id)


def test_get_default_for_cash_register_returns_none_without_assigned_printer(
    printer_env: PrinterFixtures,
) -> None:
    result = printer_env.service.get_default_for_cash_register(printer_env.register_id)
    assert result is None


def test_get_default_for_cash_register_returns_default_among_assigned(
    printer_env: PrinterFixtures,
) -> None:
    printer_env.service.create_device(
        name="Impresora A", print_method=PrintMethod.RAW_ESCPOS,
        connection_type=ConnectionType.ETHERNET, ip_address="192.168.1.50", ip_port=9100,
        cash_register_id=printer_env.register_id,
    )
    second = printer_env.service.create_device(
        name="Impresora B", print_method=PrintMethod.RAW_ESCPOS,
        connection_type=ConnectionType.ETHERNET, ip_address="192.168.1.51", ip_port=9100,
        cash_register_id=printer_env.register_id,
    )
    printer_env.service.set_default_device(second.id)

    result = printer_env.service.get_default_for_cash_register(printer_env.register_id)

    assert result is not None
    assert result.id == second.id


# -- Impresión de página de prueba: exige usuario autenticado -------------------


def _create_raw_escpos_printer(printer_env: PrinterFixtures, host: str, port: int, **overrides):
    fields = dict(
        name="Impresora térmica", print_method=PrintMethod.RAW_ESCPOS,
        connection_type=ConnectionType.ETHERNET, ip_address=host, ip_port=port,
        timeout_seconds=2,
    )
    fields.update(overrides)
    return printer_env.service.create_device(**fields)


def test_print_test_page_without_user_raises(printer_env: PrinterFixtures) -> None:
    server, host, port = _start_server()
    server.close()
    printer = _create_raw_escpos_printer(printer_env, host, port)

    with pytest.raises(BusinessRuleViolationError, match="usuario autenticado"):
        printer_env.service.print_test_page(printer.id, user_id=None)


def test_print_test_page_on_inactive_device_raises(printer_env: PrinterFixtures) -> None:
    """Rechaza incluso con un servidor real escuchando — la causa debe ser
    `is_active=False`, no un fallo de conexión (mismo criterio que
    `CashDrawerService.open_drawer`)."""
    server, host, port = _start_server()
    thread = _accept_and_discard(server)
    printer = _create_raw_escpos_printer(printer_env, host, port)
    printer_env.service.set_device_active(printer.id, False)

    with pytest.raises(BusinessRuleViolationError, match="desactivada"):
        printer_env.service.print_test_page(printer.id, user_id=printer_env.user_id)

    server.close()
    thread.join(timeout=2)


def test_print_test_page_succeeds_over_real_socket_and_logs_event(
    printer_env: PrinterFixtures,
) -> None:
    server, host, port = _start_server()
    received: list[bytes] = []

    def _run() -> None:
        connection, _address = server.accept()
        with connection:
            connection.settimeout(2)
            received.append(connection.recv(65536))

    thread = threading.Thread(target=_run)
    thread.start()

    printer = _create_raw_escpos_printer(printer_env, host, port, brand="Xprinter", model="XP-58")

    result = printer_env.service.print_test_page(
        printer.id, user_id=printer_env.user_id, username="cajero_impresora"
    )

    thread.join(timeout=3)
    server.close()

    assert result is True
    assert received and b"PAGINA DE PRUEBA" in received[0]

    events = printer_env.service.list_events(printer.id)
    assert len(events) == 1
    assert events[0].event_type is PrinterEventType.TEST_PAGE_PRINTED
    assert events[0].user_id == printer_env.user_id
    assert events[0].username == "cajero_impresora"
    assert events[0].duration_ms is not None


def test_print_test_page_failure_is_logged_and_raises(printer_env: PrinterFixtures) -> None:
    server, host, port = _start_server()
    server.close()  # nada escuchando: la conexión debe fallar
    printer = _create_raw_escpos_printer(printer_env, host, port)

    with pytest.raises(BusinessRuleViolationError):
        printer_env.service.print_test_page(printer.id, user_id=printer_env.user_id)

    events = printer_env.service.list_events(printer.id)
    assert len(events) == 1
    assert events[0].event_type is PrinterEventType.TEST_PAGE_FAILED


def test_retry_after_failed_test_page_is_allowed_and_recorded_separately(
    printer_env: PrinterFixtures,
) -> None:
    server, host, port = _start_server()
    server.close()
    printer = _create_raw_escpos_printer(printer_env, host, port)

    with pytest.raises(BusinessRuleViolationError):
        printer_env.service.print_test_page(printer.id, user_id=printer_env.user_id)
    with pytest.raises(BusinessRuleViolationError):
        printer_env.service.print_test_page(printer.id, user_id=printer_env.user_id)

    events = printer_env.service.list_events(printer.id)
    assert len(events) == 2
    assert all(e.event_type is PrinterEventType.TEST_PAGE_FAILED for e in events)


# -- Conexión / diagnóstico ----------------------------------------------------


def test_connect_without_hardware_sets_error_status(printer_env: PrinterFixtures) -> None:
    server, host, port = _start_server()
    server.close()
    printer = _create_raw_escpos_printer(printer_env, host, port)

    with pytest.raises(BusinessRuleViolationError):
        printer_env.service.connect(printer.id)

    reloaded = printer_env.service.get_device(printer.id)
    assert reloaded.connection_status is ConnectionStatus.ERROR


def test_connect_with_reachable_socket_sets_connected_status(printer_env: PrinterFixtures) -> None:
    server, host, port = _start_server()
    thread = _accept_and_discard(server)
    printer = _create_raw_escpos_printer(printer_env, host, port)

    printer_env.service.connect(printer.id)

    reloaded = printer_env.service.get_device(printer.id)
    assert reloaded.connection_status is ConnectionStatus.CONNECTED
    thread.join(timeout=1)
    server.close()


def test_reset_stale_connections_forces_disconnected(printer_env: PrinterFixtures) -> None:
    server, host, port = _start_server()
    thread = _accept_and_discard(server)
    printer = _create_raw_escpos_printer(printer_env, host, port)
    printer_env.service.connect(printer.id)
    thread.join(timeout=1)
    server.close()

    printer_env.service.reset_stale_connections()

    reloaded = printer_env.service.get_device(printer.id)
    assert reloaded.connection_status is ConnectionStatus.DISCONNECTED


def test_get_diagnostics_counts_test_page_failures_as_errors(
    printer_env: PrinterFixtures,
) -> None:
    server, host, port = _start_server()
    server.close()
    printer = _create_raw_escpos_printer(printer_env, host, port)

    with pytest.raises(BusinessRuleViolationError):
        printer_env.service.print_test_page(printer.id, user_id=printer_env.user_id)

    diagnostics = printer_env.service.get_diagnostics(printer.id)

    assert diagnostics.error_count == 1
    assert diagnostics.last_error is not None
    assert diagnostics.total_prints == 0


# -- Concurrencia ---------------------------------------------------------------


def test_concurrent_test_pages_for_different_printers_do_not_interfere(
    printer_env: PrinterFixtures,
) -> None:
    server_a, host_a, port_a = _start_server()
    server_b, host_b, port_b = _start_server()

    def _drain_forever(server: socket.socket, stop: threading.Event) -> None:
        server.settimeout(0.2)
        while not stop.is_set():
            try:
                connection, _address = server.accept()
            except OSError:
                continue
            with connection:
                connection.settimeout(1)
                with contextlib.suppress(OSError):
                    connection.recv(65536)

    stop_event = threading.Event()
    thread_a = threading.Thread(target=_drain_forever, args=(server_a, stop_event))
    thread_b = threading.Thread(target=_drain_forever, args=(server_b, stop_event))
    thread_a.start()
    thread_b.start()

    printer_a = _create_raw_escpos_printer(printer_env, host_a, port_a, name="Impresora A")
    printer_b = _create_raw_escpos_printer(printer_env, host_b, port_b, name="Impresora B")

    errors: list[Exception] = []

    def _print(printer_id: int) -> None:
        for _ in range(5):
            try:
                printer_env.service.print_test_page(printer_id, user_id=printer_env.user_id)
            except BusinessRuleViolationError:
                errors.append(RuntimeError("no debía fallar con servidor real escuchando"))

    runner_a = threading.Thread(target=_print, args=(printer_a.id,))
    runner_b = threading.Thread(target=_print, args=(printer_b.id,))
    runner_a.start()
    runner_b.start()
    runner_a.join()
    runner_b.join()

    stop_event.set()
    thread_a.join(timeout=2)
    thread_b.join(timeout=2)
    server_a.close()
    server_b.close()

    assert not errors
    assert len(printer_env.service.list_events(printer_a.id)) == 5
    assert len(printer_env.service.list_events(printer_b.id)) == 5
