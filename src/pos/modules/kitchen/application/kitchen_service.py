"""Caso de uso de Despacho (preparar/alistar/empacar/entregar pedidos).

No tiene esquema propio: la cola de Despacho es una vista especializada
sobre `restaurant.OrderItem` (ver `modules/kitchen/infrastructure` vacío a
propósito) — el encargado necesita ver y avanzar el estado de cada ítem,
con el contexto de a qué pedido/empleado pertenece, sin que el módulo de
Restaurante tenga que conocer nada de cómo se presenta esa cola. Sirve
igual para un restaurante, una ferretería, una farmacia o cualquier otro
negocio que prepare/empaque/despache pedidos.
"""

from __future__ import annotations

from datetime import UTC, datetime

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.products.infrastructure.product_repository import ProductRepository
from pos.modules.restaurant.application.dto import (
    DispatchOrderCardDTO,
    KitchenQueueItemDTO,
    OrderItemDTO,
)
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.restaurant.domain.enums import OrderItemStatus
from pos.modules.restaurant.infrastructure.models import OrderItem
from pos.modules.restaurant.infrastructure.repository import RestaurantRepository
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.users.application.user_management_service import UserManagementService

_ORDER = [
    OrderItemStatus.PENDING,
    OrderItemStatus.PREPARING,
    OrderItemStatus.READY,
    OrderItemStatus.DELIVERED,
]


def _next_status(current: OrderItemStatus) -> OrderItemStatus:
    index = _ORDER.index(current)
    if index == len(_ORDER) - 1:
        raise BusinessRuleViolationError("Este ítem ya fue despachado.")
    return _ORDER[index + 1]


class KitchenService:
    def __init__(
        self,
        user_service: UserManagementService,
        restaurant_service: RestaurantService,
        sales_service: SalesService,
        cash_register_service: CashRegisterService,
    ) -> None:
        self._user_service = user_service
        self._restaurant_service = restaurant_service
        self._sales_service = sales_service
        self._cash_register_service = cash_register_service

    def _user_name(self, user_id: int | None) -> str | None:
        if user_id is None:
            return None
        return next((u.full_name for u in self._user_service.list_users() if u.id == user_id), None)

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
                        product_image_path=product.image_path if product is not None else None,
                        created_at=order.created_at,
                        created_by_user_name=self._user_name(order.created_by_user_id),
                        customer_name=order.customer_name,
                    )
                )
            return queue

    def advance_item(
        self, order_item_id: int, *, changed_by_user_id: int | None
    ) -> KitchenQueueItemDTO:
        """Avanza el ítem al siguiente estado de la secuencia
        pendiente → en preparación → listo → despachado (nunca hacia atrás
        ni salteando pasos, para que el historial de tiempos de
        preparación sea confiable)."""
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
                product_image_path=product.image_path if product is not None else None,
                created_at=order.created_at,
                created_by_user_name=self._user_name(order.created_by_user_id),
                customer_name=order.customer_name,
            )

    def list_dispatch_queue(self) -> list[DispatchOrderCardDTO]:
        """Tarjetas de Despacho por cliente/pedido (reemplaza la vista de
        ítems sueltos de `list_queue`) — incluye tanto pedidos sin cobrar
        (Vendedor) como ya cobrados (Ventas), sin filtrar por
        pagado/entregado/origen: eso lo hace la vista (chips + buscador)."""
        with session_scope() as session:
            repo = RestaurantRepository(session)
            orders = repo.list_dispatch_queue()
            product_repo = ProductRepository(session)

            product_names: dict[int, str] = {}
            product_images: dict[int, str | None] = {}

            def _item_dto(item: OrderItem) -> OrderItemDTO:
                if item.product_id not in product_names:
                    product = product_repo.get(item.product_id)
                    product_names[item.product_id] = product.name if product is not None else "?"
                    product_images[item.product_id] = (
                        product.image_path if product is not None else None
                    )
                return OrderItemDTO(
                    id=item.id,
                    order_id=item.order_id,
                    product_id=item.product_id,
                    product_name=product_names[item.product_id],
                    quantity=item.quantity,
                    notes=item.notes,
                    status=item.status,
                    product_image_path=product_images[item.product_id],
                )

            cards: list[DispatchOrderCardDTO] = []
            for order in orders:
                caja_name: str | None = None
                if order.sale_id is not None:
                    sale = self._sales_service.get_sale(order.sale_id)
                    if sale.cash_session_id is not None:
                        cash_session = self._cash_register_service.get_session(
                            sale.cash_session_id
                        )
                        caja_name = cash_session.cash_register_name if cash_session else None
                cards.append(
                    DispatchOrderCardDTO(
                        order_id=order.id,
                        origin=order.origin,
                        customer_name=order.customer_name,
                        customer_document=order.customer_document,
                        is_paid=order.sale_id is not None,
                        caja_name=caja_name,
                        dispatch_status=order.status,
                        item_count=len(order.items),
                        total_units=sum(item.quantity for item in order.items),
                        items=[_item_dto(item) for item in order.items],
                        created_at=order.created_at,
                        created_by_user_name=self._user_name(order.created_by_user_id),
                        dispatched_by_user_name=self._user_name(order.dispatched_by_user_id),
                        sale_id=order.sale_id,
                    )
                )
            return cards

    def get_pending_dispatch_count(self) -> int:
        """Única fuente de verdad para "cuántos despachos están pendientes
        de preparar": cuenta únicamente pedidos en estado `PENDING` (no
        `PREPARING`/`READY`/`DELIVERED`) mediante un `COUNT` real, sin
        traer ni recorrer filas. Todo consumidor de este número (hoy, la
        campana del Dashboard) debe llamar este método en vez de
        recalcularlo a partir de `list_dispatch_queue`, que trae la cola
        completa para otro propósito."""
        with session_scope() as session:
            return RestaurantRepository(session).count_pending_orders()

    def mark_order_delivered(self, order_id: int, *, delivered_by_user_id: int | None) -> None:
        self._restaurant_service.mark_order_delivered(
            order_id, delivered_by_user_id=delivered_by_user_id
        )

    def advance_dispatch_status(self, order_id: int, *, changed_by_user_id: int | None) -> None:
        """Avanza el pedido al siguiente paso del botón "Siguiente proceso"
        de Despacho — ver `RestaurantService.advance_dispatch_status`."""
        self._restaurant_service.advance_dispatch_status(
            order_id, changed_by_user_id=changed_by_user_id
        )
