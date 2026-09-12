"""Casos de uso de reportes: ventas, productos, inventario, caja, con
exportación a PDF y Excel (PROJECT_SPEC.md, "REPORTES")."""

from __future__ import annotations

from collections import defaultdict
from datetime import date
from decimal import Decimal
from pathlib import Path

from pos.core.database.session import session_scope
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.reports.application.dto import (
    CashReportDTO,
    CashReportRowDTO,
    ChartPointDTO,
    InventoryReportDTO,
    InventoryReportRowDTO,
    ProductSalesReportDTO,
    ProductSalesRowDTO,
    SalesReportDTO,
    SalesReportRowDTO,
)
from pos.modules.reports.domain.enums import ReportFormat
from pos.modules.reports.infrastructure.exporter import export_table_to_excel, export_table_to_pdf
from pos.modules.reports.infrastructure.report_repository import ReportRepository


class ReportsService:
    def __init__(self, inventory_service: InventoryService) -> None:
        self._inventory_service = inventory_service

    def sales_report(self, date_from: date, date_to: date) -> SalesReportDTO:
        with session_scope() as session:
            repo = ReportRepository(session)
            rows = [
                SalesReportRowDTO(
                    sale_id=sale.id,
                    created_at=sale.created_at,
                    status=sale.status.value,
                    customer_name=customer_name,
                    total=sale.total,
                    register_name=register_name,
                )
                for sale, customer_name, register_name in repo.list_sales_in_range(
                    date_from, date_to
                )
            ]
        total_amount = sum((row.total for row in rows), Decimal(0))
        return SalesReportDTO(
            date_from=date_from,
            date_to=date_to,
            rows=rows,
            total_amount=total_amount,
            total_count=len(rows),
        )

    def product_sales_report(self, date_from: date, date_to: date) -> ProductSalesReportDTO:
        with session_scope() as session:
            repo = ReportRepository(session)
            rows = [
                ProductSalesRowDTO(sku=sku, product_name=name, quantity_sold=qty, revenue=revenue)
                for sku, name, qty, revenue in repo.product_sales_in_range(date_from, date_to)
            ]
        return ProductSalesReportDTO(date_from=date_from, date_to=date_to, rows=rows)

    def product_profit(self, date_from: date, date_to: date) -> Decimal:
        """Ganancia real (precio de venta − costo del catálogo) de las
        ventas completadas en el rango — usado por las tarjetas "Ganancias
        del día"/"Ganancias del mes" del Dashboard."""
        with session_scope() as session:
            return ReportRepository(session).product_profit_in_range(date_from, date_to)

    def sales_and_profit_chart(
        self, date_from: date, date_to: date, *, monthly: bool
    ) -> list[ChartPointDTO]:
        """Puntos de ventas+ganancias agrupados por día o por mes — el
        agrupamiento se hace en Python (no con una función de fecha del
        motor de base de datos) para que funcione igual en SQLite,
        Postgres o MySQL."""
        with session_scope() as session:
            repo = ReportRepository(session)
            sale_rows = repo.sale_totals_rows(date_from, date_to)
            profit_rows = repo.sale_item_profit_rows(date_from, date_to)

        def bucket_key(created_at: date) -> str:
            local = created_at.astimezone()
            return f"{local:%Y-%m}" if monthly else f"{local:%Y-%m-%d}"

        sales_by_bucket: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
        for created_at, total in sale_rows:
            sales_by_bucket[bucket_key(created_at)] += total

        profit_by_bucket: dict[str, Decimal] = defaultdict(lambda: Decimal(0))
        for created_at, profit in profit_rows:
            profit_by_bucket[bucket_key(created_at)] += profit

        buckets = sorted(set(sales_by_bucket) | set(profit_by_bucket))
        return [
            ChartPointDTO(
                label=bucket,
                sales_total=sales_by_bucket.get(bucket, Decimal(0)),
                profit_total=profit_by_bucket.get(bucket, Decimal(0)),
            )
            for bucket in buckets
        ]

    def inventory_report(self) -> InventoryReportDTO:
        stock = self._inventory_service.list_stock_overview()
        rows = [
            InventoryReportRowDTO(
                sku=s.product_sku,
                product_name=s.product_name,
                warehouse_name=s.warehouse_name,
                quantity=s.quantity,
                min_quantity=s.min_quantity,
                is_below_minimum=s.is_below_minimum,
            )
            for s in stock
        ]
        return InventoryReportDTO(rows=rows)

    def cash_report(self, date_from: date, date_to: date) -> CashReportDTO:
        with session_scope() as session:
            repo = ReportRepository(session)
            rows = [
                CashReportRowDTO(
                    session_id=cash_session.id,
                    register_name=register_name,
                    opened_at=cash_session.opened_at,
                    closed_at=cash_session.closed_at,
                    opening_amount=cash_session.opening_amount,
                    closing_amount=cash_session.closing_amount,
                    expected_amount=cash_session.expected_amount,
                    difference=cash_session.difference,
                )
                for cash_session, register_name in repo.list_cash_sessions_in_range(
                    date_from, date_to
                )
            ]
        return CashReportDTO(rows=rows)

    def export(
        self,
        *,
        title: str,
        headers: list[str],
        rows: list[list[str]],
        file_path: Path,
        report_format: ReportFormat,
    ) -> None:
        if report_format is ReportFormat.PDF:
            export_table_to_pdf(title=title, headers=headers, rows=rows, file_path=file_path)
        else:
            export_table_to_excel(title=title, headers=headers, rows=rows, file_path=file_path)
