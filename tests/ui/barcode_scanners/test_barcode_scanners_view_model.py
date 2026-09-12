"""Pruebas de `BarcodeScannersViewModel` con dependencias simuladas (`Mock`).

`connect_device`/`test_connection` corren en un `DeviceOperationWorker`
(hilo en background) — las pruebas usan `qtbot.waitSignal` para esperar a
que el hilo termine y la señal llegue al hilo principal."""

from __future__ import annotations

from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.barcode_scanners.presentation.barcode_scanners_view_model import (
    BarcodeScannersViewModel,
)


def _make_view_model() -> tuple[BarcodeScannersViewModel, Mock]:
    service = Mock()
    service.list_devices.return_value = []
    cash_register_service = Mock()
    cash_register_service.list_registers.return_value = []
    view_model = BarcodeScannersViewModel(service, cash_register_service, Mock())
    return view_model, service


def test_create_device_success_emits_message(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.create_device(name="Lector 1")

    assert messages == ["Lector 'Lector 1' registrado."]


def test_create_device_error_emits_error_occurred(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.create_device.side_effect = BusinessRuleViolationError("nombre obligatorio")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.create_device(name="")

    assert errors == ["nombre obligatorio"]


def test_set_default_success_emits_message(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.set_default(1)

    assert messages == ["Lector marcado como predeterminado."]


def test_delete_device_error_emits_error_occurred(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.delete_device.side_effect = BusinessRuleViolationError("no existe")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.delete_device(999)

    assert errors == ["no existe"]


def test_connect_device_success_emits_message_via_worker(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    with qtbot.waitSignal(view_model.operation_succeeded, timeout=2000):
        view_model.connect_device(1)

    assert messages == ["Lector conectado."]
    service.connect.assert_called_once_with(1)


def test_connect_device_failure_still_reloads(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.connect.side_effect = BusinessRuleViolationError("teclado emulado")
    errors = []
    view_model.error_occurred.connect(errors.append)

    with qtbot.waitSignal(view_model.error_occurred, timeout=2000):
        view_model.connect_device(1)

    assert errors == ["teclado emulado"]
    service.list_devices.assert_called_once()


def test_test_connection_success_emits_message(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.test_connection.return_value = True
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    with qtbot.waitSignal(view_model.operation_succeeded, timeout=2000):
        view_model.test_connection(1)

    assert messages == ["Conexión exitosa con el lector."]


def test_test_connection_failure_emits_error(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.test_connection.side_effect = BusinessRuleViolationError("sin hardware")
    errors = []
    view_model.error_occurred.connect(errors.append)

    with qtbot.waitSignal(view_model.error_occurred, timeout=2000):
        view_model.test_connection(1)

    assert errors == ["sin hardware"]


def test_busy_changed_emitted_around_background_operation(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.test_connection.return_value = True
    states = []
    view_model.busy_changed.connect(states.append)

    # Esperamos `operation_succeeded`, que solo se emite después de
    # `busy_changed(False)` dentro de `_handle_success` — para entonces
    # ambos estados (True al iniciar, False al terminar) ya se emitieron.
    with qtbot.waitSignal(view_model.operation_succeeded, timeout=2000):
        view_model.test_connection(1)

    assert states == [True, False]
