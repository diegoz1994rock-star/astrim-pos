"""Modelos Pydantic de la API de Despacho (Fase 4 Android) — traducen los
DTOs ya definidos en `modules.restaurant.application.dto` (los mismos que
usa la pantalla Despacho del escritorio, `kitchen_view.py`) a la forma JSON
pública. Ningún campo se recalcula acá: `KitchenService.list_dispatch_queue`
ya resuelve `is_paid`/`caja_name` en vivo, esta capa solo serializa.

`DispatchOrderCardDTO.customer_name` está tipado `str` (no opcional), pero
`Order.customer_name` en el modelo ORM sí admite `NULL`
(`infrastructure/models.py`) y hay pedidos reales, anteriores a que
`RestaurantService.create_order` empezara a aplicar `DEFAULT_CUSTOMER_NAME`
("Consumidor Final") a un nombre vacío, con ese campo en `NULL` en la base
de datos — bug real encontrado validando la Fase 4 (Pydantic rechazaba la
respuesta con un 500 en cuanto la cola incluía uno de esos pedidos). Se
corrige acá, en la capa de serialización, sin tocar el dataclass ni el
modelo ORM de una fase anterior: mismo criterio de reemplazo que ya usa
`create_order`/`create_order_from_sale` para "sin nombre"."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from pos.modules.restaurant.application.dto import DispatchOrderCardDTO, OrderItemDTO

_DEFAULT_CUSTOMER_NAME = "Consumidor Final"


class DispatchOrderItemSchema(BaseModel):
    id: int
    order_id: int
    product_id: int
    product_name: str
    quantity: int
    notes: str | None
    status: str
    product_image_path: str | None

    @classmethod
    def from_dto(cls, dto: OrderItemDTO) -> DispatchOrderItemSchema:
        return cls(
            id=dto.id,
            order_id=dto.order_id,
            product_id=dto.product_id,
            product_name=dto.product_name,
            quantity=dto.quantity,
            notes=dto.notes,
            status=dto.status.value,
            product_image_path=dto.product_image_path,
        )


class DispatchOrderCardSchema(BaseModel):
    """Un pedido/venta como tarjeta de Despacho — misma forma que
    `DispatchOrderCardDTO`, la unidad que muestra `kitchen_view.py` (una
    tarjeta por pedido/cliente, no por producto)."""

    order_id: int
    origin: str
    customer_name: str
    customer_document: str | None
    is_paid: bool
    caja_name: str | None
    dispatch_status: str
    item_count: int
    total_units: int
    items: list[DispatchOrderItemSchema]
    created_at: datetime | None
    created_by_user_name: str | None
    dispatched_by_user_name: str | None
    sale_id: int | None
    """`None` = pedido sin cobrar todavía. Si tiene valor, un cliente
    remoto puede consultar `GET /sales/{sale_id}` (API.md §3.6, requiere
    permiso `sales.create`) para el precio/pago real de la venta —
    ninguna lógica de precio se duplica acá."""

    @classmethod
    def from_dto(cls, dto: DispatchOrderCardDTO) -> DispatchOrderCardSchema:
        return cls(
            order_id=dto.order_id,
            origin=dto.origin.value,
            customer_name=dto.customer_name or _DEFAULT_CUSTOMER_NAME,
            customer_document=dto.customer_document,
            is_paid=dto.is_paid,
            caja_name=dto.caja_name,
            dispatch_status=dto.dispatch_status.value,
            item_count=dto.item_count,
            total_units=dto.total_units,
            items=[DispatchOrderItemSchema.from_dto(item) for item in dto.items],
            created_at=dto.created_at,
            created_by_user_name=dto.created_by_user_name,
            dispatched_by_user_name=dto.dispatched_by_user_name,
            sale_id=dto.sale_id,
        )
