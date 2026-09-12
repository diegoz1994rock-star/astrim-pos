"""Generación del PDF de una factura, configurable desde Administración →
Configuración de factura (`InvoiceSettingsDTO`): tamaño de papel, márgenes,
orientación, tamaño de fuente, logo, qué secciones mostrar y en qué orden,
y — desde el editor visual de plantillas — fuente/color/alineación/
espaciado por elemento, estilo de tablas y tamaño/alineación de imágenes.

No decide por sí mismo qué se imprime ni en qué orden — eso lo resuelve
`invoice_settings.domain.layout_plan.build_layout_plan`, el mismo plano que
consume el lienzo interactivo de la vista previa (`invoice_settings/
presentation/invoice_canvas_widget.py`). El PDF real se genera con
`invoice_document_renderer.render_layout_plan_to_pdf`, que dibuja ese mismo
`LayoutPlan` con las mismas funciones de medición/dibujo que ya usa el
lienzo (`shared_ui/invoice_block_rendering.py`) — así el PDF nunca puede
divergir de la vista previa en la posición de un elemento: ambos son el
mismo motor de renderizado, no dos implementaciones calibradas para
parecerse (ver `invoice_settings/domain/layout_plan.py` para el porqué de
este diseño).

"Código de barras" se genera con `python-barcode` (Code128) como una
imagen real — el código de barras real permite que "escalar"/"mover"/
"mostrar"/"ocultar" tengan sentido, pedido explícito del editor visual de
plantillas.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from xml.sax.saxutils import escape as xml_escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from pos.modules.billing.application.dto import InvoiceDTO
from pos.modules.invoice_settings.application.dto import InvoiceSettingsDTO
from pos.modules.invoice_settings.domain.layout_plan import (
    InvoiceLineItem,
    InvoiceRenderData,
    build_layout_plan,
    logo_overlay_block,
)
from pos.modules.products.domain.enums import SaleUnit
from pos.modules.sales.application.dto import SaleDTO, SaleItemDTO
from pos.shared_ui.formatting import format_currency, format_datetime_local
from pos.shared_ui.invoice_document_renderer import render_layout_plan_to_pdf

_DEFAULT_HEADER_BG_HEX = "#2F6FED"
_DEFAULT_GRID_COLOR_HEX = "#DDDDDD"
_DEFAULT_ZEBRA_COLOR_HEX = "#F5F6F8"


def _format_item_quantity(item: SaleItemDTO) -> str:
    """`"2.350 kg"` para líneas por peso, `"2"` para líneas por unidad — el
    PDF debe dejar tan claro como la venta misma que la cantidad es un
    peso, no un conteo de unidades."""
    if item.sale_unit is SaleUnit.WEIGHT:
        return f"{item.quantity} {item.unit_of_measure}"
    return str(item.quantity)


def _format_item_unit_price(item: SaleItemDTO) -> str:
    """Deja explícito que el precio es por unidad de peso (`"$X / kg"`) en
    vez de un precio unitario ambiguo, en líneas por peso."""
    price = format_currency(item.unit_price)
    if item.sale_unit is SaleUnit.WEIGHT:
        return f"{price} / {item.unit_of_measure}"
    return price


def _to_render_data(
    *,
    invoice: InvoiceDTO,
    sale: SaleDTO,
    cashier_name: str | None,
    register_name: str | None,
) -> InvoiceRenderData:
    return InvoiceRenderData(
        invoice_number=invoice.invoice_number,
        issued_at_label=format_datetime_local(invoice.issued_at, "%Y-%m-%d %H:%M"),
        customer_name=invoice.customer_name_snapshot or "Consumidor final",
        customer_document=invoice.customer_document_snapshot,
        cashier_name=cashier_name,
        register_name=register_name,
        date_label=format_datetime_local(sale.created_at, "%d/%m/%Y"),
        time_label=format_datetime_local(sale.created_at, "%I:%M %p"),
        items=[
            InvoiceLineItem(
                product_name=item.product_name,
                quantity=_format_item_quantity(item),
                unit_price=_format_item_unit_price(item),
                discount=format_currency(item.discount_amount),
                tax=format_currency(item.tax_amount),
                line_total=format_currency(item.line_total),
            )
            for item in sale.items
        ],
        subtotal_label=format_currency(sale.subtotal),
        discount_label=format_currency(sale.discount_total),
        tax_label=format_currency(sale.tax_total),
        total_label=format_currency(sale.total),
    )


def render_invoice_pdf(
    *,
    invoice: InvoiceDTO,
    sale: SaleDTO,
    settings: InvoiceSettingsDTO,
    file_path: Path,
    cashier_name: str | None = None,
    register_name: str | None = None,
) -> None:
    data = _to_render_data(
        invoice=invoice,
        sale=sale,
        cashier_name=cashier_name,
        register_name=register_name,
    )
    plan = build_layout_plan(settings, data)
    render_layout_plan_to_pdf(plan, file_path, logo_overlay=logo_overlay_block(settings))


def render_debt_payment_receipt_pdf(
    *,
    file_path: Path,
    company_name: str,
    customer_name: str,
    customer_document: str | None,
    receipt_number: str,
    invoice_number: str,
    items: list[SaleItemDTO],
    amount_paid: Decimal,
    remaining_balance: Decimal,
    paid_at: datetime,
    cashier_name: str | None,
    register_name: str | None,
) -> None:
    """Recibo de un abono a una factura (`BillingService.register_payment`)
    — a propósito NO reutiliza el sistema de plantillas configurables de
    `render_invoice_pdf` (pensado para el documento fiscal de una venta,
    con editor visual propio): esto es un recibo simple de "se abonó X a
    la factura Y", mismo espíritu liviano que `reports/infrastructure/
    exporter.py::export_table_to_pdf` (título + tabla), con un par de
    líneas de encabezado adicionales. Los productos mostrados son los de
    la propia factura (`SaleItemDTO` de `SalesService.get_sale`), no una
    consolidación entre facturas — cada recibo aplica a una sola."""
    file_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    elements: list = [
        Paragraph(company_name, styles["Title"]),
        Paragraph("Recibo de abono", styles["Heading2"]),
        Spacer(1, 8),
        Paragraph(f"N.º de recibo: {xml_escape(receipt_number)}", styles["Normal"]),
        Paragraph(f"Factura abonada: {xml_escape(invoice_number)}", styles["Normal"]),
        Paragraph(f"Cliente: {xml_escape(customer_name)}", styles["Normal"]),
    ]
    if customer_document:
        elements.append(Paragraph(f"Documento: {xml_escape(customer_document)}", styles["Normal"]))
    elements.append(
        Paragraph(f"Fecha: {format_datetime_local(paid_at, '%Y-%m-%d %H:%M')}", styles["Normal"])
    )
    if cashier_name:
        elements.append(Paragraph(f"Cajero: {xml_escape(cashier_name)}", styles["Normal"]))
    if register_name:
        elements.append(Paragraph(f"Caja: {xml_escape(register_name)}", styles["Normal"]))
    elements.append(Spacer(1, 12))

    headers = ["Producto", "Cantidad", "Precio", "Descuento", "Impuesto", "Total"]
    rows = [
        [
            item.product_name,
            _format_item_quantity(item),
            _format_item_unit_price(item),
            format_currency(item.discount_amount),
            format_currency(item.tax_amount),
            format_currency(item.line_total),
        ]
        for item in items
    ]
    table = Table([headers, *rows], repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(_DEFAULT_HEADER_BG_HEX)),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor(_DEFAULT_GRID_COLOR_HEX)),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [colors.white, colors.HexColor(_DEFAULT_ZEBRA_COLOR_HEX)],
                ),
            ]
        )
    )
    elements.append(table)
    elements.append(Spacer(1, 12))
    elements.append(
        Paragraph(f"Valor abonado: {format_currency(amount_paid)}", styles["Heading3"])
    )
    elements.append(
        Paragraph(
            f"Saldo pendiente restante: {format_currency(remaining_balance)}", styles["Normal"]
        )
    )

    doc = SimpleDocTemplate(str(file_path), pagesize=letter)
    doc.build(elements)
