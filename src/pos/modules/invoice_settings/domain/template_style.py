"""Modelo de estilo por elemento del editor visual de plantillas de
factura — dominio puro (sin Qt/ReportLab/SQLAlchemy), consumido por
`domain/layout_plan.py` para decorar cada `Block` con una apariencia
concreta, y por `application/template_style_codec.py` para su
persistencia como JSON en una sola columna nueva de `invoice_settings`.

Vive en su propio archivo (en vez de `application/dto.py` o
`domain/layout_plan.py`) para evitar un import circular: `dto.py`
necesita el tipo `TemplateConfig` para su campo `template`, y
`layout_plan.py` necesita tanto `InvoiceSettingsDTO` (de `dto.py`) como
estos tipos de estilo — ambos importan de acá, nunca al revés.

Todo campo es opcional/`None` por diseño: una fila sin ninguna
personalización (`TemplateConfig()` vacío) debe hacer que
`build_layout_plan` produzca exactamente el mismo resultado que antes de
que existiera este módulo — el editor visual solo agrega overrides, nunca
cambia el comportamiento por defecto."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Alignment = Literal["left", "center", "right"]
LetterCase = Literal["none", "upper", "lower"]


@dataclass(frozen=True)
class ElementStyle:
    """Apariencia de un bloque de texto individual (`TextBlock.style_key`).

    `letter_spacing_pt` (espaciado entre letras) se dejó fuera a propósito:
    ReportLab no lo soporta de forma nativa/fiable en `ParagraphStyle`, y
    como la vista previa debe verse exactamente igual que el PDF final,
    implementarlo solo en Qt introduciría una divergencia silenciosa entre
    ambos — se prefirió omitir la propiedad a arriesgar esa garantía."""

    font_family: str | None = None
    font_size_pt: int | None = None
    color_hex: str | None = None
    bold: bool | None = None
    italic: bool = False
    underline: bool = False
    letter_case: LetterCase = "none"
    alignment: Alignment = "left"
    line_spacing: float = 1.0
    space_before_pt: float = 0.0
    space_after_pt: float = 0.0


@dataclass(frozen=True)
class TableStyle:
    """Apariencia de un `TableBlock` (tabla de productos o una fila de
    totales) — `None` en cualquier campo conserva el color/tamaño
    hardcodeado actual de cada renderer."""

    header_bg_hex: str | None = None
    header_text_color_hex: str | None = None
    grid_color_hex: str | None = None
    zebra_color_hex: str | None = None
    row_height_pt: float | None = None
    cell_padding_pt: float | None = None


@dataclass(frozen=True)
class ImageStyle:
    """Apariencia de un `ImageBlock`/`QrBlock`/`BarcodeBlock` — `None` en
    `width_pt`/`height_pt` conserva el tamaño máximo por defecto actual
    (logo, QR o código de barras) de `layout_plan.py`.

    `absolute_x_pt`/`absolute_y_pt`: posición libre (arrastrable con el
    mouse), pensada exclusivamente para el logo — ver
    `layout_plan.py::logo_overlay_block`. `None` en cualquiera de los dos
    (el valor por defecto) significa "todavía en el flujo normal del
    documento", comportamiento idéntico al de siempre; solo cuando AMBOS
    están definidos el elemento se dibuja como una superposición de
    posición absoluta, fuera del flujo. Genérico en el dataclass
    compartido, pero solo la UI del logo lo expone/activa — QR, código de
    barras e imagen de pie nunca los usan."""

    align: Alignment = "center"
    width_pt: float | None = None
    height_pt: float | None = None
    keep_aspect_ratio: bool = True
    absolute_x_pt: float | None = None
    absolute_y_pt: float | None = None


@dataclass(frozen=True)
class TemplateConfig:
    """Conjunto completo de overrides visuales de una plantilla de
    factura. Vacío (todos los diccionarios vacíos) = sin personalización,
    comportamiento idéntico al de antes del editor visual."""

    element_styles: dict[str, ElementStyle] = field(default_factory=dict)
    table_styles: dict[str, TableStyle] = field(default_factory=dict)
    image_styles: dict[str, ImageStyle] = field(default_factory=dict)
    show_grid: bool = False
    spacing_offsets: dict[str, float] = field(default_factory=dict)
    """Micro-posicionamiento vertical por elemento (clave = mismo
    `style_key` que `element_styles`/`table_styles`/`image_styles`; valor
    en puntos, puede ser negativo). No es una coordenada: es un delta que
    `build_layout_plan` suma al hueco (`SpacerBlock`) que ya precede a ese
    bloque — mover un elemento con las flechas del teclado en el editor
    ajusta este valor, nunca las coordenadas del `Block` en sí (ver
    `domain/layout_plan.py::_apply_spacing_offsets`)."""
