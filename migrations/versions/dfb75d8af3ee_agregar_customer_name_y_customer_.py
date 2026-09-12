"""agregar customer_name y customer_document a sales

Revision ID: dfb75d8af3ee
Revises: 357bad69d2e9
Create Date: 2026-07-14 09:56:08.878555
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = 'dfb75d8af3ee'
down_revision: str | None = '357bad69d2e9'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.add_column(sa.Column('customer_name', sa.String(length=120), nullable=True))
        batch_op.add_column(sa.Column('customer_document', sa.String(length=30), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('sales', schema=None) as batch_op:
        batch_op.drop_column('customer_document')
        batch_op.drop_column('customer_name')
