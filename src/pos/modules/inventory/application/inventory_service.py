"""Casos de uso de inventario: entradas, salidas, transferencias, ajustes
y alertas de stock mínimo (PROJECT_SPEC.md, "INVENTARIO")."""

from __future__ import annotations

from decimal import Decimal

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.inventory.application.dto import (
    StockLevelDTO,
    StockMovementDTO,
    StockSummaryDTO,
    WarehouseDTO,
)
from pos.modules.inventory.domain.enums import StockMovementType, StockStatus
from pos.modules.inventory.domain.events import StockLevelChangedEvent
from pos.modules.inventory.infrastructure.models import StockLevel, StockMovement, Warehouse
from pos.modules.inventory.infrastructure.repository import InventoryRepository


def _warehouse_dto(warehouse: Warehouse) -> WarehouseDTO:
    return WarehouseDTO(
        id=warehouse.id,
        name=warehouse.name,
        location=warehouse.location,
        is_active=warehouse.is_active,
    )


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


def _stock_status(total_quantity: Decimal, min_quantity: Decimal) -> StockStatus:
    if total_quantity <= 0:
        return StockStatus.OUT
    if min_quantity > 0 and total_quantity < min_quantity:
        return StockStatus.LOW
    return StockStatus.NORMAL


def _summary_dto(
    product_id: int, sku: str, name: str, total_quantity: Decimal, min_quantity: Decimal
) -> StockSummaryDTO:
    return StockSummaryDTO(
        product_id=product_id,
        sku=sku,
        name=name,
        total_quantity=total_quantity,
        min_quantity=min_quantity,
        status=_stock_status(total_quantity, min_quantity),
    )


def _movement_dto(movement: StockMovement, product_name: str, warehouse_name: str) -> StockMovementDTO:
    return StockMovementDTO(
        id=movement.id,
        movement_type=movement.movement_type,
        quantity=movement.quantity,
        reason=movement.reason,
        created_at=movement.created_at,
        product_id=movement.product_id,
        product_name=product_name,
        warehouse_id=movement.warehouse_id,
        warehouse_name=warehouse_name,
        reference_document_type=movement.reference_document_type,
        reference_document_id=movement.reference_document_id,
        created_by_user_id=movement.created_by_user_id,
    )


