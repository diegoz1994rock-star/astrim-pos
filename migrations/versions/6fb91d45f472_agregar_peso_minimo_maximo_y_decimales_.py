"""agregar peso minimo, maximo y decimales de peso a products

Revision ID: 6fb91d45f472
Revises: 5a66b2338b0f
Create Date: 2026-07-18 09:30:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '6fb91d45f472'
down_revision: str | None = '5a66b2338b0f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('min_weight', sa.Numeric(10, 3), nullable=True))
        batch_op.add_column(sa.Column('max_weight', sa.Numeric(10, 3), nullable=True))
        batch_op.add_column(sa.Column('weight_decimal_places', sa.Integer(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('weight_decimal_places')
        batch_op.drop_column('max_weight')
        batch_op.drop_column('min_weight')
