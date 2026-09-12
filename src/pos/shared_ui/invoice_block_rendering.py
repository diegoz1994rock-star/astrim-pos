"""Medición + dibujo de cada tipo de bloque de un `LayoutPlan`
(`invoice_settings.domain.layout_plan`) — extraído de lo que antes eran
métodos privados de `InvoiceCanvasWidget` para que el lienzo interactivo
(vista previa) y `invoice_document_renderer.py` (PDF/impresión real)
llamen literalmente al mismo código: la única forma de garantizar que un
elemento nunca cambie de posición entre la vista previa y el PDF es que
ambos midan y dibujen con la misma función, no con dos implementaciones
calibradas para parecerse (ver `layout_plan.py` para el porqué de esta
separación).

Cada `build_*` mide un bloque y devuelve un `MeasuredBlock`: su tamaño
(en puntos) y una función `paint(painter, rect)` que lo dibuja en
coordenadas locales (origen en `(0, 0)`) — quien la llama decide dónde
posicionarla (`QGraphicsItem.setPos()` en el lienzo, `painter.translate()`
en el renderizador de PDF), pero nunca vuelve a calcular su tamaño."""

from __future__ import annotations

import io
from dataclasses import dataclass
from typing import Callable

import barcode as barcode_lib
import qrcode
from barcode.writer import ImageWriter
from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen, QPixmap

from pos.modules.invoice_settings.domain.layout_plan import (
    ITEMS_COLUMN_FRACTIONS,
    TOTALS_COLUMN_FRACTIONS,
    BarcodeBlock,
    QrBlock,
    TableBlock,
    TextBlock,
)
from pos.modules.invoice_settings.domain.template_style import ElementStyle, ImageStyle

PT_PER_MM = 72.0 / 25.4
BLOCK_GAP_AFTER_PT = 6.0
"""Espacio fijo que sigue a una imagen/QR/código de barras/tabla en el
flujo del documento — no forma parte del rectángulo del bloque en sí
(no se selecciona ni se dibuja), solo desplaza lo que viene después."""

HEADER_FILL = QColor("#2F6FED")
HEADER_TEXT = QColor("white")
ZEBRA_FILL = QColor("#F5F6F8")
GRID_COLOR = QColor("#DDDDDD")
CELL_PADDING_PT = 3.0

_FONT_SIZE_DELTAS = {"title": 8, "heading": 4, "normal": 0, "small": -2}

PaintFn = Callable[[QPainter, QRectF], None]


@dataclass
class MeasuredBlock:
    style_key: str
    width: float
    height: float
    paint: PaintFn
    space_before: float = 0.0
    gap_after: float = 0.0
    is_table_header: bool = False


def text_font(style: str, base_pt: int, element_style: ElementStyle) -> QFont:
    size = element_style.font_size_pt or max(base_pt + _FONT_SIZE_DELTAS[style], 6)
    font = QFont()
    if element_style.font_family:
        font.setFamily(element_style.font_family)
    elif style == "small":
        font.setStyleHint(QFont.StyleHint.Monospace)
        font.setFamily("Courier New")
    default_bold = style in ("title", "heading")
    font.setBold(bool(element_style.bold) if element_style.bold is not None else default_bold)
    font.setItalic(element_style.italic)
    font.setUnderline(element_style.underline)
    font.setPointSizeF(size)
    return font


def cased_text(text: str, element_style: ElementStyle) -> str:
    if element_style.letter_case == "upper":
        return text.upper()
    if element_style.letter_case == "lower":
        return text.lower()
    return text


def text_color(element_style: ElementStyle) -> QColor:
    return QColor(element_style.color_hex) if element_style.color_hex else QColor("black")


def alignment_flag(element_style: ElementStyle) -> Qt.AlignmentFlag:
    return {
        "left": Qt.AlignmentFlag.AlignLeft,
        "center": Qt.AlignmentFlag.AlignHCenter,
        "right": Qt.AlignmentFlag.AlignRight,
    }[element_style.alignment]


