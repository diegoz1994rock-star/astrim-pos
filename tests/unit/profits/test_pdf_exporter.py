"""Prueba de humo del exportador PDF de Ganancias: debe generar un PDF
real y válido, con y sin logo (uno inexistente nunca debe romper la
generación, mismo principio que `billing/infrastructure/pdf_renderer.py`)."""

from __future__ import annotations

from pathlib import Path

from pos.modules.profits.infrastructure.pdf_exporter import export_profits_report_to_pdf


def test_generates_valid_pdf_without_logo(tmp_path: Path) -> None:
    file_path = tmp_path / "ganancias.pdf"

    export_profits_report_to_pdf(
        file_path=file_path,
        company_name="Ferretería El Tornillo",
        logo_path=None,
        generated_by="admin",
        period_label="Diario: 2026-07-16",
        filters_description="Sin filtros",
        summary_lines=[("Total vendido", "$1,000"), ("Ganancia total", "$500")],
        headers=["Código", "Producto", "Cantidad"],
        rows=[["SKU-1", "Martillo", "3"]],
    )

    assert file_path.exists()
    assert file_path.read_bytes().startswith(b"%PDF")


def test_missing_logo_file_does_not_break_generation(tmp_path: Path) -> None:
    file_path = tmp_path / "ganancias.pdf"

    export_profits_report_to_pdf(
        file_path=file_path,
        company_name="Ferretería El Tornillo",
        logo_path="/nonexistent/logo.png",
        generated_by="admin",
        period_label="Mensual: julio 2026",
        filters_description="Categoría=Herramientas",
        summary_lines=[("Total vendido", "$1,000")],
        headers=["Código", "Producto"],
        rows=[["SKU-1", "Martillo"]],
    )

    assert file_path.exists()
    assert file_path.read_bytes().startswith(b"%PDF")
