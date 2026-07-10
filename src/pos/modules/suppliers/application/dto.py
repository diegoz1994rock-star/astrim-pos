"""DTOs de lectura del módulo de proveedores."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SupplierDTO:
    id: int
    company_name: str
    contact_name: str | None
    document_id: str | None
    email: str | None
    phone: str | None
    address: str | None
    is_deleted: bool
