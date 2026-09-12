"""Endpoints `/api/v1/sales/*` — proceso universal de venta.

Fase 3 (`drafts/*`): crear un carrito, agregar/modificar/eliminar líneas y
consultar el resumen recalculado en cualquier momento. Todo el cálculo
(subtotal, descuentos, impuestos, total) pasa por `SalesService.preview_sale`
— la misma función que ya usa `sale_view_model.py` del escritorio.

Fase 4 (`drafts/{id}/complete`, `GET /sales/{sale_id}`): cobrar el carrito,
usando exactamente `SalesService.complete_sale` — la misma llamada, con los
mismos efectos (persistir la venta, descontar inventario, mover caja), que
ya usa `SaleViewModel.complete_sale`.

Corrección crítica (post-Fase 8): `complete_draft` ahora también llama
`RestaurantService.create_order_from_sale` tras completar la venta —
réplica exacta de la rama `else` de `SaleViewModel.complete_sale`
(`sale_view_model.py`, "venta creada directo en Ventas, sin pasar por un
pedido de Vendedor"), que siempre crea un pedido de Despacho
(`origin=VENTAS`, ya con `sale_id` seteado) después de cobrar. Antes de
esta corrección, una venta completada desde Android nunca aparecía en
Despacho — bug real reportado por el usuario, no una funcionalidad nueva:
el escritorio siempre lo hizo, esta API simplemente no lo replicaba. La
llamada va **después** de `store.mark_completed(...)`, nunca antes: si
fuera antes y fallara, un reintento del mismo `draft_id` no encontraría
`completed_sale_id` seteado y volvería a llamar `complete_sale`,
duplicando la venta — con el orden actual, en el peor caso (falla la
creación del pedido, algo que en la práctica no puede pasar porque
`create_order_from_sale` solo valida "items no vacíos", ya garantizado por
una venta recién completada) la venta queda cobrada correctamente y solo
faltaría el pedido de Despacho, nunca una venta duplicada.

Generar factura automática de ventas a crédito (`BillingService`,
Facturación electrónica) sigue fuera de alcance — no reportado como bug,
a diferencia de la creación del pedido de Despacho.

`GET /sales/{sale_id}` requiere el permiso `sales.create` (no
necesariamente el mismo que ve Despacho, `kitchen.manage`) — ver
`dispatch_schemas.py::DispatchOrderCardSchema.sale_id` para el otro
consumidor de este endpoint.

Selección de bodega/caja: igual que el escritorio (`SaleViewModel.
complete_sale`, que tampoco deja elegir — toma la primera bodega y el
primer punto de caja con turno abierto), replicada acá literalmente, no
reinventada — ver `_default_warehouse_and_open_session`.

Duplicados: cada carrito (`draft_id`) solo se completa una vez — ver
`sales_draft_store.py::completion_lock`/`mark_completed`. Una segunda
solicitud de finalización sobre el mismo carrito (reintento de red, doble
tap) devuelve la venta ya persistida, sin llamar `complete_sale` de nuevo.

La única lógica que este router replica (no delega) es la validación de
stock al agregar/editar una línea del carrito (`_check_stock`): en el
escritorio vive en la capa de presentación (`SaleViewModel._check_stock`),
no en `SalesService` — se replica acá por el mismo motivo que
`products_router.py::_matches_search` replica la búsqueda en vivo del
escritorio: es una regla de UX de presentación, y esta API es otra capa de
presentación más (HTTP en vez de Qt). Sigue reutilizando
`InventoryService.get_total_available_quantity`, la misma fuente de datos,
no un cálculo propio."""

from __future__ import annotations

from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query

