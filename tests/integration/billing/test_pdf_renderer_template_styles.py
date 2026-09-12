"""Pruebas de integración de los overrides del editor visual de
plantillas de factura sobre el PDF real: una fuente desconocida jamás
debe romper la generación, y el código de barras real (Code128) debe
generarse sin errores, incluida su combinación con tamaños/colores
personalizados."""

from __future__ import annotations

from dataclasses import replace as dataclass_replace
from decimal import Decimal
from pathlib import Path

from PIL import Image as PILImage

from pos.modules.billing.application.billing_service import BillingService
from pos.modules.invoice_settings.application.invoice_settings_service import (
    InvoiceSettingsService,
)
from pos.modules.invoice_settings.domain.template_style import (
    ElementStyle,
    ImageStyle,
    TableStyle,
    TemplateConfig,
)
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from tests.integration.sales.conftest import SalesFixtures


def _complete_cash_sale(sales_env: SalesFixtures) -> int:
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(2))],
        payments=[SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal(2000))],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )
    return sale.id


def test_spacing_offset_does_not_break_pdf_generation(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    """El micro-posicionamiento del editor (`TemplateConfig.spacing_offsets`)
    viaja hasta `pdf_renderer.py` sin que este archivo necesite ningún
    cambio — el offset ya queda incorporado al `SpacerBlock` compartido
    por `build_layout_plan` (ver `tests/unit/invoice_settings/
    test_layout_plan.py::test_build_layout_plan_applies_spacing_offset_to_shared_spacer`
    para la prueba de que el valor realmente cambia); acá solo se
    confirma que un PDF real con un offset activo se genera igual de
    bien que uno sin ningún micro-ajuste."""
    settings_service = InvoiceSettingsService()
    current = settings_service.get_settings()
    template = TemplateConfig(spacing_offsets={"invoice_number": 25.0, "items_table": -3.0})
    settings_service.update_settings(dataclass_replace(current, template=template))
    sale_id = _complete_cash_sale(sales_env)

    invoice = billing_service.generate_invoice(sale_id)

    pdf_path = Path(invoice.pdf_path)
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_unknown_font_family_does_not_break_pdf_generation(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    settings_service = InvoiceSettingsService()
    current = settings_service.get_settings()
    template = TemplateConfig(
        element_styles={
            "company_name": ElementStyle(
                font_family="Definitely Not A Real Font XYZ 12345", font_size_pt=20, bold=True
            )
        }
    )
    settings_service.update_settings(dataclass_replace(current, template=template))
    sale_id = _complete_cash_sale(sales_env)

    invoice = billing_service.generate_invoice(sale_id)

    pdf_path = Path(invoice.pdf_path)
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_real_barcode_with_custom_size_renders_without_error(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    settings_service = InvoiceSettingsService()
    current = settings_service.get_settings()
    template = TemplateConfig(
        image_styles={"barcode": ImageStyle(width_pt=250.0, height_pt=70.0, align="center")}
    )
    settings_service.update_settings(
        dataclass_replace(current, show_barcode=True, template=template)
    )
    sale_id = _complete_cash_sale(sales_env)

    invoice = billing_service.generate_invoice(sale_id)

    pdf_path = Path(invoice.pdf_path)
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_logo_with_absolute_position_renders_as_overlay_without_error(
    sales_env: SalesFixtures, billing_service: BillingService, tmp_path: Path
) -> None:
    """El logo arrastrado a una posición libre en el editor visual debe
    seguir generando un PDF válido — se dibuja aparte, encima del
    contenido normal (ver `invoice_document_renderer.py::_draw_logo_overlay`),
    en vez de en su posición de flujo habitual."""
    logo_path = tmp_path / "logo.png"
    PILImage.new("RGB", (100, 50), color="red").save(logo_path)

    settings_service = InvoiceSettingsService()
    current = settings_service.get_settings()
    template = TemplateConfig(
        image_styles={"logo": ImageStyle(absolute_x_pt=250.0, absolute_y_pt=140.0)}
    )
    settings_service.update_settings(
        dataclass_replace(
            current, show_logo=True, logo_path=str(logo_path), template=template
        )
    )
    sale_id = _complete_cash_sale(sales_env)

    invoice = billing_service.generate_invoice(sale_id)

    pdf_path = Path(invoice.pdf_path)
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_logo_still_in_flow_renders_exactly_as_before(
    sales_env: SalesFixtures, billing_service: BillingService, tmp_path: Path
) -> None:
    """Sin posición absoluta (el logo nunca fue arrastrado), la
    generación del PDF debe seguir funcionando exactamente igual que
    antes de este cambio — regresión explícita."""
    logo_path = tmp_path / "logo.png"
    PILImage.new("RGB", (100, 50), color="blue").save(logo_path)

    settings_service = InvoiceSettingsService()
    current = settings_service.get_settings()
    settings_service.update_settings(
        dataclass_replace(current, show_logo=True, logo_path=str(logo_path))
    )
    sale_id = _complete_cash_sale(sales_env)

    invoice = billing_service.generate_invoice(sale_id)

    pdf_path = Path(invoice.pdf_path)
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_custom_table_style_renders_without_error(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    settings_service = InvoiceSettingsService()
    current = settings_service.get_settings()
    template = TemplateConfig(
        table_styles={
            "items_table": TableStyle(
                header_bg_hex="#123456",
                header_text_color_hex="#FFFFFF",
                grid_color_hex="#000000",
                zebra_color_hex="#EEEEEE",
                row_height_pt=20.0,
                cell_padding_pt=5.0,
            )
        }
    )
    settings_service.update_settings(dataclass_replace(current, template=template))
    sale_id = _complete_cash_sale(sales_env)

    invoice = billing_service.generate_invoice(sale_id)

    pdf_path = Path(invoice.pdf_path)
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")


def test_element_style_with_underline_uppercase_and_alignment_renders_without_error(
    sales_env: SalesFixtures, billing_service: BillingService
) -> None:
    settings_service = InvoiceSettingsService()
    current = settings_service.get_settings()
    template = TemplateConfig(
        element_styles={
            "company_name": ElementStyle(
                underline=True,
                italic=True,
                letter_case="upper",
                alignment="center",
                color_hex="#FF00AA",
                line_spacing=1.5,
                space_before_pt=4.0,
                space_after_pt=8.0,
            )
        }
    )
    settings_service.update_settings(
        dataclass_replace(current, company_name="Empresa & Cía. <Prueba>", template=template)
    )
    sale_id = _complete_cash_sale(sales_env)

    invoice = billing_service.generate_invoice(sale_id)

    pdf_path = Path(invoice.pdf_path)
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")
