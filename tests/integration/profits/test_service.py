"""Pruebas de integración de `ProfitsService`: fusión de resultados de
varias consultas del repositorio en un solo DTO por producto, derivación
de Top 10 y series de gráficos sin consultas SQL adicionales."""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from pos.core.database.session import session_scope
from pos.modules.profits.application.export_formatting import product_row_to_strings
from pos.modules.profits.application.profits_service import ProfitsService
from pos.modules.profits.domain.filters import ProfitFilters
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from tests.integration.sales.conftest import SalesFixtures

_TODAY = date.today()
_RANGE_FROM = _TODAY - timedelta(days=7)
_RANGE_TO = _TODAY + timedelta(days=1)


def _complete_sale(sales_env: SalesFixtures, quantity: Decimal, unit_price: Decimal) -> int:
    payment = SalePaymentInput(payment_method=PaymentMethod.CASH, amount=unit_price * quantity)
    sale = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=quantity)],
        payments=[payment],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )
    return sale.id


def test_get_summary_reflects_completed_sales(sales_env: SalesFixtures) -> None:
    _complete_sale(sales_env, Decimal(2), Decimal("1000"))

    service = ProfitsService()
    summary = service.get_summary(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert summary.total_revenue == Decimal(2000)
    assert summary.total_profit == Decimal(1000)  # (1000-500)*2
    assert summary.has_missing_cost is False


def test_get_product_rows_merges_stock_supplier_and_top_seller(sales_env: SalesFixtures) -> None:
    _complete_sale(sales_env, Decimal(3), Decimal("1000"))

    service = ProfitsService()
    rows = service.get_product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert len(rows) == 1
    row = rows[0]
    assert row.current_stock == Decimal(97)  # 100 - 3
    assert row.top_seller_name == "Cajero de Ventas"
    assert row.missing_cost is False
    assert row.margin_pct == Decimal("50.00")  # (1500-500*3)/1500 = 50%


def test_quantity_sold_renders_as_plain_integer_for_unit_sold_products(
    sales_env: SalesFixtures,
) -> None:
    """Réplica exacta del bug reportado: 61 unidades vendidas (repartidas
    en varias ventas, para que el `SUM` agregado sea el que produce el
    `Decimal('61.000')` de escala fija) deben mostrarse como "61", nunca
    "61.000"."""
    _complete_sale(sales_env, Decimal(40), Decimal("1000"))
    _complete_sale(sales_env, Decimal(21), Decimal("1000"))

    service = ProfitsService()
    rows = service.get_product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert len(rows) == 1
    assert rows[0].quantity_sold == Decimal("61.000")
    assert product_row_to_strings(rows[0])[3] == "61"


def test_missing_cost_row_reports_none_for_cost_profit_margin(sales_env: SalesFixtures) -> None:
    sale_id = _complete_sale(sales_env, Decimal(1), Decimal("1000"))
    with session_scope() as session:
        from pos.modules.sales.infrastructure.models import SaleItem

        item = session.query(SaleItem).filter(SaleItem.sale_id == sale_id).one()
        item.unit_cost = None
        session.add(item)

    service = ProfitsService()
    rows = service.get_product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert rows[0].missing_cost is True
    assert rows[0].total_cost is None
    assert rows[0].total_profit is None
    assert rows[0].margin_pct is None
    # el ingreso sí se conoce siempre, no depende del costo histórico
    assert rows[0].total_revenue == Decimal(1000)


def test_top_lists_derive_from_product_rows_without_extra_queries(
    sales_env: SalesFixtures,
) -> None:
    _complete_sale(sales_env, Decimal(5), Decimal("1000"))

    service = ProfitsService()
    top_lists = service.get_top_lists(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert len(top_lists.highest_profit) == 1
    assert top_lists.highest_profit[0].product_id == sales_env.product_id
    assert top_lists.most_sold[0].value == Decimal(5)


def test_chart_series_runs_without_error(sales_env: SalesFixtures) -> None:
    _complete_sale(sales_env, Decimal(1), Decimal("1000"))

    service = ProfitsService()
    series = service.get_chart_series(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert len(series.top_products_by_quantity) == 1
    assert len(series.daily_revenue) == 1
    assert len(series.cumulative_profit) == 1
    assert series.cumulative_profit[0][1] == Decimal(500)


def test_get_product_history_dto(sales_env: SalesFixtures) -> None:
    sale_id = _complete_sale(sales_env, Decimal(1), Decimal("1000"))

    service = ProfitsService()
    history = service.get_product_history(
        sales_env.product_id, _RANGE_FROM, _RANGE_TO, ProfitFilters()
    )

    assert len(history) == 1
    assert history[0].sale_id == sale_id
    assert history[0].customer_name == "(sin cliente)"


def test_export_to_excel_and_pdf_generate_valid_files(sales_env: SalesFixtures, tmp_path) -> None:  # noqa: ANN001
    _complete_sale(sales_env, Decimal(2), Decimal("1000"))
    service = ProfitsService()

    excel_path = tmp_path / "ganancias.xlsx"
    service.export_to_excel(_RANGE_FROM, _RANGE_TO, ProfitFilters(), excel_path, "Diario")
    assert excel_path.exists()

    pdf_path = tmp_path / "ganancias.pdf"
    service.export_to_pdf(
        _RANGE_FROM,
        _RANGE_TO,
        ProfitFilters(),
        pdf_path,
        company_name="Ferretería El Tornillo",
        logo_path=None,
        generated_by="admin",
        period_label="Diario: hoy",
        filters_description="Sin filtros",
    )
    assert pdf_path.exists()
    assert pdf_path.read_bytes().startswith(b"%PDF")
