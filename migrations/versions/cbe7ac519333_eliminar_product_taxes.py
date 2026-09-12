"""eliminar product_taxes

Revision ID: cbe7ac519333
Revises: 634e123dae4c
Create Date: 2026-07-13 01:01:57.464451
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'cbe7ac519333'
down_revision: str | None = '634e123dae4c'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.drop_table('product_taxes')


def downgrade() -> None:
    op.create_table(
        'product_taxes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('tax_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id']),
        sa.ForeignKeyConstraint(['tax_id'], ['taxes.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('product_id', 'tax_id', name='uq_product_tax'),
    )
