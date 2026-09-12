"""Caso de uso de Restaurante (pantalla Vendedor): mesas, sesiones de mesa
y pedidos.

**Alcance de esta versión**: cubre el ciclo completo desde que se toma un
pedido (con o sin mesa asignada — ver `Order.table_session_id`, nulo para
pedidos rápidos/mostrador) hasta que Despacho lo entrega. `Order`/`OrderItem`
no registran precio/impuesto por línea (esa responsabilidad vive en
`sales.SaleItem`); el puente hacia Caja es `Order.sale_id`: mientras sea
nulo, el pedido aparece como "pendiente de cobro" (`list_pending_payment_orders`)
y Ventas llena su propio carrito con esas líneas — ver
`sales.presentation.sale_view_model.SaleViewModel.load_from_order`. Al
completar la venta, `link_order_to_sale` marca el pedido como cobrado.
"""

from __future__ import annotations

import math
from datetime import UTC, datetime

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.products.infrastructure.product_repository import ProductRepository
from pos.modules.restaurant.application.dto import (
    DiningTableDTO,
    OrderDTO,
    OrderItemDTO,
    TableSessionDTO,
)
from pos.modules.restaurant.domain.enums import OrderItemStatus, OrderOrigin, OrderStatus, OrderType, TableStatus
from pos.modules.restaurant.domain.events import OrderCreatedEvent
from pos.modules.restaurant.infrastructure.models import DiningTable, Order, TableSession
from pos.modules.restaurant.infrastructure.repository import RestaurantRepository
from pos.modules.sales.application.dto import SaleDTO


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


def _order_to_dto(
    order: Order,
    product_names: dict[int, str],
    product_images: dict[int, str | None],
    ready_at: datetime | None = None,
) -> OrderDTO:
    return OrderDTO(
        id=order.id,
        table_session_id=order.table_session_id,
        order_type=order.order_type,
        status=order.status,
        created_at=order.created_at,
        created_by_user_id=order.created_by_user_id,
        sale_id=order.sale_id,
        customer_name=order.customer_name,
        customer_document=order.customer_document,
        origin=order.origin,
        dispatched_by_user_id=order.dispatched_by_user_id,
        ready_at=ready_at,
        items=[
            OrderItemDTO(
                id=item.id,
                order_id=order.id,
                product_id=item.product_id,
                product_name=product_names.get(item.product_id, "?"),
                quantity=item.quantity,
                notes=item.notes,
                status=item.status,
                product_image_path=product_images.get(item.product_id),
            )
            for item in order.items
        ],
    )


DEFAULT_CUSTOMER_NAME = "Consumidor Final"
"""Nombre que se guarda cuando el vendedor no escribe ninguno en el
campo opcional de Vendedor."""


