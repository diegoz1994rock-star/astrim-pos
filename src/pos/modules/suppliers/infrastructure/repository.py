"""Acceso a datos de proveedores."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.suppliers.infrastructure.models import Supplier


class SupplierRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Supplier]:
        return list(
            self._session.scalars(
                select(Supplier).where(Supplier.is_deleted.is_(False)).order_by(Supplier.company_name)
            )
        )

    def get(self, supplier_id: int) -> Supplier | None:
        return self._session.get(Supplier, supplier_id)

    def create(
        self,
        *,
        company_name: str,
        contact_name: str | None,
        document_id: str | None,
        email: str | None,
        phone: str | None,
        address: str | None,
    ) -> Supplier:
        supplier = Supplier(
            company_name=company_name,
            contact_name=contact_name,
            document_id=document_id,
            email=email,
            phone=phone,
            address=address,
        )
        self._session.add(supplier)
        self._session.flush()
        return supplier

    def set_deleted(self, supplier: Supplier, is_deleted: bool) -> None:
        supplier.is_deleted = is_deleted
