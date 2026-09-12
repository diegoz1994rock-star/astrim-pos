"""Pruebas de UI de `InterfaceSettingsView` (backend `offscreen`): imagen de
fondo del Dashboard.

No se ejercita `QFileDialog.getOpenFileName` (diálogo real bloqueante,
mismo motivo documentado en otras pruebas de UI de este proyecto)."""

from __future__ import annotations

from unittest.mock import Mock

from pytestqt.qtbot import QtBot

from pos.modules.settings.presentation.interface_settings_view import InterfaceSettingsView


def _make_view(qtbot: QtBot) -> InterfaceSettingsView:
    view = InterfaceSettingsView(Mock())
    qtbot.addWidget(view)
    return view


def test_background_image_loaded_with_empty_path_shows_placeholder(qtbot: QtBot) -> None:
    view = _make_view(qtbot)

    view._on_background_image_loaded("")

    assert view._preview.text() == "Sin imagen configurada"
    assert view._select_button.isVisible() or not view.isVisible()
    assert not view._change_button.isVisible() or not view.isVisible()


def test_background_image_loaded_with_missing_file_falls_back_to_placeholder(
    qtbot: QtBot,
) -> None:
    view = _make_view(qtbot)

    view._on_background_image_loaded("/nonexistent/background.png")

    assert view._preview.text() == "Sin imagen configurada"
