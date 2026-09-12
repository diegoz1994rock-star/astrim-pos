"""Recorre un `LayoutPlan` completo y calcula la posición (x, y) de cada
bloque medido, en el mismo orden y con la misma aritmética que
`InvoiceCanvasWidget._rebuild_scene()` — sin paginar (asume una sola
"columna" infinita, igual que el lienzo interactivo, que deja el
contenido sobrante fuera del rectángulo de página dibujado en vez de
partirlo). `invoice_document_renderer.py` es el único consumidor que
además pagina ese resultado; una prueba dedicada (`test_layout_walker.py`)
compara esta salida contra `InvoiceCanvasWidget._block_items` para el
mismo `LayoutPlan`, probando que ambos calculan exactamente los mismos
números."""

from __future__ import annotations

from dataclasses import dataclass

from pos.modules.invoice_settings.domain.layout_plan import (
    BarcodeBlock,
    ImageBlock,
    LayoutPlan,
    QrBlock,
    SpacerBlock,
    TableBlock,
    TextBlock,
)
from pos.shared_ui.invoice_block_rendering import (
    BLOCK_GAP_AFTER_PT,
    MeasuredBlock,
    aligned_x,
    build_barcode_block,
    build_image_block,
    build_qr_block,
    build_table_rows,
    build_text_block,
)


@dataclass
class PositionedBlock:
    x: float
    y: float
    block: MeasuredBlock


@dataclass
class WalkResult:
    positioned: list[PositionedBlock]
    content_bottom_pt: float


def walk_layout_plan(plan: LayoutPlan, content_width_pt: float, base_pt: int) -> WalkResult:
    y = 0.0
    positioned: list[PositionedBlock] = []
    for block in plan.blocks:
        if isinstance(block, SpacerBlock):
            y += block.height_pt
        elif isinstance(block, TextBlock):
            mb = build_text_block(block, content_width_pt, base_pt)
            top = y + mb.space_before
            positioned.append(PositionedBlock(0.0, top, mb))
            y = top + mb.height
        elif isinstance(block, ImageBlock):
            mb = build_image_block(
                block.path,
                block.image_style,
                block.max_width_pt,
                block.max_height_pt,
                block.style_key,
            )
            if mb is not None:
                x = aligned_x(mb.width, content_width_pt, block.image_style.align)
                positioned.append(PositionedBlock(x, y, mb))
                y += mb.height + mb.gap_after
        elif isinstance(block, QrBlock):
            mb = build_qr_block(block)
            x = aligned_x(mb.width, content_width_pt, block.image_style.align)
            positioned.append(PositionedBlock(x, y, mb))
            y += mb.height + mb.gap_after
        elif isinstance(block, BarcodeBlock):
            mb = build_barcode_block(block)
            if mb is not None:
                x = aligned_x(mb.width, content_width_pt, block.image_style.align)
                positioned.append(PositionedBlock(x, y, mb))
                y += mb.height + mb.gap_after
        elif isinstance(block, TableBlock):
            rows = build_table_rows(block, content_width_pt, base_pt)
            for mb in rows:
                positioned.append(PositionedBlock(0.0, y, mb))
                y += mb.height
            y += BLOCK_GAP_AFTER_PT
    return WalkResult(positioned=positioned, content_bottom_pt=y)
