"""Modelos Pydantic de la API de Caja (Fase 6 Android) — traducen
`CashRegisterDTO`/`CashSessionDTO` (ya usados por la pantalla "Caja" del
escritorio, `cash_register_view.py`) a la forma JSON pública. Ningún
cálculo propio: `expected_amount`/`difference` ya vienen resueltos por
`CashRegisterService.close_session` (mientras el turno está abierto,
ambos son `null` — el escritorio tampoco los muestra hasta el cierre)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from pos.modules.cash_register.application.dto import CashRegisterDTO, CashSessionDTO


class CashRegisterSchema(BaseModel):
    id: int
    name: str
    location: str | None
    is_active: bool

    @classmethod
    def from_dto(cls, dto: CashRegisterDTO) -> CashRegisterSchema:
        return cls(id=dto.id, name=dto.name, location=dto.location, is_active=dto.is_active)


class CashSessionSchema(BaseModel):
    id: int
    cash_register_id: int
    cash_register_name: str
    status: str
    opened_by_user_id: int
    opened_at: datetime
    opening_amount: Decimal
    closed_at: datetime | None
    closing_amount: Decimal | None
    expected_amount: Decimal | None
    difference: Decimal | None

    @classmethod
    def from_dto(cls, dto: CashSessionDTO) -> CashSessionSchema:
        return cls(
            id=dto.id,
            cash_register_id=dto.cash_register_id,
            cash_register_name=dto.cash_register_name,
            status=dto.status.value,
            opened_by_user_id=dto.opened_by_user_id,
            opened_at=dto.opened_at,
            opening_amount=dto.opening_amount,
            closed_at=dto.closed_at,
            closing_amount=dto.closing_amount,
            expected_amount=dto.expected_amount,
            difference=dto.difference,
        )


class CashRegisterStatusSchema(BaseModel):
    cash_register: CashRegisterSchema
    session: CashSessionSchema | None


class OpenCashSessionRequest(BaseModel):
    opening_amount: Decimal


class CloseCashSessionRequest(BaseModel):
    counted_amount: Decimal
