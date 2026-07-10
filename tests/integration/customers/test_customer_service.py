"""Pruebas de integración de CustomerManagementService contra SQLite real."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.customers.infrastructure.models import (
    CreditMovementType,
    LoyaltyPointsMovementType,
)


def test_create_customer(sqlite_engine: None) -> None:
    service = CustomerManagementService()

    customer = service.create_customer(full_name="Juan Pérez", credit_limit=Decimal("100000"))

    assert customer.full_name == "Juan Pérez"
    assert customer.current_debt == Decimal(0)
    assert customer.loyalty_points_balance == 0


def test_create_customer_without_name_is_rejected(sqlite_engine: None) -> None:
    service = CustomerManagementService()

    with pytest.raises(BusinessRuleViolationError):
        service.create_customer(full_name="")


def test_charge_increases_debt(sqlite_engine: None) -> None:
    service = CustomerManagementService()
    customer = service.create_customer(full_name="Ana", credit_limit=Decimal("100"))

    new_balance = service.register_credit_movement(
        customer_id=customer.id, movement_type=CreditMovementType.CHARGE, amount=Decimal("40")
    )

    assert new_balance == Decimal("40")


def test_charge_exceeding_credit_limit_is_rejected(sqlite_engine: None) -> None:
    service = CustomerManagementService()
    customer = service.create_customer(full_name="Ana", credit_limit=Decimal("50"))

    with pytest.raises(BusinessRuleViolationError):
        service.register_credit_movement(
            customer_id=customer.id, movement_type=CreditMovementType.CHARGE, amount=Decimal("60")
        )


def test_payment_decreases_debt(sqlite_engine: None) -> None:
    service = CustomerManagementService()
    customer = service.create_customer(full_name="Ana", credit_limit=Decimal("100"))
    service.register_credit_movement(
        customer_id=customer.id, movement_type=CreditMovementType.CHARGE, amount=Decimal("40")
    )

    new_balance = service.register_credit_movement(
        customer_id=customer.id, movement_type=CreditMovementType.PAYMENT, amount=Decimal("15")
    )

    assert new_balance == Decimal("25")


def test_payment_exceeding_debt_is_rejected(sqlite_engine: None) -> None:
    service = CustomerManagementService()
    customer = service.create_customer(full_name="Ana", credit_limit=Decimal("100"))

    with pytest.raises(BusinessRuleViolationError):
        service.register_credit_movement(
            customer_id=customer.id, movement_type=CreditMovementType.PAYMENT, amount=Decimal("10")
        )


def test_credit_movement_for_unknown_customer_raises_not_found(sqlite_engine: None) -> None:
    service = CustomerManagementService()

    with pytest.raises(NotFoundError):
        service.register_credit_movement(
            customer_id=9999, movement_type=CreditMovementType.CHARGE, amount=Decimal("10")
        )


def test_earn_loyalty_points_increases_balance(sqlite_engine: None) -> None:
    service = CustomerManagementService()
    customer = service.create_customer(full_name="Ana")

    new_balance = service.register_loyalty_movement(
        customer_id=customer.id, points=50, movement_type=LoyaltyPointsMovementType.EARNED
    )

    assert new_balance == 50


def test_redeem_more_points_than_available_is_rejected(sqlite_engine: None) -> None:
    service = CustomerManagementService()
    customer = service.create_customer(full_name="Ana")
    service.register_loyalty_movement(
        customer_id=customer.id, points=10, movement_type=LoyaltyPointsMovementType.EARNED
    )

    with pytest.raises(BusinessRuleViolationError):
        service.register_loyalty_movement(
            customer_id=customer.id, points=20, movement_type=LoyaltyPointsMovementType.REDEEMED
        )


def test_remove_customer_soft_deletes(sqlite_engine: None) -> None:
    service = CustomerManagementService()
    customer = service.create_customer(full_name="Temporal")

    service.remove_customer(customer.id)

    assert customer.id not in {c.id for c in service.list_customers()}
