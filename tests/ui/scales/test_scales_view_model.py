"""Pruebas de `ScalesViewModel` con dependencias simuladas (`Mock`).

`connect_device`/`test_connection` corren en un `DeviceOperationWorker`
(hilo en background, adoptado igual que `barcode_scanners`) — las pruebas
usan `qtbot.waitSignal` para esperar a que el hilo termine y la señal
llegue al hilo principal."""

from __future__ import annotations

from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.scales.presentation.scales_view_model import ScalesViewModel


def _make_view_model() -> tuple[ScalesViewModel, Mock, Mock]:
    service = Mock()
    cash_register_service = Mock()
    cash_register_service.list_registers.return_value = []
    user_service = Mock()
    user_service.list_users.return_value = []
    scale_read_service = Mock()
    view_model = ScalesViewModel(service, cash_register_service, user_service, scale_read_service)
    return view_model, service, scale_read_service


def test_load_emits_devices_cash_registers_and_users(qtbot: QtBot) -> None:
    view_model, service, _ = _make_view_model()
    service.list_devices.return_value = ["device-dto"]
    devices_received = []
    view_model.devices_loaded.connect(devices_received.append)

    view_model.load()

    assert devices_received == [["device-dto"]]


def test_create_device_success_reloads_and_emits_message(qtbot: QtBot) -> None:
    view_model, service, _ = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.create_device(name="Báscula 1", kind="generic", port="COM3")

    service.create_device.assert_called_once_with(name="Báscula 1", kind="generic", port="COM3")
    assert messages == ["Báscula 'Báscula 1' creada."]
    service.list_devices.assert_called_once()


def test_create_device_error_emits_error_occurred(qtbot: QtBot) -> None:
    view_model, service, _ = _make_view_model()
    service.create_device.side_effect = BusinessRuleViolationError("nombre obligatorio")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.create_device(name="")

    assert errors == ["nombre obligatorio"]


def test_connect_device_success_emits_message_via_worker(qtbot: QtBot) -> None:
    view_model, service, _ = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    with qtbot.waitSignal(view_model.operation_succeeded, timeout=2000):
        view_model.connect_device(1)

    service.connect.assert_called_once_with(1)
    assert messages == ["Báscula conectada."]
    service.list_devices.assert_called_once()


def test_connect_device_failure_still_reloads(qtbot: QtBot) -> None:
    view_model, service, _ = _make_view_model()
    service.connect.side_effect = BusinessRuleViolationError("no se pudo abrir el puerto")
    errors = []
    view_model.error_occurred.connect(errors.append)

    with qtbot.waitSignal(view_model.error_occurred, timeout=2000):
        view_model.connect_device(1)

    assert errors == ["no se pudo abrir el puerto"]
    service.list_devices.assert_called_once()


def test_test_connection_success_emits_message(qtbot: QtBot) -> None:
    view_model, service, _ = _make_view_model()
    service.test_connection.return_value = True
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    with qtbot.waitSignal(view_model.operation_succeeded, timeout=2000):
        view_model.test_connection(1)

    assert messages == ["Conexión exitosa con la báscula."]


def test_test_connection_failure_emits_error(qtbot: QtBot) -> None:
    view_model, service, _ = _make_view_model()
    service.test_connection.side_effect = BusinessRuleViolationError("sin hardware")
    errors = []
    view_model.error_occurred.connect(errors.append)

    with qtbot.waitSignal(view_model.error_occurred, timeout=2000):
        view_model.test_connection(1)

    assert errors == ["sin hardware"]


def test_busy_changed_emitted_around_background_operation(qtbot: QtBot) -> None:
    view_model, service, _ = _make_view_model()
    service.test_connection.return_value = True
    states = []
    view_model.busy_changed.connect(states.append)

    with qtbot.waitSignal(view_model.operation_succeeded, timeout=2000):
        view_model.test_connection(1)

    assert states == [True, False]


def test_disconnect_device_emits_message(qtbot: QtBot) -> None:
    view_model, service, _ = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.disconnect_device(1)

    service.disconnect.assert_called_once_with(1)
    assert messages == ["Báscula desconectada."]


def test_service_property_exposes_underlying_service(qtbot: QtBot) -> None:
    view_model, service, _ = _make_view_model()

    assert view_model.service is service


def test_scale_read_service_property_exposes_underlying_service(qtbot: QtBot) -> None:
    view_model, _, scale_read_service = _make_view_model()

    assert view_model.scale_read_service is scale_read_service