class InventoryService:
    """Movimientos de inventario y consulta de existencias."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def list_warehouses(self) -> list[WarehouseDTO]:
        with session_scope() as session:
            repo = InventoryRepository(session)
            return [_warehouse_dto(w) for w in repo.list_warehouses()]

    def list_all_warehouses(self) -> list[WarehouseDTO]:
        with session_scope() as session:
            repo = InventoryRepository(session)
            return [_warehouse_dto(w) for w in repo.list_all_warehouses()]

    def create_warehouse(self, *, name: str, location: str | None = None) -> WarehouseDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la bodega no puede estar vacío.")
        with session_scope() as session:
            repo = InventoryRepository(session)
            if repo.get_warehouse_by_name(name) is not None:
                raise ConflictError(f"Ya existe una bodega llamada '{name}'.")
            warehouse = repo.create_warehouse(name=name, location=location)
            return _warehouse_dto(warehouse)

    def update_warehouse(
        self, warehouse_id: int, *, name: str, location: str | None = None
    ) -> WarehouseDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la bodega no puede estar vacío.")
        with session_scope() as session:
            repo = InventoryRepository(session)
            warehouse = repo.get_warehouse(warehouse_id)
            if warehouse is None:
                raise NotFoundError(f"No existe la bodega con id={warehouse_id}.")
            existing = repo.get_warehouse_by_name(name)
            if existing is not None and existing.id != warehouse_id:
                raise ConflictError(f"Ya existe una bodega llamada '{name}'.")
            repo.update_warehouse(warehouse, name=name, location=location)
            return _warehouse_dto(warehouse)

    def set_warehouse_active(self, warehouse_id: int, is_active: bool) -> WarehouseDTO:
        with session_scope() as session:
            repo = InventoryRepository(session)
            warehouse = repo.get_warehouse(warehouse_id)
            if warehouse is None:
                raise NotFoundError(f"No existe la bodega con id={warehouse_id}.")
            repo.set_warehouse_active(warehouse, is_active)
            return _warehouse_dto(warehouse)

    def ensure_stock_levels(self, warehouse_id: int, product_ids: list[int]) -> None:
        """Crea el `StockLevel` inicial en 0 de varios productos en una
        bodega. Se invoca al crear una bodega nueva, para que los productos
        ya existentes en Catálogo aparezcan de inmediato en Inventario
        (contraparte de `initialize_stock_for_all_warehouses`, que hace lo
        mismo en la dirección producto→bodegas)."""
        with session_scope() as session:
            repo = InventoryRepository(session)
            for product_id in product_ids:
                repo.ensure_stock_level(product_id, warehouse_id)

    def initialize_stock_for_all_warehouses(self, product_id: int) -> None:
        """Crea el `StockLevel` inicial en 0 de un producto en cada bodega
        activa. Se invoca al reaccionar a `ProductCreatedEvent` (ver
        `main.py`, registro de manejadores de eventos)."""
        with session_scope() as session:
            repo = InventoryRepository(session)
            for warehouse in repo.list_warehouses():
                repo.ensure_stock_level(product_id, warehouse.id)

    def get_available_quantity(self, product_id: int, warehouse_id: int) -> Decimal:
        """Cantidad disponible de un producto en una bodega."""
        with session_scope() as session:
            repo = InventoryRepository(session)
            stock_level = repo.get_stock_level(product_id, warehouse_id)
            return stock_level.quantity if stock_level is not None else Decimal(0)

    def get_total_available_quantity(self, product_id: int) -> Decimal:
        """Cantidad disponible de un producto sumando todas las bodegas —
        la venta valida y descuenta contra el inventario general, no
        contra una bodega específica (ver `SalesService.complete_sale`)."""
        with session_scope() as session:
            return InventoryRepository(session).get_total_available_quantity(product_id)

    def list_stock_overview(self) -> list[StockLevelDTO]:
        with session_scope() as session:
            repo = InventoryRepository(session)
            return [
                _stock_dto(stock_level, sku, name, warehouse_name, min_qty)
                for stock_level, sku, name, warehouse_name, min_qty in repo.list_stock_overview()
            ]

    def list_stock_summary(self) -> list[StockSummaryDTO]:
        """Una fila por producto con la existencia total (suma de todas las
        bodegas) — pantalla principal de Existencias."""
        with session_scope() as session:
            repo = InventoryRepository(session)
            return [
                _summary_dto(product_id, sku, name, total_quantity, min_qty)
                for product_id, sku, name, total_quantity, min_qty in repo.list_stock_summary()
            ]

    def get_stock_detail(self, product_id: int) -> list[StockLevelDTO]:
        """Distribución por bodega de un producto (incluye bodegas en 0),
        para el diálogo "Ver" de Existencias."""
        with session_scope() as session:
            repo = InventoryRepository(session)
            return [
                _stock_dto(stock_level, sku, name, warehouse_name, min_qty)
                for stock_level, sku, name, warehouse_name, min_qty in (
                    repo.list_stock_overview_for_product(product_id)
                )
            ]

    def list_stock_by_warehouse(self, warehouse_id: int) -> list[StockLevelDTO]:
        """Productos con existencia (> 0) en una bodega, para "Bodegas →
        Ver productos"."""
        with session_scope() as session:
            repo = InventoryRepository(session)
            return [
                _stock_dto(stock_level, sku, name, warehouse_name, min_qty)
                for stock_level, sku, name, warehouse_name, min_qty in (
                    repo.list_stock_overview_for_warehouse(warehouse_id)
                )
            ]

    def list_movements(self) -> list[StockMovementDTO]:
        """Historial completo de movimientos de inventario, más reciente
        primero, para la pantalla "Movimientos"."""
        with session_scope() as session:
            repo = InventoryRepository(session)
            return [
                _movement_dto(movement, product_name, warehouse_name)
                for movement, sku, product_name, warehouse_name in repo.list_movements()
            ]

    def get_exit_breakdown_by_reference(
        self, *, reference_document_type: str, reference_document_id: int
    ) -> dict[int, list[tuple[int, Decimal]]]:
        """Por cada producto, de qué bodega(s) exactas salió y cuánto, para
        un documento de referencia (ej. una venta) — usado para revertir
        (anulación) reponiendo cada cantidad a la bodega real de donde
        salió, en vez de asumir que todo salió de una sola."""
        with session_scope() as session:
            repo = InventoryRepository(session)
            rows = repo.sum_exits_by_reference(
                reference_document_type=reference_document_type,
                reference_document_id=reference_document_id,
            )
        breakdown: dict[int, list[tuple[int, Decimal]]] = {}
        for product_id, warehouse_id, quantity in rows:
            breakdown.setdefault(product_id, []).append((warehouse_id, quantity))
        return breakdown

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
        reference_document_type: str | None = None,
        reference_document_id: int | None = None,
    ) -> None:
        self._apply_movement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=StockMovementType.EXIT,
            quantity=quantity,
            reason=reason,
            created_by_user_id=created_by_user_id,
            delta=-quantity,
            reference_document_type=reference_document_type,
            reference_document_id=reference_document_id,
        )

    def register_adjustment(
        self,
        *,
        product_id: int,
        warehouse_id: int,
        new_quantity: Decimal,
        reason: str | None,
        created_by_user_id: int | None,
    ) -> None:
        """Corrige la existencia a `new_quantity` (valor absoluto, ej. tras
        un conteo físico) — el sistema calcula internamente si eso implica
        sumar o restar respecto al stock actual, sin pedirle al usuario que
        elija una dirección."""
        if new_quantity < 0:
            raise BusinessRuleViolationError("La cantidad no puede ser negativa.")

        with session_scope() as session:
            repo = InventoryRepository(session)
            stock_level = repo.ensure_stock_level(product_id, warehouse_id)
            delta = new_quantity - stock_level.quantity
            if delta == 0:
                return
            stock_level.quantity = new_quantity

            repo.record_movement(
                product_id=product_id,
                warehouse_id=warehouse_id,
                movement_type=StockMovementType.ADJUSTMENT,
                quantity=abs(delta),
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
        reference_document_type: str | None = None,
        reference_document_id: int | None = None,
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
                reference_document_type=reference_document_type,
                reference_document_id=reference_document_id,
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
