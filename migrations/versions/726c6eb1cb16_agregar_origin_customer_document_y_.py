"""agregar origin, customer_document y dispatched_by_user_id a orders

Revision ID: 726c6eb1cb16
Revises: dfb75d8af3ee
Create Date: 2026-07-14 09:56:08.878555
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = '726c6eb1cb16'
down_revision: str | None = 'dfb75d8af3ee'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_document', sa.String(length=30), nullable=True))
        batch_op.add_column(
            sa.Column(
                'origin',
                sa.Enum('VENDEDOR', 'VENTAS', name='orderorigin', native_enum=False),
                nullable=False,
                server_default='VENDEDOR',
            )
        )
        batch_op.add_column(sa.Column('dispatched_by_user_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            'fk_orders_dispatched_by_user_id_users', 'users', ['dispatched_by_user_id'], ['id']
        )


def downgrade() -> None:
    with op.batch_alter_table('orders', schema=None) as batch_op:
        batch_op.drop_constraint('fk_orders_dispatched_by_user_id_users', type_='foreignkey')
        batch_op.drop_column('dispatched_by_user_id')
        batch_op.drop_column('origin')
        batch_op.drop_column('customer_document')
