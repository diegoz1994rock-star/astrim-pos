"""Endpoints `/api/v1/customers` (Fase 5 Android) — sobre
`CustomerManagementService`, el mismo caso de uso que ya usan la pantalla
"Clientes" y el buscador de cliente registrado de "Ventas" en el
escritorio.

`GET /customers` no exige el permiso `customers.manage`: el escritorio lo
llama sin ninguna restricción propia desde `SaleViewModel` (cualquier
cajero con acceso a Ventas puede buscar un cliente para una venta, ver
`sale_view_model.py`) — solo la pantalla de administración "Clientes" está
detrás de ese permiso, y eso ya lo decide qué paneles ve cada cargo, no
esta API. `POST /customers` (alta) y `POST /customers/{id}/payments`
(abono) sí lo exigen: son las dos acciones reales que ofrece esa pantalla
protegida (`customers_view.py`: "Nuevo cliente"/"Registrar abono")."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from pos.core.security.session import ActiveSession
from pos.modules.customers.application.customer_service import CustomerManagementService
from pos.modules.customers.infrastructure.models import CreditMovementType
from pos.modules.sync.server.api.customers_schemas import (
    CreateCustomerRequest,
    CustomerSchema,
    RegisterCreditPaymentRequest,
)
from pos.modules.sync.server.api.dependencies import get_current_session, require_permission

_MANAGE_PERMISSION = "customers.manage"


def create_customers_router(customer_service: CustomerManagementService) -> APIRouter:
    router = APIRouter(prefix="/customers", tags=["customers"])

    @router.get("", response_model=list[CustomerSchema])
    def list_customers(
        _session: ActiveSession = Depends(get_current_session),
    ) -> list[CustomerSchema]:
        return [CustomerSchema.from_dto(c) for c in customer_service.list_customers()]

    @router.post("", response_model=CustomerSchema, status_code=201)
    def create_customer(
        payload: CreateCustomerRequest,
        _session: ActiveSession = Depends(require_permission(_MANAGE_PERMISSION)),
    ) -> CustomerSchema:
        customer = customer_service.create_customer(
            full_name=payload.full_name,
            document_id=payload.document_id,
            email=payload.email,
            phone=payload.phone,
            address=payload.address,
            credit_limit=payload.credit_limit,
        )
        return CustomerSchema.from_dto(customer)

    @router.post("/{customer_id}/payments", response_model=CustomerSchema)
    def register_payment(
        customer_id: int,
        payload: RegisterCreditPaymentRequest,
        session: ActiveSession = Depends(require_permission(_MANAGE_PERMISSION)),
    ) -> CustomerSchema:
        customer_service.register_credit_movement(
            customer_id=customer_id,
            movement_type=CreditMovementType.PAYMENT,
            amount=payload.amount,
            reference=payload.reference,
            created_by_user_id=session.user_id,
        )
        updated = customer_service.get_customer(customer_id)
        assert updated is not None
        return CustomerSchema.from_dto(updated)

    return router
