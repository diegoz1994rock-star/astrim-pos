"""Caso de uso de Restaurante: mesas, sesiones de mesa y pedidos
(PROJECT_SPEC.md, "RESTAURANTES").

**Alcance de esta versión**: cubre el ciclo completo desde que se sienta
un cliente hasta que la cocina entrega los platos — mesas, sesiones,
pedidos e ítems. Convertir los pedidos de una sesión de mesa cerrada en
una `Sale` real de Ventas (el "cobro de mesa") queda fuera a propósito:
`Order`/`OrderItem` hoy no registran precio/impuesto por línea (esa
responsabilidad vive en `sales.SaleItem`), así que ese paso necesita su
propio diseño de conciliación de precios — no se improvisa aquí. Cerrar
una sesión de mesa hoy solo libera la mesa; queda documentado como
extensión futura en MODULES.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.products.infrastructure.product_repository import ProductRepository
from pos.modules.restaurant.application.dto import (
    DiningTableDTO,
    OrderDTO,
    OrderItemDTO,
    TableSessionDTO,
)
from pos.modules.restaurant.domain.enums import OrderStatus, OrderType, TableStatus
from pos.modules.restaurant.infrastructure.models import DiningTable, Order, TableSession
from pos.modules.restaurant.infrastructure.repository import RestaurantRepository


def _table_to_dto(table: DiningTable) -> DiningTableDTO:
    return DiningTableDTO(
        id=table.id, name=table.name, capacity=table.capacity, zone=table.zone, status=table.status
    )


def _session_to_dto(table_session: TableSession) -> TableSessionDTO:
    return TableSessionDTO(
        id=table_session.id,
        table_id=table_session.table_id,
        waiter_user_id=table_session.waiter_user_id,
        status=table_session.status,
        opened_at=table_session.opened_at,
        closed_at=table_session.closed_at,
    )


def _order_to_dto(order: Order, product_names: dict[int, str]) -> OrderDTO:
    return OrderDTO(
        id=order.id,
        table_session_id=order.table_session_id,
        order_type=order.order_type,
        status=order.status,
        items=[
            OrderItemDTO(
                id=item.id,
                order_id=order.id,
                product_id=item.product_id,
                product_name=product_names.get(item.product_id, "?"),
                quantity=item.quantity,
                notes=item.notes,
                status=item.status,
            )
            for item in order.items
        ],
    )


class RestaurantService:
    # -- Mesas ------------------------------------------------------------

    def list_tables(self) -> list[DiningTableDTO]:
        with session_scope() as session:
            return [_table_to_dto(t) for t in RestaurantRepository(session).list_tables()]

    def create_table(
        self, *, name: str, capacity: int = 4, zone: str | None = None
    ) -> DiningTableDTO:
        name = name.strip()
        if not name:
            raise BusinessRuleViolationError("El nombre de la mesa no puede estar vacío.")
        if capacity <= 0:
            raise BusinessRuleViolationError("La capacidad debe ser mayor que cero.")
        with session_scope() as session:
            table = RestaurantRepository(session).create_table(
                name=name, capacity=capacity, zone=zone
            )
            return _table_to_dto(table)

    # -- Sesiones de mesa ---------------------------------------------------

    def open_table_session(self, *, table_id: int, waiter_user_id: int) -> TableSessionDTO:
        with session_scope() as session:
            repo = RestaurantRepository(session)
            table = repo.get_table(table_id)
            if table is None:
                raise NotFoundError(f"No existe la mesa con id={table_id}.")
            if table.status is not TableStatus.FREE:
                raise BusinessRuleViolationError(f"La mesa '{table.name}' no está libre.")
            table_session = repo.create_session(table_id=table_id, waiter_user_id=waiter_user_id)
            repo.set_table_status(table, TableStatus.OCCUPIED)
            return _session_to_dto(table_session)

    def close_table_session(self, session_id: int) -> None:
        with session_scope() as session:
            repo = RestaurantRepository(session)
            table_session = repo.get_session(session_id)
            if table_session is None:
                raise NotFoundError(f"No existe la sesión de mesa con id={session_id}.")
            table = repo.get_table(table_session.table_id)
            repo.close_session(table_session, closed_at=datetime.now(UTC))
            if table is not None:
                repo.set_table_status(table, TableStatus.FREE)

    def list_open_table_sessions(self) -> list[TableSessionDTO]:
        with session_scope() as session:
            return [
                _session_to_dto(s) for s in RestaurantRepository(session).list_open_sessions()
            ]

    # -- Pedidos ------------------------------------------------------------

    def create_order(
        self,
        *,
        table_session_id: int | None,
        order_type: OrderType,
        items: list[tuple[int, int, str | None]],
    ) -> OrderDTO:
        """`items` es `(product_id, cantidad, notas)`."""
        if not items:
            raise BusinessRuleViolationError("El pedido debe tener al menos un producto.")
        if order_type is OrderType.DINE_IN and table_session_id is None:
            raise BusinessRuleViolationError(
                "Un pedido para consumo en el local requiere una sesión de mesa."
            )
        with session_scope() as session:
            repo = RestaurantRepository(session)
            product_repo = ProductRepository(session)
            order = repo.create_order(table_session_id=table_session_id, order_type=order_type)
            product_names: dict[int, str] = {}
            for product_id, quantity, notes in items:
                if quantity <= 0:
                    raise BusinessRuleViolationError(
                        "La cantidad de cada línea debe ser mayor que cero."
                    )
                product = product_repo.get(product_id)
                if product is None:
                    raise NotFoundError(f"No existe el producto con id={product_id}.")
                repo.add_order_item(order, product_id=product_id, quantity=quantity, notes=notes)
                product_names[product_id] = product.name
            return _order_to_dto(order, product_names)

    def list_orders_for_session(self, table_session_id: int) -> list[OrderDTO]:
        with session_scope() as session:
            repo = RestaurantRepository(session)
            product_repo = ProductRepository(session)
            orders = repo.list_orders_for_session(table_session_id)
            product_names = _product_names_for_orders(product_repo, orders)
            return [_order_to_dto(order, product_names) for order in orders]

    def mark_order_delivered(self, order_id: int) -> OrderDTO:
        with session_scope() as session:
            repo = RestaurantRepository(session)
            product_repo = ProductRepository(session)
            order = repo.get_order(order_id)
            if order is None:
                raise NotFoundError(f"No existe el pedido con id={order_id}.")
            repo.set_order_status(order, OrderStatus.DELIVERED)
            product_names = _product_names_for_orders(product_repo, [order])
            return _order_to_dto(order, product_names)


def _product_names_for_orders(
    product_repo: ProductRepository, orders: list[Order]
) -> dict[int, str]:
    product_ids = {item.product_id for order in orders for item in order.items}
    names: dict[int, str] = {}
    for product_id in product_ids:
        product = product_repo.get(product_id)
        if product is not None:
            names[product_id] = product.name
    return names
