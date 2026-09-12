"""Pruebas de `PercentageBar` (backend `offscreen`)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from pos.shared_ui.widgets.percentage_bar import PercentageBar


def test_set_percentage_clamps_below_zero(qtbot: QtBot) -> None:
    bar = PercentageBar()
    qtbot.addWidget(bar)

    bar.set_percentage(-10.0)

    assert bar.percentage() == 0.0


def test_set_percentage_clamps_above_hundred(qtbot: QtBot) -> None:
    bar = PercentageBar()
    qtbot.addWidget(bar)

    bar.set_percentage(150.0)

    assert bar.percentage() == 100.0


def test_fill_width_scales_proportionally_to_track_width(qtbot: QtBot) -> None:
    bar = PercentageBar()
    qtbot.addWidget(bar)
    bar.resize(200, 8)

    bar.set_percentage(50.0)

    assert bar._fill.width() == 100


def test_fill_width_is_zero_at_zero_percent(qtbot: QtBot) -> None:
    bar = PercentageBar()
    qtbot.addWidget(bar)
    bar.resize(200, 8)

    bar.set_percentage(0.0)

    assert bar._fill.width() == 0


def test_fill_width_equals_track_width_at_hundred_percent(qtbot: QtBot) -> None:
    bar = PercentageBar()
    qtbot.addWidget(bar)
    bar.resize(200, 8)

    bar.set_percentage(100.0)

    assert bar._fill.width() == 200
