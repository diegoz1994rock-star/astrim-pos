"""Prueba central de la corrección del motor de impresión de facturas:
`walk_layout_plan` (el mismo cálculo que usa el PDF real, ver
`invoice_document_renderer.py`) debe posicionar cada bloque exactamente
donde lo posiciona `InvoiceCanvasWidget` (la vista previa) para el mismo
`LayoutPlan` — ambos llaman a las mismas funciones de medición
(`invoice_block_rendering.py`), así que un desacuerdo acá sería la
regresión exacta que se reportó (el logo apareciendo en una posición
distinta en el PDF que en la vista previa)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image as PILImage
from pytestqt.qtbot import QtBot

from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.domain.layout_plan import build_layout_plan
from pos.modules.invoice_settings.presentation.invoice_canvas_widget import (
    _SAMPLE_RENDER_DATA,
    InvoiceCanvasWidget,
)
from pos.shared_ui.invoice_block_rendering import PT_PER_MM
from pos.shared_ui.invoice_layout_walker import walk_layout_plan


def _settings(**overrides) -> InvoiceSettingsDTO:
    return replace(InvoiceSettingsDTO(company_name="Ferretería El Tornillo"), **overrides)


def _apply(widget: InvoiceCanvasWidget, settings: InvoiceSettingsDTO) -> None:
    widget.set_settings(settings)
    widget._debounce.stop()  # noqa: SLF001 (mismo patrón que test_invoice_canvas_widget.py)
    widget._rebuild_scene()  # noqa: SLF001


def _compare_against_canvas(qtbot: QtBot, settings: InvoiceSettingsDTO) -> None:
    widget = InvoiceCanvasWidget()
    qtbot.addWidget(widget)
    _apply(widget, settings)

    plan = build_layout_plan(settings, _SAMPLE_RENDER_DATA)
    page = plan.page
    content_width_pt = max(
        page.width_mm * PT_PER_MM
        - page.margin_left_mm * PT_PER_MM
        - page.margin_right_mm * PT_PER_MM,
        1.0,
    )
    result = walk_layout_plan(plan, content_width_pt, page.base_font_size_pt)
    margin_left_pt = page.margin_left_mm * PT_PER_MM
    margin_top_pt = page.margin_top_mm * PT_PER_MM

    canvas_positions = [
        (item.style_key, item.pos().x(), item.pos().y())
        for items in widget._block_items  # noqa: SLF001
        for item in items
    ]
    walker_positions = [
        (positioned.block.style_key, margin_left_pt + positioned.x, margin_top_pt + positioned.y)
        for positioned in result.positioned
    ]

    assert len(canvas_positions) == len(walker_positions)
    for (canvas_key, canvas_x, canvas_y), (walker_key, walker_x, walker_y) in zip(
        canvas_positions, walker_positions, strict=True
    ):
        assert walker_key == canvas_key
        assert walker_x == pytest.approx(canvas_x), canvas_key
        assert walker_y == pytest.approx(canvas_y), canvas_key

    assert margin_top_pt + result.content_bottom_pt == pytest.approx(
        widget._content_bottom_pt  # noqa: SLF001
    )


def test_walker_matches_canvas_positions_for_default_settings(qtbot: QtBot) -> None:
    _compare_against_canvas(qtbot, _settings())


def test_walker_matches_canvas_positions_with_qr_and_barcode(qtbot: QtBot) -> None:
    _compare_against_canvas(qtbot, _settings(show_qr=True, show_barcode=True))


def test_walker_matches_canvas_position_of_logo_after_long_wrapping_company_header(
    qtbot: QtBot, tmp_path: Path
) -> None:
    """Reproduce el escenario exacto del bug reportado: un encabezado de
    empresa largo (que hace wrap a varias líneas) seguido del logo en
    flujo normal — antes de este cambio, ReportLab y Qt medían el alto de
    ese encabezado de forma distinta y el logo terminaba superpuesto al
    texto en el PDF aunque la vista previa se viera bien."""
    logo_path = tmp_path / "logo.png"
    PILImage.new("RGB", (100, 50), color="red").save(logo_path)

    settings = _settings(
        company_name=(
            "Ferretería y Distribuidora El Tornillo Dorado S.A.S. — "
            "Sucursal Centro, atención al cliente de lunes a sábado"
        ),
        show_logo=True,
        logo_path=str(logo_path),
    )
    _compare_against_canvas(qtbot, settings)
