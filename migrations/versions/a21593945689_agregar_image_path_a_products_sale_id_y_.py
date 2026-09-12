"""agregar image_path a products, sale_id y created_by_user_id a orders

Revision ID: a21593945689
Revises: 82effaca937a
Create Date: 2026-07-12 14:51:23.856804
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'a21593945689'
down_revision: str | None = '82effaca937a'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('created_by_user_id', sa.Integer(), nullable=True))
        batch_op.add_column(sa.Column('sale_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_orders_sale_id_sales', 'sales', ['sale_id'], ['id']
        )
        batch_op.create_foreign_key(
            'fk_orders_created_by_user_id_users', 'users', ['created_by_user_id'], ['id']
        )

    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.add_column(sa.Column('image_path', sa.String(length=500), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('products', schema=None) as batch_op:
        batch_op.drop_column('image_path')

    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('fk_orders_sale_id_sales', type_='foreignkey')
        batch_op.drop_constraint('fk_orders_created_by_user_id_users', type_='foreignkey')
        batch_op.drop_column('sale_id')
        batch_op.drop_column('created_by_user_id')
