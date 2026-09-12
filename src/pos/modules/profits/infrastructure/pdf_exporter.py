"""Exportación "profesional" de Ganancias a PDF: encabezado con logo y
datos de la empresa, fecha de generación, usuario, período, filtros
aplicados, resumen, tabla completa, totales, numeración de páginas y pie
de página — ver sección "EXPORTAR PDF" del pedido del módulo.

Reutiliza la misma paleta (`#2F6FED`) y estructura de tabla que
`reports/infrastructure/exporter.py::export_table_to_pdf`, pero con un
encabezado más elaborado (no se reutiliza esa función directamente por
eso); el resolutor de fuentes/logo sigue el mismo patrón defensivo de
`billing/infrastructure/pdf_renderer.py` (nunca falla la generación por
un logo faltante o inválido)."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

_HEADER_BLUE = colors.HexColor("#2F6FED")
_ROW_ALT = colors.HexColor("#F5F6F8")
_GRID_GRAY = colors.HexColor("#DDDDDD")


def _footer(canvas, doc) -> None:  # noqa: ANN001 - firma exigida por ReportLab
    canvas.saveState()
    canvas.setFont("Helvetica", 8)
    canvas.setFillColor(colors.grey)
    canvas.drawString(20 * mm, 12 * mm, "Ganancias — reporte generado por el sistema POS")
    canvas.drawRightString(letter[0] - 20 * mm, 12 * mm, f"Página {doc.page}")
    canvas.restoreState()


def export_profits_report_to_pdf(
    *,
    file_path: Path,
    company_name: str,
    logo_path: str | None,
    generated_by: str,
    period_label: str,
    filters_description: str,
    summary_lines: list[tuple[str, str]],
    headers: list[str],
    rows: list[list[str]],
) -> None:
    file_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title_style = styles["Title"]
    normal_style = styles["Normal"]
    small_style = ParagraphStyle("small", parent=normal_style, fontSize=9, textColor=colors.grey)

    elements: list = []

    if logo_path:
        logo_file = Path(logo_path)
        if logo_file.is_file():
            try:
                elements.append(Image(str(logo_file), width=35 * mm, height=20 * mm))
                elements.append(Spacer(1, 6))
            except Exception:  # noqa: BLE001 - un logo inválido nunca debe romper el PDF
                pass

    elements.append(Paragraph(company_name, title_style))
    elements.append(Paragraph("Reporte de Ganancias", styles["Heading2"]))
    elements.append(
        Paragraph(
            f"Generado el {datetime.now():%Y-%m-%d %H:%M} por {generated_by}", small_style
        )
    )
    elements.append(Paragraph(f"Período: {period_label}", small_style))
    elements.append(Paragraph(f"Filtros aplicados: {filters_description}", small_style))
    elements.append(Spacer(1, 12))

    elements.append(Paragraph("Resumen general", styles["Heading3"]))
    summary_table = Table(
        [[label, value] for label, value in summary_lines], colWidths=[70 * mm, 70 * mm]
    )
    summary_table.setStyle(
        TableStyle(
            [
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, _GRID_GRAY),
                ("ROWBACKGROUNDS", (0, 0), (-1, -1), [colors.white, _ROW_ALT]),
            ]
        )
    )
    elements.append(summary_table)
    elements.append(Spacer(1, 16))

    elements.append(Paragraph("Detalle por producto", styles["Heading3"]))
    table_data = [headers, *rows]
    detail_table = Table(table_data, repeatRows=1)
    detail_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("GRID", (0, 0), (-1, -1), 0.5, _GRID_GRAY),
                ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _ROW_ALT]),
            ]
        )
    )
    elements.append(detail_table)

    doc = SimpleDocTemplate(
        str(file_path),
        pagesize=letter,
        topMargin=15 * mm,
        bottomMargin=20 * mm,
    )
    doc.build(elements, onFirstPage=_footer, onLaterPages=_footer)
