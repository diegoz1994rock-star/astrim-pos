"""Pruebas de integración de `ProfitsRepository` contra SQLite real: la
consulta SQL agregada debe correr sin errores (joins/columnas correctas)
y, sobre todo, el costo histórico de una venta antigua debe permanecer
congelado incluso si el costo actual del producto cambia después."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal

from pos.core.database.session import session_scope
from pos.modules.profits.domain.filters import ProfitFilters
from pos.modules.profits.infrastructure.repository import ProfitsRepository
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.domain.enums import PaymentMethod
from tests.integration.sales.conftest import SalesFixtures

_TODAY = date.today()
_YESTERDAY = _TODAY - timedelta(days=1)
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


def test_numeric_aggregate_columns_are_decimal_not_float(sales_env: SalesFixtures) -> None:
    """SQLite devuelve `AVG(...)` como `float` nativo por defecto — sin el
    `type_=Numeric(12, 2)` explícito en `func.avg(...)`, `format_currency`
    (que espera `Decimal`) se rompe al exportar. Ver el fix en
    `ProfitsRepository.product_rows`."""
    _complete_sale(sales_env, Decimal(2), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        rows = repo.product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    row = rows[0]
    assert isinstance(row.avg_purchase_price, Decimal)
    assert isinstance(row.avg_sale_price, Decimal)
    assert isinstance(row.min_sale_price, Decimal)
    assert isinstance(row.max_sale_price, Decimal)


def test_historical_cost_never_changes_after_catalog_cost_changes(
    sales_env: SalesFixtures,
) -> None:
    """Réplica del ejemplo del Martillo del pedido: una venta hecha con
    costo $500 debe seguir mostrando esa ganancia para siempre, aunque el
    costo del catálogo suba después."""
    _complete_sale(sales_env, Decimal(2), Decimal("1000"))

    with session_scope() as session:
        from pos.modules.products.infrastructure.product_repository import ProductRepository

        product_repo = ProductRepository(session)
        product = product_repo.get(sales_env.product_id)
        assert product is not None
        product.cost_price = Decimal("900")
        session.add(product)

    with session_scope() as session:
        repo = ProfitsRepository(session)
        rows = repo.product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert len(rows) == 1
    row = rows[0]
    # costo original era 500: ganancia = 2*(1000-500) = 1000, no 2*(1000-900)=200
    assert row.missing_cost_count == 0
    assert row.total_profit == Decimal("1000")
    assert row.total_cost == Decimal("1000")


def test_sales_without_historical_cost_report_as_missing(sales_env: SalesFixtures) -> None:
    sale_id = _complete_sale(sales_env, Decimal(1), Decimal("1000"))

    with session_scope() as session:
        from pos.modules.sales.infrastructure.models import SaleItem

        item = session.query(SaleItem).filter(SaleItem.sale_id == sale_id).one()
        item.unit_cost = None
        session.add(item)

    with session_scope() as session:
        repo = ProfitsRepository(session)
        rows = repo.product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert len(rows) == 1
    assert rows[0].missing_cost_count == 1


def test_summary_matches_product_rows_totals(sales_env: SalesFixtures) -> None:
    _complete_sale(sales_env, Decimal(3), Decimal("1000"))
    _complete_sale(sales_env, Decimal(2), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        summary = repo.summary(_RANGE_FROM, _RANGE_TO, ProfitFilters())
        rows = repo.product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert summary.total_revenue == sum(row.total_revenue for row in rows)
    assert summary.invoice_count == 2
    assert summary.total_quantity == Decimal(5)


def test_category_groups_runs_without_error(sales_env: SalesFixtures) -> None:
    _complete_sale(sales_env, Decimal(1), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        groups = repo.category_groups(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert len(groups) == 1


def test_daily_series_runs_without_error(sales_env: SalesFixtures) -> None:
    _complete_sale(sales_env, Decimal(1), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        series = repo.daily_series(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert len(series) == 1


def test_top_sellers_by_product_runs_without_error(sales_env: SalesFixtures) -> None:
    _complete_sale(sales_env, Decimal(1), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        top_sellers = repo.top_sellers_by_product(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert top_sellers[sales_env.product_id] == "Cajero de Ventas"


def test_stock_by_product_reflects_current_stock(sales_env: SalesFixtures) -> None:
    _complete_sale(sales_env, Decimal(4), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        stock = repo.stock_by_product([sales_env.product_id], warehouse_id=None)

    # 100 inicial - 4 vendidas
    assert stock[sales_env.product_id] == Decimal(96)


def test_warehouse_filter_matches_the_real_exit_movement(sales_env: SalesFixtures) -> None:
    _complete_sale(sales_env, Decimal(1), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        matching = repo.product_rows(
            _RANGE_FROM, _RANGE_TO, ProfitFilters(warehouse_id=sales_env.warehouse_id)
        )
        non_matching = repo.product_rows(
            _RANGE_FROM, _RANGE_TO, ProfitFilters(warehouse_id=sales_env.warehouse_id + 999)
        )

    assert len(matching) == 1
    assert len(non_matching) == 0


def test_product_history_returns_line_level_detail(sales_env: SalesFixtures) -> None:
    sale_id = _complete_sale(sales_env, Decimal(2), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        history = repo.product_history(
            sales_env.product_id, _RANGE_FROM, _RANGE_TO, ProfitFilters()
        )

    assert len(history) == 1
    assert history[0].sale_id == sale_id
    assert history[0].quantity == Decimal(2)
    assert history[0].line_profit == Decimal("1000")


def test_only_with_profit_and_only_with_loss_filters(sales_env: SalesFixtures) -> None:
    _complete_sale(sales_env, Decimal(1), Decimal("1000"))  # costo 500, gana

    with session_scope() as session:
        repo = ProfitsRepository(session)
        profitable = repo.product_rows(
            _RANGE_FROM, _RANGE_TO, ProfitFilters(only_with_profit=True)
        )
        losing = repo.product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters(only_with_loss=True))

    assert len(profitable) == 1
    assert len(losing) == 0


def test_supplier_filter_uses_most_recent_received_purchase_order(
    sales_env: SalesFixtures,
) -> None:
    from pos.modules.purchasing.domain.enums import PurchaseOrderStatus
    from pos.modules.purchasing.infrastructure.models import PurchaseOrder, PurchaseOrderItem
    from pos.modules.suppliers.infrastructure.models import Supplier

    with session_scope() as session:
        supplier = Supplier(company_name="Proveedor Uno")
        session.add(supplier)
        session.flush()
        order = PurchaseOrder(
            supplier_id=supplier.id,
            status=PurchaseOrderStatus.RECEIVED,
            order_date=_YESTERDAY,
        )
        session.add(order)
        session.flush()
        session.add(
            PurchaseOrderItem(
                purchase_order_id=order.id,
                product_id=sales_env.product_id,
                quantity=Decimal(10),
                unit_cost=Decimal("500"),
            )
        )
        session.flush()
        supplier_id = supplier.id

    _complete_sale(sales_env, Decimal(1), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        matching = repo.product_rows(
            _RANGE_FROM, _RANGE_TO, ProfitFilters(supplier_id=supplier_id)
        )
        non_matching = repo.product_rows(
            _RANGE_FROM, _RANGE_TO, ProfitFilters(supplier_id=supplier_id + 999)
        )
        supplier_names = repo.latest_supplier_by_product([sales_env.product_id])

    assert len(matching) == 1
    assert len(non_matching) == 0
    assert supplier_names[sales_env.product_id] == "Proveedor Uno"


def test_category_filter(sales_env: SalesFixtures) -> None:
    with session_scope() as session:
        from pos.modules.products.infrastructure.models import Category, Product

        category = Category(name="Ferretería")
        session.add(category)
        session.flush()
        product = session.get(Product, sales_env.product_id)
        assert product is not None
        product.category_id = category.id
        session.add(product)
        category_id = category.id

    _complete_sale(sales_env, Decimal(1), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        matching = repo.product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters(category_id=category_id))
        non_matching = repo.product_rows(
            _RANGE_FROM, _RANGE_TO, ProfitFilters(category_id=category_id + 999)
        )

    assert len(matching) == 1
    assert len(non_matching) == 0


def test_product_rows_include_sale_unit(sales_env: SalesFixtures) -> None:
    """`sale_unit` debe venir de la consulta agregada (join a `Product`),
    no adivinarse en presentación — es el campo que decide si `Cantidad
    vendida`/`Stock actual` se formatean como entero o como decimal."""
    from pos.modules.products.domain.enums import SaleUnit

    _complete_sale(sales_env, Decimal(1), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        rows = repo.product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert rows[0].sale_unit is SaleUnit.UNIT


def test_product_rows_never_mix_sales_outside_the_period(sales_env: SalesFixtures) -> None:
    """Una venta fuera del rango seleccionado no debe alterar ninguna
    columna calculada del período activo — "No mezclar datos de otros
    meses"."""
    from pos.modules.sales.infrastructure.models import Sale

    _complete_sale(sales_env, Decimal(2), Decimal("1000"))
    sale_out_of_range = _complete_sale(sales_env, Decimal(50), Decimal("1000"))

    with session_scope() as session:
        session.query(Sale).filter(Sale.id == sale_out_of_range).update(
            {"created_at": datetime.combine(_RANGE_FROM - timedelta(days=30), time.min, tzinfo=UTC)}
        )

    with session_scope() as session:
        repo = ProfitsRepository(session)
        rows = repo.product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert len(rows) == 1
    assert rows[0].quantity_sold == Decimal(2)
    assert rows[0].invoice_count == 1


