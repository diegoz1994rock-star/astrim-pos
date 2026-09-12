"""Acceso a datos de inventario: bodegas, existencias y movimientos."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func, select
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

    def list_all_warehouses(self) -> list[Warehouse]:
        return list(self._session.scalars(select(Warehouse).order_by(Warehouse.name)))

    def get_warehouse(self, warehouse_id: int) -> Warehouse | None:
        return self._session.get(Warehouse, warehouse_id)

    def get_warehouse_by_name(self, name: str) -> Warehouse | None:
        return self._session.scalar(select(Warehouse).where(Warehouse.name == name))

    def create_warehouse(self, *, name: str, location: str | None) -> Warehouse:
        warehouse = Warehouse(name=name, location=location, is_active=True)
        self._session.add(warehouse)
        self._session.flush()
        return warehouse

    def update_warehouse(self, warehouse: Warehouse, *, name: str, location: str | None) -> None:
        warehouse.name = name
        warehouse.location = location
        self._session.flush()

    def set_warehouse_active(self, warehouse: Warehouse, is_active: bool) -> None:
        warehouse.is_active = is_active

    def get_stock_level(self, product_id: int, warehouse_id: int) -> StockLevel | None:
        return self._session.scalar(
            select(StockLevel).where(
                StockLevel.product_id == product_id, StockLevel.warehouse_id == warehouse_id
            )
        )

    def get_total_available_quantity(self, product_id: int) -> Decimal:
        """Suma de `StockLevel.quantity` en las bodegas ACTIVAS para un
        producto — la venta ya no valida contra una sola bodega, sino
        contra este total (ver `SalesService.complete_sale`). Una bodega
        desactivada no es "vendible" en la práctica (ver `set_warehouse_
        active`), así que su stock no debe contar como disponible aunque
        la fila de `StockLevel` siga existiendo."""
        result = self._session.execute(
            select(func.coalesce(func.sum(StockLevel.quantity), 0))
            .join(Warehouse, Warehouse.id == StockLevel.warehouse_id)
            .where(StockLevel.product_id == product_id, Warehouse.is_active.is_(True))
        ).scalar()
        return result if result is not None else Decimal(0)

    def sum_available_quantities(self, product_ids: list[int]) -> dict[int, Decimal]:
        """Igual que `get_total_available_quantity`, pero para varios
        productos en una sola consulta — evita hacer una consulta (y abrir
        una sesión) por línea al validar el stock de una venta completa."""
        if not product_ids:
            return {}
        rows = self._session.execute(
            select(StockLevel.product_id, func.coalesce(func.sum(StockLevel.quantity), 0))
            .join(Warehouse, Warehouse.id == StockLevel.warehouse_id)
            .where(StockLevel.product_id.in_(product_ids), Warehouse.is_active.is_(True))
            .group_by(StockLevel.product_id)
        ).all()
        return {product_id: total for product_id, total in rows}

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

    def list_stock_summary(self) -> list[tuple[int, str, str, Decimal, Decimal]]:
        """Devuelve (product_id, sku, nombre, cantidad_total, cantidad_mínima)
        — una fila por producto, sumando `StockLevel.quantity` de todas sus
        bodegas. Base de la pantalla principal de Existencias."""
        rows = self._session.execute(
            select(
                Product.id,
                Product.sku,
                Product.name,
                func.coalesce(func.sum(StockLevel.quantity), 0),
                StockAlertConfig.min_quantity,
            )
            .join(StockLevel, StockLevel.product_id == Product.id)
            .outerjoin(StockAlertConfig, StockAlertConfig.product_id == Product.id)
            .where(Product.is_deleted.is_(False))
            .group_by(Product.id, Product.sku, Product.name, StockAlertConfig.min_quantity)
            .order_by(Product.name)
        )
        return [(row[0], row[1], row[2], row[3], row[4] or Decimal(0)) for row in rows]

    def list_stock_overview_for_product(
        self, product_id: int
    ) -> list[tuple[StockLevel, str, str, str, Decimal]]:
        """Misma forma que `list_stock_overview` pero filtrada a un solo
        producto — incluye bodegas en 0, para el detalle "Ver"."""
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
            .where(Product.is_deleted.is_(False), StockLevel.product_id == product_id)
            .order_by(Warehouse.name)
        )
        return [(row[0], row[1], row[2], row[3], row[4] or Decimal(0)) for row in rows]

    def list_stock_overview_for_warehouse(
        self, warehouse_id: int
    ) -> list[tuple[StockLevel, str, str, str, Decimal]]:
        """Misma forma que `list_stock_overview` pero filtrada a una sola
        bodega y solo con cantidad > 0 — para "Bodegas → Ver productos",
        donde no tiene sentido listar todo el catálogo en 0."""
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
            .where(
                Product.is_deleted.is_(False),
                StockLevel.warehouse_id == warehouse_id,
                StockLevel.quantity > 0,
            )
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

    def sum_exits_by_reference(
        self, *, reference_document_type: str, reference_document_id: int
    ) -> list[tuple[int, int, Decimal]]:
        """Cantidad total de salida (`StockMovementType.EXIT`) por
        producto/bodega para un documento de referencia (ej. una venta) —
        permite reconstruir de qué bodega(s) exactas salió cada producto en
        vez de asumir una sola bodega, ya que `_allocate_and_register_exit`
        puede repartir una misma línea entre varias."""
        rows = self._session.execute(
            select(
                StockMovement.product_id,
                StockMovement.warehouse_id,
                func.sum(StockMovement.quantity),
            )
            .where(
                StockMovement.movement_type == StockMovementType.EXIT,
                StockMovement.reference_document_type == reference_document_type,
                StockMovement.reference_document_id == reference_document_id,
            )
            .group_by(StockMovement.product_id, StockMovement.warehouse_id)
        ).all()
        return [(row[0], row[1], row[2]) for row in rows]

    def list_movements_for_product(self, product_id: int) -> list[StockMovement]:
        return list(
            self._session.scalars(
                select(StockMovement)
                .where(StockMovement.product_id == product_id)
                .order_by(StockMovement.created_at.desc())
            )
        )

    def list_movements(self) -> list[tuple[StockMovement, str, str, str]]:
        """Devuelve (movimiento, sku, nombre_producto, nombre_bodega) del
        historial completo, más reciente primero — para la pantalla
        "Movimientos"."""
        rows = self._session.execute(
            select(StockMovement, Product.sku, Product.name, Warehouse.name)
            .join(Product, Product.id == StockMovement.product_id)
            .join(Warehouse, Warehouse.id == StockMovement.warehouse_id)
            .order_by(StockMovement.created_at.desc())
        )
        return [(row[0], row[1], row[2], row[3]) for row in rows]
