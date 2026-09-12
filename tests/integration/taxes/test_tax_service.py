"""Pruebas de integración de TaxService contra SQLite real: crear, editar,
activar/desactivar y eliminar impuestos — solo los activos deben aparecer
en `list_active_taxes` (lo que Ventas usa para calcular `tax_total`,
ver `sale_service._price_items`)."""

from __future__ import annotations

from decimal import Decimal

import pytest

from pos.core.events.bus import EventBus
from pos.core.exceptions import BusinessRuleViolationError, ConflictError, NotFoundError
from pos.modules.taxes.application.tax_service import TaxService


def _make_service() -> TaxService:
    return TaxService(EventBus())


def test_create_tax(sqlite_engine: None) -> None:
    service = _make_service()

    tax = service.create_tax(name="IVA 19%", rate_percent=Decimal("19"))

    assert tax.name == "IVA 19%"
    assert tax.rate_percent == Decimal("19")
    assert tax.is_active is True


def test_create_tax_rejects_empty_name(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(BusinessRuleViolationError):
        service.create_tax(name="   ", rate_percent=Decimal("19"))


def test_create_tax_rejects_negative_rate(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(BusinessRuleViolationError):
        service.create_tax(name="IVA", rate_percent=Decimal("-1"))


def test_create_tax_with_duplicate_name_raises_conflict(sqlite_engine: None) -> None:
    service = _make_service()
    service.create_tax(name="IVA 19%", rate_percent=Decimal("19"))

    with pytest.raises(ConflictError):
        service.create_tax(name="IVA 19%", rate_percent=Decimal("19"))


def test_update_tax_changes_fields(sqlite_engine: None) -> None:
    service = _make_service()
    tax = service.create_tax(name="IVA", rate_percent=Decimal("19"))

    updated = service.update_tax(tax.id, name="IVA 19%", rate_percent=Decimal("19.5"))

    assert updated.name == "IVA 19%"
    assert updated.rate_percent == Decimal("19.5")


def test_update_unknown_tax_raises_not_found(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(NotFoundError):
        service.update_tax(9999, name="IVA", rate_percent=Decimal("19"))


def test_set_active_toggles_status(sqlite_engine: None) -> None:
    service = _make_service()
    tax = service.create_tax(name="IVA", rate_percent=Decimal("19"))

    deactivated = service.set_active(tax.id, False)
    assert deactivated.is_active is False

    reactivated = service.set_active(tax.id, True)
    assert reactivated.is_active is True


def test_list_active_taxes_excludes_inactive(sqlite_engine: None) -> None:
    service = _make_service()
    active = service.create_tax(name="IVA 19%", rate_percent=Decimal("19"))
    inactive = service.create_tax(name="IVA 5%", rate_percent=Decimal("5"))
    service.set_active(inactive.id, False)

    active_taxes = service.list_active_taxes()

    assert [t.id for t in active_taxes] == [active.id]


def test_delete_tax(sqlite_engine: None) -> None:
    service = _make_service()
    tax = service.create_tax(name="IVA", rate_percent=Decimal("19"))

    service.delete_tax(tax.id)

    assert service.list_taxes() == []


def test_delete_unknown_tax_raises_not_found(sqlite_engine: None) -> None:
    service = _make_service()
    with pytest.raises(NotFoundError):
        service.delete_tax(9999)
