"""Acceso a datos de impuestos.

Reutiliza el modelo `Tax` ya existente en `products.infrastructure.models`
(antes solo se leía ahí, sin ninguna pantalla de administración propia)
en vez de duplicarlo — evita una migración de datos innecesaria."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from pos.modules.products.infrastructure.models import Tax


class TaxRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_all(self) -> list[Tax]:
        return list(self._session.scalars(select(Tax).order_by(Tax.name)))

    def list_active(self) -> list[Tax]:
        return list(
            self._session.scalars(
                select(Tax).where(Tax.is_active.is_(True)).order_by(Tax.name)
            )
        )

    def get(self, tax_id: int) -> Tax | None:
        return self._session.get(Tax, tax_id)

    def get_by_name(self, name: str) -> Tax | None:
        return self._session.scalar(select(Tax).where(Tax.name == name))

    def create(self, *, name: str, rate_percent: Decimal) -> Tax:
        tax = Tax(name=name, rate_percent=rate_percent, is_active=True)
        self._session.add(tax)
        self._session.flush()
        return tax

    def update(self, tax: Tax, *, name: str, rate_percent: Decimal) -> None:
        tax.name = name
        tax.rate_percent = rate_percent
        self._session.flush()

    def set_active(self, tax: Tax, is_active: bool) -> None:
        tax.is_active = is_active

    def delete(self, tax: Tax) -> None:
        self._session.delete(tax)
