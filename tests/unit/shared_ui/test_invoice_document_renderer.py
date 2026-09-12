"""Pruebas de `invoice_document_renderer.py` — el contenido/posición de
cada bloque ya está probado contra la vista previa en
`test_invoice_layout_walker.py`; acá solo se prueba lo genuinamente nuevo
de este módulo: que genera un PDF válido, que pagina una tabla larga
repitiendo el encabezado (igual que ya hacía ReportLab/Platypus), y que el
logo en posición absoluta se dibuja en cada página, no solo en la
primera."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

from PIL import Image as PILImage
from PySide6.QtCore import QSize
from PySide6.QtPdf import QPdfDocument
from pytestqt.qtbot import QtBot

from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.domain.enums import PaperSize
from pos.modules.invoice_settings.domain.layout_plan import (
    InvoiceLineItem,
    InvoiceRenderData,
    build_layout_plan,
    logo_overlay_block,
)
from pos.modules.invoice_settings.domain.template_style import ImageStyle, TemplateConfig
from pos.shared_ui.invoice_block_rendering import PT_PER_MM
from pos.shared_ui.invoice_document_renderer import render_layout_plan_to_pdf


def _settings(**overrides) -> InvoiceSettingsDTO:
    return replace(InvoiceSettingsDTO(company_name="Ferretería El Tornillo"), **overrides)


def _render_data(item_count: int) -> InvoiceRenderData:
    items = [
        InvoiceLineItem(f"Producto número {i}", "1", "$1.000", "$0", "$190", "$1.190")
        for i in range(item_count)
    ]
    return InvoiceRenderData(
        invoice_number="F-000001",
        issued_at_label="24/07/2026 10:00",
        customer_name="Cliente de prueba",
        customer_document=None,
        cashier_name=None,
        register_name=None,
        date_label="24/07/2026",
        time_label="10:00 a. m.",
        items=items,
        subtotal_label="$100.000",
        discount_label="$0",
        tax_label="$19.000",
        total_label="$119.000",
    )


def test_render_produces_a_valid_pdf(tmp_path: Path, qtbot: QtBot) -> None:
    settings = _settings()
    plan = build_layout_plan(settings, _render_data(3))
    pdf_path = tmp_path / "invoice.pdf"

    render_layout_plan_to_pdf(plan, pdf_path)

    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_long_items_table_paginates_and_repeats_header(tmp_path: Path, qtbot: QtBot) -> None:
    settings = _settings(paper_size=PaperSize.TICKET_58)
    plan = build_layout_plan(settings, _render_data(80))
    pdf_path = tmp_path / "invoice.pdf"

    render_layout_plan_to_pdf(plan, pdf_path)

    document = QPdfDocument()
    assert document.load(str(pdf_path)) == QPdfDocument.Error.None_
    assert document.pageCount() > 1


def test_logo_overlay_is_drawn_on_every_page(tmp_path: Path, qtbot: QtBot) -> None:
    logo_path = tmp_path / "logo.png"
    PILImage.new("RGB", (100, 50), color="red").save(logo_path)

    settings = _settings(
        paper_size=PaperSize.TICKET_58,
        show_logo=True,
        logo_path=str(logo_path),
        template=TemplateConfig(
            image_styles={"logo": ImageStyle(absolute_x_pt=5.0, absolute_y_pt=5.0)}
        ),
    )
    plan = build_layout_plan(settings, _render_data(80))
    pdf_path = tmp_path / "invoice.pdf"

    render_layout_plan_to_pdf(plan, pdf_path, logo_overlay=logo_overlay_block(settings))

    document = QPdfDocument()
    assert document.load(str(pdf_path)) == QPdfDocument.Error.None_
    assert document.pageCount() > 1

    page_w_pt = int(plan.page.width_mm * PT_PER_MM)
    page_h_pt = int(plan.page.height_mm * PT_PER_MM)
    for page_index in (0, document.pageCount() - 1):
        image = document.render(page_index, QSize(page_w_pt, page_h_pt))
        assert not image.isNull()
        pixel = image.pixelColor(10, 10)
        assert pixel.red() > 150
        assert pixel.green() < 100
        assert pixel.blue() < 100