class RestaurantService:
    """Toma de pedidos genérica (pantalla "Vendedor"): funciona con o sin
    mesa asignada, para cualquier tipo de negocio."""

    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

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
        created_by_user_id: int | None = None,
        customer_name: str | None = None,
        customer_document: str | None = None,
        origin: OrderOrigin = OrderOrigin.VENDEDOR,
    ) -> OrderDTO:
        """`items` es `(product_id, cantidad, notas)`. `table_session_id`
        es opcional: nulo para un pedido rápido/de mostrador sin mesa
        asignada (pantalla Vendedor genérica). `customer_name` vacío o
        nulo se guarda como `DEFAULT_CUSTOMER_NAME`."""
        if not items:
            raise BusinessRuleViolationError("El pedido debe tener al menos un producto.")
        if order_type is OrderType.DINE_IN and table_session_id is None:
            raise BusinessRuleViolationError(
                "Un pedido para consumo en el local requiere una sesión de mesa."
            )
        customer_name = customer_name.strip() if customer_name else ""
        customer_document = customer_document.strip() if customer_document else None
        with session_scope() as session:
            repo = RestaurantRepository(session)
            product_repo = ProductRepository(session)
            order = repo.create_order(
                table_session_id=table_session_id,
                order_type=order_type,
                created_by_user_id=created_by_user_id,
                customer_name=customer_name or DEFAULT_CUSTOMER_NAME,
                customer_document=customer_document,
                origin=origin,
            )
            product_names: dict[int, str] = {}
            product_images: dict[int, str | None] = {}
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
                product_images[product_id] = product.image_path
            order_id = order.id
            dto = _order_to_dto(order, product_names, product_images)

        self._event_bus.publish(
            OrderCreatedEvent(order_id=order_id, created_by_user_id=created_by_user_id)
        )
        return dto

    def list_orders_for_session(self, table_session_id: int) -> list[OrderDTO]:
        with session_scope() as session:
            repo = RestaurantRepository(session)
            product_repo = ProductRepository(session)
            orders = repo.list_orders_for_session(table_session_id)
            product_names, product_images = _product_info_for_orders(product_repo, orders)
            return [_order_to_dto(order, product_names, product_images) for order in orders]

    def list_pending_payment_orders(self) -> list[OrderDTO]:
        """Pedidos ya recibidos por Despacho pero sin cobrar todavía —
        alimenta "Pedidos pendientes de cobro" en Caja."""
        with session_scope() as session:
            repo = RestaurantRepository(session)
            product_repo = ProductRepository(session)
            orders = repo.list_pending_payment_orders()
            product_names, product_images = _product_info_for_orders(product_repo, orders)
            ready_at_by_order = repo.get_last_ready_at_by_order([order.id for order in orders])
            return [
                _order_to_dto(
                    order, product_names, product_images, ready_at_by_order.get(order.id)
                )
                for order in orders
            ]

    def link_order_to_sale(self, order_id: int, sale_id: int) -> None:
        """Marca un pedido como cobrado — deja de aparecer en "Pedidos
        pendientes de cobro". Se llama después de completar la venta con
        éxito (ver `SaleViewModel.load_from_order`)."""
        with session_scope() as session:
            repo = RestaurantRepository(session)
            order = repo.get_order(order_id)
            if order is None:
                raise NotFoundError(f"No existe el pedido con id={order_id}.")
            repo.link_order_to_sale(order, sale_id)

    def create_order_from_sale(
        self, sale: SaleDTO, *, created_by_user_id: int | None = None
    ) -> OrderDTO:
        """Auto-crea un pedido para Despacho cuando una venta se completa
        directo en Ventas, sin pasar por un pedido de Vendedor — nace ya
        cobrado (`sale_id` seteado desde el inicio) y con `origin=VENTAS`.

        NO debe llamarse cuando la venta viene de un pedido de Vendedor ya
        existente (`SaleViewModel._loading_order_id is not None`): ese caso
        sigue usando `link_order_to_sale`, el pedido ya está en Despacho
        desde que Vendedor lo creó."""
        if not sale.items:
            raise BusinessRuleViolationError(
                "La venta debe tener al menos un producto para aparecer en Despacho."
            )
        with session_scope() as session:
            repo = RestaurantRepository(session)
            order = repo.create_order(
                table_session_id=None,
                order_type=OrderType.QUICK,
                created_by_user_id=created_by_user_id,
                customer_name=sale.customer_name or DEFAULT_CUSTOMER_NAME,
                customer_document=sale.customer_document,
                origin=OrderOrigin.VENTAS,
            )
            repo.link_order_to_sale(order, sale.id)
            product_names: dict[int, str] = {}
            product_images: dict[int, str | None] = {}
            product_repo = ProductRepository(session)
            for item in sale.items:
                # Despacho maneja unidades enteras; el peso/decimal exacto
                # sigue siendo autoritativo en `SaleItem`/la factura, acá
                # solo importa "cuántas unidades preparar" (mínimo 1).
                quantity = max(1, math.ceil(item.quantity))
                repo.add_order_item(
                    order, product_id=item.product_id, quantity=quantity, notes=item.note
                )
                product = product_repo.get(item.product_id)
                if product is not None:
                    product_names[item.product_id] = product.name
                    product_images[item.product_id] = product.image_path
            order_id = order.id
            dto = _order_to_dto(order, product_names, product_images)

        self._event_bus.publish(
            OrderCreatedEvent(order_id=order_id, created_by_user_id=created_by_user_id)
        )
        return dto

    def mark_order_delivered(
        self, order_id: int, *, delivered_by_user_id: int | None = None
    ) -> OrderDTO:
        with session_scope() as session:
            repo = RestaurantRepository(session)
            product_repo = ProductRepository(session)
            order = repo.get_order(order_id)
            if order is None:
                raise NotFoundError(f"No existe el pedido con id={order_id}.")
            _apply_delivered(repo, order, delivered_by_user_id)
            product_names, product_images = _product_info_for_orders(product_repo, [order])
            return _order_to_dto(order, product_names, product_images)

    def advance_dispatch_status(
        self, order_id: int, *, changed_by_user_id: int | None = None
    ) -> OrderDTO:
        """Avanza un pedido al siguiente paso del flujo de Despacho con un
        único botón ("Siguiente proceso"): Pendiente → En preparación →
        Entregado → Archivado (deja de listarse en Despacho, ver
        `RestaurantRepository.list_dispatch_queue`, pero el registro se
        conserva íntegro). Reutiliza `_apply_delivered` para el paso a
        Entregado — mismo cascade de ítems/auditoría que
        `mark_order_delivered`, sin duplicar esa lógica."""
        with session_scope() as session:
            repo = RestaurantRepository(session)
            product_repo = ProductRepository(session)
            order = repo.get_order(order_id)
            if order is None:
                raise NotFoundError(f"No existe el pedido con id={order_id}.")
            if order.status is OrderStatus.PENDING:
                repo.set_order_status(order, OrderStatus.PREPARING)
            elif order.status in (OrderStatus.PREPARING, OrderStatus.READY):
                _apply_delivered(repo, order, changed_by_user_id)
            elif order.status is OrderStatus.DELIVERED:
                repo.set_order_status(order, OrderStatus.ARCHIVED)
            # CANCELLED/ARCHIVED: fuera del flujo de Despacho — no debería
            # ser alcanzable desde la UI (esos pedidos ya no se listan),
            # no-op defensivo en vez de fallar.
            product_names, product_images = _product_info_for_orders(product_repo, [order])
            return _order_to_dto(order, product_names, product_images)


def _apply_delivered(
    repo: RestaurantRepository, order: Order, delivered_by_user_id: int | None
) -> None:
    """Mutación compartida por `mark_order_delivered` y
    `advance_dispatch_status` — marca el pedido y todos sus ítems como
    entregados dentro de la sesión ya abierta por el llamador."""
    repo.set_order_status(order, OrderStatus.DELIVERED)
    repo.set_dispatched_by_user(order, delivered_by_user_id)
    for item in order.items:
        if item.status is not OrderItemStatus.DELIVERED:
            repo.set_order_item_status(
                item,
                status=OrderItemStatus.DELIVERED,
                changed_at=datetime.now(UTC),
                changed_by_user_id=delivered_by_user_id,
            )


def _product_info_for_orders(
    product_repo: ProductRepository, orders: list[Order]
) -> tuple[dict[int, str], dict[int, str | None]]:
    product_ids = {item.product_id for order in orders for item in order.items}
    names: dict[int, str] = {}
    images: dict[int, str | None] = {}
    for product_id in product_ids:
        product = product_repo.get(product_id)
        if product is not None:
            names[product_id] = product.name
            images[product_id] = product.image_path
    return names, images
