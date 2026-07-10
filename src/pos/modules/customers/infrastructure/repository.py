"""Acceso a datos de clientes: datos base, créditos y puntos de fidelidad."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.customers.infrastructure.models import (
    CreditMovementType,
    Customer,
    CustomerCreditMovement,
    CustomerLoyaltyPoints,
    LoyaltyPointsMovementType,
)


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Customer]:
        return list(
            self._session.scalars(
                select(Customer).where(Customer.is_deleted.is_(False)).order_by(Customer.full_name)
            )
        )

    def get(self, customer_id: int) -> Customer | None:
        return self._session.get(Customer, customer_id)

    def create(
        self,
        *,
        full_name: str,
        document_id: str | None,
        email: str | None,
        phone: str | None,
        address: str | None,
        credit_limit: Decimal,
    ) -> Customer:
        customer = Customer(
            full_name=full_name,
            document_id=document_id,
            email=email,
            phone=phone,
            address=address,
            credit_limit=credit_limit,
        )
        self._session.add(customer)
        self._session.flush()
        return customer

    def set_deleted(self, customer: Customer, is_deleted: bool) -> None:
        customer.is_deleted = is_deleted

    def get_current_debt(self, customer_id: int) -> Decimal:
        last_movement = self._session.scalar(
            select(CustomerCreditMovement)
            .where(CustomerCreditMovement.customer_id == customer_id)
            .order_by(CustomerCreditMovement.id.desc())
            .limit(1)
        )
        return last_movement.balance_after if last_movement is not None else Decimal(0)

    def add_credit_movement(
        self,
        *,
        customer_id: int,
        movement_type: CreditMovementType,
        amount: Decimal,
        balance_after: Decimal,
        reference: str | None,
        created_by_user_id: int | None,
    ) -> CustomerCreditMovement:
        movement = CustomerCreditMovement(
            customer_id=customer_id,
            movement_type=movement_type,
            amount=amount,
            balance_after=balance_after,
            reference=reference,
            created_by_user_id=created_by_user_id,
        )
        self._session.add(movement)
        self._session.flush()
        return movement

    def add_loyalty_movement(
        self,
        customer: Customer,
        *,
        points: int,
        movement_type: LoyaltyPointsMovementType,
        reference: str | None,
    ) -> None:
        self._session.add(
            CustomerLoyaltyPoints(
                customer_id=customer.id,
                points=points,
                movement_type=movement_type,
                reference=reference,
            )
        )
