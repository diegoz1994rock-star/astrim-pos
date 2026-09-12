"""ganancias: costo historico en sale_items e indices de rendimiento

Revision ID: f3a8c1d9e4b7
Revises: 7cddeb6ab4ee
Create Date: 2026-07-17 09:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = 'f3a8c1d9e4b7'
down_revision: str | None = '7cddeb6ab4ee'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('sale_items', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column('unit_cost', sa.Numeric(precision=12, scale=2), nullable=True)
        )
        batch_op.create_index(
            batch_op.f('ix_sale_items_product_id'), ['product_id'], unique=False
        )
        batch_op.create_index(batch_op.f('ix_sale_items_sale_id'), ['sale_id'], unique=False)

    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f('ix_sales_created_at_status'), ['created_at', 'status'], unique=False
        )


def downgrade() -> None:
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sales_created_at_status'))

    with op.batch_alter_table('sale_items', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_sale_items_sale_id'))
        batch_op.drop_index(batch_op.f('ix_sale_items_product_id'))
        batch_op.drop_column('unit_cost')
