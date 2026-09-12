"""Acceso a datos de solo lectura para Ganancias.

Consulta directamente los modelos de `sales`, `products`, `inventory`,
`purchasing`, `cash_register`, `customers` y `users` — mismo tipo de
dependencia intencional ya documentada en `reports/infrastructure/
report_repository.py` (Reportes/Ganancias dependen de otros módulos por
consulta de aplicación, no por `ForeignKey`, ver ARCHITECTURE.md §12b).

Todo el cálculo pesado ocurre en SQL agregado (`GROUP BY`, `func.sum/avg/
count/min/max`) — nunca se trae una lista completa de `SaleItem` a Python
para sumarla ahí, siguiendo la misma convención que `ReportRepository`
(obligatoria además por el mandato de rendimiento con 1M+ ventas).

Costo histórico: `SaleItem.unit_cost` es el costo congelado al momento de
cada venta (ver `sale_service._price_items`). Si algún renglón de un
producto en el período no tiene `unit_cost` (venta anterior a la
migración que agregó la columna), el costo/ganancia/margen de ESE
producto se reporta como "N/D" — nunca se aproxima con el costo actual
del catálogo, ver `ProfitsService`/`ProductProfitRow.missing_cost`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import Numeric, Row, case, func, select
from sqlalchemy.orm import Session
from sqlalchemy.sql import Select

from pos.modules.billing.infrastructure.models import Invoice
from pos.modules.cash_register.infrastructure.models import CashRegister, CashSession
from pos.modules.customers.infrastructure.models import Customer
from pos.modules.inventory.infrastructure.models import StockLevel, StockMovement
from pos.modules.products.domain.enums import SaleUnit
from pos.modules.products.infrastructure.models import Category, Product
from pos.modules.profits.domain.enums import ProfitSortOption
from pos.modules.profits.domain.filters import ProfitFilters
from pos.modules.purchasing.domain.enums import PurchaseOrderStatus
from pos.modules.purchasing.infrastructure.models import PurchaseOrder, PurchaseOrderItem
from pos.modules.sales.domain.enums import SaleStatus
from pos.modules.sales.infrastructure.models import Sale, SaleItem
from pos.modules.suppliers.infrastructure.models import Supplier
from pos.modules.users.infrastructure.models import User


def _day_bounds(day_from: date, day_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day_from, time.min, tzinfo=UTC)
    end = datetime.combine(day_to, time.max, tzinfo=UTC)
    return start, end


@dataclass(frozen=True)
class ProfitSummaryRow:
    total_revenue: Decimal
    total_quantity: Decimal
    invoice_count: int
    total_cost: Decimal | None
    total_profit: Decimal | None
    avg_margin_pct: Decimal | None


@dataclass(frozen=True)
class SaleHistoryRow:
    sale_id: int
    invoice_number: str | None
    customer_name: str | None
    user_name: str | None
    cash_register_name: str | None
    sold_at: datetime
    quantity: Decimal
    unit_cost: Decimal | None
    unit_price: Decimal
    line_profit: Decimal | None
    sale_unit: SaleUnit


_MISSING_COST_EXPR = func.sum(case((SaleItem.unit_cost.is_(None), 1), else_=0))
_LINE_COST_EXPR = SaleItem.quantity * SaleItem.unit_cost
_LINE_PROFIT_EXPR = SaleItem.line_total - _LINE_COST_EXPR


class ProfitsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _apply_filters(self, query: Select, filters: ProfitFilters) -> Select:
        if filters.category_id is not None:
            query = query.where(Product.category_id == filters.category_id)
        if filters.user_id is not None:
            query = query.where(Sale.created_by_user_id == filters.user_id)
        if filters.customer_id is not None:
            query = query.where(Sale.customer_id == filters.customer_id)
        if filters.product_code:
            query = query.where(Product.sku.ilike(f"%{filters.product_code}%"))
        if filters.product_name:
            query = query.where(Product.name.ilike(f"%{filters.product_name}%"))
        if filters.cash_register_id is not None:
            # Subconsulta EXISTS en vez de `.join()`: algunos métodos (ej.
            # `product_history`) ya traen `CashSession` unido para mostrar
            # el nombre de caja — un segundo `.join()` aquí duplicaría esa
            # tabla en el FROM. `.correlate(Sale)` es necesario porque, si
            # `CashSession` ya aparece en la consulta externa, SQLAlchemy
            # la auto-correlaciona por completo y la subconsulta se queda
            # sin FROM propio — forzamos a que solo `Sale` se correlacione.
            query = query.where(
                select(CashSession.id)
                .where(
                    CashSession.id == Sale.cash_session_id,
                    CashSession.cash_register_id == filters.cash_register_id,
                )
                .correlate(Sale)
                .exists()
            )
        if filters.warehouse_id is not None:
            query = query.where(
                select(StockMovement.id)
                .where(
                    StockMovement.reference_document_type == "sale",
                    StockMovement.reference_document_id == Sale.id,
                    StockMovement.product_id == SaleItem.product_id,
                    StockMovement.warehouse_id == filters.warehouse_id,
                )
                .correlate(Sale, SaleItem)
                .exists()
            )
        if filters.supplier_id is not None:
            query = query.where(Product.id.in_(self._product_ids_for_supplier(filters.supplier_id)))
        return query

    def _product_ids_for_supplier(self, supplier_id: int):
        latest = self._latest_supplier_subquery()
        return select(latest.c.product_id).where(latest.c.supplier_id == supplier_id)

    def _latest_supplier_subquery(self):
        """Proveedor más reciente por producto: la orden de compra RECIBIDA
        más nueva que contiene ese producto. Aproximación documentada (no
        existe un vínculo directo venta→proveedor) — decisión confirmada
        con el usuario."""
        ranked = (
            select(
                PurchaseOrderItem.product_id,
                PurchaseOrder.supplier_id,
                func.row_number()
                .over(
                    partition_by=PurchaseOrderItem.product_id,
                    order_by=PurchaseOrder.order_date.desc(),
                )
                .label("rn"),
            )
            .join(PurchaseOrder, PurchaseOrder.id == PurchaseOrderItem.purchase_order_id)
            .where(PurchaseOrder.status == PurchaseOrderStatus.RECEIVED)
            .subquery()
        )
        return (
            select(ranked.c.product_id, ranked.c.supplier_id)
            .where(ranked.c.rn == 1)
            .subquery()
        )

    def summary(self, date_from: date, date_to: date, filters: ProfitFilters) -> ProfitSummaryRow:
        start, end = _day_bounds(date_from, date_to)
        query = (
            select(
                func.coalesce(func.sum(SaleItem.line_total), 0),
                func.coalesce(func.sum(SaleItem.quantity), 0),
                func.count(func.distinct(SaleItem.sale_id)),
                func.sum(_LINE_COST_EXPR),
                func.sum(_LINE_PROFIT_EXPR),
                _MISSING_COST_EXPR,
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .join(Product, Product.id == SaleItem.product_id)
            .where(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
        )
        query = self._apply_filters(query, filters)
        row = self._session.execute(query).one()
        total_revenue, total_quantity, invoice_count, total_cost, total_profit, missing = row
        has_missing = (missing or 0) > 0
        avg_margin = None
        if not has_missing and total_revenue:
            avg_margin = (total_profit / total_revenue * 100).quantize(Decimal("0.01"))
        return ProfitSummaryRow(
            total_revenue=total_revenue,
            total_quantity=total_quantity,
            invoice_count=invoice_count,
            total_cost=None if has_missing else total_cost,
            total_profit=None if has_missing else total_profit,
            avg_margin_pct=avg_margin,
        )

    def product_rows(
        self, date_from: date, date_to: date, filters: ProfitFilters
    ) -> list[Row]:
        """Una fila por producto con las 16 columnas base. `missing_cost`
        indica si al menos una línea del producto en el período no tiene
        costo histórico — en ese caso el servicio debe mostrar "N/D" en
        costo/ganancia/margen para ESE producto, nunca aproximar."""
        start, end = _day_bounds(date_from, date_to)
        query = (
            select(
                Product.id.label("product_id"),
                Product.sku.label("code"),
                Category.name.label("category_name"),
                Product.name.label("product_name"),
                Product.sale_unit.label("sale_unit"),
                func.sum(SaleItem.quantity).label("quantity_sold"),
                func.avg(SaleItem.unit_cost, type_=Numeric(12, 2)).label("avg_purchase_price"),
                func.avg(SaleItem.unit_price, type_=Numeric(12, 2)).label("avg_sale_price"),
                func.min(SaleItem.unit_price).label("min_sale_price"),
                func.max(SaleItem.unit_price).label("max_sale_price"),
                func.sum(_LINE_COST_EXPR).label("total_cost"),
                func.sum(SaleItem.line_total).label("total_revenue"),
                func.sum(_LINE_PROFIT_EXPR).label("total_profit"),
                func.count(func.distinct(SaleItem.sale_id)).label("invoice_count"),
                func.min(Sale.created_at).label("first_sale_at"),
                func.max(Sale.created_at).label("last_sale_at"),
                _MISSING_COST_EXPR.label("missing_cost_count"),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .join(Product, Product.id == SaleItem.product_id)
            .outerjoin(Category, Category.id == Product.category_id)
            .where(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(Product.id, Product.sku, Category.name, Product.name, Product.sale_unit)
        )
        query = self._apply_filters(query, filters)

        total_profit_col = func.sum(_LINE_PROFIT_EXPR)
        missing_col = _MISSING_COST_EXPR
        if filters.only_with_profit:
            query = query.having(missing_col == 0, total_profit_col > 0)
        if filters.only_with_loss:
            query = query.having(missing_col == 0, total_profit_col < 0)

        query = query.order_by(*self._order_by(filters.sort))
        return self._session.execute(query).all()

    def _order_by(self, sort: ProfitSortOption) -> tuple:
        quantity_col = func.sum(SaleItem.quantity)
        revenue_col = func.sum(SaleItem.line_total)
        profit_col = func.sum(_LINE_PROFIT_EXPR)
        first_sale_col = func.min(Sale.created_at)
        if sort is ProfitSortOption.FIRST_SALE_ASC:
            return (first_sale_col.asc(),)
        if sort is ProfitSortOption.MOST_SOLD or sort is ProfitSortOption.HIGHEST_QUANTITY:
            return (quantity_col.desc(),)
        if sort is ProfitSortOption.LEAST_SOLD:
            return (quantity_col.asc(),)
        if sort is ProfitSortOption.HIGHEST_PROFIT:
            return (profit_col.desc().nulls_last(),)
        if sort is ProfitSortOption.LOWEST_PROFIT:
            return (profit_col.asc().nulls_last(),)
        if sort is ProfitSortOption.HIGHEST_REVENUE:
            return (revenue_col.desc(),)
        if sort is ProfitSortOption.NAME_ASC:
            return (Product.name.asc(),)
        if sort is ProfitSortOption.NAME_DESC:
            return (Product.name.desc(),)
        return (first_sale_col.asc(),)

    def category_groups(self, date_from: date, date_to: date, filters: ProfitFilters) -> list[Row]:
        start, end = _day_bounds(date_from, date_to)
        query = (
            select(
                Category.id.label("category_id"),
                Category.name.label("category_name"),
                func.sum(SaleItem.quantity).label("quantity_sold"),
                func.sum(SaleItem.line_total).label("total_revenue"),
                func.sum(_LINE_COST_EXPR).label("total_cost"),
                func.sum(_LINE_PROFIT_EXPR).label("total_profit"),
                _MISSING_COST_EXPR.label("missing_cost_count"),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .join(Product, Product.id == SaleItem.product_id)
            .outerjoin(Category, Category.id == Product.category_id)
            .where(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(Category.id, Category.name)
            .order_by(func.sum(SaleItem.line_total).desc())
        )
        query = self._apply_filters(query, filters)
        return self._session.execute(query).all()

    def daily_series(
        self, date_from: date, date_to: date, filters: ProfitFilters
    ) -> list[tuple[datetime, Decimal, Decimal | None]]:
        """(fecha de la venta, ingreso de esa línea, ganancia de esa línea o
        `None` si falta costo) crudo — el agrupamiento por día se hace en
        `ProfitsService` en Python, mismo motivo ya documentado en
        `ReportRepository.sale_totals_rows` (no depender de una función de
        fecha específica de un motor de base de datos)."""
        start, end = _day_bounds(date_from, date_to)
        query = (
            select(
                Sale.created_at,
                SaleItem.line_total,
                case((SaleItem.unit_cost.is_(None), None), else_=_LINE_PROFIT_EXPR),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .join(Product, Product.id == SaleItem.product_id)
            .where(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
        )
        query = self._apply_filters(query, filters)
        rows = self._session.execute(query).all()
        return [(row[0], row[1], row[2]) for row in rows]

    def top_sellers_by_product(
        self, date_from: date, date_to: date, filters: ProfitFilters
    ) -> dict[int, str]:
        """`{product_id: nombre_del_usuario_que_más_unidades_vendió}` en el
        período/filtros actuales. Agregado en SQL (`GROUP BY` producto +
        usuario); el "más vendió" se resuelve en Python sobre esa lista ya
        reducida (a lo sumo productos × usuarios distintos, nunca ventas
        crudas)."""
        start, end = _day_bounds(date_from, date_to)
        query = (
            select(
                SaleItem.product_id,
                Sale.created_by_user_id,
                User.full_name,
                func.sum(SaleItem.quantity).label("qty"),
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .join(Product, Product.id == SaleItem.product_id)
            .outerjoin(User, User.id == Sale.created_by_user_id)
            .where(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(SaleItem.product_id, Sale.created_by_user_id, User.full_name)
        )
        query = self._apply_filters(query, filters)
        rows = self._session.execute(query).all()

        best: dict[int, tuple[Decimal, str]] = {}
        for product_id, user_id, full_name, qty in rows:
            if user_id is None:
                continue
            current = best.get(product_id)
            if current is None or qty > current[0]:
                best[product_id] = (qty, full_name or "—")
        return {product_id: name for product_id, (_, name) in best.items()}

    def latest_supplier_by_product(self, product_ids: list[int]) -> dict[int, str]:
        if not product_ids:
            return {}
        latest = self._latest_supplier_subquery()
        rows = self._session.execute(
            select(latest.c.product_id, Supplier.company_name)
            .join(Supplier, Supplier.id == latest.c.supplier_id)
            .where(latest.c.product_id.in_(product_ids))
        ).all()
        return {product_id: name for product_id, name in rows}

    def stock_by_product(
        self, product_ids: list[int], warehouse_id: int | None
    ) -> dict[int, Decimal]:
        if not product_ids:
            return {}
        query = select(StockLevel.product_id, func.sum(StockLevel.quantity)).where(
            StockLevel.product_id.in_(product_ids)
        )
        if warehouse_id is not None:
            query = query.where(StockLevel.warehouse_id == warehouse_id)
        query = query.group_by(StockLevel.product_id)
        rows = self._session.execute(query).all()
        return {product_id: quantity for product_id, quantity in rows}

    def product_history(
        self, product_id: int, date_from: date, date_to: date, filters: ProfitFilters
    ) -> list[SaleHistoryRow]:
        """Detalle línea por línea de las ventas de un producto en el
        período — alimenta el diálogo de historial al hacer doble clic
        sobre una fila de la tabla principal."""
        start, end = _day_bounds(date_from, date_to)
        query = (
            select(
                Sale.id,
                Invoice.invoice_number,
                Customer.full_name,
                User.full_name,
                CashRegister.name,
                Sale.created_at,
                SaleItem.quantity,
                SaleItem.unit_cost,
                SaleItem.unit_price,
                case(
                    (SaleItem.unit_cost.is_(None), None),
                    else_=SaleItem.line_total - SaleItem.quantity * SaleItem.unit_cost,
                ),
                Product.sale_unit,
            )
            .join(Sale, Sale.id == SaleItem.sale_id)
            .join(Product, Product.id == SaleItem.product_id)
            .outerjoin(Invoice, Invoice.sale_id == Sale.id)
            .outerjoin(Customer, Customer.id == Sale.customer_id)
            .outerjoin(User, User.id == Sale.created_by_user_id)
            .outerjoin(CashSession, CashSession.id == Sale.cash_session_id)
            .outerjoin(CashRegister, CashRegister.id == CashSession.cash_register_id)
            .where(
                SaleItem.product_id == product_id,
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .order_by(Sale.created_at.desc())
        )
        query = self._apply_filters(query, filters)
        rows = self._session.execute(query).all()
        return [
            SaleHistoryRow(
                sale_id=row[0],
                invoice_number=row[1],
                customer_name=row[2],
                user_name=row[3],
                cash_register_name=row[4],
                sold_at=row[5],
                quantity=row[6],
                unit_cost=row[7],
                unit_price=row[8],
                line_profit=row[9],
                sale_unit=row[10],
            )
            for row in rows
        ]
