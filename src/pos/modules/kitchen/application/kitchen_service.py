"""Caso de uso de Cocina (PROJECT_SPEC.md, "COCINA").

No tiene esquema propio: la cola de cocina es una vista especializada
sobre `restaurant.OrderItem` (ver `modules/kitchen/infrastructure` vacío a
propósito) — el cocinero necesita ver y avanzar el estado de cada ítem,
con el contexto de a qué pedido/mesa pertenece, sin que el módulo de
Restaurante tenga que conocer nada de cómo se presenta esa cola.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.products.infrastructure.product_repository import ProductRepository
from pos.modules.restaurant.application.dto import KitchenQueueItemDTO
from pos.modules.restaurant.domain.enums import OrderItemStatus
from pos.modules.restaurant.infrastructure.repository import RestaurantRepository

_ORDER = [
    OrderItemStatus.PENDING,
    OrderItemStatus.PREPARING,
    OrderItemStatus.READY,
    OrderItemStatus.DELIVERED,
]


def _next_status(current: OrderItemStatus) -> OrderItemStatus:
    index = _ORDER.index(current)
    if index == len(_ORDER) - 1:
        raise BusinessRuleViolationError("Este ítem ya fue entregado.")
    return _ORDER[index + 1]


class KitchenService:
    def list_queue(self) -> list[KitchenQueueItemDTO]:
        with session_scope() as session:
            repo = RestaurantRepository(session)
            product_repo = ProductRepository(session)
            items = repo.list_kitchen_queue()

            table_names: dict[int, str] = {}
            queue: list[KitchenQueueItemDTO] = []
            for item in items:
                order = item.order
                table_name: str | None = None
                if order.table_session_id is not None:
                    table_session = repo.get_session(order.table_session_id)
                    if table_session is not None:
                        if table_session.table_id not in table_names:
                            table = repo.get_table(table_session.table_id)
                            if table is not None:
                                table_names[table_session.table_id] = table.name
                        table_name = table_names.get(table_session.table_id)
                product = product_repo.get(item.product_id)
                queue.append(
                    KitchenQueueItemDTO(
                        order_item_id=item.id,
                        order_id=order.id,
                        product_id=item.product_id,
                        product_name=product.name if product is not None else "?",
                        quantity=item.quantity,
                        notes=item.notes,
                        status=item.status,
                        order_type=order.order_type,
                        table_name=table_name,
                    )
                )
            return queue

    def advance_item(
        self, order_item_id: int, *, changed_by_user_id: int | None
    ) -> KitchenQueueItemDTO:
        """Avanza el ítem al siguiente estado de la secuencia
        pendiente → preparando → listo → entregado (nunca hacia atrás ni
        salteando pasos, para que el historial de tiempos de preparación
        sea confiable)."""
        with session_scope() as session:
            repo = RestaurantRepository(session)
            product_repo = ProductRepository(session)
            item = repo.get_order_item(order_item_id)
            if item is None:
                raise NotFoundError(f"No existe el ítem de pedido con id={order_item_id}.")
            new_status = _next_status(item.status)
            repo.set_order_item_status(
                item,
                status=new_status,
                changed_at=datetime.now(UTC),
                changed_by_user_id=changed_by_user_id,
            )
            product = product_repo.get(item.product_id)
            order = item.order
            table_name: str | None = None
            if order.table_session_id is not None:
                table_session = repo.get_session(order.table_session_id)
                if table_session is not None:
                    table = repo.get_table(table_session.table_id)
                    table_name = table.name if table is not None else None
            return KitchenQueueItemDTO(
                order_item_id=item.id,
                order_id=order.id,
                product_id=item.product_id,
                product_name=product.name if product is not None else "?",
                quantity=item.quantity,
                notes=item.notes,
                status=item.status,
                order_type=order.order_type,
                table_name=table_name,
            )
