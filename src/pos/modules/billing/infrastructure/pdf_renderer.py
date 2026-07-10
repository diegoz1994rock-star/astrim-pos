"""Generación del PDF de una factura.

No reutiliza `reports/infrastructure/exporter.py::export_table_to_pdf` tal
cual: ese exportador solo sabe dibujar título + una tabla, y una factura
necesita además un bloque de datos del negocio, uno de datos del cliente y
un resumen de totales — forzar eso dentro de una sola tabla genérica habría
dado un PDF de mala calidad para lo que en la mayoría de países es un
documento con valor fiscal. Sí reutiliza la misma librería (ReportLab) y el
mismo estilo de tabla (encabezado azul, filas alternadas) para que el
resultado se sienta parte de la misma familia visual que los reportes.
"""

from __future__ import annotations

from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from pos.modules.billing.application.dto import InvoiceDTO
from pos.modules.sales.application.dto import SaleDTO

_TABLE_STYLE = TableStyle(
    [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2F6FED")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F5F6F8")]),
    ]
)


def render_invoice_pdf(
    *, invoice: InvoiceDTO, sale: SaleDTO, business_name: str, file_path: Path
) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    elements = [
        Paragraph(business_name, styles["Title"]),
        Paragraph(f"Factura N.º {invoice.invoice_number}", styles["Heading2"]),
        Paragraph(f"Fecha de emisión: {invoice.issued_at:%Y-%m-%d %H:%M}", styles["Normal"]),
        Spacer(1, 12),
        Paragraph(
            f"Cliente: {invoice.customer_name_snapshot or 'Consumidor final'}", styles["Normal"]
        ),
    ]
    if invoice.customer_document_snapshot:
        elements.append(
            Paragraph(f"Documento: {invoice.customer_document_snapshot}", styles["Normal"])
        )
    elements.append(Spacer(1, 12))

    headers = ["Producto", "Cantidad", "Precio unit.", "Descuento", "Impuesto", "Total línea"]
    rows = [
        [
            item.product_name,
            str(item.quantity),
            f"{item.unit_price:.2f}",
            f"{item.discount_amount:.2f}",
            f"{item.tax_amount:.2f}",
            f"{item.line_total:.2f}",
        ]
        for item in sale.items
    ]
    table = Table([headers, *rows], repeatRows=1)
    table.setStyle(_TABLE_STYLE)
    elements.append(table)
    elements.append(Spacer(1, 12))

    totals_table = Table(
        [
            ["Subtotal", f"{sale.subtotal:.2f}"],
            ["Descuento", f"{sale.discount_total:.2f}"],
            ["Impuesto", f"{sale.tax_total:.2f}"],
            ["Total", f"{sale.total:.2f}"],
        ],
        colWidths=[100, 100],
    )
    totals_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 3), (-1, 3), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#DDDDDD")),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    elements.append(totals_table)

    doc = SimpleDocTemplate(str(file_path), pagesize=letter)
    doc.build(elements)
