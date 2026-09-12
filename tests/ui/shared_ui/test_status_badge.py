"""Pruebas de `StatusBadge` (backend `offscreen`)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from pos.shared_ui.widgets.status_badge import StatusBadge


def test_initial_status_sets_text_and_role(qtbot: QtBot) -> None:
    badge = StatusBadge("Conectada", "success")
    qtbot.addWidget(badge)

    assert badge._label.text() == "● Conectada"
    assert badge._label.property("role") == "success"


def test_set_status_updates_text_and_role(qtbot: QtBot) -> None:
    badge = StatusBadge("Desconectada", "secondary")
    qtbot.addWidget(badge)

    badge.set_status("Error de comunicación", "danger")

    assert badge._label.text() == "● Error de comunicación"
    assert badge._label.property("role") == "danger"


def test_empty_text_renders_no_bullet(qtbot: QtBot) -> None:
    badge = StatusBadge()
    qtbot.addWidget(badge)

    assert badge._label.text() == ""
