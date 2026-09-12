"""Acceso a datos de ventas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Row, func, select
from sqlalchemy.orm import Session, selectinload

from pos.modules.products.domain.enums import SaleUnit
from pos.modules.sales.domain.enums import PaymentMethod, SaleStatus, SaleType
from pos.modules.sales.infrastructure.models import Sale, SaleItem, SalePayment
from pos.modules.scales.domain.enums import WeightEntrySource


class SaleRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_sale(
        self,
        *,
        customer_id: int | None,
        cash_session_id: int | None,
        sale_type: SaleType,
        created_by_user_id: int | None,
        customer_name: str | None = None,
        customer_document: str | None = None,
    ) -> Sale:
        sale = Sale(
            customer_id=customer_id,
            cash_session_id=cash_session_id,
            sale_type=sale_type,
            status=SaleStatus.DRAFT,
            created_by_user_id=created_by_user_id,
            customer_name=customer_name,
            customer_document=customer_document,
        )
        self._session.add(sale)
        self._session.flush()
        return sale

    def add_item(
        self,
        *,
        sale_id: int,
        product_id: int,
        quantity: Decimal,
        unit_price: Decimal,
        discount_amount: Decimal,
        tax_amount: Decimal,
        line_total: Decimal,
        note: str | None = None,
        unit_cost: Decimal | None = None,
        sale_unit: SaleUnit = SaleUnit.UNIT,
        unit_of_measure: str = "unidad",
        weight_entry_source: WeightEntrySource | None = None,
    ) -> SaleItem:
        item = SaleItem(
            sale_id=sale_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
            unit_cost=unit_cost,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            line_total=line_total,
            note=note,
            sale_unit=sale_unit,
            unit_of_measure=unit_of_measure,
            weight_entry_source=weight_entry_source,
        )
        self._session.add(item)
        self._session.flush()
        return item

    def add_payment(
        self,
        *,
        sale_id: int,
        payment_method: PaymentMethod,
        amount: Decimal,
        reference: str | None,
    ) -> SalePayment:
        payment = SalePayment(
            sale_id=sale_id, payment_method=payment_method, amount=amount, reference=reference
        )
        self._session.add(payment)
        self._session.flush()
        return payment

    def update_totals(
        self,
        sale: Sale,
        *,
        subtotal: Decimal,
        discount_total: Decimal,
        tax_total: Decimal,
        total: Decimal,
    ) -> None:
        sale.subtotal = subtotal
        sale.discount_total = discount_total
        sale.tax_total = tax_total
        sale.total = total

    def set_status(self, sale: Sale, status: SaleStatus) -> None:
        sale.status = status

    def get(self, sale_id: int) -> Sale | None:
        return self._session.get(Sale, sale_id)

    def get_with_details(self, sale_id: int) -> Sale | None:
        return self._session.scalar(
            select(Sale)
            .options(selectinload(Sale.items), selectinload(Sale.payments))
            .where(Sale.id == sale_id)
        )

    def list_recent(self, limit: int = 50) -> list[Sale]:
        return list(
            self._session.scalars(
                select(Sale)
                .options(selectinload(Sale.items), selectinload(Sale.payments))
                .order_by(Sale.created_at.desc())
                .limit(limit)
            )
        )

    def sum_completed_total(self, start: datetime, end: datetime) -> Decimal:
        """Total vendido en el rango — agregado en SQL (`func.sum`), nunca
        sumando una lista de ventas traída a Python (Resumen Diario de
        Ventas → Historial, ver `SalesService.get_daily_totals`)."""
        return (
            self._session.scalar(
                select(func.coalesce(func.sum(Sale.total), 0)).where(
                    Sale.status == SaleStatus.COMPLETED,
                    Sale.created_at >= start,
                    Sale.created_at <= end,
                )
            )
            or Decimal(0)
        )

    def totals_by_cashier(self, start: datetime, end: datetime) -> list[Row]:
        """Una fila `(created_by_user_id, total)` por cajero — `GROUP BY`
        en SQL, mismo criterio de rendimiento que el resto del sistema
        (nunca recorrer ventas en Python para sumarlas)."""
        query = (
            select(Sale.created_by_user_id, func.sum(Sale.total))
            .where(
                Sale.status == SaleStatus.COMPLETED,
                Sale.created_at >= start,
                Sale.created_at <= end,
            )
            .group_by(Sale.created_by_user_id)
        )
        return self._session.execute(query).all()
