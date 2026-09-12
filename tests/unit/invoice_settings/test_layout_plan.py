"""Pruebas puras (sin DB, sin Qt) del plano de layout compartido entre el
PDF real y la vista previa — la garantía de que ambos renderers nunca
puedan divergir en contenido/orden/tamaño de página vive en que los dos
consumen exactamente el mismo `LayoutPlan`, así que estas pruebas son la
única red de regresión posible para esa fidelidad."""

from __future__ import annotations

from dataclasses import fields, replace

from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.domain.enums import Orientation, PaperSize
from pos.modules.invoice_settings.domain.layout_plan import (
    BarcodeBlock,
    ImageBlock,
    InvoiceLineItem,
    InvoiceRenderData,
    QrBlock,
    SpacerBlock,
    TableBlock,
    TextBlock,
    _apply_spacing_offsets,
    build_layout_plan,
    logo_overlay_block,
)
from pos.modules.invoice_settings.domain.template_style import (
    ElementStyle,
    ImageStyle,
    TableStyle,
    TemplateConfig,
)

_DATA = InvoiceRenderData(
    invoice_number="F-000001",
    issued_at_label="2026-07-13 10:00",
    customer_name="Juan Pérez",
    customer_document=None,
    cashier_name="Ana Cajera",
    register_name="Caja 1",
    date_label="13/07/2026",
    time_label="10:00 a. m.",
    items=[InvoiceLineItem("Café", "2", "5.000", "0", "950", "10.950")],
    subtotal_label="10.000",
    discount_label="0",
    tax_label="950",
    total_label="10.950",
)


def _settings(**overrides) -> InvoiceSettingsDTO:
    return replace(InvoiceSettingsDTO(company_name="Mi Negocio"), **overrides)


def test_totals_table_always_present_right_after_items_table() -> None:
    plan = build_layout_plan(_settings(), _DATA)

    table_blocks = [b for b in plan.blocks if isinstance(b, TableBlock)]
    assert len(table_blocks) == 2
    assert table_blocks[0].kind == "items"
    assert table_blocks[1].kind == "totals"


def test_totals_rows_respect_show_flags() -> None:
    plan = build_layout_plan(
        _settings(show_discounts=False, show_taxes=False, show_total=True), _DATA
    )

    totals = next(b for b in plan.blocks if isinstance(b, TableBlock) and b.kind == "totals")
    labels = [row[0] for row in totals.rows]
    assert labels == ["Subtotal", "Total"]


def test_hidden_sections_produce_no_block() -> None:
    plan = build_layout_plan(
        _settings(show_qr=False, show_barcode=False, show_cashier=False), _DATA
    )

    assert not any(isinstance(b, QrBlock) for b in plan.blocks)
    assert not any(isinstance(b, BarcodeBlock) for b in plan.blocks)
    assert not any(isinstance(b, TextBlock) and b.text.startswith("Cajero:") for b in plan.blocks)


def test_shown_sections_produce_their_block() -> None:
    plan = build_layout_plan(_settings(show_qr=True, show_barcode=True), _DATA)

    qr_blocks = [b for b in plan.blocks if isinstance(b, QrBlock)]
    barcode_blocks = [b for b in plan.blocks if isinstance(b, BarcodeBlock)]
    assert len(qr_blocks) == 1
    assert qr_blocks[0].data == "F-000001"
    assert len(barcode_blocks) == 1
    assert barcode_blocks[0].text == "F-000001"


def test_content_order_determines_header_block_sequence() -> None:
    settings = _settings(
        content_order=["time", "date", "customer", "cashier", "register", "logo", "qr", "barcode",
                        "closing_message", "social_media", "return_policy"],
        show_qr=True,
    )
    plan = build_layout_plan(settings, _DATA)

    text_blocks_in_order = [
        b.text for b in plan.blocks
        if isinstance(b, TextBlock) and b.text.split(":")[0] in ("Hora", "Fecha", "Cliente", "Cajero", "Caja")
    ]
    assert text_blocks_in_order == [
        "Hora: 10:00 a. m.",
        "Fecha: 13/07/2026",
        "Cliente: Juan Pérez",
        "Cajero: Ana Cajera",
        "Caja: Caja 1",
    ]


