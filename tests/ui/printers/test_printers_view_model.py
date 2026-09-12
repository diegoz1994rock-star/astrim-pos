"""Pruebas de `PrintersViewModel` con dependencias simuladas (`Mock`).

Nota de entorno: requieren un `QApplication`/plugin de plataforma Qt
funcional (`qtbot` de pytest-qt) — este sandbox no tiene uno disponible
(ni siquiera `offscreen` inicializa aquí), así que estas pruebas están
escritas, compiladas y lint-eadas, pero no se han podido ejecutar en este
entorno; se certifican por lectura/revisión, misma limitación ya
documentada para báscula/cajón/código de barras."""

from __future__ import annotations

from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.printers.presentation.printers_view_model import PrintersViewModel


def _make_view_model(authenticated: bool = True) -> tuple[PrintersViewModel, Mock]:
    service = Mock()
    cash_register_service = Mock()
    cash_register_service.list_registers.return_value = []
    session_manager = Mock()
    session_manager.current = (
        Mock(user_id=1, username="cajero") if authenticated else None
    )
    view_model = PrintersViewModel(service, cash_register_service, session_manager)
    return view_model, service


def test_create_device_success_emits_message(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.create_device(name="Impresora 1")

    assert messages == ["Impresora 'Impresora 1' creada."]


def test_create_device_error_emits_error_occurred(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.create_device.side_effect = BusinessRuleViolationError("nombre obligatorio")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.create_device(name="")

    assert errors == ["nombre obligatorio"]


def test_delete_device_success_emits_message(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.delete_device(1)

    service.delete_device.assert_called_once_with(1)
    assert messages == ["Impresora eliminada correctamente."]


def test_set_default_success_emits_message(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.set_default(1)

    service.set_default_device.assert_called_once_with(1)
    assert messages == ["Impresora marcada como predeterminada."]


def test_set_default_error_emits_error_occurred(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.set_default_device.side_effect = BusinessRuleViolationError("impresora inactiva")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.set_default(1)

    assert errors == ["impresora inactiva"]


def test_discover_printers_emits_detected_list(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.discover_printers.return_value = ["detected-stub"]
    detected_batches = []
    view_model.detected_printers_loaded.connect(detected_batches.append)

    view_model.discover_printers()

    assert detected_batches == [["detected-stub"]]


def test_discover_printers_error_emits_error_occurred(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.discover_printers.side_effect = BusinessRuleViolationError("sin driver disponible")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.discover_printers()

    assert errors == ["sin driver disponible"]


def test_test_connection_success_emits_message(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.test_connection.return_value = True
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.test_connection(1)

    assert messages == ["Conexión exitosa con la impresora."]


def test_test_connection_failure_emits_error_occurred(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.test_connection.return_value = False
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.test_connection(1)

    assert errors == ["No se pudo conectar con la impresora."]


def test_session_manager_property_exposes_underlying_session_manager(qtbot: QtBot) -> None:
    service = Mock()
    cash_register_service = Mock()
    cash_register_service.list_registers.return_value = []
    session_manager = Mock()

    view_model = PrintersViewModel(service, cash_register_service, session_manager)

    assert view_model.session_manager is session_manager
