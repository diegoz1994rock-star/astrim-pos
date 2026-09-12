"""agregar customer_name a orders

Revision ID: 634e123dae4c
Revises: a21593945689
Create Date: 2026-07-12 23:28:44.830294
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '634e123dae4c'
down_revision: str | None = 'a21593945689'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_name', sa.String(length=120), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_column('customer_name')
