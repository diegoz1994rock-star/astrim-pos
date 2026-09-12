"""Plano de layout de una factura — único punto de verdad de qué se
imprime, en qué orden y con qué tamaño de página, consumido tanto por el
PDF real (`billing/infrastructure/pdf_renderer.py`, vía ReportLab) como
por el lienzo interactivo de la vista previa (`presentation/invoice_canvas_widget.py`,
vía QGraphicsView/QPainter). Ninguno de los dos vuelve a decidir "qué va
primero" o "qué se muestra si el flag está apagado" — esa decisión vive
acá una sola vez, así la vista previa no puede divergir del PDF real en
contenido/orden/tamaño de página, solo puede diferir en el motor de texto
exacto (ReportLab vs Qt).

Cada `Block` lleva además un `style_key` y un override de estilo
(`element_style`/`table_style`/`image_style`, siempre presentes con
valores por defecto "sin efecto" — nunca `None` — ver
`domain/template_style.py`) para que el editor visual de plantillas
pueda apuntar exactamente a "ese" elemento desde `InvoiceSettingsDTO.template`.
Una fila sin ninguna personalización (`TemplateConfig()` vacío) produce
overrides todos-por-defecto, que ambos renderers deben tratar como
no-ops — el `LayoutPlan` resultante es idéntico al que existía antes de
que el editor de plantillas existiera.

Módulo de dominio puro: sin imports de SQLAlchemy/PySide6/reportlab, se
testea con pytest puro (`tests/unit/invoice_settings/test_layout_plan.py`).
Tampoco hace E/S de archivos (no verifica si `logo_path` existe en disco)
— cada renderer decide en el momento de dibujar qué hacer si el archivo ya
no está.

Todo elemento que aparece en un documento impreso viene EXCLUSIVAMENTE de
`InvoiceSettingsDTO`/`InvoiceRenderData` (Configuración de factura) — este
módulo nunca lee ni acepta nada de Configuración de interfaz (temas,
colores, imagen de fondo del Dashboard). Esa separación es una regla de
arquitectura, no un detalle de implementación: la vista previa del editor
y el PDF real deben verse siempre idénticos, y solo pueden divergir si uno
de los dos dibuja algo que el otro no obtuvo de esta misma fuente."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

from pos.modules.invoice_settings.application.content_items import FOOTER_KEYS, HEADER_KEYS
from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.domain.enums import PAGE_DIMENSIONS_MM, Orientation, PaperSize
from pos.modules.invoice_settings.domain.template_style import ElementStyle, ImageStyle, TableStyle

TextStyle = Literal["title", "heading", "normal", "small"]


@dataclass(frozen=True)
class InvoiceLineItem:
    product_name: str
    quantity: str
    unit_price: str
    discount: str
    tax: str
    line_total: str


@dataclass(frozen=True)
class InvoiceRenderData:
    """Datos de una factura ya formateados a texto — desacoplado a
    propósito de `InvoiceDTO`/`SaleDTO` (evitaría que `invoice_settings`
    dependa de `billing`/`sales`, ver ARCHITECTURE.md §12b; el mapeo desde
    esos DTOs reales vive en `billing`, que ya depende de `invoice_settings`,
    nunca al revés)."""

    invoice_number: str
    issued_at_label: str
    customer_name: str
    customer_document: str | None
    cashier_name: str | None
    register_name: str | None
    date_label: str
    time_label: str
    items: list[InvoiceLineItem]
    subtotal_label: str
    discount_label: str
    tax_label: str
    total_label: str


@dataclass(frozen=True)
class TextBlock:
    text: str
    style: TextStyle = "normal"
    style_key: str = ""
    element_style: ElementStyle = field(default_factory=ElementStyle)


@dataclass(frozen=True)
class TableBlock:
    headers: list[str]
    rows: list[list[str]]
    kind: Literal["items", "totals"] = "items"
    style_key: str = ""
    table_style: TableStyle = field(default_factory=TableStyle)


@dataclass(frozen=True)
class ImageBlock:
    path: str
    max_width_pt: float
    max_height_pt: float
    style_key: str = ""
    image_style: ImageStyle = field(default_factory=ImageStyle)


@dataclass(frozen=True)
class SpacerBlock:
    height_pt: float = 12.0


@dataclass(frozen=True)
class QrBlock:
    data: str
    size_pt: float = 90.0
    style_key: str = "qr"
    image_style: ImageStyle = field(default_factory=ImageStyle)


@dataclass(frozen=True)
class BarcodeBlock:
    text: str
    width_pt: float = 200.0
    height_pt: float = 50.0
    style_key: str = "barcode"
    image_style: ImageStyle = field(default_factory=ImageStyle)


Block = TextBlock | TableBlock | ImageBlock | SpacerBlock | QrBlock | BarcodeBlock

_LOGO_MAX_WIDTH_PT = 140.0
_LOGO_MAX_HEIGHT_PT = 70.0
_QR_SIZE_PT = 90.0
_BARCODE_WIDTH_PT = 200.0
_BARCODE_HEIGHT_PT = 50.0

_ITEMS_TABLE_HEADERS = [
    "Producto", "Cantidad", "Precio unit.", "Descuento", "Impuesto", "Total línea"
]

ITEMS_COLUMN_FRACTIONS = [0.28, 0.12, 0.18, 0.14, 0.14, 0.14]
"""Ancho de cada columna de la tabla de productos, como fracción del ancho
disponible de página — mismo valor usado por `pdf_renderer.py` (ReportLab)
y `invoice_canvas_widget.py` (QPainter) para que ninguna tabla se salga de
la página en tickets angostos, y para que ambos renderers reflejen las
mismas proporciones de columna."""
TOTALS_COLUMN_FRACTIONS = [0.55, 0.45]

NUDGE_STEP_PT = 1.0
"""Un paso de micro-posicionamiento por teclado (ver
`presentation/invoice_canvas_widget.py`) — una pulsación de ↑/↓ sin
modificadores mueve el elemento seleccionado exactamente esto, en puntos
tipográficos. Shift/Ctrl multiplican este valor, nunca lo reemplazan por
otra unidad."""

_TOTALS_KEYS = ("subtotal", "discount", "tax", "total")
"""Ninguna de estas 4 claves vive en `content_order` — su posición es
siempre fija (esta misma tupla define su orden de fila dentro de la tabla
fusionada, ver `_merged_totals_block`), pegada justo después de la tabla
de productos. `subtotal` siempre se imprime; `discount`/`tax`/`total`
respetan `show_discounts`/`show_taxes`/`show_total` (casillas propias en
la UI, ya no filas reordenables — ver `content_items.py`)."""


@dataclass(frozen=True)
class PageSpec:
    width_mm: float
    height_mm: float
    margin_top_mm: float
    margin_right_mm: float
    margin_bottom_mm: float
    margin_left_mm: float
    base_font_size_pt: int


@dataclass(frozen=True)
class LayoutPlan:
    page: PageSpec
    blocks: list[Block] = field(default_factory=list)


def _page_spec(settings: InvoiceSettingsDTO) -> PageSpec:
    if settings.paper_size is PaperSize.CUSTOM:
        width_mm = settings.custom_width_mm or PAGE_DIMENSIONS_MM[PaperSize.A4][0]
        height_mm = settings.custom_height_mm or PAGE_DIMENSIONS_MM[PaperSize.A4][1]
    else:
        width_mm, height_mm = PAGE_DIMENSIONS_MM[settings.paper_size]
    if settings.orientation is Orientation.LANDSCAPE:
        width_mm, height_mm = height_mm, width_mm
    return PageSpec(
        width_mm=width_mm,
        height_mm=height_mm,
        margin_top_mm=settings.margin_top_mm,
        margin_right_mm=settings.margin_right_mm,
        margin_bottom_mm=settings.margin_bottom_mm,
        margin_left_mm=settings.margin_left_mm,
        base_font_size_pt=settings.base_font_size_pt,
    )


def _element_style(settings: InvoiceSettingsDTO, style_key: str) -> ElementStyle:
    return settings.template.element_styles.get(style_key, ElementStyle())


def _table_style(settings: InvoiceSettingsDTO, style_key: str) -> TableStyle:
    return settings.template.table_styles.get(style_key, TableStyle())


def _image_style(settings: InvoiceSettingsDTO, style_key: str) -> ImageStyle:
    return settings.template.image_styles.get(style_key, ImageStyle())


def _text(settings: InvoiceSettingsDTO, text: str, style: TextStyle, style_key: str) -> TextBlock:
    return TextBlock(
        text, style, style_key=style_key, element_style=_element_style(settings, style_key)
    )


def _company_header_blocks(settings: InvoiceSettingsDTO, data: InvoiceRenderData) -> list[Block]:
    blocks: list[Block] = [_text(settings, settings.company_name, "title", "company_name")]
    optional_lines = [
        (f"NIT: {settings.company_nit}" if settings.company_nit else None, "company_nit"),
        (settings.company_address, "company_address"),
        (settings.company_city, "company_city"),
        (f"Tel: {settings.company_phone}" if settings.company_phone else None, "company_phone"),
        (settings.company_email, "company_email"),
        (settings.company_website, "company_website"),
    ]
    blocks.extend(
        _text(settings, line, "normal", style_key) for line, style_key in optional_lines if line
    )
    invoice_number_text = f"Factura N.º {data.invoice_number}"
    blocks.append(_text(settings, invoice_number_text, "heading", "invoice_number"))
    issued_at_text = f"Fecha de emisión: {data.issued_at_label}"
    blocks.append(_text(settings, issued_at_text, "normal", "issued_at"))
    return blocks


def _content_block_for_key(
    key: str, settings: InvoiceSettingsDTO, data: InvoiceRenderData
) -> list[Block]:
    if key == "logo":
        if settings.show_logo and settings.logo_path:
            image_style = _image_style(settings, "logo")
            if image_style.absolute_x_pt is not None and image_style.absolute_y_pt is not None:
                # Posición libre activa: se dibuja como superposición
                # aparte (ver `logo_overlay_block`), fuera del flujo — el
                # contenido que le seguía se recorre hacia arriba, mismo
                # mecanismo que ya existe para ocultar un elemento.
                return []
            width_pt = image_style.width_pt or _LOGO_MAX_WIDTH_PT
            height_pt = image_style.height_pt or _LOGO_MAX_HEIGHT_PT
            return [
                ImageBlock(
                    settings.logo_path,
                    width_pt,
                    height_pt,
                    style_key="logo",
                    image_style=image_style,
                )
            ]
        return []
    if key == "customer" and settings.show_customer:
        blocks: list[Block] = [
            _text(settings, f"Cliente: {data.customer_name}", "normal", "customer_name")
        ]
        if data.customer_document:
            document_text = f"Documento: {data.customer_document}"
            blocks.append(_text(settings, document_text, "normal", "customer_document"))
        return blocks
    if key == "cashier" and settings.show_cashier and data.cashier_name:
        return [_text(settings, f"Cajero: {data.cashier_name}", "normal", "cashier")]
    if key == "register" and settings.show_register and data.register_name:
        return [_text(settings, f"Caja: {data.register_name}", "normal", "register")]
    if key == "date" and settings.show_date:
        return [_text(settings, f"Fecha: {data.date_label}", "normal", "date")]
    if key == "time" and settings.show_time:
        return [_text(settings, f"Hora: {data.time_label}", "normal", "time")]
    if key == "qr" and settings.show_qr:
        image_style = _image_style(settings, "qr")
        size_pt = image_style.width_pt or _QR_SIZE_PT
        return [QrBlock(data.invoice_number, size_pt, style_key="qr", image_style=image_style)]
    if key == "barcode" and settings.show_barcode:
        image_style = _image_style(settings, "barcode")
        width_pt = image_style.width_pt or _BARCODE_WIDTH_PT
        height_pt = image_style.height_pt or _BARCODE_HEIGHT_PT
        return [
            BarcodeBlock(
                data.invoice_number,
                width_pt,
                height_pt,
                style_key="barcode",
                image_style=image_style,
            )
        ]
    if key == "closing_message" and settings.show_closing_message and settings.closing_message:
        return [_text(settings, settings.closing_message, "normal", "closing_message")]
    if key == "social_media" and settings.show_social_media and settings.social_media:
        return [_text(settings, settings.social_media, "normal", "social_media")]
    if key == "return_policy" and settings.show_return_policy and settings.return_policy:
        return [_text(settings, settings.return_policy, "normal", "return_policy")]
    return []


def logo_overlay_block(settings: InvoiceSettingsDTO) -> ImageBlock | None:
    """El logo, cuando el usuario lo posicionó libremente con el mouse
    (`ImageStyle.absolute_x_pt`/`absolute_y_pt` ambos definidos) — se
    dibuja como una superposición aparte, fuera de `build_layout_plan`
    (ver la exclusión en `_content_block_for_key`), en la posición
    absoluta exacta guardada. `None` si el logo está oculto, sin archivo
    configurado, o todavía en el flujo normal — en ese caso el lienzo/PDF
    deben seguir dibujándolo exactamente como siempre, sin llamar a esta
    función. La reutilizan tanto `invoice_canvas_widget.py` (lienzo Qt)
    como `pdf_renderer.py` (PDF real) para no duplicar esta decisión."""
    if not settings.show_logo or not settings.logo_path:
        return None
    image_style = _image_style(settings, "logo")
    if image_style.absolute_x_pt is None or image_style.absolute_y_pt is None:
        return None
    width_pt = image_style.width_pt or _LOGO_MAX_WIDTH_PT
    height_pt = image_style.height_pt or _LOGO_MAX_HEIGHT_PT
    return ImageBlock(
        settings.logo_path, width_pt, height_pt, style_key="logo", image_style=image_style
    )


def _totals_row_for_key(
    key: str, settings: InvoiceSettingsDTO, data: InvoiceRenderData
) -> list[str] | None:
    if key == "subtotal":
        return ["Subtotal", data.subtotal_label]
    if key == "discount" and settings.show_discounts:
        return ["Descuento", data.discount_label]
    if key == "tax" and settings.show_taxes:
        return ["Impuesto", data.tax_label]
    if key == "total" and settings.show_total:
        return ["Total", data.total_label]
    return None


def _merged_totals_block(
    settings: InvoiceSettingsDTO, data: InvoiceRenderData
) -> TableBlock | None:
    """Arma la tabla de totales fusionada en el orden fijo de `_TOTALS_KEYS`
    (Subtotal/Descuento/Impuesto/Total), omitiendo las filas ocultas por su
    `show_*` — posición fija, nunca depende de `content_order`."""
    rows = []
    for key in _TOTALS_KEYS:
        row = _totals_row_for_key(key, settings, data)
        if row is not None:
            rows.append(row)
    if not rows:
        return None
    return TableBlock(
        headers=[],
        rows=rows,
        kind="totals",
        style_key="totals",
        table_style=_table_style(settings, "totals"),
    )


def _items_table_block(settings: InvoiceSettingsDTO, data: InvoiceRenderData) -> TableBlock:
    rows = [
        [
            item.product_name,
            item.quantity,
            item.unit_price,
            item.discount,
            item.tax,
            item.line_total,
        ]
        for item in data.items
    ]
    return TableBlock(
        headers=list(_ITEMS_TABLE_HEADERS),
        rows=rows,
        kind="items",
        style_key="items_table",
        table_style=_table_style(settings, "items_table"),
    )


def _apply_spacing_offsets(blocks: list[Block], offsets: dict[str, float]) -> list[Block]:
    """Micro-posicionamiento del editor visual: para cada `style_key` con
    un offset acumulado, ajusta (o crea) el `SpacerBlock` que precede a la
    *primera* instancia de ese bloque — nunca agrega coordenadas al
    `Block` en sí. `items_table`/`totals` son cada uno una única
    instancia de `TableBlock` (ver `_items_table_block`/
    `_merged_totals_block`), así que "primera instancia" ya identifica el
    bloque completo sin ambigüedad de fila.

    El piso en 0.0 es la única validación que hace falta: un `SpacerBlock`
    nunca puede tener alto negativo, así que dos bloques nunca pueden
    superponerse por un offset agresivo — simplemente deja de moverse
    cuando el hueco disponible se agota (ver también el límite de tope de
    página, que sí depende de la posición acumulada y por eso vive en el
    lienzo interactivo, el único lugar que ya calcula esa posición)."""
    if not offsets:
        return blocks
    result = list(blocks)
    for style_key, offset in offsets.items():
        if not offset:
            continue
        index = next(
            (i for i, block in enumerate(result) if getattr(block, "style_key", None) == style_key),
            None,
        )
        if index is None:
            continue
        preceding = result[index - 1] if index > 0 else None
        if isinstance(preceding, SpacerBlock):
            result[index - 1] = SpacerBlock(height_pt=max(0.0, preceding.height_pt + offset))
        else:
            result.insert(index, SpacerBlock(height_pt=max(0.0, offset)))
    return result


def build_layout_plan(settings: InvoiceSettingsDTO, data: InvoiceRenderData) -> LayoutPlan:
    """Empresa, tabla de productos y tabla de totales tienen posición fija
    (nunca dependen de `content_order`, ver `content_items.py`); el resto
    de las claves de `content_order` se reparte en dos zonas alrededor de
    ese bloque fijo — antes (`HEADER_KEYS`: logo/cliente/cajero/caja/fecha/
    hora) y después (`FOOTER_KEYS`: QR/código de barras/mensaje final/
    redes/política) — cada una reordenable solo dentro de su propia zona,
    nunca mezclable con la otra ni con el bloque fijo."""
    blocks: list[Block] = []

    blocks.extend(_company_header_blocks(settings, data))
    blocks.append(SpacerBlock())

    for key in settings.content_order:
        if key in HEADER_KEYS:
            blocks.extend(_content_block_for_key(key, settings, data))

    blocks.append(SpacerBlock())
    blocks.append(_items_table_block(settings, data))
    blocks.append(SpacerBlock())
    totals_block = _merged_totals_block(settings, data)
    if totals_block is not None:
        blocks.append(totals_block)
        blocks.append(SpacerBlock())

    for key in settings.content_order:
        if key in FOOTER_KEYS:
            blocks.extend(_content_block_for_key(key, settings, data))

    blocks = _apply_spacing_offsets(blocks, settings.template.spacing_offsets)
    return LayoutPlan(page=_page_spec(settings), blocks=blocks)
