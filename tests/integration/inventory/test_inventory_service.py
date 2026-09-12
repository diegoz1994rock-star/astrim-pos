"""Pruebas de integración de InventoryService contra SQLite real."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
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


def test_get_total_available_quantity_sums_all_warehouses(
    product_id: int, warehouse_id: int
) -> None:
    service = InventoryService(EventBus())
    other_warehouse = service.create_warehouse(name="Bodega Secundaria")
    service.register_entry(
        product_id=product_id, warehouse_id=warehouse_id, quantity=Decimal("5"),
        reason=None, created_by_user_id=None,
    )
    service.register_entry(
        product_id=product_id, warehouse_id=other_warehouse.id, quantity=Decimal("30"),
        reason=None, created_by_user_id=None,
    )

    total = service.get_total_available_quantity(product_id)

    assert total == Decimal("35")


def test_get_total_available_quantity_is_zero_for_unstocked_product(product_id: int) -> None:
    service = InventoryService(EventBus())

    assert service.get_total_available_quantity(product_id) == Decimal("0")


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


def test_register_adjustment_corrects_to_lower_quantity(
    product_id: int, warehouse_id: int
) -> None:
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
        new_quantity=Decimal("7"),
        reason="Merma",
        created_by_user_id=None,
    )

    overview = service.list_stock_overview()
    assert overview[0].quantity == Decimal("7")


def test_register_adjustment_corrects_to_higher_quantity(
    product_id: int, warehouse_id: int
) -> None:
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
        new_quantity=Decimal("15"),
        reason="Conteo físico",
        created_by_user_id=None,
    )

    overview = service.list_stock_overview()
    assert overview[0].quantity == Decimal("15")


def test_register_adjustment_with_negative_quantity_is_rejected(
    product_id: int, warehouse_id: int
) -> None:
    service = InventoryService(EventBus())

    with pytest.raises(BusinessRuleViolationError):
        service.register_adjustment(
            product_id=product_id,
            warehouse_id=warehouse_id,
            new_quantity=Decimal("-1"),
            reason=None,
            created_by_user_id=None,
        )


def test_register_adjustment_with_same_quantity_is_a_no_op(
    product_id: int, warehouse_id: int
) -> None:
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
        new_quantity=Decimal("10"),
        reason=None,
        created_by_user_id=None,
    )

    overview = service.list_stock_overview()
    assert overview[0].quantity == Decimal("10")


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


def test_create_warehouse(sqlite_engine: None) -> None:
    service = InventoryService(EventBus())

    warehouse = service.create_warehouse(name="Bodega Norte", location="Calle 1")

    assert warehouse.name == "Bodega Norte"
    assert warehouse.location == "Calle 1"
    assert warehouse.is_active is True


def test_create_warehouse_with_duplicate_name_raises_conflict(sqlite_engine: None) -> None:
    service = InventoryService(EventBus())
    service.create_warehouse(name="Bodega Norte")

    with pytest.raises(ConflictError):
        service.create_warehouse(name="Bodega Norte")


def test_update_warehouse_renames(warehouse_id: int) -> None:
    service = InventoryService(EventBus())

    updated = service.update_warehouse(warehouse_id, name="Bodega Renombrada")

    assert updated.name == "Bodega Renombrada"


def test_update_unknown_warehouse_raises_not_found(sqlite_engine: None) -> None:
    service = InventoryService(EventBus())

    with pytest.raises(NotFoundError):
        service.update_warehouse(9999, name="No existe")


def test_set_warehouse_active_toggles_and_hides_from_active_list(warehouse_id: int) -> None:
    service = InventoryService(EventBus())

    updated = service.set_warehouse_active(warehouse_id, False)

    assert updated.is_active is False
    assert all(w.id != warehouse_id for w in service.list_warehouses())
    assert any(w.id == warehouse_id for w in service.list_all_warehouses())


def test_ensure_stock_levels_backfills_zero_stock_for_existing_products(
    warehouse_id: int, product_id: int
) -> None:
    service = InventoryService(EventBus())
    other_warehouse = service.create_warehouse(name="Bodega Nueva")

    service.ensure_stock_levels(other_warehouse.id, [product_id])

    overview = {s.warehouse_id: s.quantity for s in service.list_stock_overview()}
    assert overview[other_warehouse.id] == Decimal("0")


def test_list_stock_summary_sums_quantity_across_warehouses(
    product_id: int, warehouse_id: int
) -> None:
    from pos.modules.inventory.domain.enums import StockStatus

    service = InventoryService(EventBus())
    other_warehouse = service.create_warehouse(name="Bodega Patio")
    service.set_minimum_stock(product_id, Decimal("20"))
    service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("53"),
        reason=None,
        created_by_user_id=None,
    )
    service.register_entry(
        product_id=product_id,
        warehouse_id=other_warehouse.id,
        quantity=Decimal("32"),
        reason=None,
        created_by_user_id=None,
    )

    summary = service.list_stock_summary()

    assert len(summary) == 1
    assert summary[0].total_quantity == Decimal("85")
    assert summary[0].status is StockStatus.NORMAL


def test_list_stock_summary_flags_out_of_stock_and_low_stock(
    product_id: int, warehouse_id: int
) -> None:
    from pos.modules.inventory.domain.enums import StockStatus

    service = InventoryService(EventBus())
    service.set_minimum_stock(product_id, Decimal("20"))
    service.ensure_stock_levels(warehouse_id, [product_id])

    out_of_stock = service.list_stock_summary()
    assert out_of_stock[0].status is StockStatus.OUT

    service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("5"),
        reason=None,
        created_by_user_id=None,
    )
    low_stock = service.list_stock_summary()
    assert low_stock[0].status is StockStatus.LOW


def test_get_stock_detail_includes_zero_quantity_warehouses(
    product_id: int, warehouse_id: int
) -> None:
    service = InventoryService(EventBus())
    other_warehouse = service.create_warehouse(name="Bodega Norte")
    service.ensure_stock_levels(other_warehouse.id, [product_id])
    service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("53"),
        reason=None,
        created_by_user_id=None,
    )

    detail = service.get_stock_detail(product_id)

    quantities = {d.warehouse_id: d.quantity for d in detail}
    assert quantities[warehouse_id] == Decimal("53")
    assert quantities[other_warehouse.id] == Decimal("0")


def test_list_stock_by_warehouse_excludes_zero_quantity_products(
    product_id: int, warehouse_id: int
) -> None:
    service = InventoryService(EventBus())

    empty_result = service.list_stock_by_warehouse(warehouse_id)
    assert empty_result == []

    service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("15"),
        reason=None,
        created_by_user_id=None,
    )

    result = service.list_stock_by_warehouse(warehouse_id)
    assert len(result) == 1
    assert result[0].quantity == Decimal("15")


def test_list_movements_returns_full_history_with_product_and_warehouse_names(
    product_id: int, warehouse_id: int
) -> None:
    service = InventoryService(EventBus())
    service.register_entry(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("10"),
        reason="Compra inicial",
        created_by_user_id=None,
    )
    service.register_exit(
        product_id=product_id,
        warehouse_id=warehouse_id,
        quantity=Decimal("3"),
        reason="Venta",
        created_by_user_id=None,
    )

    movements = service.list_movements()

    assert len(movements) == 2
    assert movements[0].reason == "Venta"
    assert movements[1].reason == "Compra inicial"
    assert all(m.product_name == "Producto de prueba" for m in movements)
    assert all(m.warehouse_name == "Bodega Principal" for m in movements)
