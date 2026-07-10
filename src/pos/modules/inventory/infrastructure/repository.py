"""Acceso a datos de inventario: bodegas, existencias y movimientos."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.inventory.domain.enums import StockMovementType
from pos.modules.inventory.infrastructure.models import (
    StockAlertConfig,
    StockLevel,
    StockMovement,
    Warehouse,
)
from pos.modules.products.infrastructure.models import Product


class InventoryRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_warehouses(self) -> list[Warehouse]:
        return list(
            self._session.scalars(
                select(Warehouse).where(Warehouse.is_active.is_(True)).order_by(Warehouse.name)
            )
        )

    def get_warehouse(self, warehouse_id: int) -> Warehouse | None:
        return self._session.get(Warehouse, warehouse_id)

    def create_warehouse(self, *, name: str, location: str | None) -> Warehouse:
        warehouse = Warehouse(name=name, location=location, is_active=True)
        self._session.add(warehouse)
        self._session.flush()
        return warehouse

    def get_stock_level(self, product_id: int, warehouse_id: int) -> StockLevel | None:
        return self._session.scalar(
            select(StockLevel).where(
                StockLevel.product_id == product_id, StockLevel.warehouse_id == warehouse_id
            )
        )

    def ensure_stock_level(self, product_id: int, warehouse_id: int) -> StockLevel:
        stock_level = self.get_stock_level(product_id, warehouse_id)
        if stock_level is None:
            stock_level = StockLevel(
                product_id=product_id, warehouse_id=warehouse_id, quantity=Decimal(0)
            )
            self._session.add(stock_level)
            self._session.flush()
        return stock_level

    def list_stock_overview(self) -> list[tuple[StockLevel, str, str, str, Decimal]]:
        """Devuelve (stock_level, sku, nombre_producto, nombre_bodega, cantidad_minima)."""
        rows = self._session.execute(
            select(
                StockLevel,
                Product.sku,
                Product.name,
                Warehouse.name,
                StockAlertConfig.min_quantity,
            )
            .join(Product, Product.id == StockLevel.product_id)
            .join(Warehouse, Warehouse.id == StockLevel.warehouse_id)
            .outerjoin(StockAlertConfig, StockAlertConfig.product_id == StockLevel.product_id)
            .where(Product.is_deleted.is_(False))
            .order_by(Product.name)
        )
        return [(row[0], row[1], row[2], row[3], row[4] or Decimal(0)) for row in rows]

    def get_min_quantity(self, product_id: int) -> Decimal:
        config = self._session.scalar(
            select(StockAlertConfig).where(StockAlertConfig.product_id == product_id)
        )
        return config.min_quantity if config is not None else Decimal(0)

    def set_min_quantity(self, product_id: int, min_quantity: Decimal) -> None:
        config = self._session.scalar(
            select(StockAlertConfig).where(StockAlertConfig.product_id == product_id)
        )
        if config is None:
            self._session.add(StockAlertConfig(product_id=product_id, min_quantity=min_quantity))
        else:
            config.min_quantity = min_quantity

    def record_movement(
        self,
        *,
        product_id: int,
        warehouse_id: int,
        movement_type: StockMovementType,
        quantity: Decimal,
        reason: str | None,
        created_by_user_id: int | None,
        reference_document_type: str | None = None,
        reference_document_id: int | None = None,
    ) -> StockMovement:
        movement = StockMovement(
            product_id=product_id,
            warehouse_id=warehouse_id,
            movement_type=movement_type,
            quantity=quantity,
            reason=reason,
            created_by_user_id=created_by_user_id,
            reference_document_type=reference_document_type,
            reference_document_id=reference_document_id,
        )
        self._session.add(movement)
        self._session.flush()
        return movement

    def list_movements_for_product(self, product_id: int) -> list[StockMovement]:
        return list(
            self._session.scalars(
                select(StockMovement)
                .where(StockMovement.product_id == product_id)
                .order_by(StockMovement.created_at.desc())
            )
        )
