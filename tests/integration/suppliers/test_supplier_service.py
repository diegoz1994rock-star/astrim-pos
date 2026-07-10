"""Pruebas de integración de SupplierManagementService contra SQLite real."""

from __future__ import annotations

import pytest

from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.suppliers.application.supplier_service import SupplierManagementService


def test_create_supplier(sqlite_engine: None) -> None:
    service = SupplierManagementService()

    supplier = service.create_supplier(company_name="Distribuidora ABC", phone="555-1234")

    assert supplier.company_name == "Distribuidora ABC"
    assert supplier.phone == "555-1234"
    assert supplier.is_deleted is False


def test_create_supplier_without_name_is_rejected(sqlite_engine: None) -> None:
    service = SupplierManagementService()

    with pytest.raises(BusinessRuleViolationError):
        service.create_supplier(company_name="   ")


def test_remove_supplier_soft_deletes_it(sqlite_engine: None) -> None:
    service = SupplierManagementService()
    supplier = service.create_supplier(company_name="Temporal")

    service.remove_supplier(supplier.id)

    assert supplier.id not in {s.id for s in service.list_suppliers()}


def test_remove_unknown_supplier_raises_not_found(sqlite_engine: None) -> None:
    service = SupplierManagementService()

    with pytest.raises(NotFoundError):
        service.remove_supplier(9999)


def test_list_suppliers_includes_created(sqlite_engine: None) -> None:
    service = SupplierManagementService()
    service.create_supplier(company_name="Proveedor Uno")

    suppliers = service.list_suppliers()

    assert any(s.company_name == "Proveedor Uno" for s in suppliers)