# -- micro-posicionamiento (_apply_spacing_offsets) --------------------------


def test_apply_spacing_offsets_grows_existing_leading_spacer() -> None:
    blocks = [
        TextBlock("A", style_key="a"),
        SpacerBlock(height_pt=12.0),
        TextBlock("B", style_key="b"),
    ]

    result = _apply_spacing_offsets(blocks, {"b": 7.0})

    assert result[1] == SpacerBlock(height_pt=19.0)
    assert len(result) == 3


def test_apply_spacing_offsets_shrinks_existing_leading_spacer() -> None:
    blocks = [
        TextBlock("A", style_key="a"),
        SpacerBlock(height_pt=12.0),
        TextBlock("B", style_key="b"),
    ]

    result = _apply_spacing_offsets(blocks, {"b": -5.0})

    assert result[1] == SpacerBlock(height_pt=7.0)


def test_apply_spacing_offsets_never_goes_negative() -> None:
    """Empujar un elemento hacia arriba más de lo que su hueco permite se
    limita automáticamente en 0 — nunca superposición, nunca espacio
    negativo, sin que haga falta ninguna validación aparte."""
    blocks = [
        TextBlock("A", style_key="a"),
        SpacerBlock(height_pt=12.0),
        TextBlock("B", style_key="b"),
    ]

    result = _apply_spacing_offsets(blocks, {"b": -999.0})

    assert result[1] == SpacerBlock(height_pt=0.0)


def test_apply_spacing_offsets_inserts_spacer_when_none_precedes() -> None:
    """Dos bloques de texto consecutivos (sin `SpacerBlock` entre ellos,
    ej. dos líneas de encabezado seguidas) no tienen ningún hueco que
    ajustar — la primera vez que se micro-posiciona uno, se inserta un
    `SpacerBlock` nuevo en vez de tocar el bloque anterior."""
    blocks = [TextBlock("A", style_key="a"), TextBlock("B", style_key="b")]

    result = _apply_spacing_offsets(blocks, {"b": 4.0})

    assert len(result) == 3
    assert result[1] == SpacerBlock(height_pt=4.0)
    assert result[0].style_key == "a"
    assert result[2].style_key == "b"


def test_apply_spacing_offsets_on_first_block_of_the_page() -> None:
    blocks = [TextBlock("A", style_key="a"), TextBlock("B", style_key="b")]

    result = _apply_spacing_offsets(blocks, {"a": 3.0})

    assert result[0] == SpacerBlock(height_pt=3.0)
    assert result[1].style_key == "a"


def test_apply_spacing_offsets_ignores_unknown_style_key() -> None:
    blocks = [TextBlock("A", style_key="a")]

    result = _apply_spacing_offsets(blocks, {"does_not_exist": 5.0})

    assert result == blocks


def test_apply_spacing_offsets_ignores_zero_offset() -> None:
    blocks = [
        TextBlock("A", style_key="a"),
        SpacerBlock(height_pt=12.0),
        TextBlock("B", style_key="b"),
    ]

    result = _apply_spacing_offsets(blocks, {"b": 0.0})

    assert result == blocks


def test_apply_spacing_offsets_targets_only_first_instance_of_a_shared_style_key() -> None:
    """`items_table`/`totals` son cada uno una única instancia de
    `TableBlock` en el plano real, pero esta prueba confirma el
    comportamiento genérico: si un `style_key` apareciera más de una vez,
    solo la primera aparición recibe el ajuste."""
    blocks = [
        SpacerBlock(height_pt=12.0),
        TextBlock("A", style_key="shared"),
        TextBlock("A2", style_key="shared"),
    ]

    result = _apply_spacing_offsets(blocks, {"shared": 5.0})

    assert result[0] == SpacerBlock(height_pt=17.0)
    assert len(result) == 3


