"""Casos de uso de inventario: entradas, salidas, transferencias, ajustes
y alertas de stock mínimo (PROJECT_SPEC.md, "INVENTARIO")."""

from __future__ import annotations

from decimal import Decimal

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError
from pos.modules.inventory.application.dto import StockLevelDTO, WarehouseDTO
from pos.modules.inventory.domain.enums import StockMovementType
from pos.modules.inventory.domain.events import StockLevelChangedEvent
from pos.modules.inventory.infrastructure.models import StockLevel
from pos.modules.inventory.infrastructure.repository import InventoryRepository


def _stock_dto(
    stock_level: StockLevel, sku: str, product_name: str, warehouse_name: str, min_quantity: Decimal
) -> StockLevelDTO:
    return StockLevelDTO(
        product_id=stock_level.product_id,
        product_name=product_name,
        product_sku=sku,
        warehouse_id=stock_level.warehouse_id,
        warehouse_name=warehouse_name,
        quantity=stock_level.quantity,
        min_quantity=min_quantity,
        is_below_minimum=stock_level.quantity < min_quantity,
    )


class InventoryService:
    """Movimientos de inventario y consulta de existencias."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def list_warehouses(self) -> list[WarehouseDTO]:
        with session_scope() as session:
            repo = InventoryRepository(session)
            return [
                WarehouseDTO(id=w.id, name=w.name, location=w.location, is_active=w.is_active)
                for w in repo.list_warehouses()
            ]

    def create_warehouse(self, *, name: str, location: str | None = None) -> WarehouseDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la bodega no puede estar vacío.")
        with session_scope() as session:
            repo = InventoryRepository(session)
            warehouse = repo.create_warehouse(name=name, location=location)
            return WarehouseDTO(
                id=warehouse.id,
                name=warehouse.name,
                location=warehouse.location,
                is_active=warehouse.is_active,
            )

    def initialize_stock_for_all_warehouses(self, product_id: int) -> None:
        """Crea el `StockLevel` inicial en 0 de un producto en cada bodega
        activa. Se invoca al reaccionar a `ProductCreatedEvent` (ver
        `main.py`, registro de manejadores de eventos)."""
        with session_scope() as session:
            repo = InventoryRepository(session)
            for warehouse in repo.list_warehouses():
                repo.ensure_stock_level(product_id, warehouse.id)

    def get_available_quantity(self, product_id: int, warehouse_id: int) -> Decimal:
        """Cantidad disponible de un producto en una bodega. Usado por
        Ventas para validar stock suficiente antes de completar una venta
        (llamada directa síncrona, no evento — ver ARCHITECTURE.md §5b)."""
        with session_scope() as session:
            repo = InventoryRepository(session)
            stock_level = repo.get_stock_level(product_id, warehouse_id)
            return stock_level.quantity if stock_level is not None else Decimal(0)

    def list_stock_overview(self) -> list[StockLevelDTO]:
        with session_scope() as session:
            repo = InventoryRepository(session)
            return [
                _stock_dto(stock_level, sku, name, warehouse_name, min_qty)
                for stock_level, sku, name, warehouse_name, min_qty in repo.list_stock_overview()
            ]

    def set_minimum_stock(self, product_id: int, min_quantity: Decimal) -> None:
        if min_quantity < 0:
            raise BusinessRuleViolationError("El stock mínimo no puede ser negativo.")
        with session_scope() as session:
            repo = InventoryRepository(session)
            repo.set_min_quantity(product_id, min_quantity)

    def register_entry(
        self,
        *,
        product_id: int,
        warehouse_id: int,
        quantity: Decimal,
        reason: str | None,
        created_by_user_id: int | None,
    ) -> None:
        self._apply_movement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=StockMovementType.ENTRY,
            quantity=quantity,
            reason=reason,
            created_by_user_id=created_by_user_id,
            delta=quantity,
        )

    def register_exit(
        self,
        *,
        product_id: int,
        warehouse_id: int,
        quantity: Decimal,
        reason: str | None,
        created_by_user_id: int | None,
    ) -> None:
        self._apply_movement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=StockMovementType.EXIT,
            quantity=quantity,
            reason=reason,
            created_by_user_id=created_by_user_id,
            delta=-quantity,
        )

    def register_adjustment(
        self,
        *,
        product_id: int,
        warehouse_id: int,
        quantity: Decimal,
        increase: bool,
        reason: str | None,
        created_by_user_id: int | None,
    ) -> None:
        self._apply_movement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=StockMovementType.ADJUSTMENT,
            quantity=quantity,
            reason=reason,
            created_by_user_id=created_by_user_id,
            delta=quantity if increase else -quantity,
        )

    def transfer(
        self,
        *,
        product_id: int,
        source_warehouse_id: int,
        destination_warehouse_id: int,
        quantity: Decimal,
        created_by_user_id: int | None,
    ) -> None:
        if source_warehouse_id == destination_warehouse_id:
            raise BusinessRuleViolationError(
                "La bodega de origen y destino no pueden ser la misma."
            )
        if quantity <= 0:
            raise BusinessRuleViolationError("La cantidad a transferir debe ser mayor que cero.")

        with session_scope() as session:
            repo = InventoryRepository(session)
            source = repo.ensure_stock_level(product_id, source_warehouse_id)
            if source.quantity < quantity:
                raise BusinessRuleViolationError(
                    f"Stock insuficiente en la bodega de origen: hay {source.quantity}, "
                    f"se requieren {quantity}."
                )
            destination = repo.ensure_stock_level(product_id, destination_warehouse_id)

            source.quantity -= quantity
            destination.quantity += quantity

            repo.record_movement(
                product_id=product_id,
                warehouse_id=source_warehouse_id,
                movement_type=StockMovementType.TRANSFER,
                quantity=quantity,
                reason=f"Transferencia a bodega {destination_warehouse_id}",
                created_by_user_id=created_by_user_id,
            )
            repo.record_movement(
                product_id=product_id,
                warehouse_id=destination_warehouse_id,
                movement_type=StockMovementType.TRANSFER,
                quantity=quantity,
                reason=f"Transferencia desde bodega {source_warehouse_id}",
                created_by_user_id=created_by_user_id,
            )
            min_quantity = repo.get_min_quantity(product_id)
            source_quantity_after = source.quantity

        self._event_bus.publish(
            StockLevelChangedEvent(
                product_id=product_id,
                warehouse_id=source_warehouse_id,
                new_quantity=source_quantity_after,
                is_below_minimum=source_quantity_after < min_quantity,
            )
        )

    def _apply_movement(
        self,
        *,
        product_id: int,
        warehouse_id: int,
        movement_type: StockMovementType,
        quantity: Decimal,
        reason: str | None,
        created_by_user_id: int | None,
        delta: Decimal,
    ) -> None:
        if quantity <= 0:
            raise BusinessRuleViolationError("La cantidad debe ser mayor que cero.")

        with session_scope() as session:
            repo = InventoryRepository(session)
            stock_level = repo.ensure_stock_level(product_id, warehouse_id)
            new_quantity = stock_level.quantity + delta
            if new_quantity < 0:
                raise BusinessRuleViolationError(
                    f"Stock insuficiente: hay {stock_level.quantity}, "
                    f"la operación requiere {-delta}."
                )
            stock_level.quantity = new_quantity

            repo.record_movement(
                product_id=product_id,
                warehouse_id=warehouse_id,
                movement_type=movement_type,
                quantity=quantity,
                reason=reason,
                created_by_user_id=created_by_user_id,
            )
            min_quantity = repo.get_min_quantity(product_id)

        self._event_bus.publish(
            StockLevelChangedEvent(
                product_id=product_id,
                warehouse_id=warehouse_id,
                new_quantity=new_quantity,
                is_below_minimum=new_quantity < min_quantity,
            )
        )