from pos.core.security.session import ActiveSession
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.inventory.application.inventory_service import InventoryService
from pos.modules.products.application.product_service import ProductManagementService
from pos.modules.restaurant.application.restaurant_service import RestaurantService
from pos.modules.sales.application.dto import SaleItemInput, SalePaymentInput
from pos.modules.sales.application.sale_service import SalesService
from pos.modules.sales.domain.enums import PaymentMethod
from pos.modules.sync.server.api.dependencies import get_current_session, require_permission
from pos.modules.sync.server.api.sales_draft_store import SaleDraft, SaleDraftStore
from pos.modules.sync.server.api.sales_schemas import (
    AddSaleItemRequest,
    CompletedSaleSchema,
    CompleteSaleRequest,
    SaleDraftSchema,
    UpdateSaleItemRequest,
)

_SELLABLE_PAYMENT_METHODS = frozenset(
    {
        PaymentMethod.CASH,
        PaymentMethod.CARD,
        PaymentMethod.QR,
        PaymentMethod.NEQUI,
        PaymentMethod.BRE_B,
        PaymentMethod.CUSTOMER_CREDIT,
    }
)
"""Mismo subconjunto que `sale_view.py::_SELECTABLE_PAYMENT_METHODS` — los
demás valores de `PaymentMethod` (TRANSFER/DAVIPLATA/OTHER) se conservan en
el enum solo por compatibilidad con ventas históricas, el escritorio tampoco
deja elegirlos hoy."""