def test_build_layout_plan_applies_spacing_offset_to_shared_spacer() -> None:
    """Prueba de extremo a extremo (a través de `build_layout_plan`, no
    llamando a `_apply_spacing_offsets` directo): el offset guardado en
    `TemplateConfig.spacing_offsets` efectivamente cambia el
    `SpacerBlock` que ya separaba el encabezado de la tabla de
    productos — el mismo `LayoutPlan` que consume tanto el lienzo como
    el PDF real, así que esto ya prueba la paridad entre ambos."""
    baseline_plan = build_layout_plan(_settings(), _DATA)
    baseline_spacer = next(
        b for i, b in enumerate(baseline_plan.blocks)
        if isinstance(b, SpacerBlock) and isinstance(baseline_plan.blocks[i + 1], TableBlock)
    )

    settings = _settings(template=TemplateConfig(spacing_offsets={"items_table": 6.0}))
    plan = build_layout_plan(settings, _DATA)
    adjusted_spacer = next(
        b for i, b in enumerate(plan.blocks)
        if isinstance(b, SpacerBlock) and isinstance(plan.blocks[i + 1], TableBlock)
    )

    assert adjusted_spacer.height_pt == baseline_spacer.height_pt + 6.0


def test_custom_paper_size_uses_custom_dimensions() -> None:
    settings = _settings(
        paper_size=PaperSize.CUSTOM, custom_width_mm=100.0, custom_height_mm=150.0
    )
    plan = build_layout_plan(settings, _DATA)

    assert plan.page.width_mm == 100.0
    assert plan.page.height_mm == 150.0


def test_landscape_orientation_swaps_width_and_height() -> None:
    portrait_plan = build_layout_plan(_settings(paper_size=PaperSize.A4), _DATA)
    landscape_plan = build_layout_plan(
        _settings(paper_size=PaperSize.A4, orientation=Orientation.LANDSCAPE), _DATA
    )

    assert landscape_plan.page.width_mm == portrait_plan.page.height_mm
    assert landscape_plan.page.height_mm == portrait_plan.page.width_mm


def test_page_spec_carries_margins_and_font_size() -> None:
    settings = _settings(
        margin_top_mm=5.0, margin_right_mm=6.0, margin_bottom_mm=7.0, margin_left_mm=9.0,
        base_font_size_pt=14,
    )
    plan = build_layout_plan(settings, _DATA)

    assert plan.page.margin_top_mm == 5.0
    assert plan.page.margin_right_mm == 6.0
    assert plan.page.margin_bottom_mm == 7.0
    assert plan.page.margin_left_mm == 9.0
    assert plan.page.base_font_size_pt == 14


def test_logo_block_only_when_shown_and_path_set() -> None:
    without_logo = build_layout_plan(_settings(show_logo=True, logo_path=None), _DATA)
    with_logo = build_layout_plan(
        _settings(show_logo=True, logo_path="/tmp/logo.png"), _DATA
    )

    assert not any(isinstance(b, ImageBlock) for b in without_logo.blocks)
    logo_blocks = [b for b in with_logo.blocks if isinstance(b, ImageBlock)]
    assert len(logo_blocks) == 1
    assert logo_blocks[0].path == "/tmp/logo.png"


def test_logo_overlay_block_is_none_when_hidden() -> None:
    settings = _settings(
        show_logo=False,
        logo_path="/tmp/logo.png",
        template=TemplateConfig(
            image_styles={"logo": ImageStyle(absolute_x_pt=10.0, absolute_y_pt=20.0)}
        ),
    )
    assert logo_overlay_block(settings) is None


def test_logo_overlay_block_is_none_without_path() -> None:
    settings = _settings(
        show_logo=True,
        logo_path=None,
        template=TemplateConfig(
            image_styles={"logo": ImageStyle(absolute_x_pt=10.0, absolute_y_pt=20.0)}
        ),
    )
    assert logo_overlay_block(settings) is None


