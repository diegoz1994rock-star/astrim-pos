"""Pruebas de UI de `UserFormDialog` con `pytest-qt` (backend `offscreen`):
un error de validación no debe cerrar el diálogo ni perder los datos ya
ingresados — ver `_on_accept_clicked`."""

from __future__ import annotations

from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.core.exceptions import ConflictError
from pos.modules.users.presentation.user_form_dialog import UserFormDialog


def _fill_required_fields(dialog: UserFormDialog, *, username: str, full_name: str) -> None:
    dialog._username_edit.setText(username)
    dialog._full_name_edit.setText(full_name)
    dialog._password_edit.setText("clave-valida-123")
    dialog._email_edit.setText("correo@ejemplo.com")
    dialog._phone_edit.setText("3000000000")
    dialog._emergency_phone_edit.setText("3111111111")
    dialog._blood_type_edit.setText("O+")
    dialog._address_edit.setText("Calle Falsa 123")


def test_client_side_password_error_keeps_dialog_open_and_data_intact(qtbot: QtBot) -> None:
    fake_view_model = Mock()
    dialog = UserFormDialog([], fake_view_model)
    qtbot.addWidget(dialog)

    _fill_required_fields(dialog, username="usuario1", full_name="Nombre Completo")
    dialog._password_edit.setText("corta")

    dialog._on_accept_clicked()

    fake_view_model.create_user.assert_not_called()
    assert dialog.result() == 0
    assert dialog._password_error.text() == "La contraseña debe tener al menos 8 caracteres."
    assert dialog._username_edit.text() == "usuario1"
    assert dialog._full_name_edit.text() == "Nombre Completo"


def test_missing_required_contact_fields_keep_dialog_open(qtbot: QtBot) -> None:
    """Correo, teléfono, teléfono de emergencia, RH y dirección son
    obligatorios: si falta alguno, el diálogo no se cierra ni llama al
    servicio, y cada campo vacío muestra su propio error."""
    fake_view_model = Mock()
    dialog = UserFormDialog([], fake_view_model)
    qtbot.addWidget(dialog)

    dialog._username_edit.setText("usuario1")
    dialog._full_name_edit.setText("Nombre Completo")
    dialog._password_edit.setText("clave-valida-123")
    # Correo, teléfono, teléfono de emergencia, RH y dirección quedan vacíos.

    dialog._on_accept_clicked()

    fake_view_model.create_user.assert_not_called()
    assert dialog.result() == 0
    assert dialog._email_error.text() == "El correo es obligatorio."
    assert dialog._phone_error.text() == "El teléfono es obligatorio."
    assert (
        dialog._emergency_phone_error.text() == "El teléfono de emergencia es obligatorio."
    )
    assert dialog._blood_type_error.text() == "El RH es obligatorio."
    assert dialog._address_error.text() == "La dirección es obligatoria."


def test_server_side_conflict_error_keeps_dialog_open_and_routes_to_username(
    qtbot: QtBot,
) -> None:
    fake_view_model = Mock()
    fake_view_model.create_user.side_effect = ConflictError(
        "Ya existe un usuario con el nombre de usuario 'pepe'."
    )
    dialog = UserFormDialog([], fake_view_model)
    qtbot.addWidget(dialog)

    _fill_required_fields(dialog, username="pepe", full_name="Pepe")

    dialog._on_accept_clicked()

    assert dialog.result() == 0
    assert "pepe" in dialog._username_error.text()
    assert dialog._full_name_edit.text() == "Pepe"


def test_successful_submission_closes_dialog_as_accepted(qtbot: QtBot) -> None:
    fake_view_model = Mock()
    dialog = UserFormDialog([], fake_view_model)
    qtbot.addWidget(dialog)

    _fill_required_fields(dialog, username="ok_user", full_name="Ok User")

    dialog._on_accept_clicked()

    fake_view_model.create_user.assert_called_once()
    assert dialog.result() == UserFormDialog.DialogCode.Accepted
