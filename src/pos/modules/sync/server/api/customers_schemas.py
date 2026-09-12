"""Modelos Pydantic de la API de Clientes (Fase 5 Android) — traducen
`CustomerDTO` (ya usado por la pantalla "Clientes" y por el buscador de
cliente registrado de "Ventas" en el escritorio) a la forma JSON pública.
Ningún cálculo propio: `current_debt`/`credit_limit`/`loyalty_points_balance`
ya vienen resueltos por `CustomerManagementService`."""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel

from pos.modules.customers.application.dto import CustomerDTO


class CustomerSchema(BaseModel):
    id: int
    full_name: str
    document_id: str | None
    email: str | None
    phone: str | None
    address: str | None
    credit_limit: Decimal
    current_debt: Decimal
    loyalty_points_balance: int

    @classmethod
    def from_dto(cls, dto: CustomerDTO) -> CustomerSchema:
        return cls(
            id=dto.id,
            full_name=dto.full_name,
            document_id=dto.document_id,
            email=dto.email,
            phone=dto.phone,
            address=dto.address,
            credit_limit=dto.credit_limit,
            current_debt=dto.current_debt,
            loyalty_points_balance=dto.loyalty_points_balance,
        )


class CreateCustomerRequest(BaseModel):
    full_name: str
    document_id: str | None = None
    email: str | None = None
    phone: str | None = None
    address: str | None = None
    credit_limit: Decimal = Decimal(0)


class RegisterCreditPaymentRequest(BaseModel):
    amount: Decimal
    reference: str | None = None