def test_logo_overlay_block_is_none_while_still_in_flow() -> None:
    """Sin `absolute_x_pt`/`absolute_y_pt` (nunca arrastrado), el logo
    sigue en el flujo normal — no hay superposición que dibujar."""
    settings = _settings(show_logo=True, logo_path="/tmp/logo.png")
    assert logo_overlay_block(settings) is None


def test_logo_overlay_block_returns_image_block_when_absolute_position_set() -> None:
    settings = _settings(
        show_logo=True,
        logo_path="/tmp/logo.png",
        template=TemplateConfig(
            image_styles={"logo": ImageStyle(absolute_x_pt=250.0, absolute_y_pt=140.0)}
        ),
    )
    overlay = logo_overlay_block(settings)
    assert overlay is not None
    assert overlay.path == "/tmp/logo.png"
    assert overlay.style_key == "logo"
    assert overlay.image_style.absolute_x_pt == 250.0
    assert overlay.image_style.absolute_y_pt == 140.0


def test_logo_excluded_from_flow_only_when_absolute_position_set() -> None:
    """El logo con posición absoluta no debe aparecer también en
    `plan.blocks` — si apareciera en los dos lados se dibujaría dos
    veces (una en flujo, otra en superposición)."""
    in_flow = build_layout_plan(_settings(show_logo=True, logo_path="/tmp/logo.png"), _DATA)
    absolute = build_layout_plan(
        _settings(
            show_logo=True,
            logo_path="/tmp/logo.png",
            template=TemplateConfig(
                image_styles={"logo": ImageStyle(absolute_x_pt=250.0, absolute_y_pt=140.0)}
            ),
        ),
        _DATA,
    )

    assert any(
        isinstance(b, ImageBlock) and b.style_key == "logo" for b in in_flow.blocks
    )
    assert not any(
        isinstance(b, ImageBlock) and b.style_key == "logo" for b in absolute.blocks
    )


def test_invoice_render_data_has_no_interface_settings_field() -> None:
    """Blinda la separación de arquitectura entre Configuración de
    interfaz y Configuración de factura: `InvoiceRenderData` (lo único que
    `build_layout_plan` puede leer para armar el documento) nunca puede
    volver a tener un campo que permita colar la imagen del Dashboard (o
    cualquier otro recurso de interfaz) en una factura."""
    field_names = {f.name for f in fields(InvoiceRenderData)}
    assert "background_image_path" not in field_names


def test_build_layout_plan_never_emits_a_background_image_block() -> None:
    """Ningún bloque del plan puede provenir de Configuración de interfaz
    — sin un campo `background_image_path` en `InvoiceRenderData`
    (verificado arriba), `_content_block_for_key` tampoco puede producir
    un bloque con esa clave de estilo, así que esta prueba queda como una
    segunda red de regresión sobre el `LayoutPlan` resultante."""
    plan = build_layout_plan(_settings(show_qr=True, show_barcode=True), _DATA)

    assert not any(getattr(block, "style_key", None) == "background_image" for block in plan.blocks)


def _by_style_key(blocks, key):
    return next(b for b in blocks if getattr(b, "style_key", None) == key)


def test_blocks_carry_expected_style_keys() -> None:
    plan = build_layout_plan(_settings(show_qr=True, show_barcode=True), _DATA)

    style_keys = {getattr(b, "style_key", None) for b in plan.blocks}
    assert "company_name" in style_keys
    assert "invoice_number" in style_keys
    assert "customer_name" in style_keys
    assert "items_table" in style_keys
    assert "totals" in style_keys
    assert "qr" in style_keys
    assert "barcode" in style_keys


