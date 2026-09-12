"""Genera el PDF real de una factura dibujando directamente el mismo
`LayoutPlan` que ya muestra `InvoiceCanvasWidget` (vista previa) — sobre
un `QPainter`/`QPdfWriter` en vez de un `QGraphicsScene`, pero llamando a
los mismos constructores de bloque (`invoice_block_rendering.py`) a
través de `invoice_layout_walker.walk_layout_plan`. Ningún elemento puede
cambiar de posición entre la vista previa y el PDF porque ambos se miden
con el mismo código; lo único que decide este módulo es DÓNDE cortar la
página cuando el contenido no entra en una sola (paginación), algo que el
lienzo interactivo no necesita porque solo se desplaza, nunca imprime.

`writer.setResolution(72)` hace que una unidad de `QPainter` equivalga
exactamente a un punto tipográrico (1/72 pulgada) — el mismo sistema de
unidades que ya usa todo `layout_plan.py`/el lienzo, así que ningún
bloque necesita conversión de unidades para dibujarse acá."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QMarginsF, QRectF, QSizeF
from PySide6.QtGui import QPageSize, QPainter, QPdfWriter

from pos.modules.invoice_settings.domain.layout_plan import ImageBlock, LayoutPlan
from pos.shared_ui.invoice_block_rendering import PT_PER_MM, MeasuredBlock, build_image_block
from pos.shared_ui.invoice_layout_walker import PositionedBlock, walk_layout_plan


def _draw_logo_overlay(painter: QPainter, logo_overlay: ImageBlock | None) -> None:
    """Dibuja el logo en su posición absoluta (arrastrada en el editor)
    encima del contenido normal de la página actual — se llama una vez
    por cada página generada, igual que `_LogoOverlayDocTemplate.afterPage()`
    hacía con ReportLab; sin superposición activa (`logo_overlay=None`,
    el caso de siempre) no hace nada."""
    if logo_overlay is None:
        return
    mb = build_image_block(
        logo_overlay.path,
        logo_overlay.image_style,
        logo_overlay.max_width_pt,
        logo_overlay.max_height_pt,
        logo_overlay.style_key,
    )
    if mb is None:
        return
    painter.save()
    painter.translate(
        logo_overlay.image_style.absolute_x_pt, logo_overlay.image_style.absolute_y_pt
    )
    mb.paint(painter, QRectF(0, 0, mb.width, mb.height))
    painter.restore()


def render_layout_plan_to_pdf(
    plan: LayoutPlan, file_path: Path, *, logo_overlay: ImageBlock | None = None
) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)

    page = plan.page
    page_w_pt = max(page.width_mm, 1.0) * PT_PER_MM
    page_h_pt = max(page.height_mm, 1.0) * PT_PER_MM
    margin_left_pt = page.margin_left_mm * PT_PER_MM
    margin_top_pt = page.margin_top_mm * PT_PER_MM
    margin_right_pt = page.margin_right_mm * PT_PER_MM
    margin_bottom_pt = page.margin_bottom_mm * PT_PER_MM
    content_width_pt = max(page_w_pt - margin_left_pt - margin_right_pt, 1.0)
    printable_height_pt = max(page_h_pt - margin_top_pt - margin_bottom_pt, 1.0)

    result = walk_layout_plan(plan, content_width_pt, page.base_font_size_pt)

    writer = QPdfWriter(str(file_path))
    writer.setResolution(72)
    writer.setPageSize(QPageSize(QSizeF(page_w_pt, page_h_pt), QPageSize.Unit.Point))
    writer.setPageMargins(QMarginsF(0, 0, 0, 0))

    painter = QPainter(writer)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    try:
        _paint_paginated(
            painter,
            result.positioned,
            margin_left_pt=margin_left_pt,
            margin_top_pt=margin_top_pt,
            printable_height_pt=printable_height_pt,
            logo_overlay=logo_overlay,
            new_page=writer.newPage,
        )
    finally:
        painter.end()


def _paint_paginated(
    painter: QPainter,
    positioned: list[PositionedBlock],
    *,
    margin_left_pt: float,
    margin_top_pt: float,
    printable_height_pt: float,
    logo_overlay: ImageBlock | None,
    new_page,
) -> None:
    page_offset_pt = 0.0
    active_table_header: MeasuredBlock | None = None
    active_table_key: str | None = None

    for item in positioned:
        mb = item.block
        y_local = item.y - page_offset_pt
        fits = y_local + mb.height <= printable_height_pt
        if not fits and y_local > 0:
            _draw_logo_overlay(painter, logo_overlay)
            new_page()
            page_offset_pt = item.y
            y_local = 0.0
            is_continuation_row = (
                active_table_header is not None
                and mb.style_key == active_table_key
                and not mb.is_table_header
            )
            if is_continuation_row:
                header = active_table_header
                assert header is not None
                painter.save()
                painter.translate(margin_left_pt, margin_top_pt)
                header.paint(painter, QRectF(0, 0, header.width, header.height))
                painter.restore()
                page_offset_pt -= header.height
                y_local = header.height

        painter.save()
        painter.translate(margin_left_pt + item.x, margin_top_pt + y_local)
        mb.paint(painter, QRectF(0, 0, mb.width, mb.height))
        painter.restore()

        if mb.is_table_header:
            active_table_header = mb
            active_table_key = mb.style_key
        elif mb.style_key != active_table_key:
            active_table_header = None
            active_table_key = None

    _draw_logo_overlay(painter, logo_overlay)
