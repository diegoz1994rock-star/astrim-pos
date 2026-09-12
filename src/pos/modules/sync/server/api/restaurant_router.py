"""Endpoints `/api/v1/restaurant/*` — pantalla Vendedor (Fase 7 Android),
sobre `RestaurantService`/`SalesService`, el mismo caso de uso que ya usa
`restaurant_view.py`/`RestaurantViewModel` del escritorio: pedido rápido
sin mesa (`table_session_id=None`, `order_type=QUICK`), con el mismo motor
de precios en vivo que Ventas (`SalesService.preview_sale`) y la misma
confirmación (`RestaurantService.create_order`, `origin=VENDEDOR`).

El escritorio real no usa mesas en esta pantalla — el dominio de mesas
(`DiningTable`/`TableSession`) existe y está probado a nivel de servicio,
pero ninguna vista lo consume (ver docstring de `restaurant_view.py`:
"Sin mesas, comensales ni reservas"). Esta API replica exactamente lo que
la pantalla real ofrece, no una funcionalidad nueva.

Sin carrito persistido en el servidor (a diferencia de `/sales/drafts`,
Fase 3): el pedido en construcción vive en memoria del cliente Android,
igual que vive en memoria del ViewModel Qt del escritorio
(`RestaurantViewModel._items`) hasta confirmarlo — no hay concepto de
"pedido a medio hacer" que sobreviva un reinicio en ninguno de los dos
lados, así que tampoco hace falta un `draft_id` ni un store en memoria del
servidor para esto.

`POST /orders/preview` valida stock antes de calcular el total, mismo
criterio que `RestaurantViewModel._check_stock` (a su vez el mismo patrón
que `sales_router.py::_check_stock`, con la misma justificación: es una
regla de UX de presentación — el vendedor se entera de inmediato, sin
esperar a que Despacho o Caja fallen después — replicada acá porque esta
API es otra capa de presentación más, no una fuente nueva de reglas de
negocio). A diferencia de `sales_router.py`, que valida línea por línea al
agregar/editar contra un carrito ya persistido, acá se valida la lista
completa de una sola vez (sumando cantidades por producto) porque no hay
carrito servidor con el que comparar incrementalmente — mismo resultado
neto: la cantidad final de cada producto nunca puede superar lo disponible.

`POST /orders` (confirmar) NO repite la validación de stock — réplica
literal de `RestaurantViewModel.confirm_order`, que tampoco la repite
(confía en que ya se validó al armar el carrito, exactamente como en el
escritorio)."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException

from pos.core.security.session import ActiveSession
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.restaurant.domain.enums import OrderType
from pos.modules.sales.application.dto import SaleItemInput
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sync.server.api.dependencies import require_permission
from pos.modules.sync.server.api.restaurant_schemas import (
    CreateOrderRequest,
    OrderItemLineRequest,
    OrderPreviewRequest,
    OrderPreviewSchema,
    OrderSchema,
)

_REQUIRED_PERMISSION = "restaurant.manage"
"""Mismo permiso que gobierna si el panel "Vendedor" es visible en el
escritorio (ver `job_positions/domain/permission_catalog.py`)."""


def create_restaurant_router(
    restaurant_service: RestaurantService,
    sales_service: SalesService,
    inventory_service: InventoryService,
    product_service: ProductManagementService,
) -> APIRouter:
    router = APIRouter(prefix="/restaurant", tags=["restaurant"])

    def _to_sale_items(lines: list[OrderItemLineRequest]) -> list[SaleItemInput]:
        return [SaleItemInput(product_id=line.product_id, quantity=line.quantity, note=line.note) for line in lines]

    def _check_stock(items: list[SaleItemInput]) -> None:
        """Suma la cantidad solicitada por producto en toda la lista (un
        mismo `product_id` puede aparecer en más de una línea si el
        cliente todavía no las fusionó) y la compara contra el disponible
        — mismo criterio y mismo mensaje que `sales_router.py::
        _check_stock`, adaptado a validar la lista completa de una vez en
        vez de una línea contra un carrito ya persistido."""
        requested_by_product: dict[int, Decimal] = {}
        for item in items:
            requested_by_product[item.product_id] = (
                requested_by_product.get(item.product_id, Decimal(0)) + item.quantity
            )
        for product_id, requested in requested_by_product.items():
            product = product_service.get_product(product_id)
            if product is None:
                raise HTTPException(
                    status_code=404, detail=f"No existe el producto con id={product_id}."
                )
            if not product.track_inventory:
                continue
            available = inventory_service.get_total_available_quantity(product_id)
            if requested > available:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Stock insuficiente para '{product.name}'. "
                        f"Disponible: {available} {product.unit_of_measure}."
                    ),
                )

    @router.post("/orders/preview", response_model=OrderPreviewSchema)
    def preview_order(
        payload: OrderPreviewRequest,
        _session: ActiveSession = Depends(require_permission(_REQUIRED_PERMISSION)),
    ) -> OrderPreviewSchema:
        items = _to_sale_items(payload.items)
        _check_stock(items)
        preview = sales_service.preview_sale(items)
        return OrderPreviewSchema.from_preview(preview)

    @router.post("/orders", response_model=OrderSchema, status_code=201)
    def create_order(
        payload: CreateOrderRequest,
        session: ActiveSession = Depends(require_permission(_REQUIRED_PERMISSION)),
    ) -> OrderSchema:
        items = [
            (line.product_id, int(line.quantity), line.note) for line in payload.items
        ]
        order = restaurant_service.create_order(
            table_session_id=None,
            order_type=OrderType.QUICK,
            items=items,
            created_by_user_id=session.user_id,
            customer_name=payload.customer_name,
            customer_document=payload.customer_document,
        )
        return OrderSchema.from_dto(order)

    return router
