"""Pruebas de integración de ReportsService: cálculo de reportes y
exportación real a PDF/Excel."""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from pathlib import Path

from openpyxl import load_workbook

from pos.modules.reports.domain.enums import ReportFormat
from tests.integration.reports.conftest import ReportsFixtures


def test_sales_report_includes_completed_sale(reports_env: ReportsFixtures) -> None:
    report = reports_env.reports_service.sales_report(reports_env.today, reports_env.today)

    assert report.total_count == 1
    assert report.total_amount == Decimal("4000")
    assert report.rows[0].status == "completed"


def test_sales_report_outside_range_is_empty(reports_env: ReportsFixtures) -> None:
    yesterday = reports_env.today - timedelta(days=5)
    earlier = yesterday - timedelta(days=5)

    report = reports_env.reports_service.sales_report(earlier, yesterday)

    assert report.total_count == 0
    assert report.total_amount == Decimal(0)


def test_product_sales_report_aggregates_quantity_and_revenue(
    reports_env: ReportsFixtures,
) -> None:
    report = reports_env.reports_service.product_sales_report(
        reports_env.today, reports_env.today
    )

    assert len(report.rows) == 1
    assert report.rows[0].sku == "REP-1"
    assert report.rows[0].quantity_sold == Decimal("4")
    assert report.rows[0].revenue == Decimal("4000")


def test_inventory_report_reflects_sale(reports_env: ReportsFixtures) -> None:
    report = reports_env.reports_service.inventory_report()

    row = next(r for r in report.rows if r.sku == "REP-1")
    assert row.quantity == Decimal("46")


def test_product_profit_reflects_completed_sale(reports_env: ReportsFixtures) -> None:
    """Ganancia = precio de venta − costo del catálogo, por unidad
    vendida: 4 unidades × (1000 − 500) = 2000 (ver fixture `REP-1`)."""
    profit = reports_env.reports_service.product_profit(reports_env.today, reports_env.today)

    assert profit == Decimal("2000")


def test_product_profit_outside_range_is_zero(reports_env: ReportsFixtures) -> None:
    yesterday = reports_env.today - timedelta(days=5)
    earlier = yesterday - timedelta(days=5)

    profit = reports_env.reports_service.product_profit(earlier, yesterday)

    assert profit == Decimal(0)


def test_sales_and_profit_chart_daily_includes_todays_bucket(
    reports_env: ReportsFixtures,
) -> None:
    points = reports_env.reports_service.sales_and_profit_chart(
        reports_env.today - timedelta(days=1), reports_env.today, monthly=False
    )

    assert len(points) == 1
    assert points[0].sales_total == Decimal("4000")
    assert points[0].profit_total == Decimal("2000")


def test_sales_and_profit_chart_monthly_groups_by_month(reports_env: ReportsFixtures) -> None:
    month_start = reports_env.today.replace(day=1)
    points = reports_env.reports_service.sales_and_profit_chart(
        month_start, reports_env.today, monthly=True
    )

    assert len(points) == 1
    assert points[0].label == f"{reports_env.today:%Y-%m}"
    assert points[0].sales_total == Decimal("4000")


def test_cash_report_includes_closed_session(reports_env: ReportsFixtures) -> None:
    report = reports_env.reports_service.cash_report(reports_env.today, reports_env.today)

    assert len(report.rows) == 1
    assert report.rows[0].closing_amount == Decimal("14000")
    assert report.rows[0].difference == Decimal("0")


def test_export_to_pdf_creates_a_real_file(reports_env: ReportsFixtures, tmp_path: Path) -> None:
    file_path = tmp_path / "reporte.pdf"

    reports_env.reports_service.export(
        title="Reporte de prueba",
        headers=["Columna A", "Columna B"],
        rows=[["1", "2"], ["3", "4"]],
        file_path=file_path,
        report_format=ReportFormat.PDF,
    )

    assert file_path.exists()
    assert file_path.stat().st_size > 0
    assert file_path.read_bytes().startswith(b"%PDF")


def test_export_to_excel_creates_a_readable_workbook(
    reports_env: ReportsFixtures, tmp_path: Path
) -> None:
    file_path = tmp_path / "reporte.xlsx"

    reports_env.reports_service.export(
        title="Reporte de prueba",
        headers=["Columna A", "Columna B"],
        rows=[["1", "2"], ["3", "4"]],
        file_path=file_path,
        report_format=ReportFormat.EXCEL,
    )

    workbook = load_workbook(file_path)
    sheet = workbook.active
    assert sheet is not None
    assert sheet["A1"].value == "Columna A"
    assert sheet["A2"].value == "1"
