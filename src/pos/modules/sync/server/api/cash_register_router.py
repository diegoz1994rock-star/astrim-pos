"""Endpoints `/api/v1/cash-register/*` — pantalla Caja (Fase 6 Android),
sobre `CashRegisterService`, el mismo caso de uso que ya usa
`cash_register_view.py` del escritorio. Solo replica lo que esa pantalla
realmente ofrece a un cajero: ver el estado del turno, abrirlo y cerrarlo
— nunca la administración de puntos de caja (`cash_registers_view.py`,
crear/renombrar/desactivar cajas) ni los movimientos manuales de
ingreso/egreso, que son funciones distintas fuera del alcance pedido.

Sin selector de punto de caja: réplica literal de
`sales_router.py::_default_warehouse_and_open_session`, que ya toma el
primer punto de caja activo (`list_registers()[0]`) para completar una
venta sin ofrecer un selector — el mismo criterio se reutiliza acá para no
inventar una regla nueva. Un negocio con un solo punto de caja (el caso
común, ver `scripts/seed_demo_data.py`) nunca nota la diferencia.

Las tres acciones exigen el permiso `cash_register.manage` — el mismo que
gobierna si el panel "Caja" es visible en el escritorio (ver
`job_positions/domain/permission_catalog.py`), a diferencia de Clientes
(Fase 5) donde la lectura era de acceso libre: acá no hay ningún caso de
uso del escritorio que consulte el estado de caja sin pasar por ese
panel protegido."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from pos.core.security.session import ActiveSession
from pos.modules.cash_register.application.cash_register_service import CashRegisterService
from pos.modules.cash_register.application.dto import CashRegisterDTO
from pos.modules.sync.server.api.cash_register_schemas import (
    CashRegisterSchema,
    CashRegisterStatusSchema,
    CashSessionSchema,
    CloseCashSessionRequest,
    OpenCashSessionRequest,
)
from pos.modules.sync.server.api.dependencies import require_permission

_MANAGE_PERMISSION = "cash_register.manage"


def _default_register(cash_register_service: CashRegisterService) -> CashRegisterDTO:
    register = next(iter(cash_register_service.list_registers()), None)
    if register is None:
        raise HTTPException(status_code=409, detail="No hay ningún punto de caja configurado.")
    return register


def create_cash_register_router(cash_register_service: CashRegisterService) -> APIRouter:
    router = APIRouter(prefix="/cash-register", tags=["cash-register"])

    @router.get("/status", response_model=CashRegisterStatusSchema)
    def get_status(
        _session: ActiveSession = Depends(require_permission(_MANAGE_PERMISSION)),
    ) -> CashRegisterStatusSchema:
        register = _default_register(cash_register_service)
        open_session = cash_register_service.get_open_session(register.id)
        return CashRegisterStatusSchema(
            cash_register=CashRegisterSchema.from_dto(register),
            session=CashSessionSchema.from_dto(open_session) if open_session is not None else None,
        )

    @router.post("/sessions/open", response_model=CashSessionSchema, status_code=201)
    def open_session(
        payload: OpenCashSessionRequest,
        session: ActiveSession = Depends(require_permission(_MANAGE_PERMISSION)),
    ) -> CashSessionSchema:
        register = _default_register(cash_register_service)
        opened = cash_register_service.open_session(
            cash_register_id=register.id,
            opened_by_user_id=session.user_id,
            opening_amount=payload.opening_amount,
        )
        return CashSessionSchema.from_dto(opened)

    @router.post("/sessions/close", response_model=CashSessionSchema)
    def close_session(
        payload: CloseCashSessionRequest,
        session: ActiveSession = Depends(require_permission(_MANAGE_PERMISSION)),
    ) -> CashSessionSchema:
        register = _default_register(cash_register_service)
        open_session = cash_register_service.get_open_session(register.id)
        if open_session is None:
            raise HTTPException(status_code=409, detail="No hay un turno de caja abierto.")
        closed = cash_register_service.close_session(
            cash_session_id=open_session.id,
            closed_by_user_id=session.user_id,
            counted_amount=payload.counted_amount,
        )
        return CashSessionSchema.from_dto(closed)

    return router