def aligned_x(content_width: float, available_width: float, align: str) -> float:
    if align == "center":
        return max((available_width - content_width) / 2, 0.0)
    if align == "right":
        return max(available_width - content_width, 0.0)
    return 0.0


def build_text_block(block: TextBlock, width: float, base_pt: int) -> MeasuredBlock:
    font = text_font(block.style, base_pt, block.element_style)
    text = cased_text(block.text, block.element_style)
    metrics = QFontMetricsF(font)
    flags = int(Qt.TextFlag.TextWordWrap) | int(alignment_flag(block.element_style))
    bounding = metrics.boundingRect(QRectF(0, 0, width, 10_000), flags, text)
    height = max(bounding.height(), metrics.height()) + block.element_style.space_after_pt
    color = text_color(block.element_style)

    def _paint(painter: QPainter, r: QRectF) -> None:
        painter.setFont(font)
        painter.setPen(color)
        painter.drawText(r, flags, text)

    return MeasuredBlock(
        style_key=block.style_key,
        width=width,
        height=height,
        paint=_paint,
        space_before=block.element_style.space_before_pt,
    )


def build_image_block(
    path: str,
    image_style: ImageStyle,
    max_width_pt: float,
    max_height_pt: float,
    style_key: str,
) -> MeasuredBlock | None:
    """Escala el pixmap y arma el bloque medido — lo comparten el logo en
    flujo, el logo en superposición absoluta, y (vía
    `invoice_document_renderer.py`) el dibujo del logo superpuesto en el
    PDF; ninguno decide todavía su posición final, eso lo hace cada
    llamador después."""
    pixmap = QPixmap(path)
    if pixmap.isNull():
        return None
    if image_style.keep_aspect_ratio:
        scale = min(max_width_pt / pixmap.width(), max_height_pt / pixmap.height(), 1.0)
        w, h = pixmap.width() * scale, pixmap.height() * scale
    else:
        w, h = max_width_pt, max_height_pt

    def _paint(painter: QPainter, r: QRectF) -> None:
        painter.drawPixmap(r, pixmap, QRectF(pixmap.rect()))

    return MeasuredBlock(
        style_key=style_key, width=w, height=h, paint=_paint, gap_after=BLOCK_GAP_AFTER_PT
    )


def build_qr_block(block: QrBlock) -> MeasuredBlock:
    qr = qrcode.QRCode(border=1)
    qr.add_data(block.data)
    qr.make(fit=True)
    pil_image = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    buffer = io.BytesIO()
    pil_image.save(buffer, format="PNG")
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")

    def _paint(painter: QPainter, r: QRectF) -> None:
        painter.drawPixmap(r, pixmap, QRectF(pixmap.rect()))

    return MeasuredBlock(
        style_key=block.style_key,
        width=block.size_pt,
        height=block.size_pt,
        paint=_paint,
        gap_after=BLOCK_GAP_AFTER_PT,
    )


def build_barcode_block(block: BarcodeBlock) -> MeasuredBlock | None:
    barcode_class = barcode_lib.get_barcode_class("code128")
    buffer = io.BytesIO()
    barcode_class(block.text, writer=ImageWriter()).write(
        buffer, options={"write_text": False, "quiet_zone": 1}
    )
    pixmap = QPixmap()
    pixmap.loadFromData(buffer.getvalue(), "PNG")
    if pixmap.isNull():
        return None
    scale = min(block.width_pt / pixmap.width(), block.height_pt / pixmap.height())
    w, h = pixmap.width() * scale, pixmap.height() * scale

    def _paint(painter: QPainter, r: QRectF) -> None:
        painter.drawPixmap(r, pixmap, QRectF(pixmap.rect()))

    return MeasuredBlock(
        style_key=block.style_key, width=w, height=h, paint=_paint, gap_after=BLOCK_GAP_AFTER_PT
    )


