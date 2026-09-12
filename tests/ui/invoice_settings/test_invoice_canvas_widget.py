"""Pruebas de UI de `InvoiceCanvasWidget` (backend `offscreen`): construir
el lienzo y variar la configuración no debe lanzar excepciones, la escena
debe quedar con contenido real, y seleccionar un ítem debe emitir
`element_selected` con el `style_key` correcto."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PIL import Image as PILImage
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QGraphicsItem
from pytestqt.qtbot import QtBot

from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.domain.enums import Orientation, PaperSize
from pos.modules.invoice_settings.domain.layout_plan import NUDGE_STEP_PT
from pos.modules.invoice_settings.domain.template_style import ImageStyle, TemplateConfig
from pos.modules.invoice_settings.presentation.invoice_canvas_widget import (
    InvoiceCanvasWidget,
    _BlockGraphicsItem,
)


def _settings(**overrides) -> InvoiceSettingsDTO:
    return replace(InvoiceSettingsDTO(company_name="Ferretería El Tornillo"), **overrides)


def _apply(widget: InvoiceCanvasWidget, settings: InvoiceSettingsDTO) -> None:
    widget.set_settings(settings)
    widget._debounce.stop()
    widget._rebuild_scene()


def test_widget_constructs_with_default_settings(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)

    assert widget.current_layout_plan() is not None
    assert len(widget._scene.items()) > 0


def test_set_settings_rebuilds_scene_without_raising(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)

    for paper_size in (PaperSize.TICKET_58, PaperSize.A4, PaperSize.LETTER, PaperSize.CUSTOM):
        settings = _settings(
            paper_size=paper_size,
            custom_width_mm=100.0 if paper_size is PaperSize.CUSTOM else None,
            custom_height_mm=150.0 if paper_size is PaperSize.CUSTOM else None,
            show_qr=True,
            show_barcode=True,
        )
        _apply(widget, settings)
        assert len(widget._scene.items()) > 0


def test_landscape_orientation_does_not_raise(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)

    _apply(widget, _settings(paper_size=PaperSize.LETTER, orientation=Orientation.LANDSCAPE))
    assert len(widget._scene.items()) > 0


def test_missing_logo_file_does_not_raise(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)

    _apply(widget, _settings(show_logo=True, logo_path="/nonexistent/logo.png"))
    assert len(widget._scene.items()) > 0


def test_current_layout_plan_reflects_last_settings(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)

    _apply(widget, _settings(paper_size=PaperSize.A5))

    assert widget.current_layout_plan().page.width_mm == 148.0


def test_selecting_a_block_emits_element_selected_with_style_key(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings())

    block_items = [item for item in widget._scene.items() if isinstance(item, _BlockGraphicsItem)]
    assert block_items
    target = next(item for item in block_items if item.style_key == "company_name")

    with qtbot.waitSignal(widget.element_selected, timeout=1000) as blocker:
        target.setSelected(True)

    assert blocker.args == ["company_name"]


def test_set_zoom_clamps_to_configured_range(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)

    widget.set_zoom(10.0)
    assert widget.zoom() == 3.0

    widget.set_zoom(0.01)
    assert widget.zoom() == 0.25

    widget.set_zoom(1.5)
    assert widget.zoom() == 1.5


def test_set_show_grid_does_not_raise(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)

    widget.set_show_grid(True)
    widget.set_show_grid(False)


# -- micro-posicionamiento por teclado ----------------------------------


def _select(widget: InvoiceCanvasWidget, style_key: str) -> _BlockGraphicsItem:
    block_items = [item for item in widget._scene.items() if isinstance(item, _BlockGraphicsItem)]
    target = next(item for item in block_items if item.style_key == style_key)
    target.setSelected(True)
    return target


def _press(
    widget: InvoiceCanvasWidget,
    key: Qt.Key,
    modifiers: Qt.KeyboardModifier = Qt.KeyboardModifier.NoModifier,
) -> None:
    widget.keyPressEvent(QKeyEvent(QKeyEvent.Type.KeyPress, key, modifiers))


def _ordered_positions(widget: InvoiceCanvasWidget) -> list[tuple[str, float]]:
    """Posiciones en el mismo orden que `LayoutPlan.blocks` — más
    confiable que `scene.items()` (cuyo orden de iteración no está
    garantizado) para verificar qué se movió y qué no."""
    return [(item.style_key, item.pos().y()) for items in widget._block_items for item in items]


def test_arrow_down_moves_only_the_selected_element_and_what_follows(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings())
    before = dict(_ordered_positions(widget))

    _select(widget, "invoice_number")
    _press(widget, Qt.Key.Key_Down)

    after = dict(_ordered_positions(widget))
    assert after["company_name"] == before["company_name"]  # antes: sin cambios
    assert after["invoice_number"] == before["invoice_number"] + NUDGE_STEP_PT
    assert after["issued_at"] == before["issued_at"] + NUDGE_STEP_PT  # después: se corre


def test_arrow_up_moves_element_one_step_up(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings())
    _select(widget, "invoice_number")
    _press(widget, Qt.Key.Key_Down)
    _press(widget, Qt.Key.Key_Down)
    y_after_two_down = dict(_ordered_positions(widget))["invoice_number"]

    _press(widget, Qt.Key.Key_Up)

    y_after_up = dict(_ordered_positions(widget))["invoice_number"]
    assert y_after_up == y_after_two_down - NUDGE_STEP_PT


def test_shift_arrow_moves_five_steps(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings())
    before = dict(_ordered_positions(widget))["invoice_number"]
    _select(widget, "invoice_number")

    _press(widget, Qt.Key.Key_Down, Qt.KeyboardModifier.ShiftModifier)

    after = dict(_ordered_positions(widget))["invoice_number"]
    assert after == before + 5 * NUDGE_STEP_PT


def test_ctrl_arrow_moves_ten_steps(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings())
    before = dict(_ordered_positions(widget))["invoice_number"]
    _select(widget, "invoice_number")

    _press(widget, Qt.Key.Key_Down, Qt.KeyboardModifier.ControlModifier)

    after = dict(_ordered_positions(widget))["invoice_number"]
    assert after == before + 10 * NUDGE_STEP_PT


def test_repeated_presses_accumulate_in_spacing_offsets(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings())
    _select(widget, "invoice_number")

    for _ in range(7):
        _press(widget, Qt.Key.Key_Up)

    offset = widget._settings.template.spacing_offsets.get("invoice_number", 0.0)
    assert offset == -7 * NUDGE_STEP_PT


def test_nudge_never_produces_a_negative_gap(qtbot: QtBot) -> None:
    """Subir un elemento muchas más veces de las que su hueco disponible
    permite se detiene solo en 0 — nunca superposición."""
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings())
    _select(widget, "invoice_number")

    for _ in range(500):
        _press(widget, Qt.Key.Key_Up, Qt.KeyboardModifier.ControlModifier)

    index = widget._first_block_index("invoice_number")
    preceding = widget._plan.blocks[index - 1]
    assert preceding.height_pt == 0.0


def test_nudge_down_is_clamped_at_the_bottom_of_the_page(qtbot: QtBot) -> None:
    """Empujar un elemento hacia abajo mucho más de lo que cabe en la
    página se limita automáticamente — el contenido nunca se sale de la
    hoja, sin que el usuario tenga que hacer nada especial."""
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings(paper_size=PaperSize.TICKET_58))
    _select(widget, "invoice_number")

    for _ in range(50):
        _press(widget, Qt.Key.Key_Down, Qt.KeyboardModifier.ControlModifier)

    page_bottom = widget._page_bottom_pt()
    assert widget._content_bottom_pt <= page_bottom + 0.01


def test_nudge_emits_spacing_offset_changed_signal(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings())
    _select(widget, "invoice_number")

    with qtbot.waitSignal(widget.spacing_offset_changed, timeout=1000) as blocker:
        _press(widget, Qt.Key.Key_Down)

    assert blocker.args == ["invoice_number", NUDGE_STEP_PT]


def test_arrow_keys_without_selection_do_nothing(qtbot: QtBot) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings())
    before = dict(_ordered_positions(widget))

    _press(widget, Qt.Key.Key_Down)

    after = dict(_ordered_positions(widget))
    assert after == before


def test_selection_survives_first_nudge_full_rebuild(qtbot: QtBot) -> None:
    """El primer ajuste sobre un elemento sin hueco propio reconstruye la
    escena entera (cambia la cantidad de bloques) — la selección debe
    sobrevivir esa reconstrucción para que las siguientes pulsaciones
    sigan moviendo el mismo elemento sin que el usuario tenga que volver
    a hacer clic."""
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings())
    _select(widget, "invoice_number")

    _press(widget, Qt.Key.Key_Down)  # primer ajuste: reconstrucción completa

    selected = widget._scene.selectedItems()
    assert selected
    assert selected[0].style_key == "invoice_number"


# -- posición libre del logo ---------------------------------------------


def _make_logo(tmp_path: Path) -> str:
    logo_path = tmp_path / "logo.png"
    PILImage.new("RGB", (100, 50), color="red").save(logo_path)
    return str(logo_path)


def _logo_item(widget: InvoiceCanvasWidget) -> _BlockGraphicsItem:
    items = [item for item in widget._scene.items() if isinstance(item, _BlockGraphicsItem)]
    return next(item for item in items if item.style_key == "logo")


def test_logo_item_is_movable(qtbot: QtBot, tmp_path: Path) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings(show_logo=True, logo_path=_make_logo(tmp_path)))

    logo = _logo_item(widget)

    assert logo.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable


def test_non_logo_items_are_never_movable(qtbot: QtBot, tmp_path: Path) -> None:
    """Regresión explícita del pedido "solo el logo, ningún otro
    elemento": ni texto ni QR ni código de barras deben admitir
    arrastre, incluso con el logo presente en la misma escena."""
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(
        widget,
        _settings(
            show_logo=True, logo_path=_make_logo(tmp_path), show_qr=True, show_barcode=True
        ),
    )

    for item in widget._scene.items():
        if isinstance(item, _BlockGraphicsItem) and item.style_key != "logo":
            assert not (item.flags() & QGraphicsItem.GraphicsItemFlag.ItemIsMovable)


def test_dragging_logo_updates_settings_and_emits_signal(qtbot: QtBot, tmp_path: Path) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings(show_logo=True, logo_path=_make_logo(tmp_path)))
    logo = _logo_item(widget)

    with qtbot.waitSignal(widget.logo_position_changed, timeout=1000) as blocker:
        logo.setPos(QPointF(250.0, 140.0))

    assert blocker.args == [250.0, 140.0]
    logo_style = widget._settings.template.image_styles["logo"]
    assert logo_style.absolute_x_pt == 250.0
    assert logo_style.absolute_y_pt == 140.0


def test_first_drag_promotes_flow_logo_without_recreating_item(
    qtbot: QtBot, tmp_path: Path
) -> None:
    """El logo en flujo (nunca arrastrado) se convierte a posición
    absoluta en el primer movimiento sin ningún salto visual — el mismo
    item de escena pasa a ser `_logo_overlay_item`, nunca se destruye ni
    se vuelve a crear uno nuevo."""
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings(show_logo=True, logo_path=_make_logo(tmp_path)))
    logo = _logo_item(widget)
    assert widget._logo_overlay_item is None

    logo.setPos(QPointF(300.0, 200.0))

    assert widget._logo_overlay_item is logo
    assert logo.zValue() > 0


def test_logo_clamped_to_non_negative_position(qtbot: QtBot, tmp_path: Path) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings(show_logo=True, logo_path=_make_logo(tmp_path)))
    logo = _logo_item(widget)

    logo.setPos(QPointF(-50.0, -30.0))

    assert logo.pos().x() == 0.0
    assert logo.pos().y() == 0.0


def test_logo_arrow_keys_move_one_point_in_all_four_directions(
    qtbot: QtBot, tmp_path: Path
) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings(show_logo=True, logo_path=_make_logo(tmp_path)))
    logo = _logo_item(widget)
    logo.setPos(QPointF(100.0, 100.0))
    logo.setSelected(True)

    _press(widget, Qt.Key.Key_Right)
    assert logo.pos() == QPointF(101.0, 100.0)

    _press(widget, Qt.Key.Key_Left)
    assert logo.pos() == QPointF(100.0, 100.0)

    _press(widget, Qt.Key.Key_Down)
    assert logo.pos() == QPointF(100.0, 101.0)

    _press(widget, Qt.Key.Key_Up)
    assert logo.pos() == QPointF(100.0, 100.0)


def test_logo_shift_arrow_moves_ten_points(qtbot: QtBot, tmp_path: Path) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings(show_logo=True, logo_path=_make_logo(tmp_path)))
    logo = _logo_item(widget)
    logo.setPos(QPointF(100.0, 100.0))
    logo.setSelected(True)

    _press(widget, Qt.Key.Key_Right, Qt.KeyboardModifier.ShiftModifier)

    assert logo.pos() == QPointF(110.0, 100.0)


def test_logo_ctrl_arrow_moves_twenty_five_points(qtbot: QtBot, tmp_path: Path) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings(show_logo=True, logo_path=_make_logo(tmp_path)))
    logo = _logo_item(widget)
    logo.setPos(QPointF(100.0, 100.0))
    logo.setSelected(True)

    _press(widget, Qt.Key.Key_Right, Qt.KeyboardModifier.ControlModifier)

    assert logo.pos() == QPointF(125.0, 100.0)


def test_non_logo_item_left_right_arrow_keys_still_do_nothing(qtbot: QtBot) -> None:
    """Regresión: el sistema de flechas de texto (solo vertical) no debe
    verse afectado por la rama nueva del logo."""
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings())
    before = dict(_ordered_positions(widget))
    _select(widget, "invoice_number")

    _press(widget, Qt.Key.Key_Left)
    _press(widget, Qt.Key.Key_Right)

    after = dict(_ordered_positions(widget))
    assert after == before


def test_double_click_on_logo_emits_signal(qtbot: QtBot, tmp_path: Path) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, _settings(show_logo=True, logo_path=_make_logo(tmp_path)))
    logo = _logo_item(widget)

    with qtbot.waitSignal(widget.logo_double_clicked, timeout=1000):
        logo._on_double_click()  # noqa: SLF001 (wiring hecho por _make_logo_movable)


def test_logo_selection_survives_full_rebuild_in_absolute_mode(
    qtbot: QtBot, tmp_path: Path
) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    settings = _settings(
        show_logo=True,
        logo_path=_make_logo(tmp_path),
        template=TemplateConfig(
            image_styles={"logo": ImageStyle(absolute_x_pt=250.0, absolute_y_pt=140.0)}
        ),
    )
    _apply(widget, settings)
    logo = _logo_item(widget)
    logo.setSelected(True)
    widget._selected_style_key = "logo"

    widget._rebuild_scene()

    selected = widget._scene.selectedItems()
    assert selected
    assert selected[0].style_key == "logo"


def test_logo_with_absolute_position_is_excluded_from_flow_layout(
    qtbot: QtBot, tmp_path: Path
) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    settings = _settings(
        show_logo=True,
        logo_path=_make_logo(tmp_path),
        template=TemplateConfig(
            image_styles={"logo": ImageStyle(absolute_x_pt=250.0, absolute_y_pt=140.0)}
        ),
    )

    _apply(widget, settings)

    flow_style_keys = [key for items in widget._block_items for key in [i.style_key for i in items]]
    assert "logo" not in flow_style_keys
    logo = _logo_item(widget)
    assert logo.pos() == QPointF(250.0, 140.0)
