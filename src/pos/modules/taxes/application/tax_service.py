"""Caso de uso de administración de impuestos.

Solo los impuestos activos se aplican a una venta (ver `SalesService.
_price_items`, que suma `rate_percent` de `list_active_taxes()` — ya no
hay asociación por producto)."""

from __future__ import annotations

from decimal import Decimal

from pos.core.database.session import session_scope
from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.products.infrastructure.models import Tax
from pos.modules.taxes.application.dto import TaxDTO
from pos.modules.taxes.infrastructure.repository import TaxRepository


def _to_dto(tax: Tax) -> TaxDTO:
    return TaxDTO(id=tax.id, name=tax.name, rate_percent=tax.rate_percent, is_active=tax.is_active)


def _validate(name: str, rate_percent: Decimal) -> str:
    name = name.strip()
    if not name:
        raise BusinessRuleViolationError("El nombre del impuesto es obligatorio.")
    if rate_percent < 0:
        raise BusinessRuleViolationError("El porcentaje no puede ser negativo.")
    return name


class TaxService:
    def __init__(self, event_bus: EventBus) -> None:
        self._event_bus = event_bus

    def list_taxes(self) -> list[TaxDTO]:
        with session_scope() as session:
            return [_to_dto(tax) for tax in TaxRepository(session).list_all()]

    def list_active_taxes(self) -> list[TaxDTO]:
        with session_scope() as session:
            return [_to_dto(tax) for tax in TaxRepository(session).list_active()]

    def create_tax(self, *, name: str, rate_percent: Decimal) -> TaxDTO:
        name = _validate(name, rate_percent)
        with session_scope() as session:
            repo = TaxRepository(session)
            if repo.get_by_name(name) is not None:
                raise ConflictError(f"Ya existe un impuesto llamado '{name}'.")
            return _to_dto(repo.create(name=name, rate_percent=rate_percent))

    def update_tax(self, tax_id: int, *, name: str, rate_percent: Decimal) -> TaxDTO:
        name = _validate(name, rate_percent)
        with session_scope() as session:
            repo = TaxRepository(session)
            tax = repo.get(tax_id)
            if tax is None:
                raise NotFoundError(f"No existe el impuesto con id={tax_id}.")
            existing = repo.get_by_name(name)
            if existing is not None and existing.id != tax_id:
                raise ConflictError(f"Ya existe un impuesto llamado '{name}'.")
            repo.update(tax, name=name, rate_percent=rate_percent)
            return _to_dto(tax)

    def set_active(self, tax_id: int, is_active: bool) -> TaxDTO:
        with session_scope() as session:
            repo = TaxRepository(session)
            tax = repo.get(tax_id)
            if tax is None:
                raise NotFoundError(f"No existe el impuesto con id={tax_id}.")
            repo.set_active(tax, is_active)
            return _to_dto(tax)

    def delete_tax(self, tax_id: int) -> None:
        with session_scope() as session:
            repo = TaxRepository(session)
            tax = repo.get(tax_id)
            if tax is None:
                raise NotFoundError(f"No existe el impuesto con id={tax_id}.")
            repo.delete(tax)