def _table_row_height(
    cells: list[str], col_widths: list[float], font_size: float, bold: bool, padding: float
) -> float:
    font = QFont()
    font.setPointSizeF(font_size)
    font.setBold(bold)
    metrics = QFontMetricsF(font)
    row_height = 0.0
    for cell_text, col_width in zip(cells, col_widths, strict=True):
        padded_width = max(col_width - 2 * padding, 1.0)
        bounding = metrics.boundingRect(
            QRectF(0, 0, padded_width, 10_000), int(Qt.TextFlag.TextWordWrap), str(cell_text)
        )
        row_height = max(row_height, bounding.height() + 2 * padding)
    return row_height


def build_table_rows(block: TableBlock, width: float, base_pt: int) -> list[MeasuredBlock]:
    """Un `MeasuredBlock` por fila (encabezado incluido) — la separación
    fila por fila es lo que le permite a `invoice_document_renderer.py`
    partir una tabla larga entre páginas repitiendo el encabezado, igual
    que ya hacía ReportLab (`repeatRows=1`) de forma automática."""
    fractions = ITEMS_COLUMN_FRACTIONS if block.kind == "items" else TOTALS_COLUMN_FRACTIONS
    col_widths = [f * width for f in fractions]
    font_size = max(base_pt - 1, 6)
    table_style = block.table_style
    padding = table_style.cell_padding_pt or CELL_PADDING_PT
    header_fill = QColor(table_style.header_bg_hex) if table_style.header_bg_hex else HEADER_FILL
    header_text = (
        QColor(table_style.header_text_color_hex)
        if table_style.header_text_color_hex
        else HEADER_TEXT
    )
    grid_color = QColor(table_style.grid_color_hex) if table_style.grid_color_hex else GRID_COLOR
    zebra_fill = QColor(table_style.zebra_color_hex) if table_style.zebra_color_hex else ZEBRA_FILL
    row_height_override = table_style.row_height_pt

    rows_render: list[tuple[list[str], bool, QColor | None, int | None, bool]] = []
    if block.kind == "items" and block.headers:
        rows_render.append((block.headers, True, header_fill, None, True))
    for index, row in enumerate(block.rows):
        is_last = block.kind == "totals" and index == len(block.rows) - 1
        fill = zebra_fill if block.kind == "items" and index % 2 == 1 else None
        align_from = 1 if block.kind == "totals" else None
        rows_render.append((row, is_last, fill, align_from, False))

    measured_rows: list[MeasuredBlock] = []
    for cells, bold, fill, align_from, is_header in rows_render:
        text_color = header_text if is_header else QColor("black")
        row_height = _table_row_height(cells, col_widths, font_size, bold, padding)
        if row_height_override:
            row_height = row_height_override
        total_width = sum(col_widths)

        def _paint(
            painter: QPainter,
            r: QRectF,
            cells=cells,
            col_widths=col_widths,
            row_height=row_height,
            font_size=font_size,
            bold=bold,
            fill=fill,
            text_color=text_color,
            grid_color=grid_color,
            padding=padding,
            align_from=align_from,
        ) -> None:
            font = QFont()
            font.setPointSizeF(font_size)
            font.setBold(bold)
            if fill is not None:
                painter.fillRect(r, fill)
            painter.setFont(font)
            painter.setPen(text_color)
            flags_base = int(Qt.TextFlag.TextWordWrap)
            x = 0.0
            for index, (cell_text, col_width) in enumerate(zip(cells, col_widths, strict=True)):
                align = (
                    int(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
                    if align_from is not None and index >= align_from
                    else int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                )
                cell_rect = QRectF(x, 0, col_width, row_height)
                text_rect = QRectF(x + padding, 0, max(col_width - 2 * padding, 1.0), row_height)
                painter.save()
                painter.setClipRect(cell_rect)
                painter.drawText(text_rect, flags_base | align, str(cell_text))
                painter.restore()
                x += col_width
            painter.setPen(QPen(grid_color, 0.5))
            x = 0.0
            for col_width in col_widths:
                painter.drawRect(QRectF(x, 0, col_width, row_height))
                x += col_width

        measured_rows.append(
            MeasuredBlock(
                style_key=block.style_key,
                width=total_width,
                height=row_height,
                paint=_paint,
                is_table_header=is_header,
            )
        )
    return measured_rows