def test_default_sort_orders_by_first_sale_ascending(sales_env: SalesFixtures) -> None:
    """Bug reportado: sin que el usuario elija un orden manualmente, la
    tabla debe verse cronológicamente ordenada por primera venta (más
    antigua primero) — `ProfitFilters()` por defecto usa
    `ProfitSortOption.FIRST_SALE_ASC`."""
    from pos.modules.products.application.product_service import ProductManagementService
    from pos.modules.products.domain.enums import ProductType
    from pos.modules.sales.infrastructure.models import Sale

    product_service = ProductManagementService(sales_env.event_bus)
    product_b = product_service.create_product(
        sku="VENTA-2",
        name="Producto B",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("1000"),
        cost_price=Decimal("500"),
        unit_of_measure="unidad",
        track_inventory=False,
    )

    payment = SalePaymentInput(payment_method=PaymentMethod.CASH, amount=Decimal("1000"))
    sale_a = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=sales_env.product_id, quantity=Decimal(1))],
        payments=[payment],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )
    sale_b = sales_env.sales_service.complete_sale(
        items=[SaleItemInput(product_id=product_b.id, quantity=Decimal(1))],
        payments=[payment],
        cash_session_id=sales_env.cash_session_id,
        warehouse_id=sales_env.warehouse_id,
        created_by_user_id=sales_env.user_id,
    )

    with session_scope() as session:
        # A se registró primero en la BD pero su venta real es más
        # reciente que la de B — el orden debe basarse en la fecha de
        # venta (`Sale.created_at`), nunca en el orden de inserción/tabla.
        session.query(Sale).filter(Sale.id == sale_a.id).update(
            {"created_at": datetime.combine(_TODAY - timedelta(days=1), time.min, tzinfo=UTC)}
        )
        session.query(Sale).filter(Sale.id == sale_b.id).update(
            {"created_at": datetime.combine(_TODAY - timedelta(days=5), time.min, tzinfo=UTC)}
        )

    with session_scope() as session:
        repo = ProfitsRepository(session)
        rows = repo.product_rows(_RANGE_FROM, _RANGE_TO, ProfitFilters())

    assert [row.product_id for row in rows] == [product_b.id, sales_env.product_id]


def test_cash_register_filter(sales_env: SalesFixtures) -> None:
    with session_scope() as session:
        from pos.modules.cash_register.infrastructure.models import CashSession

        cash_session = session.get(CashSession, sales_env.cash_session_id)
        assert cash_session is not None
        register_id = cash_session.cash_register_id

    _complete_sale(sales_env, Decimal(1), Decimal("1000"))

    with session_scope() as session:
        repo = ProfitsRepository(session)
        matching = repo.product_rows(
            _RANGE_FROM, _RANGE_TO, ProfitFilters(cash_register_id=register_id)
        )
        non_matching = repo.product_rows(
            _RANGE_FROM, _RANGE_TO, ProfitFilters(cash_register_id=register_id + 999)
        )
        history = repo.product_history(
            sales_env.product_id,
            _RANGE_FROM,
            _RANGE_TO,
            ProfitFilters(cash_register_id=register_id),
        )

    assert len(matching) == 1
    assert len(non_matching) == 0
    assert len(history) == 1