def create_sales_router(
    sales_service: SalesService,
    inventory_service: InventoryService,
    product_service: ProductManagementService,
    cash_register_service: CashRegisterService,
    restaurant_service: RestaurantService,
) -> APIRouter:
    router = APIRouter(prefix="/sales", tags=["sales"])
    store = SaleDraftStore()

    def _draft_or_404(draft_id: str, session: ActiveSession) -> SaleDraft:
        draft = store.get(draft_id, owner_user_id=session.user_id)
        if draft is None:
            raise HTTPException(
                status_code=404, detail="No existe una venta en curso con ese id."
            )
        return draft

    def _draft_open_or_409(draft: SaleDraft) -> None:
        if draft.completed_sale_id is not None:
            raise HTTPException(
                status_code=409,
                detail="Esta venta ya fue finalizada; no se puede modificar el carrito.",
            )

    def _check_stock(
        items: list[SaleItemInput],
        product_id: int,
        quantity: Decimal,
        *,
        exclude_line_index: int | None = None,
    ) -> None:
        """Mismo criterio que `SaleViewModel._check_stock` del escritorio:
        solo aplica a productos que controlan inventario, y considera lo que
        ya hay de ese mismo producto en el carrito (excluyendo la línea que
        se está editando, si aplica) antes de comparar contra el disponible."""
        product = product_service.get_product(product_id)
        if product is None:
            raise HTTPException(
                status_code=404, detail=f"No existe el producto con id={product_id}."
            )
        if not product.track_inventory:
            return
        available = inventory_service.get_total_available_quantity(product_id)
        already_in_cart = sum(
            (
                item.quantity
                for index, item in enumerate(items)
                if item.product_id == product_id and index != exclude_line_index
            ),
            Decimal(0),
        )
        if already_in_cart + quantity > available:
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Stock insuficiente para '{product.name}'. "
                    f"Disponible: {available} {product.unit_of_measure}."
                ),
            )

    def _preview(draft_id: str, items: list[SaleItemInput]) -> SaleDraftSchema:
        preview = sales_service.preview_sale(items)
        return SaleDraftSchema.from_preview(draft_id, preview)

    def _default_warehouse_and_open_session() -> tuple[int, int]:
        """Réplica literal de `SaleViewModel.complete_sale`: sin selector,
        toma la primera bodega y el primer punto de caja con turno
        abierto, en ese orden — no una regla nueva."""
        warehouse = next(iter(inventory_service.list_warehouses()), None)
        if warehouse is None:
            raise HTTPException(status_code=409, detail="No hay ninguna bodega configurada.")
        register = next(iter(cash_register_service.list_registers()), None)
        if register is None:
            raise HTTPException(
                status_code=409, detail="No hay ningún punto de caja configurado."
            )
        open_session = cash_register_service.get_open_session(register.id)
        if open_session is None:
            raise HTTPException(
                status_code=409, detail="No hay un turno de caja abierto. Ábrelo antes de vender."
            )
        return warehouse.id, open_session.id

    @router.post("/drafts", response_model=SaleDraftSchema, status_code=201)
    def create_draft(session: ActiveSession = Depends(get_current_session)) -> SaleDraftSchema:
        draft = store.create(owner_user_id=session.user_id)
        return _preview(draft.id, draft.items)

    @router.get("/drafts/{draft_id}", response_model=SaleDraftSchema)
    def get_draft(
        draft_id: str, session: ActiveSession = Depends(get_current_session)
    ) -> SaleDraftSchema:
        draft = _draft_or_404(draft_id, session)
        return _preview(draft_id, draft.items)

    @router.post("/drafts/{draft_id}/items", response_model=SaleDraftSchema)
    def add_item(
        draft_id: str,
        payload: AddSaleItemRequest,
        session: ActiveSession = Depends(get_current_session),
    ) -> SaleDraftSchema:
        if payload.quantity <= 0:
            raise HTTPException(status_code=422, detail="La cantidad debe ser mayor que cero.")
        draft = _draft_or_404(draft_id, session)
        _draft_open_or_409(draft)
        items = draft.items
        _check_stock(items, payload.product_id, payload.quantity)

        for index, item in enumerate(items):
            if item.product_id == payload.product_id:
                # Ya está en el carrito: se suma a esa misma línea en vez de
                # duplicarla, conservando su descuento y (si no se pasó una
                # nota nueva) su nota — igual que `SaleViewModel.add_item`.
                items[index] = SaleItemInput(
                    product_id=item.product_id,
                    quantity=item.quantity + payload.quantity,
                    discount_amount=item.discount_amount,
                    note=payload.note if payload.note is not None else item.note,
                )
                break
        else:
            items.append(
                SaleItemInput(
                    product_id=payload.product_id, quantity=payload.quantity, note=payload.note
                )
            )

        updated = store.set_items(draft_id, owner_user_id=session.user_id, items=items)
        assert updated is not None
        return _preview(draft_id, updated)

    @router.patch("/drafts/{draft_id}/items/{item_index}", response_model=SaleDraftSchema)
    def update_item(
        draft_id: str,
        item_index: int,
        payload: UpdateSaleItemRequest,
        session: ActiveSession = Depends(get_current_session),
    ) -> SaleDraftSchema:
        if payload.quantity <= 0:
            raise HTTPException(status_code=422, detail="La cantidad debe ser mayor que cero.")
        draft = _draft_or_404(draft_id, session)
        _draft_open_or_409(draft)
        items = draft.items
        if not 0 <= item_index < len(items):
            raise HTTPException(status_code=404, detail="No existe esa línea en la venta.")

        item = items[item_index]
        _check_stock(items, item.product_id, payload.quantity, exclude_line_index=item_index)
        items[item_index] = SaleItemInput(
            product_id=item.product_id,
            quantity=payload.quantity,
            discount_amount=item.discount_amount,
            note=payload.note,
        )

        updated = store.set_items(draft_id, owner_user_id=session.user_id, items=items)
        assert updated is not None
        return _preview(draft_id, updated)

    @router.delete("/drafts/{draft_id}/items/{item_index}", response_model=SaleDraftSchema)
    def remove_item(
        draft_id: str,
        item_index: int,
        session: ActiveSession = Depends(get_current_session),
    ) -> SaleDraftSchema:
        draft = _draft_or_404(draft_id, session)
        _draft_open_or_409(draft)
        items = draft.items
        if not 0 <= item_index < len(items):
            raise HTTPException(status_code=404, detail="No existe esa línea en la venta.")

        del items[item_index]

        updated = store.set_items(draft_id, owner_user_id=session.user_id, items=items)
        assert updated is not None
        return _preview(draft_id, updated)

    @router.post("/drafts/{draft_id}/complete", response_model=CompletedSaleSchema)
    def complete_draft(
        draft_id: str,
        payload: CompleteSaleRequest,
        session: ActiveSession = Depends(require_permission("sales.create")),
    ) -> CompletedSaleSchema:
        with store.completion_lock(draft_id, owner_user_id=session.user_id) as draft:
            if draft is None:
                raise HTTPException(
                    status_code=404, detail="No existe una venta en curso con ese id."
                )

            if draft.completed_sale_id is not None:
                # Ya se completó antes (reintento de red, doble tap): se
                # devuelve la misma venta ya persistida, sin volver a
                # llamar `complete_sale` — evita duplicados.
                return CompletedSaleSchema.from_dto(
                    sales_service.get_sale(draft.completed_sale_id)
                )

            if not draft.items:
                raise HTTPException(
                    status_code=422, detail="La venta debe tener al menos un producto."
                )
            if not payload.payments:
                raise HTTPException(
                    status_code=422, detail="La venta debe tener al menos un medio de pago."
                )
            for payment in payload.payments:
                if payment.payment_method not in _SELLABLE_PAYMENT_METHODS:
                    raise HTTPException(
                        status_code=422,
                        detail=f"Medio de pago no disponible: {payment.payment_method.value}.",
                    )

            warehouse_id, cash_session_id = _default_warehouse_and_open_session()

            # `complete_sale` puede lanzar `DomainError` (stock insuficiente,
            # pago a crédito sin cliente, etc.) — se deja propagar sin
            # capturar: el manejador global de `errors.py` la traduce al
            # código HTTP correcto (ver `install_domain_error_handler`).
            sale = sales_service.complete_sale(
                items=draft.items,
                payments=[
                    SalePaymentInput(
                        payment_method=p.payment_method,
                        amount=p.amount,
                        reference=p.reference,
                    )
                    for p in payload.payments
                ],
                cash_session_id=cash_session_id,
                warehouse_id=warehouse_id,
                customer_id=payload.customer_id,
                created_by_user_id=session.user_id,
                customer_name=payload.customer_name,
                customer_document=payload.customer_document,
            )

            store.mark_completed(draft_id, owner_user_id=session.user_id, sale_id=sale.id)

            # Réplica de la rama `else` de `SaleViewModel.complete_sale`
            # (`sale_view_model.py`): una venta nacida directo en Ventas
            # (nunca cargada desde un pedido de Vendedor ya existente, algo
            # que esta API todavía no ofrece) siempre crea su propio pedido
            # de Despacho, ya cobrado desde el nacimiento.
            restaurant_service.create_order_from_sale(sale, created_by_user_id=session.user_id)

            return CompletedSaleSchema.from_dto(sale)

    @router.get("", response_model=list[CompletedSaleSchema])
    def list_sales(
        limit: int = Query(default=50, ge=1, le=200),
        session: ActiveSession = Depends(require_permission("sales.create")),
    ) -> list[CompletedSaleSchema]:
        """Historial de ventas (botón "Historial" de Android, réplica de
        `Ventas → Historial` del escritorio) — mismo método que usa
        `SalesHistoryView`, `SalesService.list_recent_sales`, sin filtros
        de fecha/cliente ni paginación real: el escritorio tampoco los
        tiene (ver `sales_history_view_model.py::load`). Solo lectura a
        propósito: anular venta y generar factura desde esa pantalla
        siguen siendo exclusivos del escritorio, no expuestos acá."""
        sales = sales_service.list_recent_sales(limit)
        return [CompletedSaleSchema.from_dto(sale) for sale in sales]

    @router.get("/{sale_id}", response_model=CompletedSaleSchema)
    def get_sale(
        sale_id: int,
        session: ActiveSession = Depends(require_permission("sales.create")),
    ) -> CompletedSaleSchema:
        # `get_sale` lanza `NotFoundError` si no existe — mismo manejador
        # global, sin `try/except` acá (ver nota más arriba).
        sale = sales_service.get_sale(sale_id)
        return CompletedSaleSchema.from_dto(sale)

    return router
