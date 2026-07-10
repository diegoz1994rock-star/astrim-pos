"""Acceso a datos de ventas."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from pos.modules.sales.domain.enums import PaymentMethod, SaleStatus, SaleType
from pos.modules.sales.infrastructure.models import Sale, SaleItem, SalePayment


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
    ) -> Sale:
        sale = Sale(
            customer_id=customer_id,
            cash_session_id=cash_session_id,
            sale_type=sale_type,
            status=SaleStatus.DRAFT,
            created_by_user_id=created_by_user_id,
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
    ) -> SaleItem:
        item = SaleItem(
            sale_id=sale_id,
            product_id=product_id,
            quantity=quantity,
            unit_price=unit_price,
            discount_amount=discount_amount,
            tax_amount=tax_amount,
            line_total=line_total,
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
