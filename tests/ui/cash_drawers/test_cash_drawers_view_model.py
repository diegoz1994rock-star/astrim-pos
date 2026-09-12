"""Pruebas de `CashDrawersViewModel` con dependencias simuladas (`Mock`).

La apertura manual exige un usuario autenticado (nunca aperturas anónimas)
— sin sesión activa, ni siquiera se llama al servicio."""

from __future__ import annotations

from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.cash_drawers.domain.enums import CashDrawerOpeningKind
from pos.modules.cash_drawers.presentation.cash_drawers_view_model import CashDrawersViewModel


def _make_view_model(authenticated: bool = True) -> tuple[CashDrawersViewModel, Mock]:
    service = Mock()
    cash_register_service = Mock()
    cash_register_service.list_registers.return_value = []
    session_manager = Mock()
    session_manager.current = (
        Mock(user_id=1, username="cajero") if authenticated else None
    )
    view_model = CashDrawersViewModel(service, cash_register_service, session_manager)
    return view_model, service


def test_create_device_success_emits_message(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.create_device(name="Cajón 1", port="COM3")

    assert messages == ["Cajón 'Cajón 1' creado."]


def test_open_drawer_error_emits_error_occurred(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.open_drawer.side_effect = BusinessRuleViolationError("no se pudo abrir")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.open_drawer(1, "Vuelto para cliente")

    assert errors == ["no se pudo abrir"]


def test_open_drawer_success_emits_message(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.open_drawer(1, "Vuelto para cliente")

    service.open_drawer.assert_called_once_with(
        1, user_id=1, username="cajero",
        opening_kind=CashDrawerOpeningKind.MANUAL, reason="Vuelto para cliente",
    )
    assert messages == ["Apertura enviada."]


def test_open_drawer_without_authenticated_user_does_not_call_service(qtbot: QtBot) -> None:
    view_model, service = _make_view_model(authenticated=False)
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.open_drawer(1, "Vuelto para cliente")

    service.open_drawer.assert_not_called()
    assert len(errors) == 1
    assert "iniciar sesión" in errors[0]


def test_set_default_success_emits_message(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    messages = []
    view_model.operation_succeeded.connect(messages.append)

    view_model.set_default(1)

    service.set_default_device.assert_called_once_with(1)
    assert messages == ["Cajón marcado como predeterminado."]


def test_set_default_error_emits_error_occurred(qtbot: QtBot) -> None:
    view_model, service = _make_view_model()
    service.set_default_device.side_effect = BusinessRuleViolationError("cajón inactivo")
    errors = []
    view_model.error_occurred.connect(errors.append)

    view_model.set_default(1)

    assert errors == ["cajón inactivo"]


def test_session_manager_property_exposes_underlying_session_manager(qtbot: QtBot) -> None:
    service = Mock()
    cash_register_service = Mock()
    cash_register_service.list_registers.return_value = []
    session_manager = Mock()

    view_model = CashDrawersViewModel(service, cash_register_service, session_manager)

    assert view_model.session_manager is session_manager
