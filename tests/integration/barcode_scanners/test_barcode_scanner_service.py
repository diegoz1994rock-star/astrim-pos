"""Pruebas de integración de BarcodeScannerService contra SQLite real: CRUD,
que `test_connection`/`read_code` fallen honestos (sin hardware real, y sin
soporte de software para HID) — nunca simulan éxito — y que
`simulate_scan`/`process_hid_scan` procesen y guarden el historial."""

from __future__ import annotations

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.barcode_scanners.application.barcode_scanner_service import BarcodeScannerService
from pos.modules.barcode_scanners.domain.enums import ConnectionStatus, ConnectionType


def _make_service() -> BarcodeScannerService:
    return BarcodeScannerService(EventBus())


def test_create_device_rejects_empty_name(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(BusinessRuleViolationError):
        service.create_device(name="  ")


def test_create_device_with_usb_hid_does_not_require_port(sqlite_engine: None) -> None:
    service = _make_service()

    device = service.create_device(name="Lector 1", connection_type=ConnectionType.USB_HID)

    assert device.connection_type is ConnectionType.USB_HID
    assert device.port is None


def test_create_device_with_duplicate_name_raises_conflict(sqlite_engine: None) -> None:
    service = _make_service()
    service.create_device(name="Lector 1", connection_type=ConnectionType.USB_HID)

    with pytest.raises(ConflictError):
        service.create_device(name="Lector 1", connection_type=ConnectionType.USB_HID)


def test_create_device_requires_port_for_usb_serial(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(BusinessRuleViolationError):
        service.create_device(name="Lector 1", connection_type=ConnectionType.USB_SERIAL, port=None)


def test_create_device_requires_ip_for_tcp_ip(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(BusinessRuleViolationError):
        service.create_device(name="Lector 1", connection_type=ConnectionType.TCP_IP)


def test_delete_unknown_device_raises_not_found(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(NotFoundError):
        service.delete_device(9999)


def test_test_connection_on_hid_scanner_raises_explicit_hid_message(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Lector HID", connection_type=ConnectionType.USB_HID)

    with pytest.raises(BusinessRuleViolationError, match="keyboard-wedge"):
        service.test_connection(device.id)


def test_read_code_fails_without_real_hardware(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(
        name="Lector 1", connection_type=ConnectionType.USB_SERIAL, port="/dev/tty.no-existe-nunca"
    )

    with pytest.raises(BusinessRuleViolationError):
        service.read_code(device.id)


def test_connect_without_hardware_sets_error_status(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(
        name="Lector 1", connection_type=ConnectionType.USB_SERIAL, port="/dev/tty.no-existe-nunca"
    )

    with pytest.raises(BusinessRuleViolationError):
        service.connect(device.id)

    reloaded = next(d for d in service.list_devices() if d.id == device.id)
    assert reloaded.connection_status is ConnectionStatus.ERROR


def test_reset_stale_connections_forces_disconnected(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Lector 1", connection_type=ConnectionType.USB_HID)
    service.disconnect(device.id)

    service.reset_stale_connections()

    reloaded = next(d for d in service.list_devices() if d.id == device.id)
    assert reloaded.connection_status is ConnectionStatus.DISCONNECTED


def test_list_events_records_read_failure(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(
        name="Lector 1", connection_type=ConnectionType.USB_SERIAL, port="/dev/tty.no-existe-nunca"
    )

    with pytest.raises(BusinessRuleViolationError):
        service.read_code(device.id)

    events = service.list_events(device.id)
    assert len(events) == 1


def test_set_default_device_unsets_previous_default(sqlite_engine: None) -> None:
    service = _make_service()
    first = service.create_device(name="Lector 1", connection_type=ConnectionType.USB_HID)
    second = service.create_device(name="Lector 2", connection_type=ConnectionType.USB_HID)

    service.set_default_device(first.id)
    service.set_default_device(second.id)

    devices = {d.id: d for d in service.list_devices()}
    assert devices[first.id].is_default is False
    assert devices[second.id].is_default is True


def test_simulate_scan_processes_code_and_records_history(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(name="Lector 1", connection_type=ConnectionType.USB_HID)

    outcome = service.simulate_scan(device.id, "7701234567890")

    assert outcome.is_simulated is True
    assert outcome.parsed.code == "7701234567890"
    assert outcome.parsed.is_valid

    history = service.list_scan_history(device.id)
    assert len(history) == 1
    assert history[0].is_simulated is True
    assert history[0].code == "7701234567890"

    reloaded = next(d for d in service.list_devices() if d.id == device.id)
    assert reloaded.scan_count == 1
    assert reloaded.last_read_at is not None


def test_process_hid_scan_applies_scan_configuration(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(
        name="Lector 1",
        connection_type=ConnectionType.USB_HID,
        prefix="P:",
        suffix=";",
        ignore_spaces=True,
    )

    outcome = service.process_hid_scan(device.id, "P:123 456;", duration_ms=12)

    assert outcome.parsed.code == "123456"
    assert outcome.duration_ms == 12


def test_simulate_scan_marks_result_failed_when_length_invalid(sqlite_engine: None) -> None:
    service = _make_service()
    device = service.create_device(
        name="Lector 1", connection_type=ConnectionType.USB_HID, min_length=20
    )

    outcome = service.simulate_scan(device.id, "12345")

    assert outcome.parsed.is_valid is False
    history = service.list_scan_history(device.id)
    assert history[0].result.value == "failed"
