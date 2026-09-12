"""Caso de uso de Ganancias: orquesta `ProfitsRepository` y arma los DTOs
de presentación. Módulo de solo lectura — no muta ningún dato de Ventas,
Inventario, Caja ni Facturación.

Todo el cálculo pesado (sumas, promedios, conteos) ya viene resuelto por
SQL desde el repositorio; acá solo se combinan resultados de varias
consultas (fusión por `product_id` en memoria, sobre listas ya reducidas
por SQL — nunca sobre ventas crudas) y se derivan los Top 10 reordenando
en Python la misma lista de filas por producto ya calculada, para no
repetir la consulta de agregación seis veces."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime
from decimal import Decimal
from pathlib import Path

from pos.core.database.session import session_scope
from pos.modules.profits.application.dto import (
    CategoryProfitGroupDTO,
    ChartSeriesDTO,
    ProductProfitRowDTO,
    ProductSaleHistoryEntryDTO,
    ProfitSummaryDTO,
    TopListEntryDTO,
    TopListsDTO,
)
from pos.modules.profits.application.export_formatting import (
    PRODUCT_ROW_COLUMNS,
    format_quantity,
    product_row_to_strings,
)
from pos.modules.profits.domain.filters import ProfitFilters
from pos.modules.profits.infrastructure.pdf_exporter import export_profits_report_to_pdf
from pos.modules.profits.infrastructure.repository import ProfitsRepository
from pos.modules.reports.infrastructure.exporter import export_table_to_excel

_HEADER_BLUE = "#2F6FED"

_TOP_LIST_SIZE = 10
_PIE_CHART_TOP_N = 8


class ProfitsService:
    def get_summary(
        self, date_from: date, date_to: date, filters: ProfitFilters
    ) -> ProfitSummaryDTO:
        with session_scope() as session:
            row = ProfitsRepository(session).summary(date_from, date_to, filters)
        return ProfitSummaryDTO(
            total_revenue=row.total_revenue,
            total_quantity=row.total_quantity,
            invoice_count=row.invoice_count,
            total_cost=row.total_cost,
            total_profit=row.total_profit,
            avg_margin_pct=row.avg_margin_pct,
            has_missing_cost=row.total_cost is None,
        )

    def get_product_rows(
        self, date_from: date, date_to: date, filters: ProfitFilters
    ) -> list[ProductProfitRowDTO]:
        with session_scope() as session:
            repo = ProfitsRepository(session)
            rows = repo.product_rows(date_from, date_to, filters)
            product_ids = [row.product_id for row in rows]
            stock_by_product = repo.stock_by_product(product_ids, filters.warehouse_id)
            supplier_by_product = repo.latest_supplier_by_product(product_ids)
            top_seller_by_product = repo.top_sellers_by_product(date_from, date_to, filters)

        return [
            self._to_product_row_dto(
                row, stock_by_product, supplier_by_product, top_seller_by_product
            )
            for row in rows
        ]

    def _to_product_row_dto(
        self,
        row,
        stock_by_product: dict[int, Decimal],
        supplier_by_product: dict[int, str],
        top_seller_by_product: dict[int, str],
    ) -> ProductProfitRowDTO:
        missing = row.missing_cost_count > 0
        margin_pct = None
        avg_profit_per_unit = None
        if not missing and row.total_revenue:
            margin_pct = (row.total_profit / row.total_revenue * 100).quantize(Decimal("0.01"))
        if not missing and row.quantity_sold:
            avg_profit_per_unit = (row.total_profit / row.quantity_sold).quantize(Decimal("0.01"))
        return ProductProfitRowDTO(
            product_id=row.product_id,
            code=row.code,
            category_name=row.category_name or "(sin categoría)",
            product_name=row.product_name,
            sale_unit=row.sale_unit,
            quantity_sold=row.quantity_sold,
            avg_purchase_price=None if missing else row.avg_purchase_price,
            avg_sale_price=row.avg_sale_price,
            total_cost=None if missing else row.total_cost,
            total_revenue=row.total_revenue,
            total_profit=None if missing else row.total_profit,
            margin_pct=margin_pct,
            invoice_count=row.invoice_count,
            first_sale_at=row.first_sale_at,
            last_sale_at=row.last_sale_at,
            current_stock=stock_by_product.get(row.product_id, Decimal(0)),
            supplier_name=supplier_by_product.get(row.product_id, "(sin proveedor)"),
            top_seller_name=top_seller_by_product.get(row.product_id, "—"),
            missing_cost=missing,
            min_sale_price=row.min_sale_price,
            max_sale_price=row.max_sale_price,
            avg_profit_per_unit=avg_profit_per_unit,
        )

    def get_category_groups(
        self, date_from: date, date_to: date, filters: ProfitFilters
    ) -> list[CategoryProfitGroupDTO]:
        with session_scope() as session:
            rows = ProfitsRepository(session).category_groups(date_from, date_to, filters)
        result = []
        for row in rows:
            missing = row.missing_cost_count > 0
            result.append(
                CategoryProfitGroupDTO(
                    category_id=row.category_id,
                    category_name=row.category_name or "(sin categoría)",
                    quantity_sold=row.quantity_sold,
                    total_revenue=row.total_revenue,
                    total_cost=None if missing else row.total_cost,
                    total_profit=None if missing else row.total_profit,
                    missing_cost=missing,
                )
            )
        return result

    def get_top_lists(
        self, date_from: date, date_to: date, filters: ProfitFilters
    ) -> TopListsDTO:
        """Deriva los 6 Top 10 reordenando en Python la misma lista de
        productos ya calculada por `get_product_rows` — cero consultas SQL
        adicionales."""
        rows = self.get_product_rows(date_from, date_to, filters)
        with_profit = [row for row in rows if not row.missing_cost]

        def _entries(items, value_fn) -> list[TopListEntryDTO]:
            return [
                TopListEntryDTO(
                    product_id=item.product_id, label=item.product_name, value=value_fn(item)
                )
                for item in items[:_TOP_LIST_SIZE]
            ]

        by_profit = sorted(with_profit, key=lambda r: r.total_profit, reverse=True)
        by_revenue = sorted(rows, key=lambda r: r.total_revenue, reverse=True)
        by_quantity = sorted(rows, key=lambda r: r.quantity_sold, reverse=True)

        return TopListsDTO(
            highest_profit=_entries(by_profit, lambda r: r.total_profit),
            lowest_profit=_entries(list(reversed(by_profit)), lambda r: r.total_profit),
            most_sold=_entries(by_quantity, lambda r: r.quantity_sold),
            least_sold=_entries(list(reversed(by_quantity)), lambda r: r.quantity_sold),
            highest_revenue=_entries(by_revenue, lambda r: r.total_revenue),
            lowest_revenue=_entries(list(reversed(by_revenue)), lambda r: r.total_revenue),
        )

    def get_chart_series(
        self, date_from: date, date_to: date, filters: ProfitFilters
    ) -> ChartSeriesDTO:
        with session_scope() as session:
            repo = ProfitsRepository(session)
            daily_rows = repo.daily_series(date_from, date_to, filters)

        product_rows = self.get_product_rows(date_from, date_to, filters)
        category_groups = self.get_category_groups(date_from, date_to, filters)

        by_quantity = sorted(product_rows, key=lambda r: r.quantity_sold, reverse=True)
        top_products = [
            TopListEntryDTO(product_id=r.product_id, label=r.product_name, value=r.quantity_sold)
            for r in by_quantity[:_PIE_CHART_TOP_N]
        ]

        daily_revenue_by_day: dict[date, Decimal] = defaultdict(lambda: Decimal(0))
        daily_profit_by_day: dict[date, Decimal] = defaultdict(lambda: Decimal(0))
        for sold_at, line_total, line_profit in daily_rows:
            """Igual que `reports_service.bucket_key`: convierte a hora local
            antes de tomar la fecha calendario — de lo contrario una venta
            de noche en UTC-5 ya cruzó medianoche UTC y cae en el día
            calendario equivocado en los gráficos de Ganancias."""
            day = sold_at.astimezone().date() if isinstance(sold_at, datetime) else sold_at
            daily_revenue_by_day[day] += line_total
            if line_profit is not None:
                daily_profit_by_day[day] += line_profit

        sorted_days = sorted(daily_revenue_by_day.keys())
        daily_revenue = [(day, daily_revenue_by_day[day]) for day in sorted_days]

        cumulative = []
        running_total = Decimal(0)
        for day in sorted_days:
            running_total += daily_profit_by_day.get(day, Decimal(0))
            cumulative.append((day, running_total))

        return ChartSeriesDTO(
            top_products_by_quantity=top_products,
            profit_by_category=category_groups,
            daily_revenue=daily_revenue,
            cumulative_profit=cumulative,
        )

    def get_product_history(
        self, product_id: int, date_from: date, date_to: date, filters: ProfitFilters
    ) -> list[ProductSaleHistoryEntryDTO]:
        with session_scope() as session:
            rows = ProfitsRepository(session).product_history(
                product_id, date_from, date_to, filters
            )
        return [
            ProductSaleHistoryEntryDTO(
                sale_id=row.sale_id,
                invoice_number=row.invoice_number,
                customer_name=row.customer_name or "(sin cliente)",
                user_name=row.user_name or "—",
                cash_register_name=row.cash_register_name or "—",
                sold_at=row.sold_at,
                quantity=row.quantity,
                unit_cost=row.unit_cost,
                unit_price=row.unit_price,
                line_profit=row.line_profit,
                sale_unit=row.sale_unit,
            )
            for row in rows
        ]

    def _summary_lines(self, summary: ProfitSummaryDTO) -> list[tuple[str, str]]:
        def _money(value: Decimal | None) -> str:
            return "N/D" if value is None else f"${value:,.2f}"

        return [
            ("Total vendido", f"${summary.total_revenue:,.2f}"),
            (
                "Cantidad total de productos vendidos",
                format_quantity(summary.total_quantity, None),
            ),
            ("Número de facturas", str(summary.invoice_count)),
            ("Costo total", _money(summary.total_cost)),
            ("Ganancia total", _money(summary.total_profit)),
            (
                "Margen promedio",
                "N/D" if summary.avg_margin_pct is None else f"{summary.avg_margin_pct:g}%",
            ),
        ]

    def export_to_excel(
        self,
        date_from: date,
        date_to: date,
        filters: ProfitFilters,
        file_path: Path,
        period_label: str,
    ) -> None:
        rows = self.get_product_rows(date_from, date_to, filters)
        export_table_to_excel(
            title=f"Ganancias {period_label}"[:31],
            headers=PRODUCT_ROW_COLUMNS,
            rows=[product_row_to_strings(row) for row in rows],
            file_path=file_path,
            header_fill_hex=_HEADER_BLUE,
            autofit=True,
        )

    def export_to_pdf(
        self,
        date_from: date,
        date_to: date,
        filters: ProfitFilters,
        file_path: Path,
        *,
        company_name: str,
        logo_path: str | None,
        generated_by: str,
        period_label: str,
        filters_description: str,
    ) -> None:
        summary = self.get_summary(date_from, date_to, filters)
        rows = self.get_product_rows(date_from, date_to, filters)
        export_profits_report_to_pdf(
            file_path=file_path,
            company_name=company_name,
            logo_path=logo_path,
            generated_by=generated_by,
            period_label=period_label,
            filters_description=filters_description,
            summary_lines=self._summary_lines(summary),
            headers=PRODUCT_ROW_COLUMNS,
            rows=[product_row_to_strings(row) for row in rows],
        )
