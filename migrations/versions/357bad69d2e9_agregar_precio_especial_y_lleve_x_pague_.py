"""agregar precio especial y lleve x pague y a promotions

Revision ID: 357bad69d2e9
Revises: 56a2d91b223d
Create Date: 2026-07-13 15:33:20.364952
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '357bad69d2e9'
down_revision: str | None = '56a2d91b223d'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('promotions', schema=None) as batch_op:
        batch_op.add_column(sa.Column('buy_quantity', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('pay_quantity', sa.Integer(), nullable=True))
        batch_op.alter_column(
            'description', existing_type=sa.String(length=500), type_=sa.Text()
        )
        batch_op.alter_column(
            'discount_type', existing_type=sa.String(length=12), type_=sa.String(length=30)
        )


def downgrade() -> None:
    with op.batch_alter_table('promotions', schema=None) as batch_op:
        batch_op.alter_column(
            'discount_type', existing_type=sa.String(length=30), type_=sa.String(length=12)
        )
        batch_op.alter_column(
            'description', existing_type=sa.Text(), type_=sa.String(length=500)
        )
        batch_op.drop_column('pay_quantity')
        batch_op.drop_column('buy_quantity')
