"""agregar product_barcodes

Revision ID: 7cddeb6ab4ee
Revises: ba4b1f1da138
Create Date: 2026-07-16 23:23:11.863360
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '7cddeb6ab4ee'
down_revision: str | None = 'ba4b1f1da138'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'product_barcodes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('code', sa.String(length=64), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['products.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('code'),
    )
    op.create_index(
        op.f('ix_product_barcodes_product_id'), 'product_barcodes', ['product_id'], unique=False
    )


def downgrade() -> None:
    op.drop_index(op.f('ix_product_barcodes_product_id'), table_name='product_barcodes')
    op.drop_table('product_barcodes')
