"""agregar sale_unit a products

Revision ID: f11bf9075873
Revises: cbe7ac519333
Create Date: 2026-07-13 08:08:45.012938
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'f11bf9075873'
down_revision: str | None = 'cbe7ac519333'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'sale_unit', sa.String(length=20), nullable=False, server_default='UNIT'
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('sale_unit')
