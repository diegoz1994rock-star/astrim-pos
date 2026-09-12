"""Pruebas puras del (de)codificador JSON de `TemplateConfig` — debe ser
completamente defensivo: nada de lo que pueda estar guardado en
`template_config_json` (vacío, corrupto, con claves desconocidas) puede
hacer que cargar la configuración de factura falle."""

from __future__ import annotations

from pos.modules.invoice_settings.application.template_style_codec import (
    decode_template,
    encode_template,
)
from pos.modules.invoice_settings.domain.template_style import (
    ElementStyle,
    ImageStyle,
    TableStyle,
    TemplateConfig,
)


def test_decode_none_returns_empty_template() -> None:
    assert decode_template(None) == TemplateConfig()


def test_decode_empty_string_returns_empty_template() -> None:
    assert decode_template("") == TemplateConfig()


def test_decode_corrupt_json_returns_empty_template_without_raising() -> None:
    assert decode_template("{not valid json") == TemplateConfig()


def test_decode_non_object_json_returns_empty_template() -> None:
    assert decode_template("[1, 2, 3]") == TemplateConfig()


def test_round_trip_element_style() -> None:
    template = TemplateConfig(
        element_styles={
            "company_name": ElementStyle(
                font_family="Arial",
                font_size_pt=14,
                color_hex="#FF0000",
                bold=True,
                italic=True,
                underline=True,
                letter_case="upper",
                alignment="center",
                line_spacing=1.5,
                space_before_pt=4.0,
                space_after_pt=6.0,
            )
        }
    )

    decoded = decode_template(encode_template(template))

    assert decoded == template


def test_round_trip_table_style() -> None:
    template = TemplateConfig(
        table_styles={
            "items_table": TableStyle(
                header_bg_hex="#2F6FED",
                header_text_color_hex="#FFFFFF",
                grid_color_hex="#DDDDDD",
                zebra_color_hex="#F5F6F8",
                row_height_pt=16.0,
                cell_padding_pt=4.0,
            )
        }
    )

    assert decode_template(encode_template(template)) == template


def test_round_trip_image_style() -> None:
    logo_style = ImageStyle(align="right", width_pt=120.0, height_pt=60.0, keep_aspect_ratio=False)
    template = TemplateConfig(image_styles={"logo": logo_style})

    assert decode_template(encode_template(template)) == template


def test_round_trip_image_style_with_absolute_position() -> None:
    """La posición libre del logo (arrastrable con el mouse) debe
    sobrevivir el ciclo completo de guardado/carga — sin esto, el logo
    volvería a su posición de flujo cada vez que se reabre el editor."""
    logo_style = ImageStyle(absolute_x_pt=250.0, absolute_y_pt=140.0)
    template = TemplateConfig(image_styles={"logo": logo_style})

    assert decode_template(encode_template(template)) == template


def test_decode_image_style_without_absolute_position_defaults_to_none() -> None:
    """Una plantilla guardada antes de que existiera esta función (sin
    las claves `absolute_x_pt`/`absolute_y_pt` en el JSON) debe seguir
    cargando el logo en modo de flujo normal, no en una posición
    absoluta inventada."""
    raw = '{"image_styles": {"logo": {"align": "center", "width_pt": 100.0}}}'

    decoded = decode_template(raw)

    assert decoded.image_styles["logo"].absolute_x_pt is None
    assert decoded.image_styles["logo"].absolute_y_pt is None


def test_round_trip_show_grid() -> None:
    template = TemplateConfig(show_grid=True)

    assert decode_template(encode_template(template)) == template


def test_decode_ignores_unknown_top_level_keys() -> None:
    raw = (
        '{"element_styles": {}, "table_styles": {}, "image_styles": {}, '
        '"show_grid": false, "future_field": 123}'
    )

    assert decode_template(raw) == TemplateConfig()


def test_decode_recovers_from_malformed_single_element_style() -> None:
    raw = (
        '{"element_styles": {"company_name": {"line_spacing": "not-a-number"}}, '
        '"table_styles": {}, "image_styles": {}, "show_grid": false}'
    )

    decoded = decode_template(raw)

    assert decoded.element_styles["company_name"] == ElementStyle()
