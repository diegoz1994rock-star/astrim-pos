"""Prueba de UI del flujo de login con `pytest-qt` (interacción real de
teclado/click sobre widgets Qt reales, backend `offscreen`)."""

from __future__ import annotations

from unittest.mock import Mock

from PySide6.QtCore import Qt
from pytestqt.qtbot import QtBot

from pos.core.exceptions import AuthenticationError
from pos.core.security.session import ActiveSession
from pos.modules.auth.presentation.login_view import LoginView
from pos.modules.auth.presentation.login_view_model import LoginViewModel


def test_successful_login_emits_authenticated_signal(qtbot: QtBot) -> None:
    fake_service = Mock()
    fake_session = ActiveSession(
        user_id=1,
        username="admin",
        full_name="Administrador",
        is_admin=True,
    )
    fake_service.login.return_value = fake_session

    view_model = LoginViewModel(fake_service)
    view = LoginView(view_model)
    qtbot.addWidget(view)

    with qtbot.waitSignal(view.authenticated, timeout=1000) as blocker:
        view._username_edit.setText("admin")
        view._password_edit.setText("clave-valida")
        qtbot.mouseClick(view._login_button, Qt.MouseButton.LeftButton)

    assert blocker.args[0] is fake_session
    fake_service.login.assert_called_once_with("admin", "clave-valida")


def test_failed_login_shows_error_message(qtbot: QtBot) -> None:
    fake_service = Mock()
    fake_service.login.side_effect = AuthenticationError("Usuario o contraseña incorrectos.")

    view_model = LoginViewModel(fake_service)
    view = LoginView(view_model)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)

    view._username_edit.setText("admin")
    view._password_edit.setText("clave-mala")
    qtbot.mouseClick(
        view._login_button, Qt.MouseButton.LeftButton
    )

    assert view._error_label.isVisible()
    assert "incorrect" in view._error_label.text().lower()
    assert view._password_edit.text() == ""


def test_empty_fields_do_not_call_service(qtbot: QtBot) -> None:
    fake_service = Mock()
    view_model = LoginViewModel(fake_service)
    view = LoginView(view_model)
    qtbot.addWidget(view)
    view.show()
    qtbot.waitExposed(view)

    qtbot.mouseClick(
        view._login_button, Qt.MouseButton.LeftButton
    )

    fake_service.login.assert_not_called()
    assert view._error_label.isVisible()
