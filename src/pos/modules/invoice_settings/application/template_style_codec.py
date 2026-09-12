"""(De)serialización de `TemplateConfig` a JSON para la columna
`InvoiceSettings.template_config_json` — nunca lanza: cualquier dato
ausente, corrupto o con claves desconocidas (p. ej. de una versión previa
del editor) se resuelve a valores por defecto en vez de romper la carga
de la configuración de factura."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict

from pos.modules.invoice_settings.domain.template_style import (
    ElementStyle,
    ImageStyle,
    TableStyle,
    TemplateConfig,
)

logger = logging.getLogger(__name__)


def encode_template(template: TemplateConfig) -> str:
    return json.dumps(asdict(template), ensure_ascii=False)


def _decode_element_style(raw: dict) -> ElementStyle:
    fields = ElementStyle()
    try:
        return ElementStyle(
            font_family=raw.get("font_family", fields.font_family),
            font_size_pt=raw.get("font_size_pt", fields.font_size_pt),
            color_hex=raw.get("color_hex", fields.color_hex),
            bold=raw.get("bold", fields.bold),
            italic=bool(raw.get("italic", fields.italic)),
            underline=bool(raw.get("underline", fields.underline)),
            letter_case=raw.get("letter_case", fields.letter_case),
            alignment=raw.get("alignment", fields.alignment),
            line_spacing=float(raw.get("line_spacing", fields.line_spacing)),
            space_before_pt=float(raw.get("space_before_pt", fields.space_before_pt)),
            space_after_pt=float(raw.get("space_after_pt", fields.space_after_pt)),
        )
    except (TypeError, ValueError):
        logger.warning("Estilo de elemento inválido en template_config_json, se ignora: %r", raw)
        return ElementStyle()


def _decode_table_style(raw: dict) -> TableStyle:
    try:
        return TableStyle(
            header_bg_hex=raw.get("header_bg_hex"),
            header_text_color_hex=raw.get("header_text_color_hex"),
            grid_color_hex=raw.get("grid_color_hex"),
            zebra_color_hex=raw.get("zebra_color_hex"),
            row_height_pt=raw.get("row_height_pt"),
            cell_padding_pt=raw.get("cell_padding_pt"),
        )
    except (TypeError, ValueError):
        logger.warning("Estilo de tabla inválido en template_config_json, se ignora: %r", raw)
        return TableStyle()


def _decode_image_style(raw: dict) -> ImageStyle:
    fields = ImageStyle()
    try:
        return ImageStyle(
            align=raw.get("align", fields.align),
            width_pt=raw.get("width_pt"),
            height_pt=raw.get("height_pt"),
            keep_aspect_ratio=bool(raw.get("keep_aspect_ratio", fields.keep_aspect_ratio)),
            absolute_x_pt=raw.get("absolute_x_pt"),
            absolute_y_pt=raw.get("absolute_y_pt"),
        )
    except (TypeError, ValueError):
        logger.warning("Estilo de imagen inválido en template_config_json, se ignora: %r", raw)
        return ImageStyle()


def decode_template(raw: str | None) -> TemplateConfig:
    if not raw:
        return TemplateConfig()
    try:
        payload = json.loads(raw)
        if not isinstance(payload, dict):
            raise ValueError("El JSON de la plantilla no es un objeto.")
    except (json.JSONDecodeError, ValueError):
        logger.warning("template_config_json corrupto, se usa una plantilla vacía.")
        return TemplateConfig()

    element_styles = {
        str(key): _decode_element_style(value)
        for key, value in (payload.get("element_styles") or {}).items()
        if isinstance(value, dict)
    }
    table_styles = {
        str(key): _decode_table_style(value)
        for key, value in (payload.get("table_styles") or {}).items()
        if isinstance(value, dict)
    }
    image_styles = {
        str(key): _decode_image_style(value)
        for key, value in (payload.get("image_styles") or {}).items()
        if isinstance(value, dict)
    }
    spacing_offsets = {
        str(key): float(value)
        for key, value in (payload.get("spacing_offsets") or {}).items()
        if isinstance(value, int | float)
    }
    return TemplateConfig(
        element_styles=element_styles,
        table_styles=table_styles,
        image_styles=image_styles,
        show_grid=bool(payload.get("show_grid", False)),
        spacing_offsets=spacing_offsets,
    )
