"""corregir mayusculas de sale_unit en products

Revision ID: ee4b16fa4f54
Revises: e1068900f3f2
Create Date: 2026-07-13 13:25:58.469080
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'ee4b16fa4f54'
down_revision: str | None = 'e1068900f3f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # La migración f11bf9075873 escribió `server_default='unit'` (minúscula)
    # al agregar la columna: SQLAlchemy `Enum(SaleUnit, native_enum=False)`
    # lee/escribe por el NAME del miembro ("UNIT"/"WEIGHT"), no por su
    # `.value` ("unit"/"weight") — igual que ya hace `products.product_type`
    # con "SIMPLE"/"COMPOUND"/"COMBO". El valor en minúscula quedó grabado
    # en cualquier producto creado antes de corregir ese default, y
    # `SQLAlchemy` lanza `LookupError` al leerlo de vuelta (reproducido:
    # crasheaba el dashboard post-login al listar la última venta).
    op.execute("UPDATE products SET sale_unit = 'UNIT' WHERE sale_unit = 'unit'")
    op.execute("UPDATE products SET sale_unit = 'WEIGHT' WHERE sale_unit = 'weight'")


def downgrade() -> None:
    op.execute("UPDATE products SET sale_unit = 'unit' WHERE sale_unit = 'UNIT'")
    op.execute("UPDATE products SET sale_unit = 'weight' WHERE sale_unit = 'WEIGHT'")
