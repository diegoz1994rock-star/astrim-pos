"""Endpoints `/api/v1/dispatch/*` — pantalla Despacho (Fase 4 Android),
sobre `KitchenService`, el mismo caso de uso que ya usa `kitchen_view.py`
del escritorio. Solo replica lo que esa pantalla realmente ofrece: la cola
de pedidos como tarjetas por cliente y sus dos únicas acciones —"Siguiente
proceso" (`advance_dispatch_status`) y "Marcar como entregado" del detalle
(`mark_order_delivered`) — nunca el avance ítem por ítem de
`KitchenService.list_queue`/`advance_item`, que la UI actual no expone.

Filtros (Todos/Pendientes/En preparación/.../Pedidos de Ventas) y búsqueda
son responsabilidad del cliente, igual que en `kitchen_view.py`
(`_matches_filter`/`_matches_search`): esta API siempre devuelve la cola
completa activa (sin `CANCELLED`/`ARCHIVED`), nunca pre-filtrada, para que
Android pueda ofrecer los mismos filtros sin ir al servidor por cada uno.

Las dos acciones devuelven la cola ya recargada en la misma respuesta —
mismo resultado neto que el escritorio (acción + `self.load()`), en una
sola solicitud en vez de dos."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pos.core.security.session import ActiveSession
from pos.modules.kitchen.application.kitchen_service import KitchenService
from pos.modules.sync.server.api.dependencies import require_permission
from pos.modules.sync.server.api.dispatch_schemas import DispatchOrderCardSchema

_REQUIRED_PERMISSION = "kitchen.manage"
"""Mismo permiso que gobierna si el panel "Despacho" es visible en el
escritorio (ver `job_positions/domain/permission_catalog.py`)."""


def create_dispatch_router(kitchen_service: KitchenService) -> APIRouter:
    router = APIRouter(prefix="/dispatch", tags=["dispatch"])

    def _queue() -> list[DispatchOrderCardSchema]:
        return [DispatchOrderCardSchema.from_dto(c) for c in kitchen_service.list_dispatch_queue()]

    @router.get("/orders", response_model=list[DispatchOrderCardSchema])
    def list_orders(
        _session: ActiveSession = Depends(require_permission(_REQUIRED_PERMISSION)),
    ) -> list[DispatchOrderCardSchema]:
        return _queue()

    @router.post("/orders/{order_id}/advance", response_model=list[DispatchOrderCardSchema])
    def advance_order(
        order_id: int,
        session: ActiveSession = Depends(require_permission(_REQUIRED_PERMISSION)),
    ) -> list[DispatchOrderCardSchema]:
        kitchen_service.advance_dispatch_status(order_id, changed_by_user_id=session.user_id)
        return _queue()

    @router.post("/orders/{order_id}/deliver", response_model=list[DispatchOrderCardSchema])
    def deliver_order(
        order_id: int,
        session: ActiveSession = Depends(require_permission(_REQUIRED_PERMISSION)),
    ) -> list[DispatchOrderCardSchema]:
        kitchen_service.mark_order_delivered(order_id, delivered_by_user_id=session.user_id)
        return _queue()

    return router
