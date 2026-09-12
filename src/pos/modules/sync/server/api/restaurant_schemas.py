"""Modelos Pydantic de la API de Vendedor (Fase 7 Android) — traducen los
DTOs ya definidos en `modules.restaurant.application.dto` y
`modules.sales.application.dto` (los mismos que usa `restaurant_view.py`
del escritorio: `RestaurantViewModel._items`/`SalesService.preview_sale`
para el total en vivo, `RestaurantService.create_order` para confirmar) a
la forma JSON pública. Ningún cálculo propio: el pedido en sí no tiene
precio propio (ver `restaurant_service.py`), el total en vivo siempre viene
de `SalesService.preview_sale` — la misma función que ya usa el carrito de
Ventas (Fase 3, `sales_schemas.py::SaleDraftSchema`)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from pos.modules.restaurant.application.dto import OrderDTO, OrderItemDTO
from pos.modules.sales.application.dto import SalePreviewDTO
from pos.modules.sync.server.api.sales_schemas import SaleDraftLineSchema

_DEFAULT_CUSTOMER_NAME = "Consumidor Final"
"""Mismo respaldo que ya usa `RestaurantService.create_order`/
`dispatch_schemas.py` para un nombre de cliente vacío o nulo."""


class OrderItemLineRequest(BaseModel):
    """Una línea del pedido en construcción — `quantity` es `Decimal` (no
    `int`) porque el campo de cantidad del escritorio (`restaurant_view.py
    ::_quantity_edit`) acepta cualquier número, igual que Ventas (por
    ejemplo un producto pesado en báscula); `POST /orders` la trunca a
    entero al confirmar, réplica literal de `RestaurantViewModel.
    confirm_order` (`int(item.quantity)`, sin redondear)."""

    product_id: int
    quantity: Decimal
    note: str | None = None


class OrderPreviewRequest(BaseModel):
    items: list[OrderItemLineRequest]


class OrderPreviewSchema(BaseModel):
    """Mismo total en vivo que ve el mesero antes de confirmar — misma
    forma que `SaleDraftSchema` (Fase 3) sin `draft_id`: acá no hay carrito
    persistido en el servidor, el pedido en construcción vive en memoria
    del cliente (Android), igual que vive en memoria del ViewModel Qt del
    escritorio (`RestaurantViewModel._items`) hasta confirmarlo."""

    subtotal: Decimal
    discount_total: Decimal
    tax_total: Decimal
    total: Decimal
    items: list[SaleDraftLineSchema]

    @classmethod
    def from_preview(cls, preview: SalePreviewDTO) -> OrderPreviewSchema:
        return cls(
            subtotal=preview.subtotal,
            discount_total=preview.discount_total,
            tax_total=preview.tax_total,
            total=preview.total,
            items=[SaleDraftLineSchema.from_dto(line) for line in preview.items],
        )


class CreateOrderRequest(BaseModel):
    items: list[OrderItemLineRequest]
    customer_name: str | None = None
    customer_document: str | None = None


class OrderItemSchema(BaseModel):
    id: int
    product_id: int
    product_name: str
    quantity: int
    notes: str | None
    status: str
    product_image_path: str | None

    @classmethod
    def from_dto(cls, dto: OrderItemDTO) -> OrderItemSchema:
        return cls(
            id=dto.id,
            product_id=dto.product_id,
            product_name=dto.product_name,
            quantity=dto.quantity,
            notes=dto.notes,
            status=dto.status.value,
            product_image_path=dto.product_image_path,
        )


class OrderSchema(BaseModel):
    """El pedido ya confirmado — misma forma que `OrderDTO`. Sin cobrar
    (`sale_id` es `null`): un pedido de Vendedor nace `origin=vendedor`,
    `status=pending`, y aparece automáticamente en Despacho
    (`GET /dispatch/orders`, Fase 4) — no hace falta ninguna llamada
    adicional para "enviarlo", `POST /orders` ya lo deja visible ahí."""

    id: int
    table_session_id: int | None
    order_type: str
    status: str
    items: list[OrderItemSchema]
    created_at: datetime | None
    created_by_user_id: int | None
    sale_id: int | None
    customer_name: str | None
    customer_document: str | None
    origin: str
    dispatched_by_user_id: int | None

    @classmethod
    def from_dto(cls, dto: OrderDTO) -> OrderSchema:
        return cls(
            id=dto.id,
            table_session_id=dto.table_session_id,
            order_type=dto.order_type.value,
            status=dto.status.value,
            items=[OrderItemSchema.from_dto(item) for item in dto.items],
            created_at=dto.created_at,
            created_by_user_id=dto.created_by_user_id,
            sale_id=dto.sale_id,
            customer_name=dto.customer_name or _DEFAULT_CUSTOMER_NAME,
            customer_document=dto.customer_document,
            origin=dto.origin.value,
            dispatched_by_user_id=dto.dispatched_by_user_id,
        )
