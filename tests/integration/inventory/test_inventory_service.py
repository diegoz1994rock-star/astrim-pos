"""Pruebas de integración de InventoryService contra SQLite real."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.inventory.domain.events import StockLevelChangedEvent


def test_register_entry_increases_stock(product_id: int, warehouse_id: int) -> None:
    service = InventoryService(EventBus())

    service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("50"),
        reason="Compra inicial",
        created_by_user_id=None,
    )

    overview = service.list_stock_overview()
    assert overview[0].quantity == Decimal("50")


def test_register_exit_decreases_stock(product_id: int, warehouse_id: int) -> None:
    service = InventoryService(EventBus())
    service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("50"),
        reason=None,
        created_by_user_id=None,
    )

    service.register_exit(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("20"),
        reason="Venta",
        created_by_user_id=None,
    )

    overview = service.list_stock_overview()
    assert overview[0].quantity == Decimal("30")


def test_register_exit_with_insufficient_stock_is_rejected(
    product_id: int, warehouse_id: int
) -> None:
    service = InventoryService(EventBus())

    with pytest.raises(BusinessRuleViolationError):
        service.register_exit(
            product_id=product_id,
            warehouse_id=warehouse_id,
            quantity=Decimal("10"),
            reason=None,
            created_by_user_id=None,
        )


def test_register_adjustment_can_increase_or_decrease(product_id: int, warehouse_id: int) -> None:
    service = InventoryService(EventBus())
    service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("10"),
        reason=None,
        created_by_user_id=None,
    )

    service.register_adjustment(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("3"),
        increase=False,
        reason="Merma",
        created_by_user_id=None,
    )

    overview = service.list_stock_overview()
    assert overview[0].quantity == Decimal("7")


def test_transfer_moves_stock_between_warehouses(product_id: int, warehouse_id: int) -> None:
    from pos.core.database.session import session_scope
    from pos.modules.inventory.infrastructure.models import Warehouse

    with session_scope() as session:
        other_warehouse = Warehouse(name="Bodega Secundaria")
        session.add(other_warehouse)
        session.flush()
        other_warehouse_id = other_warehouse.id

    service = InventoryService(EventBus())
    service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("20"),
        reason=None,
        created_by_user_id=None,
    )

    service.transfer(
        product_id=product_id,
        source_warehouse_id=warehouse_id,
        destination_warehouse_id=other_warehouse_id,
        quantity=Decimal("8"),
        created_by_user_id=None,
    )

    overview = {(s.warehouse_id): s.quantity for s in service.list_stock_overview()}
    assert overview[warehouse_id] == Decimal("12")
    assert overview[other_warehouse_id] == Decimal("8")


def test_transfer_with_same_source_and_destination_is_rejected(
    product_id: int, warehouse_id: int
) -> None:
    service = InventoryService(EventBus())

    with pytest.raises(BusinessRuleViolationError):
        service.transfer(
            product_id=product_id,
            source_warehouse_id=warehouse_id,
            destination_warehouse_id=warehouse_id,
            quantity=Decimal("1"),
            created_by_user_id=None,
        )


def test_movement_publishes_stock_level_changed_event(product_id: int, warehouse_id: int) -> None:
    bus = EventBus()
    received: list[StockLevelChangedEvent] = []
    bus.subscribe(StockLevelChangedEvent, received.append)
    service = InventoryService(bus)

    service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("5"),
        reason=None,
        created_by_user_id=None,
    )

    assert len(received) == 1
    assert received[0].new_quantity == Decimal("5")


def test_stock_below_minimum_is_flagged(product_id: int, warehouse_id: int) -> None:
    service = InventoryService(EventBus())
    service.set_minimum_stock(product_id, Decimal("10"))

    service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("3"),
        reason=None,
        created_by_user_id=None,
    )

    overview = service.list_stock_overview()
    assert overview[0].is_below_minimum is True
