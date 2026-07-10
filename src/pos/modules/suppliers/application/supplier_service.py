"""Casos de uso de administración de proveedores."""

from __future__ import annotations

from pos.core.database.session import session_scope
from pos.core.exceptions import BusinessRuleViolationError, NotFoundError
from pos.modules.suppliers.application.dto import SupplierDTO
from pos.modules.suppliers.infrastructure.models import Supplier
from pos.modules.suppliers.infrastructure.repository import SupplierRepository


def _to_dto(supplier: Supplier) -> SupplierDTO:
    return SupplierDTO(
        id=supplier.id,
        company_name=supplier.company_name,
        contact_name=supplier.contact_name,
        document_id=supplier.document_id,
        email=supplier.email,
        phone=supplier.phone,
        address=supplier.address,
        is_deleted=supplier.is_deleted,
    )


class SupplierManagementService:
    def list_suppliers(self) -> list[SupplierDTO]:
        with session_scope() as session:
            repo = SupplierRepository(session)
            return [_to_dto(supplier) for supplier in repo.list_all()]

    def create_supplier(
        self,
        *,
        company_name: str,
        contact_name: str | None = None,
        document_id: str | None = None,
        email: str | None = None,
        phone: str | None = None,
        address: str | None = None,
    ) -> SupplierDTO:
        company_name = company_name.strip()
        if not company_name:
            raise BusinessRuleViolationError("La razón social del proveedor es obligatoria.")
        with session_scope() as session:
            repo = SupplierRepository(session)
            supplier = repo.create(
                company_name=company_name,
                contact_name=contact_name,
                document_id=document_id,
                email=email,
                phone=phone,
                address=address,
            )
            return _to_dto(supplier)

    def remove_supplier(self, supplier_id: int) -> None:
        with session_scope() as session:
            repo = SupplierRepository(session)
            supplier = repo.get(supplier_id)
            if supplier is None:
                raise NotFoundError(f"No existe el proveedor con id={supplier_id}.")
            repo.set_deleted(supplier, True)
