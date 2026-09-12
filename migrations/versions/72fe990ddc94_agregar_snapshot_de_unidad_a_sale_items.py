"""agregar snapshot de sale_unit y unit_of_measure a sale_items

Revision ID: 72fe990ddc94
Revises: 6fb91d45f472
Create Date: 2026-07-18 09:45:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = '72fe990ddc94'
down_revision: str | None = '6fb91d45f472'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table('sale_items', schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                'sale_unit',
                sa.Enum('UNIT', 'WEIGHT', name='saleunit', native_enum=False),
                nullable=False,
                server_default='UNIT',
            )
        )
        batch_op.add_column(
            sa.Column(
                'unit_of_measure', sa.String(length=20), nullable=False, server_default='unidad'
            )
        )


def downgrade() -> None:
    with op.batch_alter_table('sale_items', schema=None) as batch_op:
        batch_op.drop_column('unit_of_measure')
        batch_op.drop_column('sale_unit')
