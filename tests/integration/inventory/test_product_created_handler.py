"""Prueba de integración del patrón de comunicación entre módulos vía
eventos (ver ARCHITECTURE.md §5): Inventario reacciona a que Productos
publique `ProductCreatedEvent` creando el `StockLevel` inicial."""

from __future__ import annotations

from decimal import Decimal

from pos.core.events.bus import EventBus
from pos.modules.inventory.application.event_handlers import InventoryProductEventHandlers
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.products.domain.enums import ProductType
from pos.modules.products.domain.events import ProductCreatedEvent


def test_creating_a_tracked_product_initializes_stock_in_every_warehouse(
    sqlite_engine: None, warehouse_id: int
) -> None:
    bus = EventBus()
    inventory_service = InventoryService(bus)
    handlers = InventoryProductEventHandlers(inventory_service)
    bus.subscribe(ProductCreatedEvent, handlers.on_product_created)

    product_service = ProductManagementService(bus)
    product = product_service.create_product(
        sku="EVT-1",
        name="Producto con seguimiento",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("10"),
        cost_price=Decimal("5"),
        unit_of_measure="unidad",
        track_inventory=True,
        tax_codes=set(),
    )

    overview = inventory_service.list_stock_overview()
    matching = [s for s in overview if s.product_id == product.id]
    assert len(matching) == 1
    assert matching[0].warehouse_id == warehouse_id
    assert matching[0].quantity == Decimal("0")


def test_creating_a_non_tracked_product_does_not_create_stock(
    sqlite_engine: None, warehouse_id: int
) -> None:
    bus = EventBus()
    inventory_service = InventoryService(bus)
    handlers = InventoryProductEventHandlers(inventory_service)
    bus.subscribe(ProductCreatedEvent, handlers.on_product_created)

    product_service = ProductManagementService(bus)
    product = product_service.create_product(
        sku="EVT-2",
        name="Servicio sin inventario",
        description=None,
        category_id=None,
        product_type=ProductType.SIMPLE,
        unit_price=Decimal("10"),
        cost_price=Decimal("5"),
        unit_of_measure="unidad",
        track_inventory=False,
        tax_codes=set(),
    )

    overview = inventory_service.list_stock_overview()
    assert not [s for s in overview if s.product_id == product.id]
