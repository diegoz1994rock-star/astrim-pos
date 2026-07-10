"""Acceso a datos de solo lectura para los reportes.

Consulta directamente los modelos de `sales`, `cash_register` y `customers`
— dependencia intencional y documentada en MODULES.md (Reportes depende de
Ventas, Inventario, Caja, Clientes, Usuarios), no una violación de
ARCHITECTURE.md §12b (esa convención es sobre columnas `ForeignKey`, no
sobre consultas de aplicación entre módulos con dependencia reconocida).
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from pos.modules.cash_register.infrastructure.models import CashRegister, CashSession
from pos.modules.customers.infrastructure.models import Customer
from pos.modules.products.infrastructure.models import Product
from pos.modules.sales.domain.enums import SaleStatus
from pos.modules.sales.infrastructure.models import Sale, SaleItem


def _day_bounds(day_from: date, day_to: date) -> tuple[datetime, datetime]:
    start = datetime.combine(day_from, time.min, tzinfo=UTC)
    end = datetime.combine(day_to, time.max, tzinfo=UTC)
    return start, end


class ReportRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_sales_in_range(self, date_from: date, date_to: date) -> list[tuple[Sale, str]]:
        start, end = _day_bounds(date_from, date_to)
        rows = self._session.execute(
            select(Sale, Customer.full_name)
            .outerjoin(Customer, Customer.id == Sale.customer_id)
            .where(Sale.created_at >= start, Sale.created_at <= end)
            .order_by(Sale.created_at)
        )
        return [(row[0], row[1] or "(sin cliente)") for row in rows]

    def list_cash_sessions_in_range(
        self, date_from: date, date_to: date
    ) -> list[tuple[CashSession, str]]:
        start, end = _day_bounds(date_from, date_to)
        rows = self._session.execute(
            select(CashSession, CashRegister.name)
            .join(CashRegister, CashRegister.id == CashSession.cash_register_id)
            .where(CashSession.opened_at >= start, CashSession.opened_at <= end)
            .order_by(CashSession.opened_at)
        )
        return [(row[0], row[1]) for row in rows]

    def product_sales_in_range(
        self, date_from: date, date_to: date
    ) -> list[tuple[str, str, Decimal, Decimal]]:
        """(sku, nombre, cantidad_vendida, ingreso) por producto, solo ventas
        completadas (excluye anuladas)."""
        start, end = _day_bounds(date_from, date_to)
        rows = self._session.execute(
            select(
                Product.sku,
                Product.name,
                func.sum(SaleItem.quantity),
                func.sum(SaleItem.line_total),
            )
            .join(SaleItem, SaleItem.product_id == Product.id)
            .join(Sale, Sale.id == SaleItem.sale_id)
            .where(
                Sale.created_at >= start,
                Sale.created_at <= end,
                Sale.status == SaleStatus.COMPLETED,
            )
            .group_by(Product.id)
            .order_by(func.sum(SaleItem.line_total).desc())
        )
        return [(row[0], row[1], row[2], row[3]) for row in rows]