def test_empty_template_produces_default_no_op_styles() -> None:
    """Una fila sin ninguna personalización (`TemplateConfig()` vacío,
    valor por defecto de `InvoiceSettingsDTO.template`) debe producir
    bloques cuyos overrides sean exactamente los valores por defecto de
    `ElementStyle`/`TableStyle`/`ImageStyle` — la garantía de que el
    editor visual nunca cambia el render de una factura no personalizada."""
    plan = build_layout_plan(_settings(), _DATA)

    company_name_block = _by_style_key(plan.blocks, "company_name")
    assert company_name_block.element_style == ElementStyle()

    items_table = _by_style_key(plan.blocks, "items_table")
    assert items_table.table_style == TableStyle()


def test_element_style_override_is_attached_to_the_matching_block() -> None:
    override = ElementStyle(font_size_pt=24, color_hex="#FF0000", bold=True)
    template = TemplateConfig(element_styles={"company_name": override})
    plan = build_layout_plan(_settings(template=template), _DATA)

    company_name_block = _by_style_key(plan.blocks, "company_name")
    assert company_name_block.element_style.font_size_pt == 24
    assert company_name_block.element_style.color_hex == "#FF0000"
    assert company_name_block.element_style.bold is True

    # otros bloques de texto no se ven afectados por un override de otro estilo.
    invoice_number_block = _by_style_key(plan.blocks, "invoice_number")
    assert invoice_number_block.element_style == ElementStyle()


def test_table_style_override_is_attached_to_the_matching_table() -> None:
    template = TemplateConfig(table_styles={"items_table": TableStyle(header_bg_hex="#123456")})
    plan = build_layout_plan(_settings(template=template), _DATA)

    items_table = _by_style_key(plan.blocks, "items_table")
    assert items_table.table_style.header_bg_hex == "#123456"

    totals_block = _by_style_key(plan.blocks, "totals")
    assert totals_block.table_style == TableStyle()


def test_image_style_override_applies_to_qr_size_and_alignment() -> None:
    template = TemplateConfig(image_styles={"qr": ImageStyle(align="left", width_pt=150.0)})
    plan = build_layout_plan(_settings(show_qr=True, template=template), _DATA)

    qr_block = next(b for b in plan.blocks if isinstance(b, QrBlock))
    assert qr_block.size_pt == 150.0
    assert qr_block.image_style.align == "left"


def test_totals_rows_always_render_in_fixed_order_regardless_of_content_order() -> None:
    """subtotal/discount/tax/total ya no son claves de `content_order` —
    su posición (siempre junto a la tabla de productos) y el orden de sus
    filas dentro de la tabla fusionada son fijos, sin importar qué
    contenga `content_order` (acá incluso con claves obsoletas que ya no
    existen — se ignoran, ver `content_items.py`)."""
    settings = _settings(
        content_order=[
            "company", "logo", "customer", "cashier", "register", "date", "time",
            "items_table", "total", "tax", "discount", "subtotal",
            "qr", "barcode", "closing_message", "social_media", "return_policy",
        ]
    )
    plan = build_layout_plan(settings, _DATA)

    table_blocks = [b for b in plan.blocks if isinstance(b, TableBlock)]
    assert len(table_blocks) == 2
    totals = table_blocks[1]
    assert [row[0] for row in totals.rows] == ["Subtotal", "Descuento", "Impuesto", "Total"]


def test_totals_keys_scattered_non_contiguously_still_produce_one_table() -> None:
    """Si el usuario arrastrara algo entre dos claves de totales, de todas
    formas se emite una sola tabla combinada (en la posición de la
    primera clave de totales encontrada), no varias tablas sueltas."""
    settings = _settings(
        content_order=[
            "company", "items_table", "subtotal", "qr", "discount", "tax", "total",
            "logo", "customer", "cashier", "register", "date", "time",
            "barcode", "closing_message", "social_media", "return_policy",
        ],
        show_qr=True,
    )
    plan = build_layout_plan(settings, _DATA)

    table_blocks = [b for b in plan.blocks if isinstance(b, TableBlock)]
    assert len(table_blocks) == 2
    row_labels = [row[0] for row in table_blocks[1].rows]
    assert row_labels == ["Subtotal", "Descuento", "Impuesto", "Total"]
